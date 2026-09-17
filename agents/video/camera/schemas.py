"""
Typed Schemas & Data Models for AI Camera Director Engine (Upgrade 6).
Includes DirectorStyleProfiles, CameraRig, CameraTrack, Shot Types, Lens Model, Composition Specs, Subject Focus, and Diagnostics.
"""
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field


# ============================================================================
# DIRECTOR STYLE PROFILES & RIG ENUMS
# ============================================================================

class DirectorStyleProfileType(str, Enum):
    DOCUMENTARY = "documentary"
    CORPORATE_PRESENTATION = "corporate_presentation"
    EDUCATIONAL = "educational"
    TECHNOLOGY_EXPLAINER = "technology_explainer"
    PRODUCT_DEMO = "product_demo"
    CINEMATIC_TRAILER = "cinematic_trailer"
    SOCIAL_REEL = "social_reel"


class ShotType(str, Enum):
    EXTREME_WIDE = "extreme_wide"
    WIDE = "wide"
    FULL = "full"
    MEDIUM = "medium"
    MEDIUM_CLOSE_UP = "medium_close_up"
    CLOSE_UP = "close_up"
    EXTREME_CLOSE_UP = "extreme_close_up"
    OVERHEAD = "overhead"
    MACRO = "macro"
    DETAIL = "detail"


class CameraMovementType(str, Enum):
    STATIC = "static"
    PAN = "pan"
    TILT = "tilt"
    DOLLY = "dolly"
    TRUCK = "truck"
    PEDESTAL = "pedestal"
    ORBIT = "orbit"
    PUSH_IN = "push_in"
    PULL_OUT = "pull_out"
    CRANE = "crane"
    HANDHELD = "handheld"
    TRACKING = "tracking"


class CompositionRule(str, Enum):
    RULE_OF_THIRDS_LEFT = "rule_of_thirds_left"
    RULE_OF_THIRDS_RIGHT = "rule_of_thirds_right"
    CENTERED = "centered"
    LEADING_LINES = "leading_lines"
    HEADROOM_BALANCED = "headroom_balanced"
    LOOK_ROOM_LEFT = "look_room_left"
    LOOK_ROOM_RIGHT = "look_room_right"
    NEGATIVE_SPACE = "negative_space"


# ============================================================================
# CAMERA RIG & LENS MODEL
# ============================================================================

class VirtualLensModel(BaseModel):
    focal_length_mm: float = 50.0        # e.g., 24mm wide to 85mm telephoto
    sensor_size_mm: Tuple[float, float] = (36.0, 24.0)  # Full-frame 35mm
    fov_degrees: float = 46.0
    perspective_strength: float = 0.50
    depth_of_field_blur: float = 0.0     # Simulated background bokeh blur
    virtual_aperture: float = 2.8


class CameraRig(BaseModel):
    rig_id: str = Field(default_factory=lambda: f"rig_{uuid.uuid4().hex[:8]}")
    virtual_sensor: str = "full_frame_35mm"
    focal_length_mm: float = 50.0
    fov_degrees: float = 46.0
    stabilization_mode: str = "gimbal_3axis"  # "gimbal_3axis", "handheld", "tripod_locked"
    exposure_profile: str = "cinematic_flat"
    motion_constraints: Dict[str, float] = Field(default_factory=lambda: {"max_pan_deg_sec": 15.0, "max_zoom_scale_sec": 1.20})
    depth_of_field_settings: Dict[str, Any] = Field(default_factory=lambda: {"enabled": False, "aperture": 2.8, "focus_dist_m": 3.0})


class DirectorStyleProfile(BaseModel):
    profile_type: DirectorStyleProfileType = DirectorStyleProfileType.TECHNOLOGY_EXPLAINER
    pacing_multiplier: float = 1.0
    preferred_shot_duration_sec: float = 3.0
    framing_preference: ShotType = ShotType.MEDIUM
    movement_intensity: float = 0.50
    lens_preference_mm: float = 50.0
    composition_preference: CompositionRule = CompositionRule.CENTERED
    transition_aggressiveness: float = 0.40

    @classmethod
    def create_profile(cls, ptype: DirectorStyleProfileType) -> "DirectorStyleProfile":
        if ptype == DirectorStyleProfileType.DOCUMENTARY:
            return cls(profile_type=ptype, pacing_multiplier=0.85, preferred_shot_duration_sec=4.0, framing_preference=ShotType.WIDE, movement_intensity=0.30, lens_preference_mm=35.0, composition_preference=CompositionRule.RULE_OF_THIRDS_LEFT)
        elif ptype == DirectorStyleProfileType.CINEMATIC_TRAILER:
            return cls(profile_type=ptype, pacing_multiplier=1.50, preferred_shot_duration_sec=1.8, framing_preference=ShotType.CLOSE_UP, movement_intensity=0.85, lens_preference_mm=85.0, composition_preference=CompositionRule.CENTERED)
        elif ptype == DirectorStyleProfileType.CORPORATE_PRESENTATION:
            return cls(profile_type=ptype, pacing_multiplier=1.00, preferred_shot_duration_sec=3.0, framing_preference=ShotType.MEDIUM, movement_intensity=0.40, lens_preference_mm=50.0, composition_preference=CompositionRule.CENTERED)
        elif ptype == DirectorStyleProfileType.EDUCATIONAL:
            return cls(profile_type=ptype, pacing_multiplier=0.90, preferred_shot_duration_sec=3.5, framing_preference=ShotType.MEDIUM, movement_intensity=0.35, lens_preference_mm=50.0, composition_preference=CompositionRule.RULE_OF_THIRDS_RIGHT)
        return cls(profile_type=ptype)


# ============================================================================
# COMPOSITION & SUBJECT MODEL
# ============================================================================

class CompositionSpec(BaseModel):
    rule: CompositionRule = CompositionRule.CENTERED
    pivot_x_frac: float = 0.50           # Center pivot [0, 1]
    pivot_y_frac: float = 0.50
    headroom_frac: float = 0.15
    look_room_frac: float = 0.20


class SubjectFocus(BaseModel):
    primary_subject: str = "main_visual"
    secondary_subjects: List[str] = Field(default_factory=list)
    attention_weights: Dict[str, float] = Field(default_factory=lambda: {"main_visual": 1.0})
    safe_region_bbox: Tuple[float, float, float, float] = (0.1, 0.1, 0.9, 0.9)
    framing_priority: int = 1


class CameraConstraints(BaseModel):
    max_pan_speed_deg_sec: float = 20.0
    max_zoom_speed_scale_sec: float = 1.15
    max_rotation_deg_sec: float = 5.0
    max_acceleration: float = 1.50
    min_shot_duration_sec: float = 1.0
    smoothing_factor: float = 0.85


# ============================================================================
# KEYFRAME & TRACK SCHEMAS
# ============================================================================

class CameraKeyframe(BaseModel):
    timestamp_sec: float
    shot_type: ShotType = ShotType.MEDIUM
    scale_zoom: float = 1.0
    pan_offset_x_frac: float = 0.0       # Resolution-relative pan shift [-0.2, 0.2]
    pan_offset_y_frac: float = 0.0
    rotation_deg: float = 0.0
    lens: VirtualLensModel = Field(default_factory=VirtualLensModel)
    composition: CompositionSpec = Field(default_factory=CompositionSpec)
    easing: str = "ease_in_out_cubic"


class CameraTrack(BaseModel):
    """Immutable sequence of planned camera keyframes directing a single scene."""
    scene_id: str
    movement_type: CameraMovementType = CameraMovementType.PUSH_IN
    rig: CameraRig = Field(default_factory=CameraRig)
    keyframes: List[CameraKeyframe] = Field(default_factory=list)
    subject_focus: SubjectFocus = Field(default_factory=SubjectFocus)
    constraints: CameraConstraints = Field(default_factory=CameraConstraints)
    motion_speed_deg_per_sec: float = 2.0
    shake_intensity: float = 0.0
    diagnostics: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        frozen = True  # Immutable per scene


# ============================================================================
# DIAGNOSTICS & STATISTICS
# ============================================================================

class CameraStatistics(BaseModel):
    average_shot_duration_sec: float = 3.0
    shot_diversity_score: float = 0.85
    movement_diversity_score: float = 0.80
    total_pan_distance_frac: float = 0.15
    total_zoom_distance_scale: float = 1.10
    composition_variance: float = 0.20
    pacing_variance: float = 0.15


class CameraDiagnosticReport(BaseModel):
    video_id: str
    overall_director_score: float = 0.85
    framing_score: float = 0.88
    movement_score: float = 0.85
    pacing_score: float = 0.82
    composition_score: float = 0.90
    continuity_score: float = 0.88
    emotion_score: float = 0.85
    stats: CameraStatistics = Field(default_factory=CameraStatistics)
    scene_camera_breakdown: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
