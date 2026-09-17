"""
PexelsVideoProvider -- Real stock video clip provider via Pexels Videos REST API.

License: Pexels License -- free for personal and commercial use, no attribution required.
See: https://www.pexels.com/license/

Fetches short, real MP4 video clips (5-15s) to use as scene backgrounds instead of
static photos, so rendered scenes contain genuine motion instead of a Ken-Burns-panned
still image. Implements MediaProvider interface and self-registers with ProviderRegistry.
"""
import os
import json
import time
import hashlib
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional
from agents.video.providers.base import (
    MediaProvider,
    MediaRequest,
    MediaCandidate,
    MediaCandidateStatus,
    ProviderCapabilities,
    ProviderHealth,
    MediaType,
    AssetProvenance
)

logger = logging.getLogger("uvicorn")


class PexelsVideoProvider(MediaProvider):
    """
    Stock video provider sourcing real MP4 clips from the Pexels Videos API.
    Falls back to a procedural placeholder image if the API key is missing or the call fails.

    Cache: Local disk under CACHE_DIR, capped at CACHE_MAX_BYTES (default 1.5 GB, video
    files are much larger than photos).
    Eviction: LRU by file mtime when cache exceeds cap.
    """

    PEXELS_VIDEO_API_URL = "https://api.pexels.com/videos/search"
    CACHE_DIR = os.path.join(".", "storage", "pexels_video_cache")
    CACHE_MAX_BYTES = 1536 * 1024 * 1024  # 1.5 GB

    MIN_DURATION_SEC = 5
    MAX_DURATION_SEC = 15

    def __init__(self):
        os.makedirs(self.CACHE_DIR, exist_ok=True)

    @property
    def provider_id(self) -> str:
        return "pexels_video"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            media_types={MediaType.STOCK_VIDEO},
            supported_aspect_ratios={"16:9", "9:16", "1:1"},
            supports_duration_control=True,
            supports_seed=False,
            supports_style_reference=False,
            requires_network=True,
            requires_api_key=True,
            supports_offline=False,
            returns_attribution=False  # Pexels: no attribution required
        )

    def readiness(self) -> ProviderHealth:
        api_key = self._get_api_key()
        return ProviderHealth(
            available=True,
            configuration_ready=bool(api_key)
        )

    def estimate_cost(self, request: MediaRequest) -> float:
        return 0.0  # Pexels API is free

    def estimate_latency(self, request: MediaRequest) -> float:
        return 3.5  # Video downloads are larger than photos -- search + download

    def _get_api_key(self) -> str:
        """Read PEXELS_API_KEY from environment (never hardcoded). Same key as stock photos."""
        from app.core.config import settings
        return settings.PEXELS_API_KEY

    def _cache_key(self, query: str, video_id: Any, width: int, height: int) -> str:
        """Deterministic cache filename from query + video id + dimensions."""
        h = hashlib.sha256(f"{query}_{video_id}_{width}x{height}".encode()).hexdigest()[:16]
        return f"pexels_video_{h}.mp4"

    def _cache_path(self, cache_key: str) -> str:
        return os.path.join(self.CACHE_DIR, cache_key)

    def _check_cache(self, cache_key: str) -> Optional[str]:
        """Returns local path if cached file exists and is non-empty, else None."""
        path = self._cache_path(cache_key)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            os.utime(path, None)
            logger.info(f"PexelsVideoProvider: Cache HIT for '{cache_key}'")
            return path
        return None

    def _enforce_cache_cap(self):
        """Evict oldest files (by mtime) until total cache size is under CACHE_MAX_BYTES."""
        cache_dir = Path(self.CACHE_DIR)
        files = [(f, f.stat()) for f in cache_dir.iterdir() if f.is_file()]
        total_size = sum(s.st_size for _, s in files)

        if total_size <= self.CACHE_MAX_BYTES:
            return

        files.sort(key=lambda x: x[1].st_mtime)
        evicted = 0
        for fpath, fstat in files:
            if total_size <= self.CACHE_MAX_BYTES:
                break
            total_size -= fstat.st_size
            fpath.unlink()
            evicted += 1

        if evicted:
            logger.info(f"PexelsVideoProvider: LRU cache eviction -- removed {evicted} file(s), "
                        f"cache now {total_size / (1024*1024):.1f} MB")

    @staticmethod
    def _detect_proxy() -> Optional[str]:
        """Precedence: PEXELS_PROXY (explicit override) > HTTPS_PROXY > HTTP_PROXY (case-insensitive)."""
        for var in ("PEXELS_PROXY", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
            val = os.environ.get(var)
            if val:
                return val
        return None

    def _build_opener(self) -> "urllib.request.OpenerDirector":
        proxy = self._detect_proxy()
        if proxy:
            logger.info(f"PexelsVideoProvider: Using proxy for Pexels requests -> {proxy}")
            handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        else:
            handler = urllib.request.ProxyHandler({})
        return urllib.request.build_opener(handler)

    def _search_pexels_videos(self, query: str, per_page: int = 3) -> Optional[Dict[str, Any]]:
        """
        Calls the Pexels Videos Search API. Returns the raw JSON response dict or None on failure.
        """
        api_key = self._get_api_key()
        if not api_key:
            logger.warning("PexelsVideoProvider: [FALLBACK] PEXELS_API_KEY not set -- cannot query Pexels Videos.")
            return None

        encoded_query = urllib.request.quote(query)
        url = (
            f"{self.PEXELS_VIDEO_API_URL}?query={encoded_query}&per_page={per_page}"
            f"&orientation=landscape&min_duration={self.MIN_DURATION_SEC}&max_duration={self.MAX_DURATION_SEC}"
        )

        req = urllib.request.Request(
            url,
            headers={
                "Authorization": api_key,
                "User-Agent": "CreateFlowAI/1.0"
            },
            method="GET"
        )

        opener = self._build_opener()
        try:
            with opener.open(req, timeout=10) as response:
                resp_body = response.read().decode("utf-8")
                logger.info(f"PexelsVideoProvider: [OK] API responded for query '{query}'.")
                return json.loads(resp_body)
        except urllib.error.HTTPError as e:
            logger.error(f"PexelsVideoProvider: [FALLBACK] HTTP {e.code} from Pexels Videos API for query '{query}': {e.reason}")
            return None
        except Exception as e:
            logger.error(
                f"PexelsVideoProvider: [FALLBACK] API call failed for query '{query}': {type(e).__name__}: {e}. "
                f"(If this is a connection reset/timeout, api.pexels.com is likely blocked by your network/firewall; "
                f"set PEXELS_PROXY or HTTPS_PROXY to a reachable proxy.)"
            )
            return None

    def _select_video_file(self, video: Dict[str, Any], target_width: int) -> Optional[Dict[str, Any]]:
        """
        Picks the best `video_files` entry: real MP4, closest to target_width without
        going far beyond it (keeps download size reasonable for a short 5-15s clip).
        """
        files = [
            f for f in (video.get("video_files") or [])
            if f.get("file_type") == "video/mp4" and f.get("link") and f.get("width")
        ]
        if not files:
            return None

        files.sort(key=lambda f: f["width"])

        # Prefer smallest file that meets or exceeds target_width (keeps quality >= target)
        for f in files:
            if f["width"] >= target_width:
                return f
        # Otherwise take the highest-resolution file available
        return files[-1]

    def _download_video(self, video_url: str, local_path: str) -> bool:
        """Downloads video from URL to local_path. Returns True on success."""
        opener = self._build_opener()
        try:
            req = urllib.request.Request(
                video_url,
                headers={"User-Agent": "CreateFlowAI/1.0"},
                method="GET"
            )
            with opener.open(req, timeout=30) as response:
                with open(local_path, "wb") as f:
                    while True:
                        chunk = response.read(1024 * 256)
                        if not chunk:
                            break
                        f.write(chunk)

            size = os.path.getsize(local_path)
            if size > 0:
                logger.info(f"PexelsVideoProvider: [OK] Downloaded {size:,} bytes -> {local_path}")
                return True
            else:
                logger.warning(f"PexelsVideoProvider: [FALLBACK] Downloaded file is 0 bytes: {local_path}")
                return False
        except Exception as e:
            logger.error(f"PexelsVideoProvider: [FALLBACK] Download failed for '{video_url}': {type(e).__name__}: {e}")
            return False

    def retrieve_candidates(self, request: MediaRequest, limit: int = 3) -> List[MediaCandidate]:
        """
        Retrieves up to `limit` downloadable video candidates from Pexels without discarding results.
        """
        t0 = time.time()
        search_terms: List[str] = []
        negative_terms: List[str] = []
        if getattr(request, "visual_query_result", None):
            from agents.video.provider_query_adapters import QueryAdapterRegistry
            adapted_vqr = QueryAdapterRegistry.adapt(self.provider_id, request.visual_query_result, None)
            query = adapted_vqr.primary_query
            search_terms = [adapted_vqr.primary_query] + adapted_vqr.alternate_queries
            negative_terms = [n.lower() for n in adapted_vqr.negative_terms if n]
        else:
            query = request.query or "abstract background"
            search_terms = [query]

        result = None
        for term in search_terms[:3]:
            res_candidate = self._search_pexels_videos(term, per_page=max(limit, 3))
            if res_candidate and res_candidate.get("videos"):
                result = res_candidate
                query = term
                break

        if not result or not result.get("videos"):
            return [self._fallback_placeholder(request, time.time() - t0, reason=f"No Pexels video results for '{query}'")]

        candidates: List[MediaCandidate] = []
        for video in result["videos"]:
            if len(candidates) >= limit:
                break

            duration = video.get("duration") or 0
            if duration and not (self.MIN_DURATION_SEC <= duration <= self.MAX_DURATION_SEC * 2):
                # API-side filter should already bound this; skip wildly out-of-range results defensively.
                continue

            tags_text = " ".join(video.get("tags") or []).lower()
            user_text = (video.get("user", {}) or {}).get("name", "").lower()
            if any(neg in tags_text or neg in user_text for neg in negative_terms):
                continue

            video_file = self._select_video_file(video, request.target_width)
            if not video_file:
                continue

            video_id = video.get("id") or f"pexels_video_{len(candidates)}"
            ck = self._cache_key(query, video_id, video_file["width"], video_file.get("height", 0))
            local_path = self._cache_path(ck)

            if not os.path.exists(local_path):
                if not self._download_video(video_file["link"], local_path):
                    continue

            dt = time.time() - t0
            videographer = (video.get("user", {}) or {}).get("name", "unknown")
            video_page_url = video.get("url") or video_file["link"]

            cand = MediaCandidate(
                provider_id=self.provider_id,
                media_type=MediaType.STOCK_VIDEO,
                asset_path=local_path,
                remote_url=video_page_url,
                width=video_file.get("width", request.target_width),
                height=video_file.get("height", request.target_height),
                duration=float(duration) if duration else None,
                mime_type="video/mp4",
                candidate_status=MediaCandidateStatus.VALIDATED_RENDER_READY,
                generation_method="retrieval_metadata",
                measured_latency_seconds=round(dt, 3),
                attribution=f"Video by {videographer} on Pexels",
                license_name="Pexels License (free, no attribution required)",
                generation_metadata={
                    "source": "pexels_video_api",
                    "query": query,
                    "video_id": video_id,
                    "videographer": videographer,
                    "duration": duration,
                    "title": f"Pexels Video {video_id}"
                }
            )
            candidates.append(cand)

        self._enforce_cache_cap()

        if not candidates:
            return [self._fallback_placeholder(request, time.time() - t0, reason="No video candidates downloaded")]

        return candidates

    def generate_or_retrieve(self, request: MediaRequest) -> MediaCandidate:
        cands = self.retrieve_candidates(request, limit=1)
        return cands[0]

    def _fallback_placeholder(self, request: MediaRequest, elapsed: float, reason: str) -> MediaCandidate:
        """Generate a procedural placeholder image when Pexels Videos API is unavailable."""
        from PIL import Image
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        placeholder_path = os.path.join(self.CACHE_DIR, f"fallback_{request.scene_id}.png")
        img = Image.new("RGB", (request.target_width, request.target_height), color=(30, 41, 59))
        img.save(placeholder_path, "PNG")

        logger.warning(f"PexelsVideoProvider: Fallback to procedural placeholder. Reason: {reason}")

        return MediaCandidate(
            provider_id=self.provider_id,
            media_type=MediaType.PROCEDURAL_BACKGROUND,
            asset_path=placeholder_path,
            width=request.target_width,
            height=request.target_height,
            mime_type="image/png",
            estimated_cost=0.0,
            measured_latency_seconds=round(elapsed, 3),
            candidate_status=MediaCandidateStatus.PROCEDURAL_PLACEHOLDER,
            generation_method="procedural",
            generation_metadata={"source": "fallback_procedural", "reason": reason}
        )

    # Legacy interface support
    def provider_name(self) -> str:
        return self.provider_id

    def supported_asset_types(self) -> list[str]:
        return ["stock_video"]

    def generate_or_fetch(self, prompt_or_query: str, asset_type: str, options: dict = None) -> AssetProvenance:
        req = MediaRequest(
            scene_id="legacy",
            query=prompt_or_query,
            media_type_preferences=[MediaType.STOCK_VIDEO]
        )
        cand = self.generate_or_retrieve(req)
        return AssetProvenance(
            asset_id=f"pexels_video_{hash(prompt_or_query)}",
            provider_name=self.provider_id,
            asset_type=asset_type,
            prompt_or_query=prompt_or_query,
            source_url_or_path=cand.asset_path or "",
            metadata=cand.generation_metadata
        )
