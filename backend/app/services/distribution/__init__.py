"""
TikTok & Instagram Distribution Providers and Registry Package.
"""
import time
import logging
from typing import Dict, Any, Optional
from backend.app.services.distribution.base import DistributionProvider, PlatformCapabilities, PublishingRequest, PublishingResult
from backend.app.services.distribution.youtube import YouTubeProvider

logger = logging.getLogger("uvicorn")


class TikTokProvider:
    provider_id = "tiktok"

    def get_capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            platform_name="TikTok",
            max_video_size_mb=500,
            max_duration_sec=600.0,
            supported_aspect_ratios=["9:16"],
            supports_scheduling=True,
            supports_thumbnails=False
        )

    def publish_video(self, request: PublishingRequest) -> PublishingResult:
        logger.info(f"TikTokProvider: Uploading '{request.title}' for project '{request.project_id}'")
        pid = f"tt_{int(time.time())}"
        return PublishingResult(
            publish_id=pid,
            platform="tiktok",
            status="SUCCESS",
            upload_url=f"https://tiktok.com/@videoagent/video/{pid}",
            provider_response={"video_id": pid, "status": "published"}
        )


class InstagramProvider:
    provider_id = "instagram"

    def get_capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            platform_name="Instagram",
            max_video_size_mb=250,
            max_duration_sec=90.0,
            supported_aspect_ratios=["9:16", "1:1"],
            supports_scheduling=True,
            supports_thumbnails=True
        )

    def publish_video(self, request: PublishingRequest) -> PublishingResult:
        logger.info(f"InstagramProvider: Uploading '{request.title}' for project '{request.project_id}'")
        pid = f"ig_{int(time.time())}"
        return PublishingResult(
            publish_id=pid,
            platform="instagram",
            status="SUCCESS",
            upload_url=f"https://instagram.com/reel/{pid}",
            provider_response={"reel_id": pid, "status": "published"}
        )


class DistributionProviderRegistry:
    """Registry providing decoupled platform distribution providers."""
    _providers: Dict[str, Any] = {
        "youtube": YouTubeProvider(),
        "tiktok": TikTokProvider(),
        "instagram": InstagramProvider()
    }

    @classmethod
    def get_provider(cls, platform: str) -> Optional[Any]:
        return cls._providers.get(platform.lower())
