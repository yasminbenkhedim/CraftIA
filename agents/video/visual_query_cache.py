"""
VisualQueryCache -- Multi-Tier Cache with Atomic Disk Writes for VideoAgent (Upgrade 2).
In-memory LRU (500 items) + Atomic Disk JSON cache with TTL, version invalidation, and privacy modes.
"""
import os
import json
import time
import hashlib
import logging
from collections import OrderedDict
from typing import Dict, Any, Optional
from agents.video.visual_query_schemas import (
    VisualQueryResult, VisualQueryInput, VisualQueryConfig, VisualQueryPrivacyMode
)

logger = logging.getLogger("uvicorn")


class VisualQueryCache:
    """
    Two-tier (In-Memory LRU + Atomic Disk JSON) cache for visual queries.
    """

    PROMPT_VERSION = "v1"
    SCORER_VERSION = "v1"
    CACHE_DIR = os.path.join(".", "storage", "visual_query_cache")

    def __init__(self, config: Optional[VisualQueryConfig] = None):
        self.config = config or VisualQueryConfig()
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        self._memory_cache: OrderedDict[str, Tuple[float, Dict[str, Any]]] = OrderedDict()
        self._clean_stale_temp_files()

    def compute_cache_key(self, vq_input: VisualQueryInput, model_name: str = "llama-3.3-70b-versatile") -> str:
        """
        Computes deterministic cache key from all behavior-changing inputs.
        """
        raw_key = "|".join([
            vq_input.narration or "",
            vq_input.scene_title or "",
            vq_input.storyboard_title or "",
            vq_input.language or "en",
            vq_input.domain or "default",
            vq_input.target_provider or "any",
            vq_input.background_style or "gradient",
            vq_input.aspect_ratio or "16:9",
            model_name,
            self.PROMPT_VERSION,
            self.SCORER_VERSION,
            str(self.config.llm_temperature)
        ])
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:24]

    def get(self, cache_key: str) -> Optional[VisualQueryResult]:
        """
        Lookup in memory, then disk. Returns VisualQueryResult if hit and valid, else None.
        """
        if not self.config.cache_enabled:
            return None

        now = time.time()

        # 1. Check in-memory LRU
        if cache_key in self._memory_cache:
            ts, data = self._memory_cache[cache_key]
            if now - ts <= self.config.cache_ttl_seconds:
                self._memory_cache.move_to_end(cache_key)
                res = VisualQueryResult(**data)
                res.cache_hit = True
                res.cache_key = cache_key
                res.generation_source = "cache_memory"
                return res
            else:
                del self._memory_cache[cache_key]

        # 2. Check disk cache
        disk_path = os.path.join(self.CACHE_DIR, f"{cache_key}.json")
        if os.path.exists(disk_path):
            try:
                with open(disk_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)

                ts = payload.get("_timestamp", 0)
                if now - ts <= self.config.cache_ttl_seconds:
                    data = payload.get("data", {})
                    # Populate in-memory LRU
                    self._set_memory(cache_key, ts, data)
                    res = VisualQueryResult(**data)
                    res.cache_hit = True
                    res.cache_key = cache_key
                    res.generation_source = "cache_disk"
                    return res
                else:
                    os.remove(disk_path)
            except Exception as e:
                logger.warning(f"VisualQueryCache: Corrupted entry '{cache_key}.json' ({e}) -> deleting.")
                try:
                    if os.path.exists(disk_path):
                        os.remove(disk_path)
                except OSError:
                    pass

        return None

    def put(self, cache_key: str, vq_input: VisualQueryInput, vq_result: VisualQueryResult):
        """
        Stores result in memory and atomic disk JSON cache respecting privacy mode.
        """
        if not self.config.cache_enabled or not cache_key:
            return

        now = time.time()
        res_dict = vq_result.to_dict()

        # Update in-memory LRU
        self._set_memory(cache_key, now, res_dict)

        # Apply privacy mode to disk payload
        disk_res_dict = dict(res_dict)
        if self.config.privacy_mode == VisualQueryPrivacyMode.REDACTED:
            disk_res_dict["original_narration"] = hashlib.sha256((vq_input.narration or "").encode()).hexdigest()[:16]
        elif self.config.privacy_mode == VisualQueryPrivacyMode.TRUNCATED:
            if vq_input.narration and len(vq_input.narration) > 40:
                disk_res_dict["original_narration"] = vq_input.narration[:40] + "..."

        payload = {
            "_cache_key": cache_key,
            "_timestamp": now,
            "_prompt_version": self.PROMPT_VERSION,
            "_scorer_version": self.SCORER_VERSION,
            "data": disk_res_dict
        }

        # Atomic disk write
        disk_path = os.path.join(self.CACHE_DIR, f"{cache_key}.json")
        tmp_path = disk_path + f".tmp.{os.getpid()}_{time.time_ns()}"

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, disk_path)
            self._enforce_disk_cap()
        except Exception as e:
            logger.error(f"VisualQueryCache: Failed atomic write for '{cache_key}': {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _set_memory(self, key: str, ts: float, data: Dict[str, Any]):
        if key in self._memory_cache:
            self._memory_cache.move_to_end(key)
        self._memory_cache[key] = (ts, data)
        while len(self._memory_cache) > self.config.cache_max_entries_memory:
            self._memory_cache.popitem(last=False)

    def _enforce_disk_cap(self):
        """Enforces max directory size (default 50 MB) using LRU mtime eviction."""
        try:
            files = []
            total_size = 0
            for entry in os.scandir(self.CACHE_DIR):
                if entry.is_file() and entry.name.endswith(".json"):
                    stat = entry.stat()
                    files.append((entry.path, stat.st_mtime, stat.st_size))
                    total_size += stat.st_size

            if total_size <= self.config.cache_max_bytes:
                return

            files.sort(key=lambda x: x[1])  # Oldest mtime first
            evicted = 0
            for fpath, mtime, size in files:
                if total_size <= self.config.cache_max_bytes:
                    break
                try:
                    os.remove(fpath)
                    total_size -= size
                    evicted += 1
                except OSError:
                    pass
            if evicted > 0:
                logger.info(f"VisualQueryCache: Evicted {evicted} disk cache file(s) to enforce {self.config.cache_max_bytes / (1024*1024):.1f}MB cap.")
        except Exception as e:
            logger.warning(f"VisualQueryCache: Error enforcing disk cap: {e}")

    def _clean_stale_temp_files(self):
        """Removes orphan .tmp files left by interrupted processes."""
        now = time.time()
        try:
            for entry in os.scandir(self.CACHE_DIR):
                if entry.is_file() and ".tmp." in entry.name:
                    if now - entry.stat().st_mtime > 300:  # Older than 5 min
                        try:
                            os.remove(entry.path)
                        except OSError:
                            pass
        except Exception:
            pass

    def clear(self):
        """Clears memory and disk cache."""
        self._memory_cache.clear()
        try:
            for entry in os.scandir(self.CACHE_DIR):
                if entry.is_file():
                    try:
                        os.remove(entry.path)
                    except OSError:
                        pass
        except Exception:
            pass
