"""
Typed Schemas & Data Models for AI Video Critic & Self-Evaluation Engine (Upgrade 8).
Includes FindingSeverity, ReleaseVerdict, CriticFinding, QualityScorecard, RevisionRecommendationPlan, and CriticRunManifest.
"""
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field


# ============================================================================
# ENUMS
# ============================================================================

class FindingSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    BLOCKER = "blocker"


class FindingStatus(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    FALSE_POSITIVE = "false_positive"
    DEFERRED = "deferred"
    FIXED = "fixed"
    VERIFIED = "verified"


class ReleaseVerdict(str, Enum):
    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    REVISION_REQUIRED = "revision_required"
    BLOCKED = "blocked"


# ============================================================================
# CRITIC FINDING SCHEMAS
# ============================================================================

class CriticFinding(BaseModel):
    finding_id: str = Field(default_factory=lambda: f"find_{uuid.uuid4().hex[:8]}")
    critic_type: str                  # e.g., "technical", "temporal", "audio_sync", "accessibility"
    category: str
    subcategory: str
    title: str
    description: str = ""
    severity: FindingSeverity = FindingSeverity.MEDIUM
    confidence: float = 1.0           # [0.0, 1.0]
    scene_id: Optional[str] = None
    layer_id: Optional[str] = None
    time_range_sec: Optional[Tuple[float, float]] = None
    frame_range: Optional[Tuple[int, int]] = None
    evidence_ids: List[str] = Field(default_factory=list)
    expected_behavior: str = ""
    observed_behavior: str = ""
    threshold: Optional[float] = None
    score_impact: float = 0.05
    root_cause_hypothesis: str = ""
    affected_pipeline_stage: str = "compositor"
    recommended_action: str = "adjust_safe_region"
    automatic_fix_eligibility: bool = True
    status: FindingStatus = FindingStatus.OPEN


# ============================================================================
# SCORECARD SCHEMAS
# ============================================================================

class QualityScorecard(BaseModel):
    video_id: str
    narrative_quality: float = 0.90
    semantic_relevance: float = 0.92
    visual_continuity: float = 0.88
    camera_quality: float = 0.90
    motion_graphics_quality: float = 0.92
    temporal_quality: float = 0.95
    audio_quality: float = 0.94
    synchronization_quality: float = 0.90
    caption_quality: float = 0.92
    accessibility_score: float = 0.95
    technical_integrity: float = 0.98
    compliance_confidence: float = 0.96
    factual_consistency: float = 0.95
    overall_production_quality: float = 0.92
    release_verdict: ReleaseVerdict = ReleaseVerdict.READY
    blocker_count: int = 0
    warning_count: int = 0


# ============================================================================
# REVISION PLAN SCHEMAS
# ============================================================================

class RevisionRecommendation(BaseModel):
    recommendation_id: str = Field(default_factory=lambda: f"rec_{uuid.uuid4().hex[:8]}")
    related_finding_ids: List[str] = Field(default_factory=list)
    root_cause: str
    affected_stage: str               # "orchestrator", "camera", "compositor"
    action_type: str                  # "adjust_crop", "rerank_asset", "rebalance_audio"
    target_scene_id: str
    target_layer_id: Optional[str] = None
    proposed_parameter_changes: Dict[str, Any] = Field(default_factory=dict)
    expected_score_improvement: float = 0.08
    dependency_order: int = 1
    automatic_fix_eligibility: bool = True


class RevisionRecommendationPlan(BaseModel):
    video_id: str
    recommendations: List[RevisionRecommendation] = Field(default_factory=list)
    total_expected_improvement: float = 0.15
    execution_dependency_order: List[str] = Field(default_factory=list)


# ============================================================================
# MANIFEST SCHEMAS
# ============================================================================

class CriticRunManifest(BaseModel):
    run_id: str = Field(default_factory=lambda: f"crun_{uuid.uuid4().hex[:8]}")
    video_id: str
    mode: str = "production"
    findings_count: int = 0
    scorecard: QualityScorecard
    revision_plan: RevisionRecommendationPlan
    execution_time_ms: float = 45.0
