"""
Retention Architect for Stage 1.5 Execution in VideoAgent.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.app.services.llm import LLMService
from agents.video.master_system_prompt import MASTER_SYSTEM_PROMPT_V2


class PatternInterrupt(BaseModel):
    timestamp: float
    interrupt_type: str  # e.g., "zoom_in", "glitch", "text_pop", "broll_overlay"
    parameters: Dict[str, Any] = Field(default_factory=dict)


class SFXCue(BaseModel):
    timestamp: float
    sfx_type: str  # e.g., "riser", "whoosh", "bass_drop", "impact"
    duration: float = 1.0


class EditingBlueprint(BaseModel):
    pattern_interrupts: List[PatternInterrupt] = Field(default_factory=list)
    sfx_cues: List[SFXCue] = Field(default_factory=list)
    hook_rewrite: str = ""
    target_pacing_wpm: int = 160


class RetentionArchitect:
    """
    Retention Architect generating post-production blueprints for timeline retention optimization.
    """

    @classmethod
    def generate_blueprint(
        cls,
        screenplay: Any,
        llm_service: Optional[Any] = None
    ) -> EditingBlueprint:
        if llm_service is None:
            llm_service = LLMService

        # Deterministic default blueprint generation for robust offline / fast path
        interrupts = []
        sfx = []
        current_time = 0.0

        if hasattr(screenplay, "scenes") and screenplay.scenes:
            for i, scene in enumerate(screenplay.scenes):
                dur = getattr(scene, "target_scene_duration", 4.0)
                # 3-Second rule: add zoom punch-in at 2.0s mark
                interrupts.append(PatternInterrupt(
                    timestamp=round(current_time + 2.0, 2),
                    interrupt_type="zoom_in",
                    parameters={"zoom_factor": 1.15, "scene_id": scene.scene_id}
                ))

                # Add sound effect riser/whoosh
                sfx.append(SFXCue(
                    timestamp=round(current_time + 0.5, 2),
                    sfx_type="whoosh" if i > 0 else "riser",
                    duration=0.8
                ))

                current_time += dur

        if not interrupts:
            interrupts = [
                PatternInterrupt(timestamp=1.5, interrupt_type="zoom_in", parameters={"zoom_factor": 1.15}),
                PatternInterrupt(timestamp=4.5, interrupt_type="broll_overlay", parameters={"overlay_type": "graphic"})
            ]
            sfx = [
                SFXCue(timestamp=0.0, sfx_type="riser", duration=1.0),
                SFXCue(timestamp=3.0, sfx_type="whoosh", duration=0.5)
            ]

        try:
            prompt = f"""
            Analyze this screenplay and generate a Retention Editing Blueprint:
            Screenplay: {screenplay}
            Output a valid JSON matching the EditingBlueprint model with pattern interrupts, zoom punch-ins, audio risers, and B-roll cues.
            """
            raw_json = llm_service.generate_json(prompt=prompt, system_prompt=MASTER_SYSTEM_PROMPT_V2, fallback_dict={})
            if raw_json and isinstance(raw_json, dict) and "pattern_interrupts" in raw_json:
                return EditingBlueprint.model_validate(raw_json)
        except Exception as e:
            import logging
            logging.getLogger("uvicorn").warning(f"RetentionArchitect: LLM blueprint generation failed ({e}) -- using deterministic fallback.")

        # hook_rewrite is intentionally left empty. It used to hold a canned
        # "Discover how X transforms outcomes." string that the orchestrator painted
        # across the top of scene 1 -- a template sentence, not real copy. Scene text
        # now comes solely from the AI screenwriter, and the video shows no top overlay.
        return EditingBlueprint(
            pattern_interrupts=interrupts,
            sfx_cues=sfx,
            hook_rewrite="",
            target_pacing_wpm=160
        )
