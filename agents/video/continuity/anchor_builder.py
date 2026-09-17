"""
Visual Style Anchor Builder for VideoAgent Continuity Engine.
Derives VisualStyleAnchor following strict priority order.
"""
import uuid
import logging
from typing import List, Optional
from PIL import Image
from agents.video.continuity.schemas import (
    VisualStyleAnchor,
    ColorPalette,
    PaletteColor,
    TypographyStyle,
    VisualMedium,
    RealismLevel,
    LightingStyle,
    ContrastProfile,
    CompositionStyle,
    CameraLanguage,
    MotionStyle,
    TransitionFamily,
    StyleAnchorSource
)
from agents.video.orchestration.schemas import (
    VideoGenerationRequest,
    DirectorBrief,
    SuppliedAsset,
    ProviderSummary
)

logger = logging.getLogger("uvicorn")


class VisualStyleAnchorBuilder:
    """
    Builder deriving project VisualStyleAnchor with explicit locked fields and priority tracking.
    """

    @classmethod
    def analyze_supplied_asset_colors(cls, file_path: str) -> Optional[List[str]]:
        """Extracts dominant hex colors from a local image file using PIL quantization."""
        try:
            with Image.open(file_path) as img:
                img_small = img.convert("RGB").resize((100, 100))
                # Quantize to 3 main colors
                quantized = img_small.quantize(colors=3)
                palette = quantized.getpalette()[:9]
                hex_colors = []
                for i in range(0, len(palette), 3):
                    r, g, b = palette[i], palette[i+1], palette[i+2]
                    hex_colors.append(f"#{r:02X}{g:02X}{b:02X}")
                return hex_colors
        except Exception as e:
            logger.warning(f"VisualStyleAnchorBuilder: Could not analyze supplied asset '{file_path}': {e}")
            return None

    @classmethod
    def build_anchor(
        cls,
        request: VideoGenerationRequest,
        director_brief: DirectorBrief,
        supplied_assets: Optional[List[SuppliedAsset]] = None,
        provider_summary: Optional[List[ProviderSummary]] = None
    ) -> VisualStyleAnchor:
        anchor_id = f"anchor_{uuid.uuid4().hex[:8]}"
        locked: set[str] = set()
        overridable: set[str] = {"composition_style", "motion_style", "transition_family"}
        warnings: List[str] = []

        # Priority 1: Brand Constraints
        if request.brand_constraints:
            brand = request.brand_constraints
            primary = brand.primary_color
            secondary = brand.secondary_color
            palette = ColorPalette(
                palette_id=f"brand_{brand.brand_name}",
                colors=[
                    PaletteColor(hex_value=primary, role="background"),
                    PaletteColor(hex_value=secondary, role="accent")
                ],
                background_color=primary,
                foreground_color="#F8FAFC",
                accent_colors=[secondary],
                source="brand_constraints"
            )
            typography = TypographyStyle(heading_family=brand.font_family, body_family=brand.font_family)
            source = StyleAnchorSource.BRAND_CONSTRAINTS
            locked.update({"palette", "typography", "brand_reference_id"})

        # Priority 2: Supplied Assets (when brand colors unlocked)
        elif supplied_assets and len(supplied_assets) > 0:
            asset_colors = cls.analyze_supplied_asset_colors(supplied_assets[0].file_path)
            if asset_colors and len(asset_colors) >= 2:
                palette = ColorPalette(
                    palette_id=f"asset_{supplied_assets[0].asset_id}",
                    colors=[
                        PaletteColor(hex_value=asset_colors[0], role="background"),
                        PaletteColor(hex_value=asset_colors[1], role="accent")
                    ],
                    background_color=asset_colors[0],
                    foreground_color="#FFFFFF",
                    accent_colors=[asset_colors[1]],
                    source="supplied_assets"
                )
                source = StyleAnchorSource.SUPPLIED_ASSETS
            else:
                palette = ColorPalette(
                    palette_id="director_default",
                    colors=[PaletteColor(hex_value="#0F172A", role="background"), PaletteColor(hex_value="#38BDF8", role="accent")],
                    background_color="#0F172A", foreground_color="#F8FAFC", accent_colors=["#38BDF8"], source="director"
                )
                source = StyleAnchorSource.DIRECTOR_DIRECTION
            typography = TypographyStyle()

        # Priority 3: Director Brief
        else:
            dir_colors = director_brief.global_visual_direction.color_palette
            bg = dir_colors[0] if len(dir_colors) > 0 else "#0F172A"
            accent = dir_colors[1] if len(dir_colors) > 1 else "#38BDF8"
            palette = ColorPalette(
                palette_id="director_brief",
                colors=[PaletteColor(hex_value=bg, role="background"), PaletteColor(hex_value=accent, role="accent")],
                background_color=bg,
                foreground_color="#F8FAFC",
                accent_colors=[accent],
                source="director_brief"
            )
            typography = TypographyStyle()
            source = StyleAnchorSource.DIRECTOR_DIRECTION

        return VisualStyleAnchor(
            anchor_id=anchor_id,
            version="1.0.0",
            palette=palette,
            typography=typography,
            visual_medium=VisualMedium.MOTION_GRAPHICS,
            realism_level=RealismLevel.STYLIZED_GRAPHIC,
            lighting_style=LightingStyle.CLEAN_STUDIO,
            contrast_profile=ContrastProfile.HIGH_READABILITY,
            composition_style=CompositionStyle.CENTERED,
            camera_language=CameraLanguage.STATIC,
            motion_style=MotionStyle.STATIC,
            transition_family=TransitionFamily.FADE,
            brand_reference_id=request.brand_constraints.brand_name if request.brand_constraints else None,
            locked_fields=locked,
            overridable_fields=overridable,
            source=source,
            confidence=0.95,
            warnings=warnings
        )
