"""
Typed Declarative Schemas for Professional Multi-Layer Compositor (Upgrade 5).
Includes 10 Layer Types, Keyframe Engine, Effect System, Mask Engine, and Hierarchical SceneGraph.
"""
import uuid
import math
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Union
from pydantic import BaseModel, Field


# ============================================================================
# METADATA & ENUMS
# ============================================================================

class CompositorVersion(str, Enum):
    GRAPH_VERSION = "2.0.0"
    SCHEMA_VERSION = "5.0.0"
    CREATED_BY = "CraftAI Professional Compositor"
    UPGRADE_VERSION = "Upgrade 5"


class BlendMode(str, Enum):
    NORMAL = "normal"
    MULTIPLY = "multiply"
    SCREEN = "screen"
    OVERLAY = "overlay"
    ADD = "add"


class MaskType(str, Enum):
    RECTANGLE = "rectangle"
    ROUNDED_RECTANGLE = "rounded_rectangle"
    CIRCLE = "circle"
    ALPHA_MATTE = "alpha_matte"
    CLIPPING_PATH = "clipping_path"


class EasingType(str, Enum):
    LINEAR = "linear"
    EASE_IN_QUAD = "ease_in_quad"
    EASE_OUT_QUAD = "ease_out_quad"
    EASE_IN_OUT_CUBIC = "ease_in_out_cubic"
    SPRING_BOUNCE = "spring_bounce"


# ============================================================================
# KEYFRAME & ANIMATION SYSTEM
# ============================================================================

class KeyframeValue(BaseModel):
    """Multi-type keyframe value supporting float, vec2, vec3, color, opacity, scale, rotation."""
    float_val: Optional[float] = None
    vec2_val: Optional[Tuple[float, float]] = None
    vec3_val: Optional[Tuple[float, float, float]] = None
    color_hex: Optional[str] = None


class Keyframe(BaseModel):
    timestamp_sec: float
    property_name: str  # "position", "scale", "rotation", "opacity", "blur", "color"
    value: KeyframeValue
    easing: EasingType = EasingType.EASE_IN_OUT_CUBIC


class AnimationTrack(BaseModel):
    track_id: str = Field(default_factory=lambda: f"track_{uuid.uuid4().hex[:8]}")
    target_property: str  # "transform", "opacity", "color", "scale", "rotation", "blur", "camera"
    keyframes: List[Keyframe] = Field(default_factory=list)


# ============================================================================
# TYPED EFFECTS SYSTEM
# ============================================================================

class BaseEffect(BaseModel):
    effect_id: str = Field(default_factory=lambda: f"fx_{uuid.uuid4().hex[:8]}")
    effect_type: str
    enabled: bool = True


class BlurEffect(BaseEffect):
    effect_type: str = "blur"
    radius_px: float = 5.0


class ShadowEffect(BaseEffect):
    effect_type: str = "shadow"
    offset_x: float = 4.0
    offset_y: float = 4.0
    blur_radius: float = 8.0
    color_hex: str = "#000000"
    opacity: float = 0.50


class GlowEffect(BaseEffect):
    effect_type: str = "glow"
    radius_px: float = 12.0
    color_hex: str = "#38BDF8"
    intensity: float = 0.80


class ColorGradeEffect(BaseEffect):
    effect_type: str = "color_grade"
    temperature_k: float = 5500.0
    tint: float = 0.0


class BrightnessEffect(BaseEffect):
    effect_type: str = "brightness"
    delta: float = 0.0  # -1.0 to 1.0


class ContrastEffect(BaseEffect):
    effect_type: str = "contrast"
    factor: float = 1.0  # 0.0 to 2.0


class TintEffect(BaseEffect):
    effect_type: str = "tint"
    color_hex: str = "#38BDF8"
    mix_opacity: float = 0.30


class SharpenEffect(BaseEffect):
    effect_type: str = "sharpen"
    strength: float = 0.50


class VignetteEffect(BaseEffect):
    effect_type: str = "vignette"
    strength: float = 0.30
    radius: float = 0.80


TypedEffect = Union[
    BlurEffect, ShadowEffect, GlowEffect, ColorGradeEffect, BrightnessEffect,
    ContrastEffect, TintEffect, SharpenEffect, VignetteEffect
]


# ============================================================================
# MASK SYSTEM
# ============================================================================

class LayerMask(BaseModel):
    mask_id: str = Field(default_factory=lambda: f"mask_{uuid.uuid4().hex[:8]}")
    mask_type: MaskType = MaskType.RECTANGLE
    corner_radius: float = 0.0
    feather_px: float = 0.0
    invert: bool = False
    asset_path: Optional[str] = None


# ============================================================================
# 10 DECLARATIVE LAYER SCHEMAS
# ============================================================================

class Transform2D(BaseModel):
    position_x: float = 0.50  # Normalized [0, 1] relative to width
    position_y: float = 0.50  # Normalized [0, 1] relative to height
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation_deg: float = 0.0
    anchor_x: float = 0.50    # Pivot point [0, 1]
    anchor_y: float = 0.50


class BaseCompositorLayer(BaseModel):
    node_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    layer_id: str
    layer_name: str
    layer_type: str
    z_index: int = 0
    start_sec: float = 0.0
    end_sec: float = 999.0
    opacity: float = 1.0
    transform: Transform2D = Field(default_factory=Transform2D)
    crop_bounds: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    visible: bool = True
    blend_mode: BlendMode = BlendMode.NORMAL
    mask: Optional[LayerMask] = None
    effects: List[Any] = Field(default_factory=list)
    animation_tracks: List[AnimationTrack] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class BackgroundLayer(BaseCompositorLayer):
    layer_type: str = "background"
    fill_style: str = "gradient"  # "solid", "gradient", "pattern", "noise"
    colors: List[str] = Field(default_factory=lambda: ["#0F172A", "#1E293B"])


class VideoLayer(BaseCompositorLayer):
    layer_type: str = "video"
    asset_path: str
    clip_start_sec: float = 0.0
    playback_rate: float = 1.0
    volume: float = 1.0


class ImageLayer(BaseCompositorLayer):
    layer_type: str = "image"
    asset_path: str
    aspect_mode: str = "cover"  # "cover", "contain", "stretch"


class ChartLayer(BaseCompositorLayer):
    layer_type: str = "chart"
    chart_type: str = "bar_chart"  # "bar_chart", "line_chart", "pie_chart"
    title: str = ""
    labels: List[str] = Field(default_factory=list)
    data: List[float] = Field(default_factory=list)
    palette_colors: List[str] = Field(default_factory=list)


class CaptionLayer(BaseCompositorLayer):
    layer_type: str = "caption"
    text: str = ""
    highlight_color: str = "#FACC15"
    font_family: str = "Inter"
    font_size: int = 36


class OverlayLayer(BaseCompositorLayer):
    layer_type: str = "overlay"
    overlay_kind: str = "particles"  # "particles", "grid", "vignette"


class LogoLayer(BaseCompositorLayer):
    layer_type: str = "logo"
    asset_path: str


class LowerThirdLayer(BaseCompositorLayer):
    layer_type: str = "lower_third"
    name_text: str = ""
    title_text: str = ""
    accent_color: str = "#38BDF8"


class ShapeLayer(BaseCompositorLayer):
    layer_type: str = "shape"
    shape_type: str = "rectangle"  # "rectangle", "ellipse"
    fill_color: str = "#38BDF8"
    stroke_color: str = "#FFFFFF"
    stroke_width: float = 2.0


class TitleLayer(BaseCompositorLayer):
    layer_type: str = "title"
    title_text: str = ""
    subtitle_text: Optional[str] = None
    font_family: str = "Inter"
    primary_color: str = "#FFFFFF"


# ============================================================================
# HIERARCHICAL SCENEGRAPH SCHEMAS
# ============================================================================

class LayerGroupNode(BaseModel):
    group_id: str
    group_name: str
    z_index_base: int = 0
    layers: List[Any] = Field(default_factory=list)


class DeclarativeSceneNode(BaseModel):
    node_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    graph_version: str = CompositorVersion.GRAPH_VERSION.value
    schema_version: str = CompositorVersion.SCHEMA_VERSION.value
    created_by: str = CompositorVersion.CREATED_BY.value
    upgrade_version: str = CompositorVersion.UPGRADE_VERSION.value

    scene_id: str
    scene_title: str
    duration_sec: float
    fps: int = 30
    width: int = 1920
    height: int = 1080

    background_group: LayerGroupNode = Field(default_factory=lambda: LayerGroupNode(group_id="bg_group", group_name="BackgroundGroup", z_index_base=0))
    media_group: LayerGroupNode = Field(default_factory=lambda: LayerGroupNode(group_id="media_group", group_name="MediaGroup", z_index_base=10))
    graphics_group: LayerGroupNode = Field(default_factory=lambda: LayerGroupNode(group_id="gfx_group", group_name="GraphicsGroup", z_index_base=20))
    text_group: LayerGroupNode = Field(default_factory=lambda: LayerGroupNode(group_id="text_group", group_name="TextGroup", z_index_base=30))
    overlay_group: LayerGroupNode = Field(default_factory=lambda: LayerGroupNode(group_id="overlay_group", group_name="OverlayGroup", z_index_base=40))
    camera_track: Optional[Any] = None

    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class MasterSceneGraph(BaseModel):
    node_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    graph_version: str = CompositorVersion.GRAPH_VERSION.value
    schema_version: str = CompositorVersion.SCHEMA_VERSION.value
    created_by: str = CompositorVersion.CREATED_BY.value
    upgrade_version: str = CompositorVersion.UPGRADE_VERSION.value

    project_title: str
    resolution: Tuple[int, int] = (1920, 1080)
    fps: int = 30
    scenes: List[DeclarativeSceneNode] = Field(default_factory=list)


# ============================================================================
# DIAGNOSTICS SCHEMAS
# ============================================================================

class FrameRenderStatistics(BaseModel):
    frame_index: int
    scene_id: str
    render_latency_ms: float
    cache_hits: int = 0
    cache_misses: int = 0
    layers_rendered: int = 0
    effects_rendered: int = 0
    blend_operations: int = 0
    memory_usage_mb: float = 0.0
    warnings: List[str] = Field(default_factory=list)


class CompositorDiagnosticReport(BaseModel):
    video_id: str
    total_frames_rendered: int
    average_fps: float
    total_cache_hits: int
    total_cache_misses: int
    invisible_layer_count: int = 0
    out_of_bounds_count: int = 0
    missing_asset_count: int = 0
    scene_render_stats: List[FrameRenderStatistics] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
