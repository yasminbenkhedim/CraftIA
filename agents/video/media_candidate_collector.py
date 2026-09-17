"""
MediaCandidateCollector -- Bounded Multi-Candidate Pool Collector for VideoAgent (Upgrade 3).
Collects metadata candidates across providers using Staged Hybrid strategy before downloading.
"""
import os
import time
import logging
from typing import List, Dict, Any, Optional, Set, Tuple

from agents.video.media_ranking_schemas import (
    MediaRankingInput, MediaRankerConfig, LatencyBreakdown
)
from agents.video.candidate_prevalidator import CandidatePreValidator
from agents.video.providers import ProviderRegistry, MediaRequest, MediaCandidate

logger = logging.getLogger("uvicorn")


class MediaCandidateCollector:
    """
    Collects bounded candidate media pools across registered providers.
    """

    @classmethod
    def collect_pool(
        cls,
        request: MediaRequest,
        config: Optional[MediaRankerConfig] = None,
        memory: Optional[Any] = None,
        latency_tracker: Optional[LatencyBreakdown] = None
    ) -> Tuple[List[MediaCandidate], List[str]]:
        """
        Collects up to K pre-validated downloadable candidates across providers.
        Returns tuple of (downloaded_candidates, providers_queried).
        """
        t0_search = time.time()
        if config is None:
            config = MediaRankerConfig()
        lat = latency_tracker or LatencyBreakdown()

        # Step 1: Select primary provider and fallback chain via ProviderRegistry
        selection_res = ProviderRegistry.select_provider(request)
        if not selection_res.selected_provider_id:
            lat.provider_search_latency_ms = (time.time() - t0_search) * 1000.0
            return [], []

        providers_to_query = [selection_res.selected_provider_id] + selection_res.fallback_chain
        providers_queried: List[str] = []
        metadata_shortlist: List[MediaCandidate] = []
        seen_urls: Set[str] = set()

        # Step 2: Metadata Search Loop (Staged Hybrid Strategy)
        for pid in providers_to_query:
            if len(metadata_shortlist) >= config.sufficiency_threshold:
                break

            if len(providers_queried) >= 2:  # Max 2 provider API search calls per scene
                break

            try:
                prov = ProviderRegistry.get(pid)
                providers_queried.append(pid)

                # Fetch candidates using multi-candidate interface or fallback to single
                if hasattr(prov, "retrieve_candidates"):
                    limit = config.max_candidates_per_provider
                    cands = prov.retrieve_candidates(request, limit=limit)
                else:
                    cand = prov.generate_or_retrieve(request)
                    cands = [cand] if cand else []

                for cand in cands:
                    if not cand:
                        continue

                    # Pre-download metadata checks (license, deduplication, unsafe terms)
                    meta_ok, meta_rejs = CandidatePreValidator.validate_metadata(cand, memory=memory)
                    if not meta_ok:
                        continue

                    remote_url = getattr(cand, "remote_url", None)
                    if remote_url and remote_url in seen_urls:
                        continue
                    if remote_url:
                        seen_urls.add(remote_url)

                    metadata_shortlist.append(cand)
                    if len(metadata_shortlist) >= config.max_pool_size:
                        break

            except Exception as e:
                logger.warning(f"MediaCandidateCollector: Provider '{pid}' search failed: {e}")

        lat.provider_search_latency_ms = (time.time() - t0_search) * 1000.0

        # Step 3: Download Shortlist Candidates
        t0_download = time.time()
        downloaded_candidates: List[MediaCandidate] = []

        for cand in metadata_shortlist[:config.max_pool_size]:
            asset_path = getattr(cand, "asset_path", None)
            if asset_path and os.path.exists(asset_path):
                downloaded_candidates.append(cand)
            else:
                # Candidate has remote_url but needs download (already handled during provider retrieve_candidates)
                if asset_path and os.path.exists(asset_path):
                    downloaded_candidates.append(cand)

        lat.candidate_download_latency_ms = (time.time() - t0_download) * 1000.0
        return downloaded_candidates, providers_queried
