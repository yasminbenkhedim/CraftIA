"""
Visual Continuity Package for VideoAgent.
"""
from agents.video.continuity.schemas import (
    VisualMedium,
    RealismLevel,
    LightingStyle,
    ContrastProfile,
    CompositionStyle,
    CameraLanguage,
    MotionStyle,
    TransitionFamily,
    StyleAnchorSource,
    ContinuityPriority,
    CharacterContinuityCapability,
    CONTINUITY_COMPONENT_WEIGHTS,
    PaletteColor,
    ColorPalette,
    TypographyStyle,
    VisualStyleAnchor,
    SceneContinuitySpec,
    StyleFingerprint,
    ContinuityScoreEvidence,
    VisualContinuityReport,
    VisualVarietyPolicy
)
from agents.video.continuity.anchor_builder import VisualStyleAnchorBuilder
from agents.video.continuity.validator import VisualContinuityValidator
