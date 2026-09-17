"""
Typed Schemas for Editable Project Manifest & Audit Trail.
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field
from agents.video.orchestration.schemas import (
    VideoGenerationRequest,
    DirectorBrief,
    Screenplay,
    ProductionPlan,
    PlanningValidationIssue
)
from agents.video.continuity.schemas import (
    VisualStyleAnchor,
    SceneContinuitySpec,
    VisualContinuityReport,
    StyleFingerprint
)
from agents.video.providers.base import (
    MediaCandidateStatus,
    MediaType,
    ProviderSelectionResult
)


class ProjectLifecycleStatus(str, Enum):
    PLANNED = "planned"
    ASSETS_RESOLVED = "assets_resolved"
    AUDIO_GENERATED = "audio_generated"
    TIMELINE_READY = "timeline_ready"
    RENDERED = "rendered"
    VALIDATED = "validated"
    FAILED = "failed"


class DependencyStatus(str, Enum):
    UNCHANGED = "unchanged"
    RECOMPUTED = "recomputed"
    INVALIDATED = "invalidated"
    PENDING = "pending"


class ProjectChangeOperation(str, Enum):
    PROJECT_CREATED = "project_created"
    SCENE_UPDATED = "scene_updated"
    SCENE_REGENERATED = "scene_regenerated"
    ASSET_REPLACED = "asset_replaced"
    NARRATION_UPDATED = "narration_updated"
    TRANSITION_UPDATED = "transition_updated"
    STYLE_ANCHOR_UPDATED = "style_anchor_updated"
    TIMELINE_REBUILT = "timeline_rebuilt"
    RENDER_COMPLETED = "render_completed"


class ProjectChangeRecord(BaseModel):
    change_id: str
    timestamp: str
    operation: ProjectChangeOperation
    target_type: str  # "scene", "asset", "manifest"
    target_id: str
    changed_fields: List[str]
    reason: Optional[str] = None
    previous_checksum: Optional[str] = None
    new_checksum: Optional[str] = None


class ProjectAsset(BaseModel):
    asset_id: str
    logical_role: str
    scene_ids: List[str]
    provider_id: str
    generation_method: str
    candidate_status: MediaCandidateStatus
    media_type: MediaType
    path_kind: str = "project_relative"  # "project_relative", "external_local", "remote"
    original_source: Optional[str] = None
    discovered_remote_url: Optional[str] = None
    local_path: Optional[str] = None
    checksum_sha256: Optional[str] = None
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    license_name: Optional[str] = None
    attribution: Optional[str] = None
    style_fingerprint: Optional[StyleFingerprint] = None
    validation_status: str = "VALID"
    placeholder: bool = False
    warnings: List[str] = Field(default_factory=list)


class ProjectAudioAsset(BaseModel):
    audio_id: str
    audio_type: str  # "narration", "music", "sfx"
    local_path: str
    duration_seconds: float


class ProjectSubtitleAsset(BaseModel):
    subtitle_id: str
    local_path: str
    language: str


class TimelineClip(BaseModel):
    clip_id: str
    scene_id: str
    asset_id: str
    track_type: str  # "video", "image", "overlay", "narration", "music", "subtitle"
    start_time: float
    end_time: float
    source_in: float = 0.0
    source_out: float
    transition_in: str = "fade"
    transition_out: str = "fade"
    transform: Dict[str, Any] = Field(default_factory=dict)
    opacity: float = 1.0
    volume: float = 1.0
    locked: bool = False


class ProjectTimeline(BaseModel):
    duration_seconds: float
    frame_rate: float = 30.0
    width: int = 1920
    height: int = 1080
    aspect_ratio: str = "16:9"
    tracks: List[List[TimelineClip]] = Field(default_factory=list)


class RenderOutputRecord(BaseModel):
    render_id: str
    output_path: str
    rendered_at: str
    duration_seconds: float
    file_size_bytes: int
    resolution: str


class ProjectValidationReport(BaseModel):
    passed: bool
    issues: List[PlanningValidationIssue] = Field(default_factory=list)


class EditableVideoProjectManifest(BaseModel):
    schema_name: str = "videoagent_project"
    schema_version: str = "1.0.0"
    project_id: str
    lifecycle_status: ProjectLifecycleStatus = ProjectLifecycleStatus.PLANNED
    project_root: Optional[str] = None
    created_at: str
    updated_at: str
    pipeline_version: str = "v4.0.0"

    request: VideoGenerationRequest
    director_brief: DirectorBrief
    screenplay: Screenplay
    production_plan: ProductionPlan

    visual_style_anchor: VisualStyleAnchor
    scene_continuity_specs: List[SceneContinuitySpec]
    continuity_report: VisualContinuityReport

    assets: List[ProjectAsset] = Field(default_factory=list)
    audio_assets: List[ProjectAudioAsset] = Field(default_factory=list)
    subtitle_assets: List[ProjectSubtitleAsset] = Field(default_factory=list)

    provider_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    beat_analysis: Optional[Dict[str, Any]] = None
    timeline: ProjectTimeline
    render_outputs: List[RenderOutputRecord] = Field(default_factory=list)

    validation_report: ProjectValidationReport
    warnings: List[str] = Field(default_factory=list)
    change_history: List[ProjectChangeRecord] = Field(default_factory=list)
    manifest_checksum: Optional[str] = None
