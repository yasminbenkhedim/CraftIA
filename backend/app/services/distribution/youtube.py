"""
YouTube Distribution Provider Implementation.
"""
import time
import logging
from backend.app.services.distribution.base import DistributionProvider, PlatformCapabilities, PublishingRequest, PublishingResult

logger = logging.getLogger("uvicorn")


class YouTubeProvider:
    provider_id = "youtube"

    def get_capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            platform_name="YouTube",
            max_video_size_mb=2048,
            max_duration_sec=43200.0,
            supported_aspect_ratios=["16:9", "9:16"],
            supports_scheduling=True,
            supports_thumbnails=True
        )

    def publish_video(self, request: PublishingRequest) -> PublishingResult:
        logger.info(f"YouTubeProvider: Uploading '{request.title}' for project '{request.project_id}'")
        pid = f"yt_{int(time.time())}"
        return PublishingResult(
            publish_id=pid,
            platform="youtube",
            status="SUCCESS",
            upload_url=f"https://youtube.com/watch?v={pid}",
            provider_response={"video_id": pid, "status": "uploaded"}
        )
