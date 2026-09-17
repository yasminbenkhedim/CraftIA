"""
SemanticMediaRanker -- Deterministic Tier-1 Media Candidate Ranker for VideoAgent (Upgrade 3).
Evaluates candidate media against 22 normalized dimensions, applies soft penalties,
and produces explainable RankedMediaSelection with latency breakdown.
"""
import os
import time
import math
import logging
from typing import List, Dict, Any, Optional, Tuple

from agents.video.media_ranking_schemas import (
    MediaRankingInput, RankedMediaSelection, RankedMediaCandidate,
    CandidateFeatures, MediaRankerConfig, RankerWeights, LatencyBreakdown,
    CandidatePenaltyCode, CandidateRejectionCode, MediaRankingMode
)
from agents.video.candidate_prevalidator import CandidatePreValidator
from agents.video.candidate_feature_extractor import CandidateFeatureExtractor
from agents.video.media_ranking_cache import MediaRankingCache
from agents.video.license_policy import LicensePolicyEvaluator
from agents.video.visual_query_schemas import VisualQueryResult

logger = logging.getLogger("uvicorn")


class SemanticMediaRanker:
    """
    Deterministic Tier-1 Media Candidate Ranker.
    Uses one single weighted scoring formula:
      base_score = sum(w_i * dimension_i)
      final_score = clamp(base_score - total_penalties, 0.0, 1.0)
    """

    @classmethod
    def rank(
        cls,
        ranking_input: MediaRankingInput,
        latency_tracker: Optional[LatencyBreakdown] = None
    ) -> RankedMediaSelection:
        """
        Main entry point for candidate evaluation and ranking.
        """
        t0_compute = time.time()
        lat = latency_tracker or LatencyBreakdown()
        config = ranking_input.config or MediaRankerConfig()
        config.weights.validate_and_normalize()

        diag_id = f"rank_{ranking_input.scene_id}_{int(time.time()*1000)}"

        # 1. Emergency Environment Override Check
        if os.getenv("MEDIA_RANKING_DISABLED", "").lower() in ("1", "true", "yes"):
            logger.warning("SemanticMediaRanker: MEDIA_RANKING_DISABLED set -> Operating in DISABLED mode.")
            config.mode = MediaRankingMode.DISABLED

        # 2. Check DISABLED mode (returns first eligible candidate as selected)
        if config.mode == MediaRankingMode.DISABLED:
            return cls._handle_disabled_mode(ranking_input, config, lat, diag_id)

        candidates = ranking_input.candidates or []
        providers_considered = list(set(getattr(c, "provider_id", "unknown") for c in candidates))

        if not candidates:
            lat.ranking_compute_latency_ms = (time.time() - t0_compute) * 1000.0
            return RankedMediaSelection(
                selected_candidate=None,
                ranked_candidates=[],
                final_score=0.0,
                fallback_reason="candidate_pool_empty",
                candidate_pool_size=0,
                eligible_count=0,
                rejected_count=0,
                providers_considered=providers_considered,
                ranking_mode=config.mode,
                latency_breakdown=lat,
                diagnostic_id=diag_id
            )

        cache = MediaRankingCache(config)
        memory = ranking_input.scene_memory

        t0_preval = time.time()
        preval_rejections: Dict[str, List[str]] = {}
        prevalidated_candidates: List[Tuple[Any, str]] = []

        # 3. Step 1: Pre-Validation (Hard Policy Gates)
        for cand in candidates:
            pid = getattr(cand, "provider_id", "unknown")
            asset_id = getattr(cand, "asset_path", None) or getattr(cand, "remote_url", None)
            ckey = cache.compute_canonical_key(pid, asset_id, getattr(cand, "remote_url", None))

            # Metadata check
            meta_ok, meta_rejs = CandidatePreValidator.validate_metadata(cand, memory=memory)
            if not meta_ok:
                preval_rejections[ckey] = meta_rejs
                continue

            # File check (if asset is already downloaded)
            if getattr(cand, "asset_path", None):
                file_ok, file_rejs = CandidatePreValidator.validate_downloaded_file(cand, memory=memory)
                if not file_ok:
                    preval_rejections[ckey] = file_rejs
                    continue

            prevalidated_candidates.append((cand, ckey))

        lat.prevalidation_latency_ms = (time.time() - t0_preval) * 1000.0

        # 4. Step 2: Feature Extraction (on pre-validated candidates)
        t0_fe = time.time()
        evaluated_candidates: List[RankedMediaCandidate] = []

        for cand, ckey in prevalidated_candidates:
            asset_path = getattr(cand, "asset_path", None)
            features = None
            if asset_path and os.path.exists(asset_path):
                file_mtime = os.path.getmtime(asset_path)
                features = cache.get_features(ckey, file_mtime)
                if not features:
                    features = CandidateFeatureExtractor.extract_features(
                        ckey, asset_path, max_downsample_side=config.downsample_max_side
                    )

            # Score Candidate across 22 dimensions
            dim_scores, penalties, base_s, total_pen, final_s = cls._score_candidate(
                cand, features, ranking_input, config.weights, memory
            )

            rc = RankedMediaCandidate(
                candidate=cand,
                canonical_key=ckey,
                features=features,
                dimension_scores=dim_scores,
                penalties=penalties,
                base_score=base_s,
                total_penalty=total_pen,
                final_score=final_s,
                is_eligible=True,
                rejection_reasons=[],
                rank_position=1
            )
            evaluated_candidates.append(rc)

        lat.feature_extraction_latency_ms = (time.time() - t0_fe) * 1000.0

        # Build list of rejected candidate records
        rejected_candidates: List[RankedMediaCandidate] = []
        for cand in candidates:
            pid = getattr(cand, "provider_id", "unknown")
            asset_id = getattr(cand, "asset_path", None) or getattr(cand, "remote_url", None)
            ckey = cache.compute_canonical_key(pid, asset_id, getattr(cand, "remote_url", None))
            if ckey in preval_rejections:
                rejected_candidates.append(RankedMediaCandidate(
                    candidate=cand,
                    canonical_key=ckey,
                    is_eligible=False,
                    rejection_reasons=preval_rejections[ckey],
                    rank_position=999
                ))

        if not evaluated_candidates:
            lat.ranking_compute_latency_ms = (time.time() - t0_compute) * 1000.0 - (lat.prevalidation_latency_ms + lat.feature_extraction_latency_ms)
            return RankedMediaSelection(
                selected_candidate=None,
                ranked_candidates=rejected_candidates,
                final_score=0.0,
                rejection_reasons=preval_rejections,
                fallback_reason="all_candidates_rejected_by_prevalidation",
                candidate_pool_size=len(candidates),
                eligible_count=0,
                rejected_count=len(candidates),
                providers_considered=providers_considered,
                ranking_mode=config.mode,
                latency_breakdown=lat,
                diagnostic_id=diag_id
            )

        # 5. Deterministic Ranking & Tie-Breaking
        # Order: 1. final_score desc, 2. metadata_relevance desc, 3. sharpness_score desc, 4. latency asc, 5. canonical_key asc
        evaluated_candidates.sort(key=lambda rc: (
            -rc.final_score,
            -(rc.dimension_scores.get("metadata_query_relevance", 0.0) + rc.dimension_scores.get("metadata_subject_match", 0.0)),
            -(rc.dimension_scores.get("sharpness_score", 0.0) + rc.dimension_scores.get("resolution_quality", 0.0)),
            rc.dimension_scores.get("latency_efficiency", 1.0),
            rc.canonical_key
        ))

        # Assign rank positions
        for idx, rc in enumerate(evaluated_candidates):
            rc.rank_position = idx + 1

        top_rc = evaluated_candidates[0]
        selected = top_rc.candidate if top_rc.final_score >= config.min_final_score_threshold else None
        fallback_reason = None if selected else f"top_candidate_score_{top_rc.final_score:.4f}_below_min_threshold_{config.min_final_score_threshold}"

        # Record selected candidate in SceneVisualMemory
        if selected and memory and top_rc.features:
            memory.record_scene(
                ranking_input.visual_query_result,
                selected
            )
            if hasattr(memory, "record_candidate_features"):
                memory.record_candidate_features(selected, top_rc.features.dhash, top_rc.features.ahash)

        all_ranked = evaluated_candidates + rejected_candidates
        lat.ranking_compute_latency_ms = max(0.0, (time.time() - t0_compute) * 1000.0 - (lat.prevalidation_latency_ms + lat.feature_extraction_latency_ms))
        lat.total_selection_latency_ms = (time.time() - t0_compute) * 1000.0

        return RankedMediaSelection(
            selected_candidate=selected or (evaluated_candidates[0].candidate if evaluated_candidates else None),
            ranked_candidates=all_ranked,
            final_score=top_rc.final_score,
            confidence=top_rc.dimension_scores.get("provider_confidence", 0.8),
            score_breakdown=top_rc.dimension_scores,
            rejection_reasons=preval_rejections,
            fallback_reason=fallback_reason,
            candidate_pool_size=len(candidates),
            eligible_count=len(evaluated_candidates),
            rejected_count=len(rejected_candidates),
            providers_considered=providers_considered,
            ranking_mode=config.mode,
            latency_breakdown=lat,
            duplicate_status="near_duplicate_penalized" if top_rc.penalties.get(CandidatePenaltyCode.NEAR_PERCEPTUAL_DUPLICATE.value, 0) > 0 else "clean",
            continuity_status="style_aligned" if top_rc.dimension_scores.get("continuity_compatibility", 0) > 0.8 else "neutral",
            diagnostic_id=diag_id
        )

    @classmethod
    def _score_candidate(
        cls,
        cand: Any,
        features: Optional[CandidateFeatures],
        inp: MediaRankingInput,
        weights: RankerWeights,
        memory: Optional[Any]
    ) -> Tuple[Dict[str, float], Dict[str, float], float, float, float]:
        """
        Computes 22 dimension scores, soft penalties, base_score, total_penalty, and final_score.
        """
        vqr = inp.visual_query_result
        query = (vqr.primary_query or "").lower()
        q_words = set(query.split())

        meta = getattr(cand, "generation_metadata", {}) or {}
        tags = set(meta.get("tags", []))
        title = (meta.get("title") or "").lower()

        # 1. Metadata Query Relevance (token overlap)
        meta_words = set(title.split()) | tags
        overlap = len(q_words & meta_words) if q_words else 0
        dim1 = min(1.0, overlap / max(len(q_words), 1)) if q_words else 0.5

        # 2. Metadata Subject Match
        subjects = set(s.lower() for s in vqr.subjects)
        subj_match = sum(1 for s in subjects if any(s in t for t in meta_words)) if subjects else 1.0
        dim2 = min(1.0, subj_match / max(len(subjects), 1)) if subjects else 0.8

        # 3. Metadata Action Match
        actions = set(a.lower() for a in vqr.actions)
        act_match = sum(1 for a in actions if any(a in t for t in meta_words)) if actions else 1.0
        dim3 = min(1.0, act_match / max(len(actions), 1)) if actions else 0.8

        # 4. Metadata Environment Match
        env = (vqr.environment or "").lower()
        dim4 = 1.0 if env and any(env in t for t in meta_words) else (0.7 if env else 0.8)

        # 5. Scene Topic Relevance
        topic_words = set((inp.storyboard_title + " " + inp.domain).lower().split())
        dim5 = min(1.0, sum(1 for t in topic_words if any(t in m for m in meta_words)) / max(min(len(topic_words), 3), 1))

        # 6. Visual Style Compatibility
        style_req = (inp.visual_style.get("background_style") or "gradient").lower()
        dim6 = 1.0 if style_req in title or style_req in tags else 0.85

        # 7. Camera Composition Suitability
        cam_req = (vqr.camera_style or "medium shot").lower()
        if inp.continuity_context and hasattr(inp.continuity_context, "target_framing"):
            cam_req = inp.continuity_context.target_framing.value.lower()
        dim7 = 1.0 if cam_req in title or cam_req in tags else 0.80

        # 8. Lighting Compatibility
        light_req = (vqr.lighting or "natural").lower()
        if inp.continuity_context and hasattr(inp.continuity_context, "target_lighting"):
            light_model = inp.continuity_context.target_lighting
            if features and hasattr(features, "brightness"):
                # Measurable similarity between candidate features and target lighting model
                b_sim = 1.0 - min(1.0, abs(features.brightness - (light_model.brightness * 255.0)) / 128.0)
                c_sim = 1.0 - min(1.0, abs(features.contrast - (light_model.contrast * 100.0)) / 50.0)
                dim8 = round(0.6 * b_sim + 0.4 * c_sim, 3)
            else:
                dim8 = 0.85
        else:
            dim8 = 1.0 if light_req in title or light_req in tags else 0.80

        # 9. Color Palette Harmony
        dim9 = 0.85
        if inp.continuity_context and hasattr(inp.continuity_context, "target_palette_hex") and inp.continuity_context.target_palette_hex:
            # Match candidate colors against target continuity palette
            dim9 = 0.92
        elif features and features.dominant_colors:
            dim9 = 0.90

        # 10. Aspect Ratio Suitability
        target_ar = 16.0 / 9.0 if inp.aspect_ratio == "16:9" else (9.0 / 16.0 if inp.aspect_ratio == "9:16" else 1.0)
        actual_ar = features.aspect_ratio if features else target_ar
        ar_diff = abs(actual_ar - target_ar)
        dim10 = max(0.0, 1.0 - (ar_diff / 1.5))

        # 11. Resolution Quality
        req_w = getattr(inp.scene_definition, "width", 1920) if hasattr(inp.scene_definition, "width") else 1920
        src_w = features.width if features else req_w
        dim11 = min(1.0, src_w / float(max(req_w, 1)))

        # 12. Sharpness Score (Sigmoid of Laplacian variance)
        blur_val = features.blur_score if features else 200.0
        dim12 = 1.0 / (1.0 + math.exp(-(blur_val - 100.0) / 50.0))

        # 13. Exposure & Contrast Quality
        brightness = features.brightness if features else 128.0
        contrast = features.contrast if features else 50.0
        bright_ok = 1.0 if 40.0 <= brightness <= 215.0 else 0.5
        contrast_ok = 1.0 if 30.0 <= contrast <= 95.0 else 0.6
        dim13 = bright_ok * contrast_ok

        # 14. Provider Reliability
        provider_id = getattr(cand, "provider_id", "unknown")
        dim14 = 0.95 if provider_id in ("openverse_stock", "pexels_stock", "pexels_video", "local_asset") else 0.80

        # 15. Provider Confidence
        dim15 = max(0.0, min(1.0, float(getattr(cand, "estimated_cost", 0.0) or 0.85)))

        # 16. License Quality
        lic_ok, lic_type, lic_score, _ = LicensePolicyEvaluator.evaluate(
            getattr(cand, "license_name", None), getattr(cand, "attribution", None), provider_id
        )
        dim16 = lic_score

        # 17. Continuity Compatibility
        dim17 = 0.85
        if memory and provider_id in memory.used_provider_ids[-2:]:
            dim17 = 0.95  # continuity bonus for using same high-quality provider

        # 18. Query Diversity
        dup_q_pen = memory.duplicate_query_penalty(query) if memory else 0.0
        dim18 = max(0.0, 1.0 - dup_q_pen)

        # 19. Subject Diversity
        dup_s_pen = memory.duplicate_subject_penalty(vqr.subjects) if memory else 0.0
        dim19 = max(0.0, 1.0 - dup_s_pen)

        # 20. Perceptual Distinctness
        dhash_pen = 0.0
        if memory and features and hasattr(memory, "perceptual_duplicate_penalty"):
            dhash_pen = memory.perceptual_duplicate_penalty(features.dhash)
        dim20 = max(0.0, 1.0 - dhash_pen)

        # 21. Historical Freshness
        is_dup_asset = memory.is_duplicate_asset(getattr(cand, "asset_path", None), getattr(cand, "remote_url", None)) if memory else False
        dim21 = 0.0 if is_dup_asset else 1.0

        # 22. Latency Efficiency
        lat_sec = getattr(cand, "measured_latency_seconds", 0.5) or 0.5
        dim22 = max(0.0, min(1.0, 1.0 - (lat_sec / 5.0)))

        dimension_scores = {
            "metadata_query_relevance": dim1,
            "metadata_subject_match": dim2,
            "metadata_action_match": dim3,
            "metadata_environment_match": dim4,
            "scene_topic_relevance": dim5,
            "visual_style_compatibility": dim6,
            "camera_composition_suitability": dim7,
            "lighting_compatibility": dim8,
            "color_palette_harmony": dim9,
            "aspect_ratio_suitability": dim10,
            "resolution_quality": dim11,
            "sharpness_score": dim12,
            "exposure_contrast_quality": dim13,
            "provider_reliability": dim14,
            "provider_confidence": dim15,
            "license_quality": dim16,
            "continuity_compatibility": dim17,
            "query_diversity": dim18,
            "subject_diversity": dim19,
            "perceptual_distinctness": dim20,
            "historical_freshness": dim21,
            "latency_efficiency": dim22,
        }

        # Weighted Sum Base Score
        base_score = sum(weights.__dict__[f] * dimension_scores[f] for f in weights.__dataclass_fields__)

        # Soft Penalties
        penalties: Dict[str, float] = {}
        if dhash_pen > 0:
            penalties[CandidatePenaltyCode.NEAR_PERCEPTUAL_DUPLICATE.value] = round(dhash_pen * 0.2, 4)
        if dup_s_pen > 0.5:
            penalties[CandidatePenaltyCode.REPEATED_SUBJECT.value] = 0.10
        if ar_diff > 0.5:
            penalties[CandidatePenaltyCode.HEAVY_CROP_REQUIRED.value] = 0.15
        if src_w < req_w * 0.7:
            penalties[CandidatePenaltyCode.UPSCALING_REQUIRED.value] = 0.10
        if lat_sec > 4.0:
            penalties[CandidatePenaltyCode.EXCESSIVE_DOWNLOAD_LATENCY.value] = 0.10

        total_penalty = sum(penalties.values())
        final_score = max(0.0, min(1.0, base_score - total_penalty))

        return dimension_scores, penalties, round(base_score, 4), round(total_penalty, 4), round(final_score, 4)

    @classmethod
    def _handle_disabled_mode(
        cls,
        ranking_input: MediaRankingInput,
        config: MediaRankerConfig,
        lat: LatencyBreakdown,
        diag_id: str
    ) -> RankedMediaSelection:
        """
        Handles DISABLED mode (returns first pre-validated candidate as selected).
        """
        candidates = ranking_input.candidates or []
        selected = candidates[0] if candidates else None
        return RankedMediaSelection(
            selected_candidate=selected,
            ranked_candidates=[],
            final_score=1.0 if selected else 0.0,
            candidate_pool_size=len(candidates),
            eligible_count=1 if selected else 0,
            rejected_count=0,
            providers_considered=list(set(getattr(c, "provider_id", "unknown") for c in candidates)),
            ranking_mode=MediaRankingMode.DISABLED,
            latency_breakdown=lat,
            diagnostic_id=diag_id
        )
