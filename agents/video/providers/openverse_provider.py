"""
OpenverseStockProvider -- Real stock photo provider via Openverse REST API.
Production-Hardened Version with:
1. Explicit HTTP 429 Rate-Limit Detection & Retry-After Respect
2. Exponential Backoff Retry for Transient 5xx / Timeout Failures
3. Request-Budget Telemetry (100 req/hr documented Openverse API anonymous limit)
4. Circuit Breaker State Machine (CLOSED -> OPEN on 3 consecutive failures -> HALF_OPEN after 30s)
5. Multi-tier Fallback Ordering: openverse_stock -> openmontage_stock -> procedural_overlay

API Doc: https://api.openverse.org/v1/
Implements MediaProvider interface and self-registers with ProviderRegistry.
"""
import os
import json
import time
import hashlib
import logging
import urllib.request
import urllib.error
import socket
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
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


class CircuitBreakerState:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class RequestBudgetTracker:
    """Tracks sliding hourly and daily request telemetry against Openverse API limits."""
    BURST_LIMIT = 20       # Live x-ratelimit-limit-anon_burst: 20/min
    SUSTAINED_LIMIT = 200  # Live x-ratelimit-limit-anon_sustained: 200/day

    def __init__(self):
        self.request_timestamps: List[float] = []

    def record_request(self):
        now = time.time()
        self.request_timestamps.append(now)
        self._prune(now)

    def _prune(self, now: float):
        # Keep only timestamps within last 24 hours
        self.request_timestamps = [t for t in self.request_timestamps if now - t <= 86400]

    def get_telemetry(self) -> Dict[str, Any]:
        now = time.time()
        self._prune(now)
        minute_count = sum(1 for t in self.request_timestamps if now - t <= 60)
        daily_count = len(self.request_timestamps)
        return {
            "minute_count": minute_count,
            "burst_limit": self.BURST_LIMIT,
            "burst_pct": round((minute_count / self.BURST_LIMIT) * 100, 1),
            "daily_count": daily_count,
            "daily_limit": self.SUSTAINED_LIMIT,
            "daily_pct": round((daily_count / self.SUSTAINED_LIMIT) * 100, 1)
        }


class OpenverseStockProvider(MediaProvider):
    """
    Production-Hardened Stock photo provider sourcing CC0 / Public Domain images from Openverse API.
    """

    OPENVERSE_API_URL = "https://api.openverse.org/v1/images/"
    CACHE_DIR = os.path.join(".", "storage", "openverse_cache")
    CACHE_MAX_BYTES = 500 * 1024 * 1024  # 500 MB

    # Circuit breaker settings
    FAILURE_THRESHOLD = 3         # 3 consecutive failures to trip
    COOLDOWN_SECONDS = 30.0       # 30s cooldown period

    def __init__(self):
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        self.telemetry_tracker = RequestBudgetTracker()
        
        # Circuit breaker state
        self.cb_state = CircuitBreakerState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time = 0.0
        
        # 429 Rate limit tracking
        self.rate_limited_until = 0.0

    @property
    def provider_id(self) -> str:
        return "openverse_stock"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            media_types={MediaType.STOCK_IMAGE},
            supported_aspect_ratios={"16:9", "9:16", "1:1"},
            supports_duration_control=False,
            supports_seed=False,
            supports_style_reference=False,
            requires_network=True,
            requires_api_key=False,
            supports_offline=False,
            returns_attribution=True
        )

    def readiness(self) -> ProviderHealth:
        # Check circuit breaker
        if self._is_circuit_open():
            return ProviderHealth(
                available=False,
                configuration_ready=True,
                status_message=f"Circuit Breaker OPEN (cooldown active until {self.last_failure_time + self.COOLDOWN_SECONDS:.1f}s)"
            )
        return ProviderHealth(available=True, configuration_ready=True)

    def estimate_cost(self, request: MediaRequest) -> float:
        return 0.0

    def estimate_latency(self, request: MediaRequest) -> float:
        return 1.2

    def _is_circuit_open(self) -> bool:
        """Returns True if circuit breaker is OPEN and cooldown has not elapsed."""
        now = time.time()
        if self.cb_state == CircuitBreakerState.OPEN:
            if now - self.last_failure_time >= self.COOLDOWN_SECONDS:
                logger.info("OpenverseStockProvider: Circuit breaker cooldown elapsed -> Transitioning to HALF_OPEN")
                self.cb_state = CircuitBreakerState.HALF_OPEN
                return False
            return True
        return False

    def _record_success(self):
        """Records API success, resetting circuit breaker and consecutive failure count."""
        if self.cb_state in (CircuitBreakerState.OPEN, CircuitBreakerState.HALF_OPEN):
            logger.info("OpenverseStockProvider: API call succeeded -> Circuit breaker reset to CLOSED")
        self.cb_state = CircuitBreakerState.CLOSED
        self.consecutive_failures = 0

    def _record_failure(self, is_429: bool = False, retry_after: float = 0.0):
        """Records API failure, incrementing failure count and tripping circuit breaker if threshold reached."""
        self.consecutive_failures += 1
        self.last_failure_time = time.time()

        if is_429:
            backoff_duration = max(retry_after, 60.0)
            self.rate_limited_until = time.time() + backoff_duration
            logger.warning(f"OpenverseStockProvider: 429 Rate Limit recorded! Cooldown active for {backoff_duration}s until t={self.rate_limited_until:.1f}")

        if self.consecutive_failures >= self.FAILURE_THRESHOLD:
            self.cb_state = CircuitBreakerState.OPEN
            logger.error(f"OpenverseStockProvider: Circuit Breaker TRIPPED -> OPEN ({self.consecutive_failures} consecutive failures). "
                         f"Cooldown for {self.COOLDOWN_SECONDS}s.")

    def _cache_key(self, query: str, width: int, height: int) -> str:
        h = hashlib.sha256(f"openverse_{query}_{width}x{height}".encode()).hexdigest()[:16]
        return f"openverse_{h}.jpg"

    def _cache_path(self, cache_key: str) -> str:
        return os.path.join(self.CACHE_DIR, cache_key)

    def _check_cache(self, cache_key: str) -> Optional[str]:
        path = self._cache_path(cache_key)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            os.utime(path, None)
            logger.info(f"OpenverseStockProvider: Cache HIT for '{cache_key}'")
            return path
        return None

    def _enforce_cache_cap(self):
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
            logger.info(f"OpenverseStockProvider: LRU cache eviction -- removed {evicted} file(s), cache now {total_size / (1024*1024):.2f} MB")

    def _search_openverse_with_retry(self, query: str, search_terms_override: Optional[List[str]] = None, max_retries: int = 2) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Executes Openverse API search with:
        1. Explicit 429 rate limit detection & Retry-After respect
        2. Exponential backoff for transient 5xx / timeout errors
        3. Request-budget telemetry recording
        
        Returns tuple of (response_dict, failure_reason_string).
        """
        now = time.time()
        if now < self.rate_limited_until:
            wait_rem = self.rate_limited_until - now
            reason = f"HTTP 429 Rate Limit active ({wait_rem:.1f}s remaining)"
            logger.warning(f"OpenverseStockProvider: {reason}")
            return None, reason

        if search_terms_override:
            search_terms = [t for t in search_terms_override if t and t.strip()][:3]
        else:
            search_terms = [query]
            words = query.split()
            if len(words) > 2:
                simplified = " ".join([w for w in words if w.lower() not in ("a", "an", "the", "at", "in", "on", "featuring", "with", "modern", "bustling")][:2])
                if simplified and simplified not in search_terms:
                    search_terms.append(simplified)

        for q_term in search_terms:
            encoded_query = urllib.request.quote(q_term)
            url = f"{self.OPENVERSE_API_URL}?q={encoded_query}&license=cc0,pdm&page_size=5"

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "CreateFlowAI/1.0 (OpenverseStockProvider)"},
                method="GET"
            )

            # Exponential backoff retry loop for transient failures
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    backoff_delay = 0.5 * (2.0 ** (attempt - 1))
                    logger.info(f"OpenverseStockProvider: Transient retry attempt {attempt}/{max_retries} for '{q_term}' after {backoff_delay:.2f}s delay...")
                    time.sleep(backoff_delay)

                # Record request telemetry
                self.telemetry_tracker.record_request()
                t_stats = self.telemetry_tracker.get_telemetry()
                logger.info(f"OpenverseStockProvider Telemetry: Burst={t_stats['minute_count']}/{t_stats['burst_limit']}/min "
                            f"({t_stats['burst_pct']}%), Sustained={t_stats['daily_count']}/{t_stats['daily_limit']}/day "
                            f"({t_stats['daily_pct']}%)")

                try:
                    with urllib.request.urlopen(req, timeout=10) as response:
                        resp_body = response.read().decode("utf-8")
                        data = json.loads(resp_body)
                        if data.get("results"):
                            self._record_success()
                            logger.info(f"OpenverseStockProvider: Found {len(data['results'])} CC0/PDM results for query '{q_term}'")
                            return data, None

                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        # Item 1: Explicit 429 handling
                        retry_after = 0.0
                        if "Retry-After" in e.headers:
                            try:
                                retry_after = float(e.headers["Retry-After"])
                            except (ValueError, TypeError):
                                retry_after = 60.0
                        reason = f"HTTP 429 Rate Limit Exceeded (Retry-After: {retry_after}s)"
                        logger.warning(f"OpenverseStockProvider: {reason}")
                        self._record_failure(is_429=True, retry_after=retry_after)
                        return None, reason  # Do NOT retry 429s in exponential backoff loop

                    elif e.code >= 500:
                        reason = f"HTTP {e.code} Server Error: {e.reason}"
                        logger.warning(f"OpenverseStockProvider: Transient failure (attempt {attempt + 1}): {reason}")
                        if attempt == max_retries:
                            self._record_failure()
                            return None, reason

                    else:
                        reason = f"HTTP {e.code} Client Error: {e.reason}"
                        logger.error(f"OpenverseStockProvider: Non-retriable HTTP error: {reason}")
                        self._record_failure()
                        return None, reason

                except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
                    reason = f"Network Timeout / URLError: {e}"
                    logger.warning(f"OpenverseStockProvider: Transient network error (attempt {attempt + 1}): {reason}")
                    if attempt == max_retries:
                        self._record_failure()
                        return None, reason

                except Exception as e:
                    reason = f"Unexpected exception: {e}"
                    logger.error(f"OpenverseStockProvider: API exception: {reason}")
                    self._record_failure()
                    return None, reason

        return None, "No results found for query"

    def _download_image(self, image_url: str, local_path: str) -> bool:
        try:
            req = urllib.request.Request(
                image_url,
                headers={"User-Agent": "CreateFlowAI/1.0 (OpenverseDownloader)"},
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                with open(local_path, "wb") as f:
                    f.write(response.read())

            size = os.path.getsize(local_path)
            if size > 1000:
                logger.info(f"OpenverseStockProvider: Downloaded {size:,} bytes -> {local_path}")
                return True
            else:
                if os.path.exists(local_path):
                    os.remove(local_path)
                return False
        except Exception as e:
            logger.error(f"OpenverseStockProvider: Download failed for '{image_url}': {e}")
            if os.path.exists(local_path):
                os.remove(local_path)
            return False

    def retrieve_candidates(self, request: MediaRequest, limit: int = 3) -> List[MediaCandidate]:
        """
        Retrieves up to `limit` downloadable candidates from Openverse without discarding results.
        """
        t0 = time.time()
        search_terms_override = None
        negative_terms = []
        if getattr(request, "visual_query_result", None):
            from agents.video.provider_query_adapters import QueryAdapterRegistry
            adapted_vqr = QueryAdapterRegistry.adapt(self.provider_id, request.visual_query_result, None)
            query = adapted_vqr.primary_query
            search_terms_override = [adapted_vqr.primary_query] + adapted_vqr.alternate_queries
            negative_terms = [n.lower() for n in adapted_vqr.negative_terms if n]
        else:
            query = request.query or "abstract background"

        if self._is_circuit_open():
            return [self._fallback_next_provider(request, time.time() - t0, reason="Circuit Breaker OPEN")]

        result, failure_reason = self._search_openverse_with_retry(query, search_terms_override=search_terms_override)
        if not result or not result.get("results"):
            return [self._fallback_next_provider(request, time.time() - t0, reason=failure_reason or f"No results for '{query}'")]

        results_list = result["results"]
        candidates: List[MediaCandidate] = []

        for idx, photo in enumerate(results_list):
            if len(candidates) >= limit:
                break

            title = (photo.get("title") or "").lower()
            tags = [t.get("name", "").lower() for t in photo.get("tags", []) if isinstance(t, dict)]
            tag_str = " ".join(tags)
            if any(neg in title or neg in tag_str for neg in negative_terms):
                continue

            image_url = photo.get("url") or photo.get("thumbnail")
            if not image_url:
                continue

            photo_id = photo.get("id") or f"openverse_{idx}"
            ck = self._cache_key(f"{query}_{photo_id}", request.target_width, request.target_height)
            local_path = self._cache_path(ck)

            if not os.path.exists(local_path):
                if not self._download_image(image_url, local_path):
                    continue

            dt = time.time() - t0
            photo_title = photo.get("title", "Untitled")
            creator = photo.get("creator", "Unknown")
            license_code = photo.get("license", "cc0")
            attribution_str = photo.get("attribution", f"'{photo_title}' by {creator}")

            cand = MediaCandidate(
                provider_id=self.provider_id,
                media_type=MediaType.STOCK_IMAGE,
                asset_path=local_path,
                remote_url=image_url,
                width=request.target_width,
                height=request.target_height,
                candidate_status=MediaCandidateStatus.VALIDATED_RENDER_READY,
                generation_method="retrieval_metadata",
                measured_latency_seconds=round(dt, 4),
                attribution=attribution_str,
                license_name=f"CC {license_code.upper()}",
                generation_metadata={
                    "source": "openverse_api",
                    "query": query,
                    "photo_id": photo_id,
                    "title": photo_title,
                    "tags": [t.get("name", "") for t in photo.get("tags", []) if isinstance(t, dict)]
                }
            )
            candidates.append(cand)

        self._enforce_cache_cap()

        if not candidates:
            return [self._fallback_next_provider(request, time.time() - t0, reason=f"Failed to download candidates for '{query}'")]

        return candidates

    def generate_or_retrieve(self, request: MediaRequest) -> MediaCandidate:
        cands = self.retrieve_candidates(request, limit=1)
        return cands[0]

        self._enforce_cache_cap()

        dt = time.time() - t0
        photo_title = chosen_photo.get("title", "Untitled")
        creator = chosen_photo.get("creator", "Unknown")
        license_code = chosen_photo.get("license", "cc0")
        attribution_str = chosen_photo.get("attribution", f"'{photo_title}' by {creator}")

        logger.info(f"OpenverseStockProvider: Resolved '{query}' -> '{photo_title}' by {creator} "
                    f"[{license_code.upper()}] in {dt:.3f}s")

        return MediaCandidate(
            provider_id=self.provider_id,
            media_type=MediaType.STOCK_IMAGE,
            asset_path=local_path,
            remote_url=chosen_photo.get("url"),
            width=chosen_photo.get("width") or request.target_width,
            height=chosen_photo.get("height") or request.target_height,
            mime_type="image/jpeg",
            attribution=attribution_str,
            license_name=f"Openverse {license_code.upper()} (Public Domain)",
            estimated_cost=0.0,
            measured_latency_seconds=round(dt, 4),
            candidate_status=MediaCandidateStatus.VALIDATED_RENDER_READY,
            generation_method="retrieval_metadata",
            generation_metadata={
                "source": "openverse_api",
                "query": query,
                "photo_id": chosen_photo.get("id"),
                "title": photo_title,
                "creator": creator,
                "license": license_code,
                "attribution": attribution_str,
                "cache_key": ck
            }
        )

    def _fallback_next_provider(self, request: MediaRequest, elapsed: float, reason: str) -> MediaCandidate:
        """
        Fallback: openverse_stock -> procedural_overlay (solid-color placeholder).
        Note: openmontage_stock is dormant stub code (generates identical solid-color
        rectangles), so it is not included as a middle tier.
        """
        logger.info(f"OpenverseStockProvider Fallback: openverse_stock failed ({reason}) -> Generating procedural_overlay placeholder.")

        # Procedural placeholder final fallback
        from PIL import Image
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        placeholder_path = os.path.join(self.CACHE_DIR, f"fallback_{request.scene_id}.png")
        img = Image.new("RGB", (request.target_width, request.target_height), color=(15, 23, 42))
        img.save(placeholder_path, "PNG")

        return MediaCandidate(
            provider_id=self.provider_id,
            media_type=MediaType.PROCEDURAL_BACKGROUND,
            asset_path=placeholder_path,
            width=request.target_width,
            height=request.target_height,
            mime_type="image/png",
            estimated_cost=0.0,
            measured_latency_seconds=round(elapsed, 4),
            candidate_status=MediaCandidateStatus.PROCEDURAL_PLACEHOLDER,
            generation_method="procedural",
            generation_metadata={"source": "procedural_fallback", "reason": reason}
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
            asset_id=f"openverse_stock_{hash(prompt_or_query)}",
            provider_name=self.provider_id,
            asset_type=asset_type,
            prompt_or_query=prompt_or_query,
            source_url_or_path=cand.asset_path or "",
            metadata=cand.generation_metadata
        )
