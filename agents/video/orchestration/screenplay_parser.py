"""
Screenplay Parser for Shot-Level Metadata & Camera Directives.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ShotMetadata(BaseModel):
    shot_index: int
    scene_id: str
    line_text: str
    visual_focus: str
    negative_prompt: str = "blur, low resolution, artifacts, distorted"
    camera_movement: str = "static"
    suggested_cut_cadence_seconds: float = 3.0


class ScreenplayParser:
    """
    Parses screenplay text and scenes into fine-grained shot-level metadata directives.
    """

    @classmethod
    def parse_screenplay_shots(cls, screenplay: Any) -> List[ShotMetadata]:
        shots: List[ShotMetadata] = []
        if not hasattr(screenplay, "scenes") or not screenplay.scenes:
            return shots

        for s_idx, scene in enumerate(screenplay.scenes):
            narration = getattr(scene, "narration", "")
            scene_id = getattr(scene, "scene_id", f"scene_{s_idx+1}")
            lines = [l.strip() for l in narration.split(".") if l.strip()]

            if not lines:
                lines = [narration or scene_id]

            for l_idx, line in enumerate(lines):
                shots.append(ShotMetadata(
                    shot_index=len(shots) + 1,
                    scene_id=scene_id,
                    line_text=line,
                    visual_focus=f"Key visual subject for '{line[:30]}...'",
                    camera_movement="zoom_in" if l_idx % 2 == 1 else "static",
                    suggested_cut_cadence_seconds=round(max(2.0, len(line.split()) / 2.5), 1)
                ))

        return shots
