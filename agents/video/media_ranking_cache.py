"""
MediaRankingCache -- Feature & Ranking Cache with Shared Asset Contract (Upgrade 3).
Caches candidate feature vectors, perceptual hashes, and canonical metadata entries.
"""
import os
import json
import time
import hashlib
import logging
from collections import OrderedDict
from typing import Dict, Any, Optional, Tuple
from agents.video.media_ranking_schemas import (
    CandidateFeatures, SharedAssetCacheEntry, MediaRankerConfig
)

logger = logging.getLogger("uvicorn")


class MediaRankingCache:
    """
    Two-tier (In-Memory LRU + Atomic Disk JSON) cache for media feature extraction and ranking.
    """

    RANKER_CONFIG_VERSION = "v1"
    FEATURE_EXTRACTOR_VERSION = "v1"
    CACHE_DIR = os.path.join(".", "storage", "media_ranking_cache")

    def __init__(self, config: Optional[MediaRankerConfig] = None):
        self.config = config or MediaRankerConfig()
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        self._memory_cache: OrderedDict[str, SharedAssetCacheEntry] = OrderedDict()

    @classmethod
    def compute_canonical_key(
        cls,
        provider_id: str,
        provider_asset_id: Optional[str],
        remote_url: Optional[str],
        content_sha256: Optional[str] = None
    ) -> str:
        """
        Computes stable canonical candidate key across providers.
        """
        raw = f"{provider_id}|{provider_asset_id or ''}|{remote_url or ''}|{content_sha256 or ''}"
        return f"cand_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"

    def get_features(self, canonical_key: str, file_mtime: float) -> Optional[CandidateFeatures]:
        """
        Looks up cached CandidateFeatures by canonical key and file mtime.
        """
        if canonical_key in self._memory_cache:
            entry = self._memory_cache[canonical_key]
            if abs(entry.file_mtime - file_mtime) < 1.0 and entry.features:
                self._memory_cache.move_to_end(canonical_key)
                return entry.features

        disk_path = os.path.join(self.CACHE_DIR, f"{canonical_key}.json")
        if os.path.exists(disk_path):
            try:
                with open(disk_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)

                if payload.get("_extractor_version") == self.FEATURE_EXTRACTOR_VERSION:
                    fdata = payload.get("features")
                    if fdata:
                        features = CandidateFeatures(**fdata)
                        return features
            except Exception:
                try:
                    os.remove(disk_path)
                except OSError:
                    pass

        return None

    def put_entry(self, entry: SharedAssetCacheEntry):
        """
        Stores SharedAssetCacheEntry in memory and disk cache.
        """
        if not entry.canonical_asset_key:
            return

        self._memory_cache[entry.canonical_asset_key] = entry
        if len(self._memory_cache) > 500:
            self._memory_cache.popitem(last=False)

        # Atomic disk write
        disk_path = os.path.join(self.CACHE_DIR, f"{entry.canonical_asset_key}.json")
        tmp_path = disk_path + f".tmp.{os.getpid()}_{time.time_ns()}"

        try:
            payload = {
                "canonical_asset_key": entry.canonical_asset_key,
                "validated_path": entry.validated_path,
                "mime_type": entry.mime_type,
                "dimensions": list(entry.dimensions),
                "file_size_bytes": entry.file_size_bytes,
                "file_mtime": entry.file_mtime,
                "content_sha256": entry.content_sha256,
                "perceptual_dhash": entry.perceptual_dhash,
                "_extractor_version": self.FEATURE_EXTRACTOR_VERSION,
                "_timestamp": time.time(),
                "features": entry.features.to_dict() if entry.features else None
            }
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, disk_path)
        except Exception as e:
            logger.error(f"MediaRankingCache: Atomic write failed for '{entry.canonical_asset_key}': {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
