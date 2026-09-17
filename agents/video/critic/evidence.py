"""
CriticEvidenceCollector for CraftAI (Upgrade 8).
Gathers pre-render artifacts, SceneGraph dumps, timing manifests, and rendered video metadata.
"""
import os
import uuid
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class EvidenceItem(BaseModel):
    evidence_id: str = Field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:8]}")
    source_stage: str
    source_artifact: str
    scene_id: Optional[str] = None
    raw_value: Any = None
    confidence: float = 1.0


class CriticEvidenceCollector:
    """
    Central evidence collection engine gathering build artifacts, timing manifests, and metadata.
    """

    @classmethod
    def collect_evidence(
        cls,
        storyboard: Any,
        master_scene_graph: Optional[Any] = None,
        mp4_path: Optional[str] = None
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []

        # 1. Storyboard Evidence
        if storyboard:
            items.append(EvidenceItem(
                source_stage="storyboard",
                source_artifact="title",
                raw_value=storyboard.title
            ))
            items.append(EvidenceItem(
                source_stage="storyboard",
                source_artifact="scene_count",
                raw_value=len(storyboard.scenes)
            ))

        # 2. Master SceneGraph Evidence
        if master_scene_graph:
            items.append(EvidenceItem(
                source_stage="compositor",
                source_artifact="scene_nodes",
                raw_value=len(master_scene_graph.scenes)
            ))

        # 3. Rendered MP4 File Evidence
        if mp4_path and os.path.exists(mp4_path):
            file_size = os.path.getsize(mp4_path)
            items.append(EvidenceItem(
                source_stage="renderer",
                source_artifact="mp4_file_size",
                raw_value=file_size
            ))

        return items
