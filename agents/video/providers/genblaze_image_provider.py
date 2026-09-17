"""
Genblaze-Inspired Generative Image & Background Texture Provider.
Classified as GENERATED_IMAGE.
"""
import os
import time
import uuid
import logging
from PIL import Image, ImageDraw
from agents.video.providers.base import (
    MediaProvider,
    MediaRequest,
    MediaCandidate,
    MediaCandidateStatus,
    ProviderCapabilities,
    ProviderHealth,
    MediaType,
    AssetProvenance
)

logger = logging.getLogger("uvicorn")


class GenblazeImageProvider(MediaProvider):
    """
    Genblaze Generative Image Provider with procedural gradient generator fallback.
    """

    @property
    def provider_id(self) -> str:
        return "genblaze_image"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            media_types={MediaType.PROCEDURAL_BACKGROUND, MediaType.GENERATED_IMAGE},
            supported_aspect_ratios={"16:9", "9:16", "1:1"},
            supports_duration_control=False,
            supports_seed=True,
            supports_style_reference=True,
            supports_transparency=False,
            requires_network=False,
            requires_api_key=False,
            supports_offline=True,
            returns_attribution=False
        )

    def readiness(self) -> ProviderHealth:
        return ProviderHealth(available=True, configuration_ready=True)

    def generate_or_retrieve(self, request: MediaRequest) -> MediaCandidate:
        t0 = time.time()
        output_dir = "./storage/genblaze_assets"
        os.makedirs(output_dir, exist_ok=True)

        # Deprecation handling: normalize GENERATED_IMAGE to PROCEDURAL_BACKGROUND
        resolved_media_type = MediaType.PROCEDURAL_BACKGROUND
        if MediaType.GENERATED_IMAGE in request.media_type_preferences:
            logger.warning("GenblazeImageProvider: Deprecated MediaType.GENERATED_IMAGE requested. Normalizing to MediaType.PROCEDURAL_BACKGROUND.")

        asset_id = f"genblaze_img_{uuid.uuid4().hex[:8]}"
        output_path = os.path.join(output_dir, f"{asset_id}.png")

        # Procedural slate hero background image generation
        img = Image.new("RGB", (request.target_width, request.target_height), color=(15, 23, 42)) # Sleek dark slate #0F172A
        draw = ImageDraw.Draw(img)

        # Subtle accent geometric texture
        draw.rectangle([50, 50, request.target_width - 50, request.target_height - 50], outline=(56, 189, 248), width=3) # Electric cyan border

        img.save(output_path, "PNG")
        dt = time.time() - t0

        return MediaCandidate(
            provider_id=self.provider_id,
            media_type=resolved_media_type,
            asset_path=output_path,
            width=request.target_width,
            height=request.target_height,
            mime_type="image/png",
            estimated_cost=0.0,
            measured_latency_seconds=round(dt, 3),
            candidate_status=MediaCandidateStatus.PROCEDURAL_PLACEHOLDER,
            generation_method="procedural",
            generation_metadata={"model": "genblaze_procedural_v1", "color_palette": ["#0F172A", "#38BDF8"], "is_neural_synthesis": False}
        )

    # Legacy interface support
    def provider_name(self) -> str:
        return self.provider_id

    def supported_asset_types(self) -> list[str]:
        return ["image", "background_texture", "hero_visual"]

    def generate_or_fetch(self, prompt_or_query: str, asset_type: str, options: dict = None) -> AssetProvenance:
        req = MediaRequest(
            scene_id="legacy",
            query=prompt_or_query,
            media_type_preferences=[MediaType.GENERATED_IMAGE]
        )
        cand = self.generate_or_retrieve(req)
        return AssetProvenance(
            asset_id=f"genblaze_{uuid.uuid4().hex[:8]}",
            provider_name=self.provider_id,
            asset_type=asset_type,
            prompt_or_query=prompt_or_query,
            source_url_or_path=cand.asset_path or "",
            metadata=cand.generation_metadata
        )
