"""
Typed Schemas & Models for Visual Continuity Engine (Upgrade 4).
"""
import math
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Tuple
from pydantic import BaseModel, Field


class NarrativeArcStage(str, Enum):
    OPENING = "opening"
    DEVELOPMENT = "development"
    PEAK = "peak"
    CONCLUSION = "conclusion"


class EmotionalStage(str, Enum):
    INTRODUCTION = "introduction"
    PROBLEM = "problem"
    ANALYSIS = "analysis"
    SOLUTION = "solution"
    CONCLUSION = "conclusion"


class CameraFraming(str, Enum):
    EXTREME_WIDE = "extreme_wide"
    WIDE = "wide"
    MEDIUM = "medium"
    CLOSE_UP = "close_up"
    DETAIL = "detail"


class CameraMotionVector(str, Enum):
    STATIC = "static"
    PUSH_IN = "push_in"
    PULL_OUT = "pull_out"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    TILT_UP = "tilt_up"
    TILT_DOWN = "tilt_down"


class LightingHardness(str, Enum):
    SOFT_DIFFUSED = "soft_diffused"
    BALANCED_STUDIO = "balanced_studio"
    HARD_DIRECT = "hard_direct"


class LightingDirection(str, Enum):
    FRONTAL = "frontal"
    SIDE_KEY = "side_key"
    BACKLIT = "backlit"
    TOP_DOWN = "top_down"
    AMBIENT = "ambient"


class LightingModel(BaseModel):
    """Cinematic lighting parameters measurable from histograms/metadata."""
    brightness: float = 0.50          # 0.0 (dark) to 1.0 (bright)
    contrast: float = 0.50            # 0.0 (low) to 1.0 (high)
    temperature: float = 5500.0       # Color temp in Kelvin (2700K warm to 8000K cool)
    saturation: float = 0.50         # 0.0 (grayscale) to 1.0 (vivid)
    hardness: LightingHardness = LightingHardness.BALANCED_STUDIO
    direction: LightingDirection = LightingDirection.SIDE_KEY

    def similarity(self, other: "LightingModel") -> float:
        """Calculates normalized similarity score (0.0 to 1.0) between two lighting models."""
        b_diff = abs(self.brightness - other.brightness)
        c_diff = abs(self.contrast - other.contrast)
        t_diff = min(abs(self.temperature - other.temperature) / 4000.0, 1.0)
        s_diff = abs(self.saturation - other.saturation)
        h_match = 1.0 if self.hardness == other.hardness else 0.5
        d_match = 1.0 if self.direction == other.direction else 0.5

        weighted = (
            0.25 * (1.0 - b_diff) +
            0.25 * (1.0 - c_diff) +
            0.20 * (1.0 - t_diff) +
            0.15 * (1.0 - s_diff) +
            0.08 * h_match +
            0.07 * d_match
        )
        return max(0.0, min(1.0, weighted))


class MotifNode(BaseModel):
    tag: str
    category: str  # e.g., "subject", "environment", "concept"
    parent_motif: Optional[str] = None
    related_motifs: List[str] = Field(default_factory=list)


class MotifGraph(BaseModel):
    """Storytelling relationship graph for coherent visual progression."""
    nodes: Dict[str, MotifNode] = Field(default_factory=dict)

    @classmethod
    def create_default(cls) -> "MotifGraph":
        graph = cls()
        # Healthcare motif hierarchy
        graph.nodes["healthcare"] = MotifNode(tag="healthcare", category="concept", related_motifs=["hospital", "medicine"])
        graph.nodes["hospital"] = MotifNode(tag="hospital", category="environment", parent_motif="healthcare", related_motifs=["doctor", "laboratory"])
        graph.nodes["doctor"] = MotifNode(tag="doctor", category="subject", parent_motif="hospital", related_motifs=["patient", "mri"])
        graph.nodes["patient"] = MotifNode(tag="patient", category="subject", parent_motif="hospital", related_motifs=["recovery", "doctor"])
        graph.nodes["mri"] = MotifNode(tag="mri", category="equipment", parent_motif="hospital", related_motifs=["laboratory"])
        graph.nodes["laboratory"] = MotifNode(tag="laboratory", category="environment", parent_motif="healthcare", related_motifs=["mri", "research"])
        graph.nodes["recovery"] = MotifNode(tag="recovery", category="concept", parent_motif="patient", related_motifs=["health"])

        # Technology motif hierarchy
        graph.nodes["technology"] = MotifNode(tag="technology", category="concept", related_motifs=["computing", "ai"])
        graph.nodes["computing"] = MotifNode(tag="computing", category="environment", parent_motif="technology", related_motifs=["server", "code"])
        graph.nodes["ai"] = MotifNode(tag="ai", category="concept", parent_motif="technology", related_motifs=["neural_network", "data"])
        return graph

    def get_relationship_score(self, tag1: str, tag2: str) -> float:
        """Calculates narrative coherence score between two visual motif tags."""
        t1, t2 = tag1.lower().strip(), tag2.lower().strip()
        if t1 == t2:
            return 1.0
        n1 = self.nodes.get(t1)
        if not n1:
            return 0.5
        if t2 in n1.related_motifs or t2 == n1.parent_motif:
            return 0.85
        return 0.40


class TransitionPlan(BaseModel):
    scene_id: str
    recommended_transition: str  # "fade", "slide_left", "dissolve", "zoom_in", "cut"
    duration_sec: float = 0.50
    motion_alignment_score: float = 0.90
    color_similarity_score: float = 0.85
    reasoning: str = ""


class SceneContinuityContext(BaseModel):
    """Immutable context directing individual scene candidate selection & rendering."""
    scene_id: str
    scene_index: int
    total_scenes: int
    arc_stage: NarrativeArcStage
    emotional_stage: EmotionalStage
    target_palette_hex: List[str]
    target_lighting: LightingModel
    target_framing: CameraFraming
    recommended_motion: CameraMotionVector
    target_density: float = 0.50
    motif_tags: List[str] = Field(default_factory=list)
    recommended_transition: str = "fade"
    target_continuity_score: float = 0.85

    class Config:
        frozen = True  # Immutable per scene


class ContinuityDiagnosticReport(BaseModel):
    """Complete diagnostic report for video visual continuity."""
    video_id: str
    overall_continuity_score: float
    palette_score: float
    lighting_score: float
    framing_score: float
    motion_score: float
    emotion_score: float
    provider_diversity_score: float
    motif_diversity_score: float
    transition_quality_score: float
    scene_breakdown: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
