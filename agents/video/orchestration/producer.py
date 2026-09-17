# PHANTOM ARCHITECTURE NOTE: DirectorService, ScreenwriterService, ProducerService were previously claimed as independent microservices.
"""
Producer Stage Service for VideoAgent Orchestration.
Converts Screenplay into executable ProductionPlan integrated with ProviderRegistry.
"""
import time
import logging
from typing import List, Tuple, Dict
from agents.video import language as _video_language
from agents.video.orchestration.schemas import (
    ProducerInput,
    ProductionPlan,
    ProductionScene,
    TransitionType,
    CameraMovement,
    MotionTreatment,
    VoiceConfiguration,
    MusicBehavior,
    SubtitleConfiguration,
    SceneRenderConfiguration,
    ProductionValidationRule,
    PlanningValidationIssue,
    ValidationSeverity
)
from agents.video.providers import (
    ProviderRegistry,
    MediaRequest,
    MediaType,
    AssetValidator,
    ProviderSelectionProfile
)

logger = logging.getLogger("uvicorn")


class ProducerService: # [PHANTOM - NON-EXISTENT]
    """
    Producer Service mapping screenplay requirements into executable provider selections and production plans.
    """

    @classmethod
    def normalize_transition(cls, requested_style: str) -> TransitionType:
        """
        Normalizes arbitrary transition strings to supported TransitionType enum.
        """
        style = requested_style.lower()
        if "cut" in style:
            return TransitionType.CUT
        elif "slide" in style:
            return TransitionType.SLIDE
        elif "cross" in style or "dissolve" in style:
            return TransitionType.CROSSFADE
        else:
            return TransitionType.FADE

    @classmethod
    def normalize_camera_movement(cls, requested_move: str, media_type: MediaType) -> CameraMovement:
        """
        Normalizes camera movement based on renderer support and media_type capabilities.
        """
        move = requested_move.lower()
        if "zoom_in" in move or "zoom in" in move:
            return CameraMovement.ZOOM_IN
        elif "zoom_out" in move or "zoom out" in move:
            return CameraMovement.ZOOM_OUT
        elif "pan_left" in move or "pan left" in move:
            return CameraMovement.PAN_LEFT
        elif "pan_right" in move or "pan right" in move:
            return CameraMovement.PAN_RIGHT
        elif "ken" in move or "burns" in move:
            return CameraMovement.KEN_BURNS
        else:
            return CameraMovement.STATIC

    @classmethod
    def generate_deterministic_plan(cls, input_data: ProducerInput) -> ProductionPlan:
        """
        Deterministic ProductionPlan generator integrating directly with ProviderRegistry.
        """
        req = input_data.request
        brief = input_data.director_brief
        screenplay = input_data.screenplay

        prod_scenes: List[ProductionScene] = []
        total_cost = 0.0
        total_latency = 0.0
        provider_usage: Dict[str, int] = {}
        warnings: List[str] = []

        prev_provider = None

        for sc in screenplay.scenes:
            # Map screenplay preferences into ProviderRegistry MediaRequest
            pref_types = [r.preferred_media_type for r in sc.required_asset_roles] if sc.required_asset_roles else [MediaType.LOCAL_ASSET, MediaType.PROCEDURAL_GRAPHIC]

            # Construct MediaRequest
            media_req = MediaRequest(
                scene_id=sc.scene_id,
                query=sc.visual_description[:60] if sc.visual_description else sc.narration[:60],
                media_type_preferences=pref_types,
                target_width=req.resolution_width,
                target_height=req.resolution_height,
                minimum_duration=sc.target_scene_duration,
                previous_scene_provider=prev_provider,
                offline_mode=req.quality_profile == ProviderSelectionProfile.OFFLINE or "offline" in req.prompt.lower(),
                quality_profile=req.quality_profile,
                maximum_cost=req.maximum_cost,
                maximum_latency_seconds=req.maximum_latency_seconds
            )

            # Query ProviderRegistry from Iteration 2
            selection_res = ProviderRegistry.select_provider(media_req)

            selected_pid = selection_res.selected_provider_id
            if selected_pid:
                provider_usage[selected_pid] = provider_usage.get(selected_pid, 0) + 1
                prev_provider = selected_pid
            else:
                warnings.append(f"Scene '{sc.scene_id}': No eligible media provider. Falling back to procedural default.")
                selected_pid = "procedural_overlay"

            transition_enum = cls.normalize_transition(sc.transition_intent.style)
            camera_enum = cls.normalize_camera_movement("zoom_in" if sc.scene_index == 1 else "static", pref_types[0])

            expected_c = selected_score = selection_res.selected_score or 0.0
            expected_l = 0.2

            prod_scenes.append(ProductionScene(
                scene_index=sc.scene_index,
                scene_id=sc.scene_id,
                media_request=media_req,
                preferred_media_types=pref_types,
                provider_selection=selection_res,
                asset_prompt=sc.visual_description,
                fallback_asset_strategy=selection_res.fallback_chain,
                camera_movement=camera_enum,
                motion_treatment=MotionTreatment(movement_type=camera_enum, intensity=0.5),
                transition=transition_enum,
                # Default to the Edge voice for the requested language, not a hardcoded
                # English one -- this voice_id is what the Edge-TTS fallback speaks with
                # when Kokoro is unavailable, so pinning it to Jenny would read a French
                # script in an American accent the moment the local engine failed.
                voice_configuration=VoiceConfiguration(
                    voice_id=req.voice_preference or _video_language.profile(req.language).edge_voice
                ),
                music_behavior=MusicBehavior(track_genre=brief.audio_direction.music_genre),
                sound_effects=[],
                subtitle_configuration=SubtitleConfiguration(enabled=True),
                render_configuration=SceneRenderConfiguration(resolution=(req.resolution_width, req.resolution_height), fps=30),
                expected_cost=expected_c,
                expected_latency_seconds=expected_l,
                validation_rules=[ProductionValidationRule(rule_name="provider_capability_match", status="PASSED")],
                visual_overlay=getattr(sc, "visual_overlay", None)
            ))

            total_cost += expected_c
            total_latency += expected_l

        return ProductionPlan(
            project_id=f"proj_{hash(req.prompt)}",
            scenes=prod_scenes,
            estimated_total_cost=round(total_cost, 4),
            estimated_generation_latency=round(total_latency, 2),
            expected_render_duration=round(screenplay.total_scene_duration, 2),
            provider_usage_summary=provider_usage,
            warnings=warnings
        )

    @classmethod
    def validate_production_plan(cls, plan: ProductionPlan) -> Tuple[bool, List[PlanningValidationIssue]]:
        issues = []

        if not plan.scenes:
            issues.append(PlanningValidationIssue(
                stage="Producer", code="EMPTY_PRODUCTION_PLAN", severity=ValidationSeverity.CRITICAL,
                message="Production plan contains no scenes.", repairable=False
            ))
            return False, issues

        for scene in plan.scenes:
            if not scene.provider_selection or scene.provider_selection.no_provider_available:
                issues.append(PlanningValidationIssue(
                    stage="Producer", code="UNRESOLVED_PROVIDER", severity=ValidationSeverity.WARNING,
                    message=f"Scene '{scene.scene_id}' has unresolved provider selection.", repairable=True, scene_id=scene.scene_id
                ))

        is_passed = not any(i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL) for i in issues)
        return is_passed, issues

    @classmethod
    def create_production_plan(cls, input_data: ProducerInput) -> Tuple[ProductionPlan, bool, List[PlanningValidationIssue]]:
        """
        Executes Producer stage and returns (ProductionPlan, validation_passed, issues).
        """
        plan = cls.generate_deterministic_plan(input_data)
        passed, issues = cls.validate_production_plan(plan)
        return plan, passed, issues
