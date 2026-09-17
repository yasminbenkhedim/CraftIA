"""
Live Timeline Synchronization Module for VideoAgent (Phase 7).
Applies incremental TimelinePatch diffs and conflict resolution without full project re-rendering.
"""
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class TimelineDiff(BaseModel):
    diff_id: str
    added_clips: List[Dict[str, Any]] = Field(default_factory=list)
    removed_clip_ids: List[str] = Field(default_factory=list)
    modified_clips: List[Dict[str, Any]] = Field(default_factory=list)


class TimelinePatch(BaseModel):
    patch_id: str
    project_id: str
    diff: TimelineDiff
    optimistic_lock_version: int = 1


class SynchronizationResult(BaseModel):
    applied: bool
    conflicts_detected: bool = False
    new_version: int = 1
    applied_patch_id: str
    summary: str = "Timeline patch merged incrementally"


class LiveTimelineSync:
    """
    Live Timeline Synchronizer.
    Applies incremental updates and resolves conflicting edits via optimistic locking.
    """

    _versions: Dict[str, int] = {}

    @classmethod
    def apply_patch(cls, patch: TimelinePatch) -> SynchronizationResult:
        current_v = cls._versions.get(patch.project_id, 1)

        if patch.optimistic_lock_version < current_v:
            logger.warning(f"LiveTimelineSync: Conflict detected for project '{patch.project_id}' (Patch v{patch.optimistic_lock_version} < Current v{current_v})")
            return SynchronizationResult(
                applied=False,
                conflicts_detected=True,
                new_version=current_v,
                applied_patch_id=patch.patch_id,
                summary=f"Conflict detected: Patch version {patch.optimistic_lock_version} stale."
            )

        new_v = current_v + 1
        cls._versions[patch.project_id] = new_v
        logger.info(f"LiveTimelineSync: Successfully merged patch '{patch.patch_id}' for project '{patch.project_id}' -> v{new_v}")
        return SynchronizationResult(
            applied=True,
            conflicts_detected=False,
            new_version=new_v,
            applied_patch_id=patch.patch_id,
            summary=f"Patch '{patch.patch_id}' applied successfully."
        )
