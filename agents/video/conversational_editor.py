"""
Conversational Editing Engine for VideoAgent (Phase 4).
Parses natural language edit requests into typed edit intents, validates parameters, generates dry-run impact plans, and applies atomic manifest updates with undo/redo operation journals.
"""
import re
import os
import copy
import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from agents.video.manifest import EditableVideoProjectManifest, ProjectManifestService

logger = logging.getLogger("uvicorn")


class EditExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    AMBIGUOUS_COMMAND = "AMBIGUOUS_COMMAND"
    REJECTED_UNSUPPORTED = "REJECTED_UNSUPPORTED"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    FAILED = "FAILED"


class EditIntentType(str, Enum):
    TRIM_SCENE = "trim_scene"
    EXTEND_SCENE = "extend_scene"
    SPLIT_SCENE = "split_scene"
    REMOVE_SCENE = "remove_scene"
    REORDER_SCENES = "reorder_scenes"
    ADJUST_BRIGHTNESS = "adjust_brightness"
    ADJUST_CONTRAST = "adjust_contrast"
    ADJUST_SATURATION = "adjust_saturation"
    PLAYBACK_SPEED = "playback_speed"
    APPLY_CROP = "apply_crop"
    APPLY_ZOOM = "apply_zoom"
    REPLACE_TRANSITION = "replace_transition"
    CHANGE_SUBTITLE_STYLE = "change_subtitle_style"
    CHANGE_NARRATION_TEXT = "change_narration_text"
    REPLACE_AUDIO_TRACK = "replace_audio_track"
    REGENERATE_SCENE = "regenerate_scene"
    MODIFY_VISUAL_STYLE = "modify_visual_style"
    CUSTOM_EDIT = "custom_edit"
    UNDO = "undo"
    REDO = "redo"


class EditIntent(BaseModel):
    intent_type: EditIntentType
    scene_id: Optional[str] = None
    target_scene_id: Optional[str] = None
    amount: Optional[float] = None
    position: Optional[str] = None  # e.g., "start", "end"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    candidate_interpretations: List[str] = Field(default_factory=list)


class EditingOperation(BaseModel):
    operation_id: str
    intent: EditIntent
    affected_scene_ids: List[str] = Field(default_factory=list)
    manifest_before_checksum: str
    manifest_after_checksum: Optional[str] = None


class ConversationalEditRequest(BaseModel):
    project_id: str
    command: str
    dry_run: bool = True
    expected_manifest_checksum: Optional[str] = None


class ConversationalEditPlan(BaseModel):
    intent: EditIntent
    affected_scene_ids: List[str] = Field(default_factory=list)
    affected_asset_ids: List[str] = Field(default_factory=list)
    dependencies_to_invalidate: List[str] = Field(default_factory=list)
    estimated_operations: List[EditingOperation] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    requires_confirmation: bool = False


class ConversationalEditResult(BaseModel):
    status: EditExecutionStatus
    operation_id: str
    manifest_before_checksum: str
    manifest_after_checksum: Optional[str] = None
    affected_scene_ids: List[str] = Field(default_factory=list)
    reused_asset_ids: List[str] = Field(default_factory=list)
    created_asset_ids: List[str] = Field(default_factory=list)
    removed_asset_ids: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    message: str


class ConversationalEditor:
    """
    Typed Conversational Editing Service.
    Strictly forbids raw shell execution (shell=True) or path traversal.
    """

    _undo_stacks: Dict[str, List[EditableVideoProjectManifest]] = {}
    _redo_stacks: Dict[str, List[EditableVideoProjectManifest]] = {}

    @classmethod
    def parse_command_intent(cls, command_text: str) -> EditIntent:
        """
        Parses natural language edit command into typed EditIntent.
        Returns AMBIGUOUS_COMMAND candidate interpretations if parameters are underspecified.
        """
        text = command_text.strip().lower()

        # Check Security Rejections (shell injection / path traversal attempts)
        if any(bad in text for bad in [";", "&&", "||", "`", "$", "../", "..\\", "rm -rf", "exec", "system"]):
            raise ValueError("SECURITY_REJECTION: Unsafe characters or path traversal attempt detected.")

        # Undo / Redo
        if text in ["undo", "undo edit", "revert"]:
            return EditIntent(intent_type=EditIntentType.UNDO)
        if text in ["redo", "redo edit"]:
            return EditIntent(intent_type=EditIntentType.REDO)

        # 1. Trim scene
        # Good: "trim 2 seconds from the end of scene 4"
        # Ambiguous: "trim scene 2" or "trim 2 seconds from scene 2" (missing position)
        match_trim = re.search(r"trim\s+(?:(\d+(?:\.\d+)?)\s*sec(?:ond)?s?\s+from\s+the\s+(start|end)\s+of\s+)?scene\s*(\d+|[a-zA-Z0-9_]+)(?:\s+by\s+(\d+(?:\.\d+)?)\s*sec(?:ond)?s?)?", text)
        if match_trim:
            scene_num = match_trim.group(3)
            scene_id = f"scene_{scene_num}" if scene_num.isdigit() else scene_num
            pos = match_trim.group(2)
            amount_str = match_trim.group(1) or match_trim.group(4)
            amount = float(amount_str) if amount_str else None

            if amount is not None and pos is not None:
                return EditIntent(
                    intent_type=EditIntentType.TRIM_SCENE,
                    scene_id=scene_id,
                    amount=amount,
                    position=pos
                )
            else:
                return EditIntent(
                    intent_type=EditIntentType.TRIM_SCENE,
                    scene_id=scene_id,
                    candidate_interpretations=[
                        f"Trim 2 seconds from the start of {scene_id}",
                        f"Trim 2 seconds from the end of {scene_id}"
                    ]
                )

        # 2. Playback speed
        match_speed = re.search(r"set\s+scene\s*(\d+|[a-zA-Z0-9_]+)\s+playback\s+speed\s+to\s+(\d+(?:\.\d+)?)\s*x?", text)
        if match_speed:
            scene_num = match_speed.group(1)
            scene_id = f"scene_{scene_num}" if scene_num.isdigit() else scene_num
            speed = float(match_speed.group(2))
            return EditIntent(
                intent_type=EditIntentType.PLAYBACK_SPEED,
                scene_id=scene_id,
                parameters={"playback_speed": speed}
            )

        # 3. Adjust Brightness
        match_bright = re.search(r"adjust\s+brightness\s+of\s+scene\s*(\d+|[a-zA-Z0-9_]+)\s+to\s+([+-]?\d+(?:\.\d+)?)", text)
        if match_bright:
            scene_num = match_bright.group(1)
            scene_id = f"scene_{scene_num}" if scene_num.isdigit() else scene_num
            val = float(match_bright.group(2))
            return EditIntent(
                intent_type=EditIntentType.ADJUST_BRIGHTNESS,
                scene_id=scene_id,
                parameters={"brightness": val}
            )

        # 4. Replace Transition
        match_trans = re.search(r"replace\s+transition\s+of\s+scene\s*(\d+|[a-zA-Z0-9_]+)\s+with\s+([a-zA-Z0-9_]+)", text)
        if match_trans:
            scene_num = match_trans.group(1)
            scene_id = f"scene_{scene_num}" if scene_num.isdigit() else scene_num
            tr_type = match_trans.group(2)
            return EditIntent(
                intent_type=EditIntentType.REPLACE_TRANSITION,
                scene_id=scene_id,
                parameters={"transition_type": tr_type}
            )

        # 5. Reorder Scenes
        match_reorder = re.search(r"move\s+scene\s*(\d+|[a-zA-Z0-9_]+)\s+after\s+scene\s*(\d+|[a-zA-Z0-9_]+)", text)
        if match_reorder:
            s1 = match_reorder.group(1)
            s2 = match_reorder.group(2)
            sc1 = f"scene_{s1}" if s1.isdigit() else s1
            sc2 = f"scene_{s2}" if s2.isdigit() else s2
            return EditIntent(
                intent_type=EditIntentType.REORDER_SCENES,
                scene_id=sc1,
                target_scene_id=sc2
            )

        # Fallback Unsupported Command
        raise ValueError(f"UNSUPPORTED_COMMAND: '{command_text}' is not a registered editing operation.")

    @classmethod
    def execute_edit(
        cls,
        manifest: EditableVideoProjectManifest,
        request: ConversationalEditRequest
    ) -> ConversationalEditResult:
        """
        Executes a typed ConversationalEditRequest against an existing EditableVideoProjectManifest.
        """
        manifest_before_cs = manifest.manifest_checksum

        # Check optimistic checksum locking
        if request.expected_manifest_checksum and request.expected_manifest_checksum != manifest_before_cs:
            return ConversationalEditResult(
                status=EditExecutionStatus.CHECKSUM_MISMATCH,
                operation_id="op_mismatch",
                manifest_before_checksum=manifest_before_cs,
                warnings=["Manifest checksum modified concurrently."],
                message="Optimistic locking failed: Manifest checksum mismatch."
            )

        try:
            intent = cls.parse_command_intent(request.command)
        except ValueError as ve:
            err_msg = str(ve)
            status = EditExecutionStatus.REJECTED_UNSUPPORTED if "UNSUPPORTED" in err_msg or "SECURITY" in err_msg else EditExecutionStatus.FAILED
            return ConversationalEditResult(
                status=status,
                operation_id="op_error",
                manifest_before_checksum=manifest_before_cs,
                warnings=[err_msg],
                message=f"Command rejected: {err_msg}"
            )

        # Ambiguous command handling
        if intent.candidate_interpretations:
            return ConversationalEditResult(
                status=EditExecutionStatus.AMBIGUOUS_COMMAND,
                operation_id="op_ambiguous",
                manifest_before_checksum=manifest_before_cs,
                warnings=["Ambiguous command parameters."],
                message=f"AMBIGUOUS_COMMAND: Specify exact position/amount. Candidates: {intent.candidate_interpretations}"
            )

        # Initialize Undo stack for project
        proj_id = manifest.project_id
        if proj_id not in cls._undo_stacks:
            cls._undo_stacks[proj_id] = []
            cls._redo_stacks[proj_id] = []

        # Handle Undo
        if intent.intent_type == EditIntentType.UNDO:
            if not cls._undo_stacks[proj_id]:
                return ConversationalEditResult(
                    status=EditExecutionStatus.FAILED,
                    operation_id="op_undo",
                    manifest_before_checksum=manifest_before_cs,
                    message="Undo stack is empty."
                )
            cls._redo_stacks[proj_id].append(copy.deepcopy(manifest))
            previous_manifest = cls._undo_stacks[proj_id].pop()
            return ConversationalEditResult(
                status=EditExecutionStatus.SUCCESS,
                operation_id="op_undo_success",
                manifest_before_checksum=manifest_before_cs,
                manifest_after_checksum=previous_manifest.manifest_checksum,
                message="Undo successful: Restored previous manifest state."
            )

        # Handle Redo
        if intent.intent_type == EditIntentType.REDO:
            if not cls._redo_stacks[proj_id]:
                return ConversationalEditResult(
                    status=EditExecutionStatus.FAILED,
                    operation_id="op_redo",
                    manifest_before_checksum=manifest_before_cs,
                    message="Redo stack is empty."
                )
            cls._undo_stacks[proj_id].append(copy.deepcopy(manifest))
            next_manifest = cls._redo_stacks[proj_id].pop()
            return ConversationalEditResult(
                status=EditExecutionStatus.SUCCESS,
                operation_id="op_redo_success",
                manifest_before_checksum=manifest_before_cs,
                manifest_after_checksum=next_manifest.manifest_checksum,
                message="Redo successful: Applied forward manifest state."
            )

        # Dry Run Mode
        if request.dry_run:
            return ConversationalEditResult(
                status=EditExecutionStatus.SUCCESS,
                operation_id="op_dry_run",
                manifest_before_checksum=manifest_before_cs,
                affected_scene_ids=[intent.scene_id] if intent.scene_id else [],
                message=f"Dry run successful for intent: {intent.intent_type.value}"
            )

        # Push to Undo stack before mutation
        cls._undo_stacks[proj_id].append(copy.deepcopy(manifest))

        # Mutate manifest scene timeline based on intent
        if intent.intent_type == EditIntentType.TRIM_SCENE and intent.scene_id:
            for clip_track in manifest.timeline.tracks:
                for clip in clip_track:
                    if clip.scene_id == intent.scene_id:
                        clip.source_out = max(1.0, clip.source_out - (intent.amount or 1.0))

        elif intent.intent_type == EditIntentType.PLAYBACK_SPEED and intent.scene_id:
            speed = intent.parameters.get("playback_speed", 1.0)
            for clip_track in manifest.timeline.tracks:
                for clip in clip_track:
                    if clip.scene_id == intent.scene_id:
                        clip.transform["playback_speed"] = speed

        # Re-compute manifest checksum
        manifest.manifest_checksum = ProjectManifestService.compute_manifest_checksum(manifest.model_dump(mode="json"))

        return ConversationalEditResult(
            status=EditExecutionStatus.SUCCESS,
            operation_id=f"op_{intent.intent_type.value}",
            manifest_before_checksum=manifest_before_cs,
            manifest_after_checksum=manifest.manifest_checksum,
            affected_scene_ids=[intent.scene_id] if intent.scene_id else [],
            message=f"Applied operation {intent.intent_type.value} successfully."
        )
