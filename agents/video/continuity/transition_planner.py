"""
TransitionPlanner for Visual Continuity Engine (Upgrade 4).
Dynamically computes transition type and duration based on motion vectors, color similarity, emotion, and rhythm.
"""
import math
from typing import List, Optional
from agents.video.continuity.engine_schemas import (
    TransitionPlan,
    CameraMotionVector,
    EmotionalStage,
    LightingModel
)
from agents.video.storyboard import SceneDefinition


class TransitionPlanner:
    """
    Computes optimal transitions between scenes using visual energy and vector matching.
    """

    @classmethod
    def plan_transition(
        cls,
        outgoing_scene: SceneDefinition,
        incoming_scene: SceneDefinition,
        outgoing_motion: CameraMotionVector,
        incoming_motion: CameraMotionVector,
        outgoing_lighting: LightingModel,
        incoming_lighting: LightingModel,
        emotional_stage: EmotionalStage
    ) -> TransitionPlan:
        # Calculate color & lighting similarity
        lighting_sim = outgoing_lighting.similarity(incoming_lighting)

        # Evaluate motion vector alignment
        motion_aligned = False
        if outgoing_motion == incoming_motion and outgoing_motion != CameraMotionVector.STATIC:
            motion_aligned = True
        elif (outgoing_motion == CameraMotionVector.PAN_LEFT and incoming_motion == CameraMotionVector.PAN_LEFT) or \
             (outgoing_motion == CameraMotionVector.PUSH_IN and incoming_motion == CameraMotionVector.PUSH_IN):
            motion_aligned = True

        # Rule 1: Emotional conclusions or major scene breaks -> FADE
        if emotional_stage == EmotionalStage.CONCLUSION or outgoing_scene.transition == "fade":
            return TransitionPlan(
                scene_id=outgoing_scene.scene_id,
                recommended_transition="fade",
                duration_sec=0.75,
                color_similarity_score=lighting_sim,
                motion_alignment_score=1.0 if motion_aligned else 0.5,
                reasoning="Emotional conclusion / section boundary -> Fade"
            )

        # Rule 2: High motion alignment with matching pan/zoom -> SLIDE or MATCH CUT
        if motion_aligned:
            return TransitionPlan(
                scene_id=outgoing_scene.scene_id,
                recommended_transition="slide_left",
                duration_sec=0.50,
                color_similarity_score=lighting_sim,
                motion_alignment_score=0.95,
                reasoning="Motion vector alignment (continuous movement) -> Slide"
            )

        # Rule 3: High color similarity -> DISSOLVE
        if lighting_sim >= 0.70:
            return TransitionPlan(
                scene_id=outgoing_scene.scene_id,
                recommended_transition="dissolve",
                duration_sec=0.50,
                color_similarity_score=lighting_sim,
                motion_alignment_score=0.80,
                reasoning="High color/lighting similarity -> Dissolve"
            )

        # Rule 4: High emotional energy or analysis -> CUT / ZOOM_IN
        if emotional_stage in (EmotionalStage.PROBLEM, EmotionalStage.ANALYSIS):
            return TransitionPlan(
                scene_id=outgoing_scene.scene_id,
                recommended_transition="zoom_in",
                duration_sec=0.40,
                color_similarity_score=lighting_sim,
                motion_alignment_score=0.85,
                reasoning="High analytical tension -> Zoom In"
            )

        # Default smooth fallback
        return TransitionPlan(
            scene_id=outgoing_scene.scene_id,
            recommended_transition="fade",
            duration_sec=0.50,
            color_similarity_score=lighting_sim,
            motion_alignment_score=0.75,
            reasoning="Default visual continuity fallback -> Smooth Fade"
        )
