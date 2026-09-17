"""
Local Asset & Uploaded Media Provider.
Classified as LOCAL_ASSET / UPLOADED_MEDIA.
"""
import os
import time
from pathlib import Path
from PIL import Image
from agents.video.providers.base import (
    MediaProvider,
    MediaRequest,
    MediaCandidate,
    ProviderCapabilities,
    ProviderHealth,
    MediaType,
    ProviderInvalidAssetError
)


class LocalAssetProvider(MediaProvider):
    """
    Retrieves local assets, uploaded media, slide renders, or cached image/video files.
    """

    @property
    def provider_id(self) -> str:
        return "local_asset"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            media_types={MediaType.LOCAL_ASSET, MediaType.UPLOADED_MEDIA},
            supported_aspect_ratios={"16:9", "9:16", "1:1"},
            supports_duration_control=True,
            supports_seed=False,
            supports_style_reference=False,
            supports_transparency=True,
            requires_network=False,
            requires_api_key=False,
            supports_offline=True,
            returns_attribution=False
        )

    def readiness(self) -> ProviderHealth:
        return ProviderHealth(available=True, configuration_ready=True)

    def generate_or_retrieve(self, request: MediaRequest) -> MediaCandidate:
        t0 = time.time()
        output_dir = "./storage/video_assets"
        os.makedirs(output_dir, exist_ok=True)

        # Check if caller provided explicit local path in request visual_style
        target_path = request.visual_style.get("local_asset_path")

        if not target_path or not os.path.exists(target_path):
            # Create deterministic local asset file for request query
            target_path = os.path.join(output_dir, f"local_{request.scene_id}.png")
            img = Image.new("RGB", (request.target_width, request.target_height), color=(30, 41, 59))
            img.save(target_path, "PNG")

        dt = time.time() - t0

        return MediaCandidate(
            provider_id=self.provider_id,
            media_type=MediaType.LOCAL_ASSET,
            asset_path=target_path,
            width=request.target_width,
            height=request.target_height,
            mime_type="image/png",
            estimated_cost=0.0,
            measured_latency_seconds=round(dt, 3),
            generation_metadata={"storage_location": "local_filesystem"}
        )
