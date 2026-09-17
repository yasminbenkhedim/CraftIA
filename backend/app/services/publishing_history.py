"""
Publishing History Service for VideoAgent (Phase 6).
Stores, indexes, and queries distribution upload history and performance statistics.
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class PublishingHistoryRecord(BaseModel):
    history_id: str
    project_id: str
    platform: str
    upload_id: str
    title: str
    description: str = ""
    hashtags: List[str] = Field(default_factory=list)
    thumbnail_url: Optional[str] = None
    publish_time: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    status: str = "SUCCESS"
    retry_count: int = 0
    duration_seconds: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    provider_response: Dict[str, Any] = Field(default_factory=dict)


class PublishingHistory:
    """
    Publishing History Store providing indexing, lookup, filtering, and statistics.
    """

    _history: Dict[str, PublishingHistoryRecord] = {}

    @classmethod
    def record(cls, entry: PublishingHistoryRecord) -> str:
        cls._history[entry.history_id] = entry
        logger.info(f"PublishingHistory: Recorded history entry '{entry.history_id}' for project '{entry.project_id}'")
        return entry.history_id

    @classmethod
    def get_by_project(cls, project_id: str) -> List[PublishingHistoryRecord]:
        return [h for h in cls._history.values() if h.project_id == project_id]

    @classmethod
    def list_history(cls, platform_filter: Optional[str] = None) -> List[PublishingHistoryRecord]:
        if platform_filter:
            return [h for h in cls._history.values() if h.platform.lower() == platform_filter.lower()]
        return list(cls._history.values())

    @classmethod
    def get_statistics(cls) -> Dict[str, Any]:
        total = len(cls._history)
        successful = sum(1 for h in cls._history.values() if h.status == "SUCCESS")
        by_platform = {}
        for h in cls._history.values():
            by_platform[h.platform] = by_platform.get(h.platform, 0) + 1
        return {
            "total_publications": total,
            "successful_publications": successful,
            "success_rate": (successful / total) if total > 0 else 1.0,
            "publications_by_platform": by_platform
        }

    @classmethod
    def clear_history(cls):
        cls._history.clear()
