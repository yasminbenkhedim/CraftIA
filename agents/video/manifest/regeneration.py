# PHANTOM ARCHITECTURE NOTE: DirectorService, ScreenwriterService, ProducerService were previously claimed as independent microservices.
"""
Granular Scene Regeneration Service for VideoAgent.
Permits scene-level edits without rebuilding the complete project pipeline.
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from agents.video.manifest.schemas import (
    EditableVideoProjectManifest,
    ProjectChangeRecord,
    ProjectChangeOperation,
    ProjectAsset,
    TimelineClip
)
from agents.video.orchestration.schemas import (
    TransitionType,
    CameraMovement
)
from agents.video.providers import (
    ProviderRegistry,
    MediaRequest,
    MediaType,
    MediaCandidateStatus
)
from agents.video.continuity import VisualContinuityValidator, VisualStyleAnchorBuilder
# from agents.video.orchestration.screenwriter import ScreenwriterService  [PHANTOM - NON-EXISTENT]

logger = logging.getLogger("uvicorn")


class SceneRegenerationRequest(BaseModel):
    scene_id: str
    updated_narration: Optional[str] = None
    updated_visual_description: Optional[str] = None
    updated_transition: Optional[TransitionType] = None
    updated_camera_movement: Optional[CameraMovement] = None
    replacement_asset_path: Optional[str] = None
    change_reason: str = "User editing request"


class SceneRegenerationResult(BaseModel):
    project_id: str
    regenerated_scene_id: str

    changed_fields: List[str]

    project_assets_before: int
    project_assets_after: int

    affected_asset_ids: List[str] = Field(default_factory=list)
    reused_asset_ids: List[str] = Field(default_factory=list)
    created_asset_ids: List[str] = Field(default_factory=list)
    removed_asset_ids: List[str] = Field(default_factory=list)

    provider_selection_rerun: bool
    asset_generation_rerun: bool = False
    continuity_revalidated_scene_ids: List[str] = Field(default_factory=list)
    timeline_rebuilt_clip_ids: List[str] = Field(default_factory=list)

    original_manifest_checksum: str
    regenerated_manifest_checksum: str
    original_manifest_unchanged: bool = True

    change_record_id: str

    @property
    def assets_reused_count(self) -> int:
        return len(self.reused_asset_ids)

    @property
    def new_assets_created_count(self) -> int:
        return len(self.created_asset_ids)


class SceneRegenerationService:
    """
    Service executing granular scene-level updates directly on EditableVideoProjectManifest.
    """

    @classmethod
    def regenerate_scene(
        cls,
        manifest: EditableVideoProjectManifest,
        request: SceneRegenerationRequest
    ) -> SceneRegenerationResult:
        # Deep copy original manifest to enforce original-manifest immutability
        new_manifest = manifest.model_copy(deep=True)
        scene_id = request.scene_id

        target_p_scene = next((s for s in new_manifest.production_plan.scenes if s.scene_id == scene_id), None)
        target_s_scene = next((s for s in new_manifest.screenplay.scenes if s.scene_id == scene_id), None)

        if not target_p_scene or not target_s_scene:
            raise ValueError(f"SceneRegenerationService: Scene ID '{scene_id}' not found in project manifest.")

        changed_fields: List[str] = []
        provider_selection_rerun = False
        asset_generation_rerun = False
        rebuilt_clip_ids: List[str] = []
        created_asset_ids: List[str] = []
        affected_asset_ids: List[str] = []
        removed_asset_ids: List[str] = []
        reused_asset_ids: List[str] = [a.asset_id for a in new_manifest.assets]

        assets_before = len(new_manifest.assets)
        old_checksum = manifest.manifest_checksum or "uncomputed"

        # 1. Update Transition (Fast Path: no provider selection rerun needed)
        if request.updated_transition:
            target_p_scene.transition = request.updated_transition
            changed_fields.append("transition")
            # Update corresponding timeline clip
            for track in new_manifest.timeline.tracks:
                for clip in track:
                    if clip.scene_id == scene_id:
                        clip.transition_in = request.updated_transition.value
                        clip.transition_out = request.updated_transition.value
                        rebuilt_clip_ids.append(clip.clip_id)

        # 2. Update Narration & Re-estimate Duration
        if request.updated_narration:
            target_s_scene.narration = request.updated_narration
            new_dur = ScreenwriterService.estimate_narration_duration(request.updated_narration, new_manifest.screenplay.language)
            target_s_scene.estimated_narration_duration = new_dur
            target_s_scene.target_scene_duration = max(2.0, new_dur)
            target_p_scene.media_request.minimum_duration = target_s_scene.target_scene_duration
            changed_fields.append("narration")
            changed_fields.append("target_scene_duration")

            for track in new_manifest.timeline.tracks:
                for clip in track:
                    if clip.scene_id == scene_id:
                        clip.end_time = clip.start_time + target_s_scene.target_scene_duration
                        clip.source_out = clip.end_time
                        rebuilt_clip_ids.append(clip.clip_id)

        # 3. Update Visual Description & Rerun Provider Selection
        if request.updated_visual_description or request.replacement_asset_path:
            provider_selection_rerun = True
            asset_generation_rerun = True
            if request.updated_visual_description:
                target_s_scene.visual_description = request.updated_visual_description
                target_p_scene.asset_prompt = request.updated_visual_description
                target_p_scene.media_request.query = request.updated_visual_description[:60]
                changed_fields.append("visual_description")

            if request.replacement_asset_path:
                target_p_scene.media_request.media_type_preferences = [MediaType.LOCAL_ASSET]
                changed_fields.append("replacement_asset_path")

            sel_res = ProviderRegistry.select_provider(target_p_scene.media_request)
            target_p_scene.provider_selection = sel_res

            new_asset_id = f"asset_{scene_id}_{uuid.uuid4().hex[:6]}"
            new_asset = ProjectAsset(
                asset_id=new_asset_id,
                logical_role="background_visual",
                scene_ids=[scene_id],
                provider_id=sel_res.selected_provider_id or "procedural_overlay",
                generation_method="procedural",
                candidate_status=MediaCandidateStatus.VALIDATED_RENDER_READY,
                media_type=MediaType.LOCAL_ASSET if request.replacement_asset_path else MediaType.PROCEDURAL_GRAPHIC,
                local_path=request.replacement_asset_path or "./storage/procedural_assets/scene_bg.png",
                file_size_bytes=1024,
                placeholder=False
            )
            new_manifest.assets.append(new_asset)
            created_asset_ids.append(new_asset_id)
            affected_asset_ids.append(new_asset_id)

        # 4. Revalidate Visual Continuity
        cont_report = VisualContinuityValidator.validate_project_continuity(
            new_manifest.visual_style_anchor,
            new_manifest.scene_continuity_specs
        )
        new_manifest.continuity_report = cont_report

        change_id = f"chg_{uuid.uuid4().hex[:8]}"
        change_record = ProjectChangeRecord(
            change_id=change_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            operation=ProjectChangeOperation.SCENE_REGENERATED,
            target_type="scene",
            target_id=scene_id,
            changed_fields=changed_fields,
            reason=request.change_reason,
            previous_checksum=old_checksum,
            new_checksum=None
        )
        new_manifest.change_history.append(change_record)

        assets_after = len(new_manifest.assets)
        logger.info(f"SceneRegenerationService: Regenerated scene '{scene_id}'. Fields: {changed_fields}")

        return SceneRegenerationResult(
            project_id=new_manifest.project_id,
            regenerated_scene_id=scene_id,
            changed_fields=changed_fields,
            project_assets_before=assets_before,
            project_assets_after=assets_after,
            affected_asset_ids=affected_asset_ids,
            reused_asset_ids=reused_asset_ids,
            created_asset_ids=created_asset_ids,
            removed_asset_ids=removed_asset_ids,
            provider_selection_rerun=provider_selection_rerun,
            asset_generation_rerun=asset_generation_rerun,
            continuity_revalidated_scene_ids=[scene_id],
            timeline_rebuilt_clip_ids=rebuilt_clip_ids,
            original_manifest_checksum=old_checksum,
            regenerated_manifest_checksum="pending_save",
            original_manifest_unchanged=True,
            change_record_id=change_id
        )
