"""
Typed Schemas for VideoAgent Orchestration (Director, Screenwriter, Producer).
"""
from enum import Enum
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field, validator
from agents.video.providers.base import ProviderSelectionProfile, MediaType, ProviderSelectionResult


_PROMPT_COMMAND_PREFIXES = [
    "generate a", "generate an", "generate", "create a", "create an", "create",
    "make a", "make an", "make", "produce a", "produce an", "produce",
    "build a", "build an", "build", "write a", "write an", "write",
    "design a", "design an", "design", "craft a", "craft an", "craft",
]


def extract_topic_phrase(prompt: str) -> str:
    """
    Strips a leading imperative command verb (e.g. "Generate a", "Create an") from a
    raw user prompt so the remainder reads as a topic noun phrase when spliced into
    narration sentence templates like "Discover how {topic} transforms outcomes."

    Without this, a prompt like "Generate a professional explainer video..." (an
    instruction TO the AI, not a description of the video's subject) gets spoken
    verbatim as "Discover how Generate a professional explainer transforms
    outcomes" -- grammatically broken narration that Edge-TTS reads aloud exactly
    as written, which is what actually made the voiceover sound bad.
    """
    if not prompt:
        return prompt
    stripped = prompt.strip()
    lower = stripped.lower()
    for prefix in _PROMPT_COMMAND_PREFIXES:
        if lower.startswith(prefix + " "):
            return stripped[len(prefix):].strip()
    return stripped


def safe_word_truncate(text: str, max_len: int, suffix: str = "") -> str:
    """
    Truncates text to at most max_len characters WITHOUT cutting a word in half.
    Used whenever raw prompt/title text is spliced into spoken narration or on-screen
    text -- a plain text[:max_len] slice can land mid-word (e.g. "...explainer v"),
    which Edge-TTS then reads aloud verbatim, producing broken-sounding speech.
    """
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.rstrip(",.;:-") + suffix


# ============================================================================
# SHARED REQUEST SCHEMAS
# ============================================================================

class BrandConstraints(BaseModel):
    brand_name: str
    primary_color: str = "#0F172A"
    secondary_color: str = "#38BDF8"
    font_family: str = "Inter"
    logo_path: Optional[str] = None


class SuppliedAsset(BaseModel):
    asset_id: str
    file_path: str
    asset_type: MediaType
    description: str = ""


class ProviderSummary(BaseModel):
    provider_id: str
    supported_media_types: List[str]
    is_offline: bool
    requires_api_key: bool


class PlanningExecutionMode(str, Enum):
    DETERMINISTIC = "deterministic"
    STRUCTURED_MODEL = "structured_model"
    AUTO = "auto"


class VideoGenerationRequest(BaseModel):
    prompt: str
    title: Optional[str] = None
    language: str = "en"
    target_audience: Optional[str] = "General Audience"
    objective: Optional[str] = "Inform and Engage"
    tone: Optional[str] = "Professional"
    target_duration_seconds: float = 30.0
    aspect_ratio: str = "16:9"
    resolution_width: int = 1920
    resolution_height: int = 1080
    quality_profile: ProviderSelectionProfile = ProviderSelectionProfile.CINEMATIC_QUALITY
    maximum_cost: Optional[float] = None
    maximum_latency_seconds: Optional[float] = None
    voice_preference: Optional[str] = None
    music_preference: Optional[str] = None
    execution_mode: PlanningExecutionMode = PlanningExecutionMode.DETERMINISTIC
    brand_constraints: Optional[BrandConstraints] = None
    supplied_assets: List[SuppliedAsset] = Field(default_factory=list)
    prohibited_content: List[str] = Field(default_factory=list)
    additional_instructions: List[str] = Field(default_factory=list)

    @validator('prompt')
    def non_empty_prompt(cls, v):
        if not v or not v.strip():
            raise ValueError("Video request prompt cannot be empty.")
        return v


# ============================================================================
# DIRECTOR STAGE SCHEMAS
# ============================================================================

class NarrativeStructure(str, Enum):
    PROBLEM_SOLUTION = "PROBLEM_SOLUTION"
    HOOK_EXPLAIN_PROVE_ACT = "HOOK_EXPLAIN_PROVE_ACT"
    CHRONOLOGICAL = "CHRONOLOGICAL"
    TUTORIAL = "TUTORIAL"
    PRODUCT_DEMO = "PRODUCT_DEMO"
    DATA_STORY = "DATA_STORY"
    BEFORE_AFTER = "BEFORE_AFTER"
    QUESTION_ANSWER = "QUESTION_ANSWER"


class EmotionalBeat(BaseModel):
    timestamp_frac: float
    emotion: str
    intensity: float = Field(ge=0.0, le=1.0)


class PacingStrategy(BaseModel):
    average_scene_duration_sec: float
    rhythm_style: str  # "fast_paced", "moderate", "deliberate"


class GlobalVisualDirection(BaseModel):
    color_palette: List[str] = Field(default_factory=lambda: ["#0F172A", "#38BDF8"])
    composition_style: str = "clean_modern"


class AudioDirection(BaseModel):
    music_genre: str = "ambient_tech"
    voice_tone: str = "confident"


class DirectorInput(BaseModel):
    request: VideoGenerationRequest
    available_provider_summary: List[ProviderSummary]


class DirectorSceneBeat(BaseModel):
    """
    One beat of the narrative arc, authored by the AI Director (Phase 1).
    Gives the Screenwriter a concrete purpose + message per scene instead of
    leaving it to infer the whole structure from the prompt alone.
    """
    scene_number: int
    purpose: str = "body"            # hook | problem | solution | proof | cta
    mood: str = "neutral"
    key_message: str = ""
    target_duration: float = 6.0
    visual_strategy: str = "stock_video"   # stock_video | user_upload | motion_graphic
    uploaded_file_ref: Optional[str] = None


class DirectorBrief(BaseModel):
    project_title: str
    objective: str
    target_audience: str
    core_message: str
    narrative_structure: NarrativeStructure
    tone: str
    emotional_progression: List[EmotionalBeat]
    opening_hook: str
    closing_message: str
    call_to_action: Optional[str] = None
    pacing_strategy: PacingStrategy
    total_duration_seconds: float
    recommended_scene_count: int
    scene_duration_budget: List[float]
    global_visual_direction: GlobalVisualDirection
    audio_direction: AudioDirection
    prohibited_patterns: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    # Per-scene narrative arc from the AI Director. Empty when the deterministic
    # planner produced the brief; the Screenwriter then falls back to generic roles.
    scene_plan: List[DirectorSceneBeat] = Field(default_factory=list)


# ============================================================================
# SCREENWRITER STAGE SCHEMAS
# ============================================================================

class OnScreenText(BaseModel):
    text: str
    position: str = "center"
    entrance_animation: str = "typewriter"


class TransitionIntent(BaseModel):
    style: str = "fade"
    duration_sec: float = 0.5


class AssetRole(BaseModel):
    role_name: str
    preferred_media_type: MediaType


class ClaimReference(BaseModel):
    claim_text: str
    source: str = "user_prompt"


class ScreenplayScene(BaseModel):
    scene_index: int
    scene_id: str
    scene_objective: str
    narrative_role: str
    narration: str
    on_screen_text: List[OnScreenText] = Field(default_factory=list)
    visual_description: str
    shot_description: str
    emotional_beat: str
    estimated_narration_duration: float
    target_scene_duration: float
    transition_intent: TransitionIntent = Field(default_factory=TransitionIntent)
    required_asset_roles: List[AssetRole] = Field(default_factory=list)
    continuity_references: List[str] = Field(default_factory=list)
    facts_or_claims: List[ClaimReference] = Field(default_factory=list)
    prohibited_repetition: List[str] = Field(default_factory=list)
    visual_overlay: Optional[Any] = None
    # Provider-ready search terms authored by the AI screenwriter (Phase 2). Empty for
    # deterministically-generated scenes, where VisualQueryGenerator derives queries instead.
    stock_search_queries: List[str] = Field(default_factory=list)
    on_screen_stats: List[str] = Field(default_factory=list)


class ScreenwriterInput(BaseModel):
    request: VideoGenerationRequest
    director_brief: DirectorBrief


class Screenplay(BaseModel):
    title: str
    language: str
    scenes: List[ScreenplayScene]
    total_narration_duration: float
    total_scene_duration: float
    repeated_terms: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)


# ============================================================================
# PRODUCER STAGE SCHEMAS
# ============================================================================

class TransitionType(str, Enum):
    CUT = "cut"
    FADE = "fade"
    CROSSFADE = "crossfade"
    SLIDE = "slide"


class CameraMovement(str, Enum):
    STATIC = "static"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    KEN_BURNS = "ken_burns"


class MotionTreatment(BaseModel):
    movement_type: CameraMovement = CameraMovement.STATIC
    intensity: float = 0.5


class VoiceConfiguration(BaseModel):
    voice_id: str = "en-US-JennyNeural"
    speaking_rate: float = 1.0


class MusicBehavior(BaseModel):
    track_genre: str = "ambient"
    volume: float = 0.2


class SoundEffectCue(BaseModel):
    cue_name: str
    timestamp_sec: float


class SubtitleConfiguration(BaseModel):
    enabled: bool = True
    font_scale: float = 1.0


class SceneRenderConfiguration(BaseModel):
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 30


class ProductionValidationRule(BaseModel):
    rule_name: str
    status: str = "PASSED"


class ProductionScene(BaseModel):
    scene_index: int
    scene_id: str
    media_request: Any  # MediaRequest instance
    preferred_media_types: List[MediaType]
    provider_selection: Optional[ProviderSelectionResult] = None
    asset_prompt: str
    fallback_asset_strategy: List[str] = Field(default_factory=list)
    camera_movement: CameraMovement = CameraMovement.STATIC
    motion_treatment: MotionTreatment = Field(default_factory=MotionTreatment)
    transition: TransitionType = TransitionType.FADE
    voice_configuration: VoiceConfiguration = Field(default_factory=VoiceConfiguration)
    music_behavior: MusicBehavior = Field(default_factory=MusicBehavior)
    sound_effects: List[SoundEffectCue] = Field(default_factory=list)
    subtitle_configuration: SubtitleConfiguration = Field(default_factory=SubtitleConfiguration)
    render_configuration: SceneRenderConfiguration = Field(default_factory=SceneRenderConfiguration)
    color_palette: List[str] = Field(default_factory=list)
    expected_cost: float = 0.0
    expected_latency_seconds: float = 0.2
    validation_rules: List[ProductionValidationRule] = Field(default_factory=list)
    visual_overlay: Optional[Any] = None


class ProducerInput(BaseModel):
    request: VideoGenerationRequest
    director_brief: DirectorBrief
    screenplay: Screenplay
    provider_registry_summary: List[ProviderSummary]


class ProductionPlan(BaseModel):
    project_id: str
    scenes: List[ProductionScene]
    estimated_total_cost: float
    estimated_generation_latency: float
    expected_render_duration: float
    provider_usage_summary: Dict[str, int] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    editing_blueprint: Optional[Any] = None
    visual_anchor: Optional[Any] = None

    def apply_blueprint(self, blueprint: Any):
        """Attaches Retention Editing Blueprint to the Production Plan."""
        self.editing_blueprint = blueprint
        if hasattr(blueprint, "pattern_interrupts"):
            for interrupt in blueprint.pattern_interrupts:
                target_scene_id = interrupt.parameters.get("scene_id")
                if target_scene_id:
                    for scene in self.scenes:
                        if scene.scene_id == target_scene_id and interrupt.interrupt_type == "zoom_in":
                            zoom_val = float(interrupt.parameters.get("zoom_factor", 1.15))
                            scene.motion_treatment = MotionTreatment(
                                movement_type=CameraMovement.ZOOM_IN,
                                intensity=zoom_val
                            )

    def apply_visual_anchor(self, anchor: Any):
        """Attaches VisualStyleAnchor and updates scene style treatments for cross-scene consistency."""
        self.visual_anchor = anchor
        if hasattr(anchor, "palette") and anchor.palette:
            bg_hex = getattr(anchor.palette, "background_color", "#0F172A")
            for scene in self.scenes:
                scene.color_palette = [bg_hex]


# Shared Planning Limits Configuration
class VideoPlanningLimits(BaseModel):
    min_scene_count: int = 3
    max_scene_count: int = 10
    min_scene_duration_seconds: float = 1.0
    max_scene_duration_seconds: float = 15.0
    duration_tolerance_seconds: float = 1.0

PLANNING_LIMITS = VideoPlanningLimits()


class PlanningExecutionMode(str, Enum):
    DETERMINISTIC = "deterministic"
    STRUCTURED_MODEL = "structured_model"
    AUTO = "auto"


class PlanningRepairPolicy(BaseModel):
    max_repair_attempts: int = 1
    fallback_on_failure: bool = True


class PlanningInvariantError(Exception):
    def __init__(self, code: str, message: str, stage: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(f"[{stage}] {code}: {message}")
        self.code = code
        self.message = message
        self.stage = stage
        self.details = details or {}


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PlanningValidationIssue(BaseModel):
    stage: str
    code: str
    severity: ValidationSeverity
    message: str
    scene_id: Optional[str] = None
    field_path: Optional[str] = None
    repairable: bool = True
    repair_action: Optional[str] = None


class PlanningStageMetric(BaseModel):
    stage_name: str
    start_time: float
    end_time: float
    execution_duration_sec: float
    execution_mode: PlanningExecutionMode = PlanningExecutionMode.DETERMINISTIC
    execution_source: str = "deterministic_planner"
    model_requested: Optional[str] = None
    model_used: Optional[str] = None
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    validation_passed: bool = True
    validation_issue_count: int = 0
    repair_attempts: int = 0
    warning_count: int = 0


class VideoPlanningResult(BaseModel):
    planning_id: str
    request: VideoGenerationRequest
    director_brief: DirectorBrief
    screenplay: Screenplay
    production_plan: ProductionPlan
    stage_metrics: List[PlanningStageMetric]
    warnings: List[str] = Field(default_factory=list)
    fallback_stages: List[str] = Field(default_factory=list)
    schema_version: str = "v3.1.0"
