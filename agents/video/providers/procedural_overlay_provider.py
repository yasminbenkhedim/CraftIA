"""
Procedural Overlay Media Provider wrapper for VideoAIOverlayGenerator.
Classified as PROCEDURAL_GRAPHIC / TITLE_CARD.
"""
import os
import time
from agents.video.ai_overlay_generator import VideoAIOverlayGenerator
from agents.video.providers.base import (
    MediaProvider,
    MediaRequest,
    MediaCandidate,
    ProviderCapabilities,
    ProviderHealth,
    MediaType
)


class ProceduralOverlayProvider(MediaProvider):
    """
    Wraps VideoAIOverlayGenerator as a procedural graphics & title card provider.
    """

    @property
    def provider_id(self) -> str:
        return "procedural_overlay"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            media_types={MediaType.PROCEDURAL_GRAPHIC, MediaType.TITLE_CARD},
            supported_aspect_ratios={"16:9", "9:16", "1:1"},
            supports_duration_control=False,
            supports_seed=True,
            supports_style_reference=True,
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

        asset_path = VideoAIOverlayGenerator.generate_broll_card(
            title_text=request.query[:30],
            subtitle_text="Procedural Info Card",
            width=request.target_width,
            height=request.target_height,
            output_dir=output_dir
        )
        dt = time.time() - t0

        return MediaCandidate(
            provider_id=self.provider_id,
            media_type=MediaType.PROCEDURAL_GRAPHIC,
            asset_path=asset_path,
            width=request.target_width,
            height=request.target_height,
            mime_type="image/png",
            estimated_cost=0.0,
            measured_latency_seconds=round(dt, 3),
            generation_metadata={"rendering_engine": "PIL procedural text card renderer"}
        )
