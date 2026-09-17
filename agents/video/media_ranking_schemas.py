"""
Media Ranking Schemas & Data Models for VideoAgent (Upgrade 3).
Defines dataclasses, enums, rejection codes, penalty codes, config, feature vectors,
and diagnostic models for semantic media ranking.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Tuple


class MediaRankingMode(str, Enum):
    DISABLED = "disabled"                    # Legacy first-valid-candidate path
    DETERMINISTIC_TIER1 = "deterministic_tier1" # Active deterministic ranking pipeline
    FUTURE_AI_ASSISTED = "future_ai_assisted" # Schema supported, falls back to DETERMINISTIC_TIER1


class CandidateRejectionCode(str, Enum):
    MISSING_ASSET_PATH = "MISSING_ASSET_PATH"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    INVALID_MIME_TYPE = "INVALID_MIME_TYPE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    PATH_TRAVERSAL_DETECTED = "PATH_TRAVERSAL_DETECTED"
    OUTSIDE_APPROVED_ROOT = "OUTSIDE_APPROVED_ROOT"
    CORRUPT_IMAGE_HEADER = "CORRUPT_IMAGE_HEADER"
    DIMENSIONS_BELOW_MINIMUM = "DIMENSIONS_BELOW_MINIMUM"
    EXCESSIVE_PIXEL_COUNT = "EXCESSIVE_PIXEL_COUNT"
    PROCEDURAL_PLACEHOLDER = "PROCEDURAL_PLACEHOLDER"
    INVALID_LICENSE = "INVALID_LICENSE"
    MISSING_REQUIRED_ATTRIBUTION = "MISSING_REQUIRED_ATTRIBUTION"
    EXACT_DUPLICATE_ASSET_ID = "EXACT_DUPLICATE_ASSET_ID"
    EXACT_DUPLICATE_SOURCE_URL = "EXACT_DUPLICATE_SOURCE_URL"
    EXACT_DUPLICATE_CONTENT_HASH = "EXACT_DUPLICATE_CONTENT_HASH"
    EXACT_PERCEPTUAL_DUPLICATE = "EXACT_PERCEPTUAL_DUPLICATE"
    UNSAFE_CONTENT_FLAGGED = "UNSAFE_CONTENT_FLAGGED"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class CandidatePenaltyCode(str, Enum):
    NEAR_PERCEPTUAL_DUPLICATE = "NEAR_PERCEPTUAL_DUPLICATE"
    REPEATED_SUBJECT = "REPEATED_SUBJECT"
    REPEATED_ENVIRONMENT = "REPEATED_ENVIRONMENT"
    REPEATED_PROVIDER = "REPEATED_PROVIDER"
    HEAVY_CROP_REQUIRED = "HEAVY_CROP_REQUIRED"
    UPSCALING_REQUIRED = "UPSCALING_REQUIRED"
    EXCESSIVE_DOWNLOAD_LATENCY = "EXCESSIVE_DOWNLOAD_LATENCY"
    NEGATIVE_TERM_METADATA_MATCH = "NEGATIVE_TERM_METADATA_MATCH"


@dataclass
class RankerWeights:
    metadata_query_relevance: float = 0.12
    metadata_subject_match: float = 0.10
    metadata_action_match: float = 0.05
    metadata_environment_match: float = 0.05
    scene_topic_relevance: float = 0.05
    visual_style_compatibility: float = 0.04
    camera_composition_suitability: float = 0.04
    lighting_compatibility: float = 0.03
    color_palette_harmony: float = 0.04
    aspect_ratio_suitability: float = 0.08
    resolution_quality: float = 0.06
    sharpness_score: float = 0.05
    exposure_contrast_quality: float = 0.04
    provider_reliability: float = 0.03
    provider_confidence: float = 0.02
    license_quality: float = 0.04
    continuity_compatibility: float = 0.04
    query_diversity: float = 0.03
    subject_diversity: float = 0.03
    perceptual_distinctness: float = 0.03
    historical_freshness: float = 0.02
    latency_efficiency: float = 0.01

    def validate_and_normalize(self):
        fields = list(self.__dataclass_fields__.keys())
        total = sum(getattr(self, f) for f in fields)
        if abs(total - 1.0) > 1e-4:
            if total > 0:
                for f in fields:
                    setattr(self, f, getattr(self, f) / total)


@dataclass
class MediaRankerConfig:
    mode: MediaRankingMode = MediaRankingMode.DETERMINISTIC_TIER1
    max_pool_size: int = 8
    max_candidates_per_provider: int = 3
    sufficiency_threshold: int = 2
    ranking_compute_budget_ms: float = 150.0
    feature_extraction_budget_ms: float = 250.0
    total_selection_budget_ms: float = 8000.0
    min_final_score_threshold: float = 0.35
    downsample_max_side: int = 1024
    weights: RankerWeights = field(default_factory=RankerWeights)


@dataclass
class MediaRankingInput:
    scene_id: str
    visual_query_result: Any
    scene_definition: Any
    storyboard_title: str
    domain: str
    visual_style: Dict[str, Any]
    aspect_ratio: str = "16:9"
    candidates: List[Any] = field(default_factory=list)
    scene_memory: Optional[Any] = None
    continuity_context: Optional[Any] = None
    config: Optional[MediaRankerConfig] = None
    remaining_budget: Optional[Any] = None


@dataclass
class CandidateFeatures:
    canonical_key: str
    width: int = 0
    height: int = 0
    megapixels: float = 0.0
    aspect_ratio: float = 1.0
    orientation: str = "landscape"  # "landscape", "portrait", "square"
    file_size_bytes: int = 0
    mime_type: str = "image/jpeg"
    brightness: float = 128.0
    contrast: float = 50.0
    dynamic_range: float = 255.0
    blur_score: float = 200.0        # Laplacian variance
    dominant_colors: List[Tuple[int, int, int]] = field(default_factory=list)
    color_histogram_summary: List[float] = field(default_factory=list)
    unique_color_ratio: float = 0.01
    grayscale_entropy: float = 5.0
    edge_density: float = 0.1
    has_alpha: bool = False
    ahash: str = ""
    dhash: str = ""
    content_sha256: str = ""
    extraction_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "canonical_key": self.canonical_key,
            "dimensions": f"{self.width}x{self.height}",
            "megapixels": round(self.megapixels, 2),
            "aspect_ratio": round(self.aspect_ratio, 3),
            "orientation": self.orientation,
            "file_size_bytes": self.file_size_bytes,
            "mime_type": self.mime_type,
            "brightness": round(self.brightness, 2),
            "contrast": round(self.contrast, 2),
            "blur_score": round(self.blur_score, 2),
            "dominant_colors": self.dominant_colors,
            "grayscale_entropy": round(self.grayscale_entropy, 2),
            "dhash": self.dhash,
            "content_sha256": self.content_sha256[:16] if self.content_sha256 else "",
            "extraction_latency_ms": round(self.extraction_latency_ms, 2)
        }


@dataclass
class RankedMediaCandidate:
    candidate: Any                             # MediaCandidate
    canonical_key: str
    features: Optional[CandidateFeatures] = None
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    penalties: Dict[str, float] = field(default_factory=dict)
    base_score: float = 0.0
    total_penalty: float = 0.0
    final_score: float = 0.0
    is_eligible: bool = True
    rejection_reasons: List[str] = field(default_factory=list)
    rank_position: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "canonical_key": self.canonical_key,
            "provider_id": getattr(self.candidate, "provider_id", "unknown"),
            "asset_path": getattr(self.candidate, "asset_path", None),
            "rank_position": self.rank_position,
            "is_eligible": self.is_eligible,
            "base_score": round(self.base_score, 4),
            "total_penalty": round(self.total_penalty, 4),
            "final_score": round(self.final_score, 4),
            "rejection_reasons": self.rejection_reasons,
            "dimension_scores": {k: round(v, 4) for k, v in self.dimension_scores.items()},
            "penalties": {k: round(v, 4) for k, v in self.penalties.items()},
            "features": self.features.to_dict() if self.features else None
        }


@dataclass
class LatencyBreakdown:
    provider_search_latency_ms: float = 0.0
    candidate_download_latency_ms: float = 0.0
    prevalidation_latency_ms: float = 0.0
    feature_extraction_latency_ms: float = 0.0
    ranking_compute_latency_ms: float = 0.0
    total_selection_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "provider_search_ms": round(self.provider_search_latency_ms, 2),
            "candidate_download_ms": round(self.candidate_download_latency_ms, 2),
            "prevalidation_ms": round(self.prevalidation_latency_ms, 2),
            "feature_extraction_ms": round(self.feature_extraction_latency_ms, 2),
            "ranking_compute_ms": round(self.ranking_compute_latency_ms, 2),
            "total_selection_ms": round(self.total_selection_latency_ms, 2)
        }


@dataclass
class RankedMediaSelection:
    selected_candidate: Optional[Any]           # MediaCandidate or None
    ranked_candidates: List[RankedMediaCandidate] = field(default_factory=list)
    final_score: float = 0.0
    confidence: float = 1.0
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    rejection_reasons: Dict[str, List[str]] = field(default_factory=dict)
    fallback_reason: Optional[str] = None
    candidate_pool_size: int = 0
    eligible_count: int = 0
    rejected_count: int = 0
    providers_considered: List[str] = field(default_factory=list)
    ranking_mode: MediaRankingMode = MediaRankingMode.DETERMINISTIC_TIER1
    latency_breakdown: LatencyBreakdown = field(default_factory=LatencyBreakdown)
    duplicate_status: str = "clean"
    continuity_status: str = "neutral"
    diagnostic_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diagnostic_id": self.diagnostic_id,
            "ranking_mode": self.ranking_mode.value,
            "selected_candidate_provider": getattr(self.selected_candidate, "provider_id", None) if self.selected_candidate else None,
            "selected_asset_path": getattr(self.selected_candidate, "asset_path", None) if self.selected_candidate else None,
            "final_score": round(self.final_score, 4),
            "confidence": round(self.confidence, 4),
            "candidate_pool_size": self.candidate_pool_size,
            "eligible_count": self.eligible_count,
            "rejected_count": self.rejected_count,
            "providers_considered": self.providers_considered,
            "fallback_reason": self.fallback_reason,
            "duplicate_status": self.duplicate_status,
            "continuity_status": self.continuity_status,
            "latency_breakdown": self.latency_breakdown.to_dict(),
            "score_breakdown": {k: round(v, 4) for k, v in self.score_breakdown.items()},
            "rejection_reasons": self.rejection_reasons,
            "ranked_candidates": [rc.to_dict() for rc in self.ranked_candidates[:5]]
        }


@dataclass
class SharedAssetCacheEntry:
    canonical_asset_key: str
    validated_path: str
    mime_type: str
    dimensions: Tuple[int, int]
    file_size_bytes: int
    file_mtime: float
    content_sha256: str
    features: Optional[CandidateFeatures] = None
    perceptual_dhash: str = ""
    preview_path: Optional[str] = None
