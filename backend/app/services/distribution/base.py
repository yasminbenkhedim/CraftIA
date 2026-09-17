"""
Distribution Provider Base Specifications & Schemas (Phase 6).
Credential isolation & platform capabilities protocol.
"""
from enum import Enum
from datetime import datetime
from typing import Dict, Any, List, Optional, Protocol
from pydantic import BaseModel, Field


class PlatformCapabilities(BaseModel):
    platform_name: str
    max_video_size_mb: int = 500
    max_duration_sec: float = 600.0
    supported_aspect_ratios: List[str] = Field(default_factory=lambda: ["16:9", "9:16", "1:1"])
    supports_scheduling: bool = True
    supports_thumbnails: bool = True


class PublishingRequest(BaseModel):
    project_id: str
    platform: str
    video_path: str
    title: str
    description: str = ""
    hashtags: List[str] = Field(default_factory=list)
    thumbnail_path: Optional[str] = None
    schedule_time: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PublishingResult(BaseModel):
    publish_id: str
    platform: str
    status: str = "SUCCESS"
    upload_url: Optional[str] = None
    publish_time: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    warnings: List[str] = Field(default_factory=list)
    provider_response: Dict[str, Any] = Field(default_factory=dict)


class DistributionProvider(Protocol):
    provider_id: str

    def get_capabilities(self) -> PlatformCapabilities: ...
    def publish_video(self, request: PublishingRequest) -> PublishingResult: ...
