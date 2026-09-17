"""
Typed Schemas for Visual Continuity Engine (Style Anchors, Fingerprints, Reports, Variety Rules).
"""
import re
import math
from enum import Enum
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field, validator


class CharacterContinuityCapability(str, Enum):
    UNSUPPORTED = "unsupported"
    EXACT_ASSET_REUSE = "exact_asset_reuse"
    TEMPLATE_SLOT_REUSE = "template_slot_reuse"
    IMAGE_REFERENCE_CONDITIONING = "image_reference_conditioning"
    IDENTITY_ADAPTER = "identity_adapter"


CONTINUITY_COMPONENT_WEIGHTS: Dict[str, float] = {
    "palette": 0.20,
    "typography": 0.15,
    "template_family": 0.15,
    "reference_preservation": 0.15,
    "visual_medium": 0.10,
    "composition": 0.10,
    "motion_transition": 0.10,
    "provider_determinism": 0.05,
}


class VisualMedium(str, Enum):
    MOTION_GRAPHICS = "motion_graphics"
    STOCK_FOOTAGE = "stock_footage"
    PHOTOGRAPHIC_IMAGE = "photographic_image"
    PROCEDURAL_SLATE = "procedural_slate"
    ILLUSTRATION = "illustration"
    MIXED_MEDIA = "mixed_media"


class RealismLevel(str, Enum):
    STYLIZED_GRAPHIC = "stylized_graphic"
    SEMI_REALISTIC = "semi_realistic"
    PHOTOREALISTIC = "photorealistic"


class LightingStyle(str, Enum):
    CLEAN_STUDIO = "clean_studio"
    HIGH_CONTRAST = "high_contrast"
    SOFT_AMBIENT = "soft_ambient"
    CINEMATIC_DRAMATIC = "cinematic_dramatic"


class ContrastProfile(str, Enum):
    HIGH_READABILITY = "high_readability"
    BALANCED = "balanced"
    LOW_CONTRAST_SOFT = "low_contrast_soft"


class CompositionStyle(str, Enum):
    CENTERED = "centered"
    LEFT_WEIGHTED = "left_weighted"
    RIGHT_WEIGHTED = "right_weighted"
    SPLIT_SCREEN = "split_screen"
    FULL_BLEED = "full_bleed"
    CARD_GRID = "card_grid"
    DATA_DASHBOARD = "data_dashboard"


class CameraLanguage(str, Enum):
    STATIC = "static"
    SUBTLE_ZOOM = "subtle_zoom"
    SMOOTH_PAN = "smooth_pan"
    DYNAMIC_KEN_BURNS = "dynamic_ken_burns"


class MotionStyle(str, Enum):
    STATIC = "static"
    SUBTLE = "subtle"
    DYNAMIC = "dynamic"
    KINETIC_TEXT = "kinetic_text"
    KEN_BURNS = "ken_burns"


class TransitionFamily(str, Enum):
    CUT = "cut"
    FADE = "fade"
    CROSSFADE = "crossfade"
    SLIDE = "slide"


class StyleAnchorSource(str, Enum):
    BRAND_CONSTRAINTS = "brand_constraints"
    SUPPLIED_ASSETS = "supplied_assets"
    DIRECTOR_DIRECTION = "director_direction"
    QUALITY_PROFILE_DEFAULT = "quality_profile_default"
    DETERMINISTIC_SYSTEM_DEFAULT = "deterministic_system_default"


class ContinuityPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PaletteColor(BaseModel):
    hex_value: str
    role: str  # "primary", "secondary", "accent", "background", "text"
    usage_weight: float = 0.2

    @validator('hex_value')
    def validate_hex(cls, v):
        if not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', v):
            raise ValueError(f"Invalid hex color: {v}")
        return v.upper()


class ColorPalette(BaseModel):
    palette_id: str
    colors: List[PaletteColor]
    background_color: str = "#0F172A"
    foreground_color: str = "#F8FAFC"
    accent_colors: List[str] = Field(default_factory=lambda: ["#38BDF8"])
    source: str = "default"

    @classmethod
    def calculate_luminance(cls, hex_color: str) -> float:
        """Calculates relative luminance according to WCAG 2.1 specifications."""
        hex_clean = hex_color.lstrip('#')
        if len(hex_clean) == 3:
            hex_clean = ''.join(c * 2 for c in hex_clean)
        r, g, b = [int(hex_clean[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
        
        def srgb_to_linear(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        lr, lg, lb = srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b)
        return 0.2126 * lr + 0.7152 * lg + 0.0722 * lb

    @classmethod
    def calculate_contrast_ratio(cls, hex1: str, hex2: str) -> float:
        """Calculates WCAG contrast ratio between two colors (1.0 to 21.0)."""
        l1 = cls.calculate_luminance(hex1)
        l2 = cls.calculate_luminance(hex2)
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return round((lighter + 0.05) / (darker + 0.05), 2)


class TypographyStyle(BaseModel):
    heading_family: str = "Inter"
    body_family: str = "Roboto"
    numeric_family: Optional[str] = "Outfit"
    heading_weight: int = 700
    body_weight: int = 400
    capitalization: str = "none"  # "none", "uppercase", "titlecase"
    alignment: str = "center"  # "left", "center", "right"
    maximum_heading_lines: int = 2
    maximum_body_lines: int = 4


class VisualStyleAnchor(BaseModel):
    anchor_id: str
    version: str = "1.0.0"

    palette: ColorPalette
    typography: TypographyStyle
    visual_medium: VisualMedium = VisualMedium.MOTION_GRAPHICS
    realism_level: RealismLevel = RealismLevel.STYLIZED_GRAPHIC
    lighting_style: LightingStyle = LightingStyle.CLEAN_STUDIO
    contrast_profile: ContrastProfile = ContrastProfile.HIGH_READABILITY
    composition_style: CompositionStyle = CompositionStyle.CENTERED
    camera_language: CameraLanguage = CameraLanguage.STATIC
    motion_style: MotionStyle = MotionStyle.STATIC
    transition_family: TransitionFamily = TransitionFamily.FADE

    brand_reference_id: Optional[str] = None
    character_reference_ids: List[str] = Field(default_factory=list)
    environment_reference_ids: List[str] = Field(default_factory=list)
    object_reference_ids: List[str] = Field(default_factory=list)

    texture_keywords: List[str] = Field(default_factory=list)
    positive_style_constraints: List[str] = Field(default_factory=list)
    negative_style_constraints: List[str] = Field(default_factory=list)

    locked_fields: Set[str] = Field(default_factory=set)
    overridable_fields: Set[str] = Field(default_factory=set)

    source: StyleAnchorSource = StyleAnchorSource.DETERMINISTIC_SYSTEM_DEFAULT
    confidence: float = 0.90
    warnings: List[str] = Field(default_factory=list)


class SceneContinuitySpec(BaseModel):
    scene_id: str
    inherited_anchor_id: str
    inherited_fields: Set[str] = Field(default_factory=set)
    overrides: Dict[str, Any] = Field(default_factory=dict)
    continuity_references: List[str] = Field(default_factory=list)
    required_style_capabilities: Set[str] = Field(default_factory=set)
    expected_style_fingerprint: Optional[Dict[str, Any]] = None
    allowed_deviation: float = 0.20
    continuity_priority: ContinuityPriority = ContinuityPriority.HIGH
    intentional_style_break: bool = False
    style_break_reason: Optional[str] = None


class StyleFingerprint(BaseModel):
    palette_hash: str
    dominant_colors: List[str]
    typography_id: str
    template_family: str
    provider_id: str
    generation_method: str
    seed: Optional[int] = None
    reference_asset_ids: List[str] = Field(default_factory=list)
    transition_family: str
    motion_style: str
    aspect_ratio: str
    resolution: str
    visual_medium: str
    logical_asset_id: str = ""


class ContinuityScoreEvidence(BaseModel):
    provider_id: str
    raw_score: float = 0.90
    confidence: float = 0.95
    effective_score: float = 0.855
    profile_weight: float = 0.20
    weighted_contribution: float = 0.171
    evidence: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    unsupported_requirements: List[str] = Field(default_factory=list)


class VisualContinuityReport(BaseModel):
    project_score: float
    confidence: float
    scene_scores: Dict[str, float] = Field(default_factory=dict)
    issues: List[Any] = Field(default_factory=list)  # PlanningValidationIssue
    auto_repairs: List[Dict[str, Any]] = Field(default_factory=list)
    unresolved_issue_count: int = 0
    passed: bool = True


class VisualVarietyPolicy(BaseModel):
    maximum_consecutive_same_composition: int = 3
    maximum_repeated_visual_prompt_similarity: float = 0.85
    maximum_same_transition_run: int = 4
    require_visual_change_every_n_scenes: int = 2
    allow_repetition_for_branding: bool = True
