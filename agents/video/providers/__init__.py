"""
Media Providers Package for VideoAgent.
"""
from agents.video.providers.base import (
    MediaType,
    ProviderSelectionProfile,
    MediaRequest,
    ProviderCapabilities,
    ProviderHealth,
    MediaCandidate,
    MediaCandidateStatus,
    ProviderScore,
    ProviderSelectionResult,
    MediaProvider,
    ProviderRegistry,
    ProviderQualityEvaluator,
    AssetValidator,
    ProviderError,
    ProviderUnavailableError,
    ProviderConfigurationError,
    ProviderCapabilityError,
    ProviderGenerationError,
    ProviderTimeoutError,
    ProviderInvalidAssetError
)
from agents.video.providers.procedural_overlay_provider import ProceduralOverlayProvider
from agents.video.providers.local_asset_provider import LocalAssetProvider
from agents.video.providers.genblaze_image_provider import GenblazeImageProvider
from agents.video.providers.openmontage_provider import OpenMontageStockProvider
from agents.video.providers.pexels_provider import PexelsStockProvider
from agents.video.providers.pexels_video_provider import PexelsVideoProvider
from agents.video.providers.openverse_provider import OpenverseStockProvider
from agents.video.providers.comfyui_provider import ComfyUIGenerativeProvider
from agents.video.providers.flora_provider import FloraAIGenerativeProvider


# Register all production & remix providers on package import
ProviderRegistry.register(ProceduralOverlayProvider())
ProviderRegistry.register(LocalAssetProvider())
ProviderRegistry.register(GenblazeImageProvider())
ProviderRegistry.register(OpenMontageStockProvider())
ProviderRegistry.register(PexelsStockProvider())
ProviderRegistry.register(PexelsVideoProvider())
ProviderRegistry.register(OpenverseStockProvider())
ProviderRegistry.register(ComfyUIGenerativeProvider())
ProviderRegistry.register(FloraAIGenerativeProvider())



