"""
PexelsStockProvider -- Real stock photo provider via Pexels REST API.

License: Pexels License -- free for personal and commercial use, no attribution required.
See: https://www.pexels.com/license/

Implements MediaProvider interface and self-registers with ProviderRegistry.
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


class PexelsStockProvider(MediaProvider):
    """
    Stock photo provider sourcing real images from the Pexels API.
    Falls back to procedural_overlay if API key is missing or call fails.

    Cache: Local disk under CACHE_DIR, capped at CACHE_MAX_BYTES (default 500 MB).
    Eviction: LRU by file mtime when cache exceeds cap.
    """

    PEXELS_API_URL = "https://api.pexels.com/v1/search"
    CACHE_DIR = os.path.join(".", "storage", "pexels_cache")
    CACHE_MAX_BYTES = 500 * 1024 * 1024  # 500 MB

    def __init__(self):
        os.makedirs(self.CACHE_DIR, exist_ok=True)

    @property
    def provider_id(self) -> str:
        return "pexels_stock"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            media_types={MediaType.STOCK_IMAGE},
            supported_aspect_ratios={"16:9", "9:16", "1:1"},
            supports_duration_control=False,
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
        return 1.5  # ~1.5s for search + download

    def _get_api_key(self) -> str:
        """Read PEXELS_API_KEY from environment (never hardcoded)."""
        from app.core.config import settings
        return settings.PEXELS_API_KEY

    def _cache_key(self, query: str, width: int, height: int) -> str:
        """Deterministic cache filename from query + dimensions."""
        h = hashlib.sha256(f"{query}_{width}x{height}".encode()).hexdigest()[:16]
        return f"pexels_{h}.jpg"

    def _cache_path(self, cache_key: str) -> str:
        return os.path.join(self.CACHE_DIR, cache_key)

    def _check_cache(self, cache_key: str) -> Optional[str]:
        """Returns local path if cached file exists and is non-empty, else None."""
        path = self._cache_path(cache_key)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            # Touch mtime for LRU tracking
            os.utime(path, None)
            logger.info(f"PexelsStockProvider: Cache HIT for '{cache_key}'")
            return path
        return None

    def _enforce_cache_cap(self):
        """Evict oldest files (by mtime) until total cache size is under CACHE_MAX_BYTES."""
        cache_dir = Path(self.CACHE_DIR)
        files = [(f, f.stat()) for f in cache_dir.iterdir() if f.is_file()]
        total_size = sum(s.st_size for _, s in files)

        if total_size <= self.CACHE_MAX_BYTES:
            return

        # Sort by mtime ascending (oldest first)
        files.sort(key=lambda x: x[1].st_mtime)
        evicted = 0
        for fpath, fstat in files:
            if total_size <= self.CACHE_MAX_BYTES:
                break
            total_size -= fstat.st_size
            fpath.unlink()
            evicted += 1

        if evicted:
            logger.info(f"PexelsStockProvider: LRU cache eviction -- removed {evicted} file(s), "
                        f"cache now {total_size / (1024*1024):.1f} MB")

    @staticmethod
    def _detect_proxy() -> Optional[str]:
        """
        Returns an HTTPS proxy URL if one is configured, else None.
        Precedence: PEXELS_PROXY (explicit override) > HTTPS_PROXY > HTTP_PROXY
        (case-insensitive). Lets a corporate proxy (e.g. PwC) be used for Pexels.
        """
        for var in ("PEXELS_PROXY", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
            val = os.environ.get(var)
            if val:
                return val
        return None

    def _build_opener(self) -> "urllib.request.OpenerDirector":
        """
        Builds a urllib opener honoring an optional proxy. When no proxy is set,
        ProxyHandler({}) is used to explicitly bypass any system proxy so behaviour
        is deterministic.
        """
        proxy = self._detect_proxy()
        if proxy:
            logger.info(f"PexelsStockProvider: Using proxy for Pexels requests -> {proxy}")
            handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        else:
            handler = urllib.request.ProxyHandler({})
        return urllib.request.build_opener(handler)

    def _search_pexels(self, query: str, per_page: int = 1) -> Optional[Dict[str, Any]]:
        """
        Calls Pexels Search API. Returns the raw JSON response dict or None on failure.
        """
        api_key = self._get_api_key()
        if not api_key:
            logger.warning("PexelsStockProvider: [FALLBACK] PEXELS_API_KEY not set -- cannot query Pexels.")
            return None

        encoded_query = urllib.request.quote(query)
        url = f"{self.PEXELS_API_URL}?query={encoded_query}&per_page={per_page}&orientation=landscape"

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
                logger.info(f"PexelsStockProvider: [OK] API responded for query '{query}'.")
                return json.loads(resp_body)
        except urllib.error.HTTPError as e:
            logger.error(f"PexelsStockProvider: [FALLBACK] HTTP {e.code} from Pexels API for query '{query}': {e.reason}")
            return None
        except Exception as e:
            logger.error(
                f"PexelsStockProvider: [FALLBACK] API call failed for query '{query}': {type(e).__name__}: {e}. "
                f"(If this is a connection reset/timeout, api.pexels.com is likely blocked by your network/firewall; "
                f"set PEXELS_PROXY or HTTPS_PROXY to a reachable proxy.)"
            )
            return None

    def _download_image(self, image_url: str, local_path: str) -> bool:
        """Downloads image from URL to local_path. Returns True on success."""
        opener = self._build_opener()
        try:
            req = urllib.request.Request(
                image_url,
                headers={"User-Agent": "CreateFlowAI/1.0"},
                method="GET"
            )
            with opener.open(req, timeout=15) as response:
                with open(local_path, "wb") as f:
                    f.write(response.read())

            size = os.path.getsize(local_path)
            if size > 0:
                logger.info(f"PexelsStockProvider: [OK] Downloaded {size:,} bytes -> {local_path}")
                return True
            else:
                logger.warning(f"PexelsStockProvider: [FALLBACK] Downloaded file is 0 bytes: {local_path}")
                return False
        except Exception as e:
            logger.error(f"PexelsStockProvider: [FALLBACK] Download failed for '{image_url}': {type(e).__name__}: {e}")
            return False

    def retrieve_candidates(self, request: MediaRequest, limit: int = 3) -> List[MediaCandidate]:
        """
        Retrieves up to `limit` downloadable candidates from Pexels without discarding results.
        """
        t0 = time.time()
        search_terms = []
        negative_terms = []
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
            res_candidate = self._search_pexels(term, per_page=limit)
            if res_candidate and res_candidate.get("photos"):
                result = res_candidate
                query = term
                break

        if not result or not result.get("photos"):
            return [self._fallback_placeholder(request, time.time() - t0, reason=f"No Pexels results for '{query}'")]

        candidates: List[MediaCandidate] = []
        for idx, photo in enumerate(result["photos"]):
            if len(candidates) >= limit:
                break

            alt_text = (photo.get("alt") or "").lower()
            photographer_text = (photo.get("photographer") or "").lower()
            if any(neg in alt_text or neg in photographer_text for neg in negative_terms):
                continue

            candidate_url = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("large") or photo.get("src", {}).get("original")
            if not candidate_url:
                continue

            photo_id = photo.get("id") or f"pexels_{idx}"
            ck = self._cache_key(f"{query}_{photo_id}", request.target_width, request.target_height)
            local_path = self._cache_path(ck)

            if not os.path.exists(local_path):
                if not self._download_image(candidate_url, local_path):
                    continue

            dt = time.time() - t0
            photographer = photo.get("photographer", "unknown")
            photo_url = photo.get("url") or candidate_url

            cand = MediaCandidate(
                provider_id=self.provider_id,
                media_type=MediaType.STOCK_IMAGE,
                asset_path=local_path,
                remote_url=photo_url,
                width=photo.get("width", request.target_width),
                height=photo.get("height", request.target_height),
                candidate_status=MediaCandidateStatus.VALIDATED_RENDER_READY,
                generation_method="retrieval_metadata",
                measured_latency_seconds=round(dt, 3),
                attribution=f"Photo by {photographer} on Pexels",
                license_name="Pexels License (free, no attribution required)",
                generation_metadata={
                    "source": "pexels_api",
                    "query": query,
                    "photo_id": photo_id,
                    "photographer": photographer,
                    "title": photo.get("alt", "Pexels Photo")
                }
            )
            candidates.append(cand)

        self._enforce_cache_cap()

        if not candidates:
            return [self._fallback_placeholder(request, time.time() - t0, reason="No candidates downloaded")]

        return candidates

    def generate_or_retrieve(self, request: MediaRequest) -> MediaCandidate:
        cands = self.retrieve_candidates(request, limit=1)
        return cands[0]

        dt = time.time() - t0
        logger.info(f"PexelsStockProvider: Resolved '{query}' -> photo by {photographer} "
                    f"({photo_width}x{photo_height}) in {dt:.3f}s")

        return MediaCandidate(
            provider_id=self.provider_id,
            media_type=MediaType.STOCK_IMAGE,
            asset_path=local_path,
            remote_url=image_url,
            width=photo_width,
            height=photo_height,
            mime_type="image/jpeg",
            license_name="Pexels License (free, no attribution required)",
            estimated_cost=0.0,
            measured_latency_seconds=round(dt, 3),
            candidate_status=MediaCandidateStatus.VALIDATED_RENDER_READY,
            generation_method="retrieval_metadata",
            generation_metadata={
                "source": "pexels_api",
                "query": query,
                "photo_id": photo.get("id"),
                "photographer": photographer,
                "pexels_url": photo.get("url", ""),
                "cache_key": ck
            }
        )

    def _fallback_placeholder(self, request: MediaRequest, elapsed: float, reason: str) -> MediaCandidate:
        """Generate a procedural placeholder when Pexels API is unavailable."""
        from PIL import Image
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        placeholder_path = os.path.join(self.CACHE_DIR, f"fallback_{request.scene_id}.png")
        img = Image.new("RGB", (request.target_width, request.target_height), color=(30, 41, 59))
        img.save(placeholder_path, "PNG")

        logger.warning(f"PexelsStockProvider: Fallback to procedural placeholder. Reason: {reason}")

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
        return ["stock_image"]

    def generate_or_fetch(self, prompt_or_query: str, asset_type: str, options: dict = None) -> AssetProvenance:
        req = MediaRequest(
            scene_id="legacy",
            query=prompt_or_query,
            media_type_preferences=[MediaType.STOCK_IMAGE]
        )
        cand = self.generate_or_retrieve(req)
        return AssetProvenance(
            asset_id=f"pexels_stock_{hash(prompt_or_query)}",
            provider_name=self.provider_id,
            asset_type=asset_type,
            prompt_or_query=prompt_or_query,
            source_url_or_path=cand.asset_path or "",
            metadata=cand.generation_metadata
        )
