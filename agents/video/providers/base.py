"""
Production-Grade Media Provider Registry, 7-Dimension Quality Evaluator, and Asset Validation Layer.

Replaces hardcoded provider decisions with dynamic, profile-weighted scoring across:
  1. Task Fit
  2. Output Quality
  3. Control and Customization
  4. Reliability
  5. Cost Efficiency
  6. Latency and Speed
  7. Visual Style Continuity
"""
import os
import abc
import time
import hashlib
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Union
from pydantic import BaseModel, Field
from PIL import Image

logger = logging.getLogger("uvicorn")


# ============================================================================
# DOMAIN ENUMS & TYPED SCHEMAS
# ============================================================================

class MediaType(str, Enum):
    GENERATED_IMAGE = "generated_image"
    GENERATED_VIDEO = "generated_video"
    STOCK_IMAGE = "stock_image"
    STOCK_VIDEO = "stock_video"
    UPLOADED_MEDIA = "uploaded_media"
    LOCAL_ASSET = "local_asset"
    SCREENSHOT = "screenshot"
    CHART = "chart"
    ICON = "icon"
    PROCEDURAL_GRAPHIC = "procedural_graphic"
    PROCEDURAL_BACKGROUND = "procedural_background"
    TITLE_CARD = "title_card"


class ProviderSelectionProfile(str, Enum):
    CINEMATIC_QUALITY = "cinematic_quality"
    FAST_PREVIEW = "fast_preview"
    LOW_COST = "low_cost"
    OFFLINE = "offline"
    SOCIAL_MEDIA = "social_media"
    CORPORATE = "corporate"
    EDUCATIONAL = "educational"


# Structured Provider Exceptions
class ProviderError(Exception):
    """Base exception for provider operations."""
    pass

class ProviderUnavailableError(ProviderError):
    pass

class ProviderConfigurationError(ProviderError):
    pass

class ProviderCapabilityError(ProviderError):
    pass

class ProviderGenerationError(ProviderError):
    pass

class ProviderTimeoutError(ProviderError):
    pass

class ProviderInvalidAssetError(ProviderError):
    pass


class MediaRequest(BaseModel):
    scene_id: str
    query: str
    media_type_preferences: List[MediaType]
    excluded_media_types: List[MediaType] = Field(default_factory=list)
    aspect_ratio: str = "16:9"
    target_width: int = 1920
    target_height: int = 1080
    minimum_duration: Optional[float] = None
    visual_style: Dict[str, Any] = Field(default_factory=dict)
    previous_scene_provider: Optional[str] = None
    previous_scene_style_reference: Optional[str] = None
    offline_mode: bool = False
    quality_profile: ProviderSelectionProfile = ProviderSelectionProfile.CINEMATIC_QUALITY
    maximum_cost: Optional[float] = None
    maximum_latency_seconds: Optional[float] = None
    required_capabilities: Set[str] = Field(default_factory=set)
    visual_query_result: Optional[Any] = None

    class Config:
        arbitrary_types_allowed = True


class ProviderCapabilities(BaseModel):
    media_types: Set[MediaType]
    supported_aspect_ratios: Set[str] = Field(default_factory=lambda: {"16:9", "9:16", "1:1"})
    supports_duration_control: bool = True
    supports_seed: bool = False
    supports_style_reference: bool = False
    supports_image_reference: bool = False
    supports_character_reference: bool = False
    supports_palette_control: bool = True
    supports_typography_control: bool = True
    supports_template_locking: bool = True
    supports_camera_control: bool = True
    supports_motion_control: bool = True
    requires_network: bool = False
    requires_api_key: bool = False
    supports_offline: bool = True
    returns_attribution: bool = False


class ProviderHealth(BaseModel):
    available: bool = True
    configuration_ready: bool = True
    consecutive_failures: int = 0
    total_requests: int = 0
    total_successes: int = 0
    rolling_success_rate: float = 1.0
    rolling_average_latency_sec: float = 0.5
    temporary_penalty: float = 0.0
    last_failure_timestamp: Optional[float] = None


class MediaCandidateStatus(str, Enum):
    DISCOVERED_REMOTE = "discovered_remote"
    DOWNLOADED_UNVALIDATED = "downloaded_unvalidated"
    VALIDATED_RENDER_READY = "validated_render_ready"
    PROCEDURAL_PLACEHOLDER = "procedural_placeholder"
    FAILED = "failed"


class MediaCandidate(BaseModel):
    provider_id: str
    media_type: MediaType
    asset_path: Optional[str] = None
    remote_url: Optional[str] = None
    preview_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    mime_type: Optional[str] = None
    attribution: Optional[str] = None
    license_name: Optional[str] = None
    generation_metadata: Dict[str, Any] = Field(default_factory=dict)
    estimated_cost: float = 0.0
    measured_latency_seconds: Optional[float] = None
    style_fingerprint: Optional[Dict[str, Any]] = None
    candidate_status: MediaCandidateStatus = MediaCandidateStatus.VALIDATED_RENDER_READY
    generation_method: str = "procedural"  # "procedural", "retrieval_metadata", "uploaded", "ai_image_synthesis", "ai_video_synthesis"


# Legacy AssetProvenance adapter
class AssetProvenance(BaseModel):
    asset_id: str
    provider_name: str
    asset_type: str
    prompt_or_query: str
    source_url_or_path: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# EVALUATOR SCHEMA & WEIGHT PROFILES
# ============================================================================

class DimensionScore(BaseModel):
    raw_score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    weighted_score: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence_source: str


class ProviderScore(BaseModel):
    provider_id: str
    total_score: float = Field(ge=0.0, le=1.0)
    task_fit: DimensionScore
    output_quality: DimensionScore
    control_customization: DimensionScore
    reliability: DimensionScore
    cost_efficiency: DimensionScore
    latency_speed: DimensionScore
    style_continuity: DimensionScore
    rejection_reasons: List[str] = Field(default_factory=list)


class ProviderSelectionResult(BaseModel):
    request_id: str
    selected_provider_id: Optional[str] = None
    selected_score: Optional[float] = None
    rankings: List[ProviderScore] = Field(default_factory=list)
    rejection_reasons: Dict[str, List[str]] = Field(default_factory=dict)
    fallback_chain: List[str] = Field(default_factory=list)
    selection_reasons: List[str] = Field(default_factory=list)
    profile: ProviderSelectionProfile
    no_provider_available: bool = False


# Configurable 7-Dimension Profile Weights (Weights MUST sum to 1.0 per profile)
PROFILE_WEIGHTS: Dict[ProviderSelectionProfile, Dict[str, float]] = {
    ProviderSelectionProfile.CINEMATIC_QUALITY: {
        "output_quality": 0.35, "task_fit": 0.25, "style_continuity": 0.20,
        "control_customization": 0.10, "reliability": 0.05, "cost_efficiency": 0.03, "latency_speed": 0.02
    },
    ProviderSelectionProfile.FAST_PREVIEW: {
        "latency_speed": 0.40, "reliability": 0.30, "cost_efficiency": 0.15,
        "task_fit": 0.10, "output_quality": 0.03, "control_customization": 0.01, "style_continuity": 0.01
    },
    ProviderSelectionProfile.LOW_COST: {
        "cost_efficiency": 0.45, "reliability": 0.25, "task_fit": 0.15,
        "latency_speed": 0.10, "output_quality": 0.03, "control_customization": 0.01, "style_continuity": 0.01
    },
    ProviderSelectionProfile.OFFLINE: {
        "reliability": 0.35, "task_fit": 0.25, "output_quality": 0.20,
        "latency_speed": 0.10, "cost_efficiency": 0.05, "control_customization": 0.03, "style_continuity": 0.02
    },
    ProviderSelectionProfile.CORPORATE: {
        "style_continuity": 0.35, "task_fit": 0.25, "output_quality": 0.20,
        "reliability": 0.10, "control_customization": 0.05, "latency_speed": 0.03, "cost_efficiency": 0.02
    },
    ProviderSelectionProfile.SOCIAL_MEDIA: {
        "task_fit": 0.35, "output_quality": 0.30, "latency_speed": 0.15,
        "cost_efficiency": 0.10, "reliability": 0.05, "control_customization": 0.03, "style_continuity": 0.02
    },
    ProviderSelectionProfile.EDUCATIONAL: {
        "task_fit": 0.40, "output_quality": 0.25, "style_continuity": 0.15,
        "reliability": 0.10, "control_customization": 0.05, "latency_speed": 0.03, "cost_efficiency": 0.02
    }
}


# Validate that profile weights sum to 1.0
for profile, weights in PROFILE_WEIGHTS.items():
    total_w = sum(weights.values())
    assert abs(total_w - 1.0) < 1e-5, f"Profile weights for {profile} must sum to 1.0, got {total_w}"


# ============================================================================
# ABSTRACT MEDIA PROVIDER CONTRACT
# ============================================================================

class MediaProvider(abc.ABC):
    """
    Abstract Base Class for all Media Generation, Stock Sourcing, and Asset Providers.
    """

    @property
    @abc.abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for the provider e.g. 'procedural_overlay', 'local_asset'."""
        pass

    @abc.abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Returns factual capabilities of the provider."""
        pass

    @abc.abstractmethod
    def readiness(self) -> ProviderHealth:
        """Returns current health and configuration readiness of provider."""
        pass

    @abc.abstractmethod
    def generate_or_retrieve(self, request: MediaRequest) -> MediaCandidate:
        """Executes generation or fetch operation and returns MediaCandidate."""
        pass

    def retrieve_candidates(self, request: MediaRequest, limit: int = 3) -> List[MediaCandidate]:
        """
        Multi-candidate retrieval interface (Upgrade 3).
        Default implementation delegates to generate_or_retrieve().
        """
        cand = self.generate_or_retrieve(request)
        return [cand] if cand else []

    def estimate_cost(self, request: MediaRequest) -> float:
        """Estimates cost in USD for servicing request (default: 0.0 for local/procedural)."""
        return 0.0

    def estimate_latency(self, request: MediaRequest) -> float:
        """Estimates latency in seconds for servicing request."""
        return 0.2

    # Backward compatibility helper
    def provider_name(self) -> str:
        return self.provider_id

    def supported_asset_types(self) -> List[str]:
        return [t.value for t in self.capabilities().media_types]


# ============================================================================
# ASSET VALIDATOR
# ============================================================================

class AssetValidator:
    """
    Measurable Media Property Validator for candidates returned by providers.
    """

    @classmethod
    def validate_candidate(cls, candidate: MediaCandidate, request: MediaRequest) -> bool:
        """
        Validates path existence, candidate status, non-empty file size, dimensions, and readability.
        """
        if candidate.candidate_status not in (MediaCandidateStatus.VALIDATED_RENDER_READY, MediaCandidateStatus.PROCEDURAL_PLACEHOLDER):
            logger.warning(f"AssetValidator: Candidate from '{candidate.provider_id}' has invalid status '{candidate.candidate_status}'.")
            return False

        if not candidate.asset_path:
            logger.warning(f"AssetValidator: Candidate from '{candidate.provider_id}' missing asset_path.")
            return False

        path = Path(candidate.asset_path)
        if not path.exists():
            logger.warning(f"AssetValidator: Asset path '{path}' does not exist.")
            return False

        if path.stat().st_size == 0:
            logger.warning(f"AssetValidator: Asset file '{path}' is empty (0 bytes).")
            return False

        # Validate image readability & dimensions if file is an image
        ext = path.suffix.lower()
        if ext in [".png", ".jpg", ".jpeg", ".webp"]:
            try:
                with Image.open(path) as img:
                    img.verify()
                with Image.open(path) as img:
                    w, h = img.size
                    candidate.width = w
                    candidate.height = h
                    if w < 100 or h < 100:
                        logger.warning(f"AssetValidator: Image dimensions ({w}x{h}) below minimum threshold.")
                        return False
            except Exception as e:
                logger.warning(f"AssetValidator: Failed to decode image '{path}': {e}")
                return False

        return True


# ============================================================================
# 7-DIMENSION PROVIDER QUALITY EVALUATOR
# ============================================================================

class ProviderQualityEvaluator:
    """
    Evaluates and ranks media providers across 7 explicit quality dimensions.
    """

    # Static baseline quality ratings (Factual metadata ratings)
    STATIC_QUALITY_RATINGS: Dict[str, float] = {
        "local_asset": 0.85,
        "uploaded_media": 0.90,
        "genblaze_image": 0.80,
        "openmontage_stock": 0.75,
        "pexels_stock": 0.82,
        "pexels_video": 0.88,
        "openverse_stock": 0.83,
        "procedural_overlay": 0.65
    }

    # Static control ratings
    STATIC_CONTROL_RATINGS: Dict[str, float] = {
        "procedural_overlay": 0.95,
        "genblaze_image": 0.85,
        "local_asset": 0.70,
        "uploaded_media": 0.60,
        "openmontage_stock": 0.50,
        "pexels_stock": 0.45,
        "pexels_video": 0.45,
        "openverse_stock": 0.50
    }

    @classmethod
    def evaluate_provider(
        cls,
        provider: MediaProvider,
        request: MediaRequest,
        profile: ProviderSelectionProfile
    ) -> tuple[ProviderScore, List[str]]:
        caps = provider.capabilities()
        health = provider.readiness()
        reasons = []

        # 1. Eligibility Checks
        if not caps.media_types.intersection(set(request.media_type_preferences)):
            reasons.append(f"Does not support preferred media types {request.media_type_preferences}")

        if request.excluded_media_types and caps.media_types.issubset(set(request.excluded_media_types)):
            reasons.append(f"Media types are in excluded list {request.excluded_media_types}")

        if request.offline_mode and not caps.supports_offline:
            reasons.append("Requires online network connection while offline_mode=True")

        if not health.available or not health.configuration_ready:
            reasons.append(f"Provider health unavailable (available={health.available}, config_ready={health.configuration_ready})")

        est_cost = provider.estimate_cost(request)
        if request.maximum_cost is not None and est_cost > request.maximum_cost:
            reasons.append(f"Estimated cost (${est_cost:.2f}) exceeds maximum budget (${request.maximum_cost:.2f})")

        est_lat = provider.estimate_latency(request)
        if request.maximum_latency_seconds is not None and est_lat > request.maximum_latency_seconds:
            reasons.append(f"Estimated latency ({est_lat:.2f}s) exceeds maximum threshold ({request.maximum_latency_seconds:.2f}s)")

        w = PROFILE_WEIGHTS[profile]

        # 2. Dimension Scores Calculation (0.0 to 1.0)
        # Task Fit
        task_fit_score = 0.95 if any(mt in caps.media_types for mt in request.media_type_preferences[:1]) else 0.60
        task_fit = DimensionScore(
            raw_score=task_fit_score, weight=w["task_fit"],
            weighted_score=round(task_fit_score * w["task_fit"], 4),
            reason=f"Matches primary media preference {request.media_type_preferences[0] if request.media_type_preferences else 'generic'}",
            evidence_source="static_capability"
        )

        # Output Quality
        base_q = cls.STATIC_QUALITY_RATINGS.get(provider.provider_id, 0.70)
        output_quality = DimensionScore(
            raw_score=base_q, weight=w["output_quality"],
            weighted_score=round(base_q * w["output_quality"], 4),
            reason=f"Baseline static visual fidelity rating ({base_q:.2f})",
            evidence_source="static_capability"
        )

        # Control & Customization
        ctrl_q = cls.STATIC_CONTROL_RATINGS.get(provider.provider_id, 0.70)
        control_customization = DimensionScore(
            raw_score=ctrl_q, weight=w["control_customization"],
            weighted_score=round(ctrl_q * w["control_customization"], 4),
            reason=f"Parameter & aspect ratio customization support ({ctrl_q:.2f})",
            evidence_source="static_capability"
        )

        # Reliability
        rel_score = max(0.0, health.rolling_success_rate - health.temporary_penalty)
        reliability = DimensionScore(
            raw_score=rel_score, weight=w["reliability"],
            weighted_score=round(rel_score * w["reliability"], 4),
            reason=f"Historical rolling success rate ({health.rolling_success_rate:.2f}) with penalty ({health.temporary_penalty:.2f})",
            evidence_source="historical_health"
        )

        # Cost Efficiency
        cost_score = 1.0 if est_cost == 0.0 else max(0.1, 1.0 - (est_cost / 1.00))
        cost_efficiency = DimensionScore(
            raw_score=cost_score, weight=w["cost_efficiency"],
            weighted_score=round(cost_score * w["cost_efficiency"], 4),
            reason=f"Zero API cost for local/procedural asset" if est_cost == 0.0 else f"Estimated API cost ${est_cost:.3f}",
            evidence_source="estimated_cost"
        )

        # Latency & Speed
        lat_score = max(0.1, min(1.0, 1.0 - (est_lat / 5.0)))
        latency_speed = DimensionScore(
            raw_score=lat_score, weight=w["latency_speed"],
            weighted_score=round(lat_score * w["latency_speed"], 4),
            reason=f"Low estimated latency ({est_lat:.2f}s)",
            evidence_source="measured_latency"
        )

        # Visual Style Continuity
        cont_score = 0.90 if request.previous_scene_provider == provider.provider_id else 0.70
        style_continuity = DimensionScore(
            raw_score=cont_score, weight=w["style_continuity"],
            weighted_score=round(cont_score * w["style_continuity"], 4),
            reason="Matches previous scene provider ID" if request.previous_scene_provider == provider.provider_id else "Standard cross-scene transition compatibility",
            evidence_source="style_metadata"
        )

        total_score = round(
            task_fit.weighted_score + output_quality.weighted_score +
            control_customization.weighted_score + reliability.weighted_score +
            cost_efficiency.weighted_score + latency_speed.weighted_score +
            style_continuity.weighted_score, 4
        )

        score_model = ProviderScore(
            provider_id=provider.provider_id,
            total_score=total_score,
            task_fit=task_fit,
            output_quality=output_quality,
            control_customization=control_customization,
            reliability=reliability,
            cost_efficiency=cost_efficiency,
            latency_speed=latency_speed,
            style_continuity=style_continuity,
            rejection_reasons=reasons
        )

        return score_model, reasons


# ============================================================================
# PROVIDER REGISTRY & DETERMINISTIC RANKER
# ============================================================================

class ProviderRegistry:
    """
    Central Provider Registry managing pluggable media providers, health penalties, and deterministic selection.
    """
    _providers: Dict[str, MediaProvider] = {}
    _health: Dict[str, ProviderHealth] = {}

    @classmethod
    def register(cls, provider: MediaProvider):
        pid = provider.provider_id
        cls._providers[pid] = provider
        if pid not in cls._health:
            cls._health[pid] = provider.readiness()
        logger.info(f"ProviderRegistry: Registered provider '{pid}'")

    @classmethod
    def unregister(cls, provider_id: str):
        if provider_id in cls._providers:
            del cls._providers[provider_id]
            logger.info(f"ProviderRegistry: Unregistered provider '{provider_id}'")

    @classmethod
    def get(cls, provider_id: str) -> MediaProvider:
        if provider_id not in cls._providers:
            raise KeyError(f"Provider '{provider_id}' not found in registry. Available: {list(cls._providers.keys())}")
        return cls._providers[provider_id]

    @classmethod
    def list_all(cls) -> List[MediaProvider]:
        return list(cls._providers.values())

    @classmethod
    def list_ready(cls) -> List[MediaProvider]:
        return [p for p in cls._providers.values() if p.readiness().available and p.readiness().configuration_ready]

    @classmethod
    def record_success(cls, provider_id: str, latency_sec: float):
        if provider_id in cls._health:
            h = cls._health[provider_id]
            h.total_requests += 1
            h.total_successes += 1
            h.consecutive_failures = 0
            h.rolling_success_rate = min(1.0, h.total_successes / float(h.total_requests))
            h.rolling_average_latency_sec = round((h.rolling_average_latency_sec * 0.8) + (latency_sec * 0.2), 3)
            h.temporary_penalty = max(0.0, h.temporary_penalty - 0.1)

    @classmethod
    def record_failure(cls, provider_id: str, error_msg: str):
        if provider_id in cls._health:
            h = cls._health[provider_id]
            h.total_requests += 1
            h.consecutive_failures += 1
            h.last_failure_timestamp = time.time()
            h.rolling_success_rate = min(1.0, h.total_successes / float(h.total_requests))
            h.temporary_penalty = min(0.5, h.temporary_penalty + 0.2)
            logger.warning(f"ProviderRegistry: Recorded failure for '{provider_id}' ({error_msg}). Penalty: {h.temporary_penalty:.2f}")

    @classmethod
    def find_eligible(cls, request: MediaRequest, profile: ProviderSelectionProfile) -> tuple[List[ProviderScore], Dict[str, List[str]]]:
        rankings = []
        rejection_reasons = {}

        for pid, provider in cls._providers.items():
            score_model, reasons = ProviderQualityEvaluator.evaluate_provider(provider, request, profile)
            if reasons:
                rejection_reasons[pid] = reasons
            else:
                rankings.append(score_model)

        # Deterministic Ranking Tie-Breaking Order:
        # 1. Total score descending
        # 2. Reliability raw score descending
        # 3. Latency raw score descending
        # 4. Provider ID alphabetical
        rankings.sort(key=lambda s: (
            -s.total_score,
            -s.reliability.raw_score,
            -s.latency_speed.raw_score,
            s.provider_id
        ))

        return rankings, rejection_reasons

    @classmethod
    def select_provider(
        cls,
        request: MediaRequest,
        profile: Optional[ProviderSelectionProfile] = None
    ) -> ProviderSelectionResult:
        prof = profile or request.quality_profile
        req_id = f"req_{hashlib.md5(f'{request.scene_id}_{request.query}'.encode()).hexdigest()[:8]}"

        rankings, rejection_reasons = cls.find_eligible(request, prof)

        if not rankings:
            return ProviderSelectionResult(
                request_id=req_id,
                selected_provider_id=None,
                selected_score=None,
                rankings=[],
                rejection_reasons=rejection_reasons,
                fallback_chain=[],
                selection_reasons=["No eligible media provider satisfied request constraints."],
                profile=prof,
                no_provider_available=True
            )

        selected = rankings[0]
        fallback_chain = [r.provider_id for r in rankings[1:]]

        sel_reasons = [
            f"Selected '{selected.provider_id}' with total score {selected.total_score:.4f} under '{prof.value}' profile.",
            f"Task fit: {selected.task_fit.reason}",
            f"Cost & latency: {selected.cost_efficiency.reason}, {selected.latency_speed.reason}"
        ]

        return ProviderSelectionResult(
            request_id=req_id,
            selected_provider_id=selected.provider_id,
            selected_score=selected.total_score,
            rankings=rankings,
            rejection_reasons=rejection_reasons,
            fallback_chain=fallback_chain,
            selection_reasons=sel_reasons,
            profile=prof,
            no_provider_available=False
        )


# Backward compatibility alias
MediaProviderRegistry = ProviderRegistry

