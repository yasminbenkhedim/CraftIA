# PHANTOM ARCHITECTURE NOTE: DirectorService, ScreenwriterService, ProducerService were previously claimed as independent microservices.
"""
VideoPlanningOrchestrator -- Master Orchestration Workflow Engine.
Controls Director -> Screenwriter -> Producer stages and provides backward compatibility with Storyboard.
"""
import uuid
import time
import logging
from typing import List, Tuple, Dict, Any, Optional

from agents.video.orchestration.schemas import (
    VideoGenerationRequest,
    DirectorInput,
    DirectorBrief,
    ScreenwriterInput,
    Screenplay,
    ProducerInput,
    ProductionPlan,
    VideoPlanningResult,
    PlanningStageMetric,
    ProviderSummary,
    PlanningValidationIssue,
    PlanningExecutionMode,
    PlanningInvariantError,
    CameraMovement
)
from agents.video.orchestration.director import DirectorService
from agents.video.orchestration.screenwriter import ScreenwriterService
from agents.video.orchestration.producer import ProducerService
from agents.video.providers import ProviderRegistry
from agents.video.storyboard import Storyboard, SceneDefinition, TextLayer, VisualOverlay

logger = logging.getLogger("uvicorn")


class VideoPlanningOrchestrator:
    """
    Master Orchestrator managing Director, Screenwriter, and Producer stages with complete traceability.
    """

    @classmethod
    def get_provider_summaries(cls) -> List[ProviderSummary]:
        summaries = []
        for prov in ProviderRegistry.list_all():
            caps = prov.capabilities()
            summaries.append(ProviderSummary(
                provider_id=prov.provider_id,
                supported_media_types=[t.value for t in caps.media_types],
                is_offline=caps.supports_offline,
                requires_api_key=caps.requires_api_key
            ))
        return summaries

    @classmethod
    def plan_video(
        cls,
        request: VideoGenerationRequest,
        planning_mode: Optional[PlanningExecutionMode] = None
    ) -> VideoPlanningResult:
        if planning_mode:
            request.execution_mode = planning_mode
        t0_master = time.time()
        planning_id = f"plan_{uuid.uuid4().hex[:8]}"
        stage_metrics: List[PlanningStageMetric] = []
        warnings: List[str] = []
        fallback_stages: List[str] = []

        prov_summaries = cls.get_provider_summaries()

        if request.prohibited_content:
            logger.info(f"VideoPlanningOrchestrator [Groq Prompt Context]: Enforcing prohibited_content terms in LLM planning context: {request.prohibited_content}")

        # ====================================================================
        # Stage 1: Director Service
        # ====================================================================
        t0 = time.time()
        dir_input = DirectorInput(request=request, available_provider_summary=prov_summaries)
        director_brief, dir_passed, dir_issues = DirectorService.create_brief(dir_input)
        dt_dir = time.time() - t0

        # Validate Director invariants (executes in normal and python -O modes)
        if len(director_brief.scene_duration_budget) != director_brief.recommended_scene_count:
            raise PlanningInvariantError(
                code="DIRECTOR_BUDGET_LENGTH_MISMATCH",
                message=f"Director scene budget length ({len(director_brief.scene_duration_budget)}) != recommended count ({director_brief.recommended_scene_count})",
                stage="Director",
                details={"expected": director_brief.recommended_scene_count, "actual": len(director_brief.scene_duration_budget)}
            )

        stage_metrics.append(PlanningStageMetric(
            stage_name="Director",
            start_time=t0,
            end_time=time.time(),
            execution_duration_sec=round(dt_dir, 3),
            execution_mode=request.execution_mode if hasattr(request, "execution_mode") else PlanningExecutionMode.DETERMINISTIC,
            execution_source="deterministic_planner",
            model_requested=None,
            model_used=None,
            fallback_used=False,
            fallback_reason=None,
            validation_passed=dir_passed,
            validation_issue_count=len(dir_issues),
            warning_count=len(dir_issues)
        ))

        # ====================================================================
        # Stage 2: Screenwriter Service
        # ====================================================================
        t0 = time.time()
        scr_input = ScreenwriterInput(request=request, director_brief=director_brief)
        screenplay, scr_passed, scr_issues = ScreenwriterService.create_screenplay(scr_input)
        dt_scr = time.time() - t0

        # Validate Screenwriter invariants
        if len(screenplay.scenes) != director_brief.recommended_scene_count:
            raise PlanningInvariantError(
                code="SCREENPLAY_SCENE_COUNT_MISMATCH",
                message=f"Screenplay scene count ({len(screenplay.scenes)}) != Director count ({director_brief.recommended_scene_count})",
                stage="Screenwriter",
                details={"expected": director_brief.recommended_scene_count, "actual": len(screenplay.scenes)}
            )

        stage_metrics.append(PlanningStageMetric(
            stage_name="Screenwriter",
            start_time=t0,
            end_time=time.time(),
            execution_duration_sec=round(dt_scr, 3),
            execution_mode=request.execution_mode if hasattr(request, "execution_mode") else PlanningExecutionMode.DETERMINISTIC,
            execution_source="deterministic_planner",
            model_requested=None,
            model_used=None,
            fallback_used=False,
            fallback_reason=None,
            validation_passed=scr_passed,
            validation_issue_count=len(scr_issues),
            warning_count=len(scr_issues)
        ))

        # ====================================================================
        # Stage 3: Producer Service
        # ====================================================================
        t0 = time.time()
        prod_input = ProducerInput(
            request=request,
            director_brief=director_brief,
            screenplay=screenplay,
            provider_registry_summary=prov_summaries
        )
        production_plan, prod_passed, prod_issues = ProducerService.create_production_plan(prod_input)
        dt_prod = time.time() - t0

        # Validate Producer invariants
        if len(production_plan.scenes) != len(screenplay.scenes):
            raise PlanningInvariantError(
                code="PRODUCTION_PLAN_SCENE_COUNT_MISMATCH",
                message=f"ProductionPlan scene count ({len(production_plan.scenes)}) != Screenplay count ({len(screenplay.scenes)})",
                stage="Producer",
                details={"expected": len(screenplay.scenes), "actual": len(production_plan.scenes)}
            )

        stage_metrics.append(PlanningStageMetric(
            stage_name="Producer",
            start_time=t0,
            end_time=time.time(),
            execution_duration_sec=round(dt_prod, 3),
            execution_mode=request.execution_mode if hasattr(request, "execution_mode") else PlanningExecutionMode.DETERMINISTIC,
            execution_source="deterministic_planner",
            model_requested=None,
            model_used=None,
            fallback_used=False,
            fallback_reason=None,
            validation_passed=prod_passed,
            validation_issue_count=len(prod_issues),
            warning_count=len(prod_issues)
        ))

        # Aggregate warnings
        all_issues = dir_issues + scr_issues + prod_issues
        for issue in all_issues:
            warnings.append(f"[{issue.stage}] {issue.code}: {issue.message}")

        logger.info(f"VideoPlanningOrchestrator: Completed orchestration '{planning_id}' in {time.time() - t0_master:.3f}s")

        return VideoPlanningResult(
            planning_id=planning_id,
            request=request,
            director_brief=director_brief,
            screenplay=screenplay,
            production_plan=production_plan,
            stage_metrics=stage_metrics,
            warnings=warnings,
            fallback_stages=["Director", "Screenwriter", "Producer"],
            schema_version="v3.0.0"
        )

    @classmethod
    def convert_production_plan_to_storyboard(cls, planning_result: VideoPlanningResult) -> Storyboard:
        """
        Backward-compatibility adapter: Converts VideoPlanningResult into legacy Storyboard object
        for seamless execution with existing SceneComposer and VideoRenderer.
        """
        plan = planning_result.production_plan
        screenplay = planning_result.screenplay

        # Director-assigned user uploads, keyed by scene index (Phase 3 Track A).
        beat_by_index = {
            beat.scene_number: beat.uploaded_file_ref
            for beat in (getattr(planning_result.director_brief, "scene_plan", []) or [])
            if getattr(beat, "uploaded_file_ref", None)
        }

        scenes: List[SceneDefinition] = []
        for p_scene, s_scene in zip(plan.scenes, screenplay.scenes):
            text_layers = []
            for ost in s_scene.on_screen_text:
                text_layers.append(TextLayer(
                    text=ost.text,
                    position=ost.position,
                    entrance=ost.entrance_animation
                ))

            vis_overlay = getattr(s_scene, "visual_overlay", None) or getattr(p_scene, "visual_overlay", None)

            trans_val = "zoom_in" if getattr(p_scene.motion_treatment, "movement_type", None) == CameraMovement.ZOOM_IN else p_scene.transition.value

            # NOTE: scene 1's text layer used to be overwritten with
            # editing_blueprint.hook_rewrite, which stamped a canned marketing sentence
            # over whatever the screenwriter wrote. That injection is removed -- scene
            # text now comes only from the screenplay.

            # Background colour for the procedural gradient fallback.
            # NOTE: the renderer writes this straight into a BGR frame buffer, so values
            # here are B,G,R -- the default [42,23,15] is #0F172A reversed. Hex sources
            # must therefore be reversed on conversion, otherwise the palette renders with
            # red and blue swapped.
            bg_color_bgr = [42, 23, 15]

            def _hex_to_bgr(hex_str: str):
                h = (hex_str or "").lstrip("#")
                if len(h) != 6:
                    return None
                try:
                    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
                except ValueError:
                    return None
                return [b, g, r]

            # Prefer the AI Director's chosen palette so the whole video shares one look.
            director_palette = getattr(
                getattr(planning_result.director_brief, "global_visual_direction", None),
                "color_palette", None
            ) or []
            for hex_c in director_palette:
                converted = _hex_to_bgr(hex_c)
                if converted:
                    bg_color_bgr = converted
                    break
            else:
                v_anchor = getattr(plan, "visual_anchor", None) or getattr(getattr(plan, "production_plan", None), "visual_anchor", None)
                if v_anchor and hasattr(v_anchor, "palette"):
                    converted = _hex_to_bgr(getattr(v_anchor.palette, "background_color", "#0F172A"))
                    if converted:
                        bg_color_bgr = converted

            sc_def = SceneDefinition(
                scene_id=p_scene.scene_id,
                scene_title=s_scene.on_screen_text[0].text if s_scene.on_screen_text else p_scene.scene_id,
                duration_sec=s_scene.target_scene_duration,
                background_color=bg_color_bgr,
                background_style="gradient",
                text_layers=text_layers,
                transition=trans_val,
                narration=s_scene.narration,
                speech_text=s_scene.narration,
                voice=p_scene.voice_configuration.voice_id,
                visual_overlay=vis_overlay,
                motion_zoom=float(p_scene.motion_treatment.intensity) if getattr(p_scene, "motion_treatment", None) else 1.0,
                stock_search_queries=list(getattr(s_scene, "stock_search_queries", []) or []),
                on_screen_stats=list(getattr(s_scene, "on_screen_stats", []) or []),
                uploaded_file_ref=beat_by_index.get(p_scene.scene_index, None),
            )
            scenes.append(sc_def)

        sb = Storyboard(
            title=planning_result.director_brief.project_title,
            aspect_ratio=planning_result.request.aspect_ratio,
            resolution=[planning_result.request.resolution_width, planning_result.request.resolution_height],
            scenes=scenes,
            music_mood=planning_result.director_brief.audio_direction.music_genre,
            # The last point where the planning request is still in scope. Everything after
            # this adapter sees only the Storyboard, so the language has to be copied onto
            # it here or the TTS stage has no way to know what it is voicing.
            language=planning_result.request.language,
        )
        sb.editing_blueprint = getattr(plan, "editing_blueprint", None)
        sb.sfx_cues = getattr(getattr(plan, "editing_blueprint", None), "sfx_cues", [])
        return sb
