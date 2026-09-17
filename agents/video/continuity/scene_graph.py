"""
SceneGraph Representation for CraftAI Video Generation (Upgrade 4).
Structures scene components into a unified declarative scene graph for rendering.
"""
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
from agents.video.continuity.engine_schemas import CameraFraming, CameraMotionVector, SceneContinuityContext


class BackgroundNode(BaseModel):
    bg_type: str = "gradient"  # "gradient", "solid", "image", "pattern"
    colors: List[str] = Field(default_factory=lambda: ["#0F172A", "#1E293B"])
    angle_deg: float = 135.0


class MediaNode(BaseModel):
    asset_path: Optional[str] = None
    remote_url: Optional[str] = None
    provider_id: str = "procedural"
    media_type: str = "stock_image"
    opacity: float = 1.0
    aspect_ratio: str = "16:9"
    attribution: Optional[str] = None


class ChartNode(BaseModel):
    chart_type: Optional[str] = None  # "bar", "line", "pie"
    title: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    data: List[float] = Field(default_factory=list)
    palette_colors: List[str] = Field(default_factory=lambda: ["#38BDF8", "#818CF8"])
    font_family: str = "Inter"


class OverlayNode(BaseModel):
    overlay_type: Optional[str] = None  # "grid", "vignette", "particle"
    color: str = "#000000"
    opacity: float = 0.20


class CaptionNode(BaseModel):
    text: str = ""
    start_sec: float = 0.0
    duration_sec: float = 2.0
    highlight_color: str = "#FACC15"
    font_family: str = "Inter"
    font_size: int = 36


class TitleNode(BaseModel):
    title_text: Optional[str] = None
    subtitle_text: Optional[str] = None
    position: str = "center"  # "center", "lower_third", "top"
    font_family: str = "Inter"
    primary_color: str = "#FFFFFF"


class CameraMotionNode(BaseModel):
    framing: CameraFraming = CameraFraming.WIDE
    motion_vector: CameraMotionVector = CameraMotionVector.PUSH_IN
    pan_speed: float = 1.0
    zoom_scale: float = 1.10


class TransitionNode(BaseModel):
    transition_type: str = "fade"
    duration_sec: float = 0.50
    overlap_mult: float = 1.0


class SceneGraphNode(BaseModel):
    scene_id: str
    scene_title: str
    duration_sec: float
    fps: int = 30
    width: int = 1920
    height: int = 1080

    background: BackgroundNode = Field(default_factory=BackgroundNode)
    media: Optional[MediaNode] = None
    chart: Optional[ChartNode] = None
    overlay: Optional[OverlayNode] = None
    captions: List[CaptionNode] = Field(default_factory=list)
    title: Optional[TitleNode] = None
    camera: CameraMotionNode = Field(default_factory=CameraMotionNode)
    transition: TransitionNode = Field(default_factory=TransitionNode)

    continuity_context: Optional[SceneContinuityContext] = None
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class VideoSceneGraph(BaseModel):
    """Whole-video SceneGraph structure holding ordered SceneGraphNodes."""
    video_id: str
    title: str
    aspect_ratio: str = "16:9"
    resolution: Tuple[int, int] = (1920, 1080)
    total_duration_sec: float = 0.0
    scenes: List[SceneGraphNode] = Field(default_factory=list)
