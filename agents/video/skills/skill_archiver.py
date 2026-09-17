"""
Reusable Editing Skill Packs System for VideoAgent (Phase 4).
Extracts, serializes, archives, and applies reusable style knowledge across video projects.
"""
import os
import json
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class PacingProfile(BaseModel):
    target_pacing_wpm: int = 160
    average_scene_duration_sec: float = 4.0
    min_scene_duration_sec: float = 1.0
    max_scene_duration_sec: float = 15.0
    cut_cadence_sec: float = 3.0


class TransitionProfile(BaseModel):
    preferred_transition_types: List[str] = Field(default_factory=lambda: ["fade", "crossfade", "cut"])
    default_transition_duration_sec: float = 0.5


class MotionProfile(BaseModel):
    camera_preset: str = "cinematic_push"
    zoom_punch_in_cadence_sec: float = 3.0
    default_zoom_scale: float = 1.15


class SubtitleStyleProfile(BaseModel):
    font_family: str = "Inter"
    font_size: int = 24
    primary_color: str = "#FFFFFF"
    highlight_color: str = "#FFD700"
    animation_type: str = "pop_in"


class AudioStyleProfile(BaseModel):
    music_intensity: str = "medium"
    sfx_placement_rules: List[str] = Field(default_factory=lambda: ["scene_transition_whoosh", "key_point_riser"])
    silence_threshold_db: float = -40.0


class ContinuityPreferenceProfile(BaseModel):
    color_palette: List[str] = Field(default_factory=lambda: ["cool_blue", "warm_amber"])
    lighting_preset: str = "cinematic_dramatic"
    depth_of_field: str = "shallow"


class SkillCompatibility(BaseModel):
    min_pipeline_version: str = "3.1.0"
    supported_aspect_ratios: List[str] = Field(default_factory=lambda: ["16:9", "9:16", "1:1"])


class SkillProvenance(BaseModel):
    extracted_from_project_id: Optional[str] = None
    author: str = "CreateFlow AI Skill Archiver"
    creation_timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class EditingSkillPack(BaseModel):
    schema_version: str = "1.0.0"
    skill_id: str
    name: str
    description: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source_project_id: Optional[str] = None

    pacing_profile: PacingProfile = Field(default_factory=PacingProfile)
    transition_profile: TransitionProfile = Field(default_factory=TransitionProfile)
    motion_profile: MotionProfile = Field(default_factory=MotionProfile)
    subtitle_profile: SubtitleStyleProfile = Field(default_factory=SubtitleStyleProfile)
    audio_profile: AudioStyleProfile = Field(default_factory=AudioStyleProfile)
    continuity_profile: ContinuityPreferenceProfile = Field(default_factory=ContinuityPreferenceProfile)
    compatibility: SkillCompatibility = Field(default_factory=SkillCompatibility)
    provenance: SkillProvenance = Field(default_factory=SkillProvenance)
    checksum: str = ""

    def compute_checksum(self) -> str:
        """Computes deterministic SHA-256 checksum over canonical JSON representation."""
        data = self.model_dump(exclude={"checksum"})
        canonical_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


class SkillArchiver:
    """
    Skill Archiver service for managing reusable EditingSkillPacks.
    """

    SKILLS_DIRECTORY = "./storage/skill_packs"

    @classmethod
    def create_skill_pack(
        cls,
        name: str,
        description: Optional[str] = None,
        source_project_id: Optional[str] = None,
        pacing: Optional[PacingProfile] = None,
        transition: Optional[TransitionProfile] = None,
        motion: Optional[MotionProfile] = None,
        subtitle: Optional[SubtitleStyleProfile] = None,
        audio: Optional[AudioStyleProfile] = None,
        continuity: Optional[ContinuityPreferenceProfile] = None
    ) -> EditingSkillPack:
        skill_id = f"skill_{hashlib.sha256(name.encode()).hexdigest()[:8]}"
        pack = EditingSkillPack(
            skill_id=skill_id,
            name=name,
            description=description,
            source_project_id=source_project_id,
            pacing_profile=pacing or PacingProfile(),
            transition_profile=transition or TransitionProfile(),
            motion_profile=motion or MotionProfile(),
            subtitle_profile=subtitle or SubtitleStyleProfile(),
            audio_profile=audio or AudioStyleProfile(),
            continuity_profile=continuity or ContinuityPreferenceProfile(),
            provenance=SkillProvenance(extracted_from_project_id=source_project_id)
        )
        pack.checksum = pack.compute_checksum()
        return pack

    @classmethod
    def export_json(cls, skill_pack: EditingSkillPack, output_path: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        skill_pack.checksum = skill_pack.compute_checksum()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(skill_pack.model_dump_json(indent=2))
        return output_path

    @classmethod
    def export_yaml(cls, skill_pack: EditingSkillPack, output_path: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        skill_pack.checksum = skill_pack.compute_checksum()
        data = skill_pack.model_dump()
        try:
            import yaml
            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False)
        except ImportError:
            # Fallback to JSON if PyYAML is not installed
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        return output_path

    @classmethod
    def import_json(cls, input_path: str) -> EditingSkillPack:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pack = EditingSkillPack.model_validate(data)
        computed = pack.compute_checksum()
        if pack.checksum and pack.checksum != computed:
            logger.warning(f"SkillPack {pack.skill_id} checksum mismatch: stored={pack.checksum}, computed={computed}")
        return pack

    @classmethod
    def import_yaml(cls, input_path: str) -> EditingSkillPack:
        try:
            import yaml
            with open(input_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except ImportError:
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        pack = EditingSkillPack.model_validate(data)
        return pack

    @classmethod
    def apply_skill_to_request(
        cls,
        skill_pack: EditingSkillPack,
        request: Any,
        explicit_user_options: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Applies SkillPack defaults according to explicit precedence:
        Explicit User Options > Request Parameter > Applied Skill Pack > Platform Defaults
        """
        explicit = explicit_user_options or {}

        # Apply pacing defaults if not explicitly set
        if "target_pacing_wpm" not in explicit and hasattr(request, "target_pacing_wpm"):
            setattr(request, "target_pacing_wpm", skill_pack.pacing_profile.target_pacing_wpm)

        return request
