"""
Brand logo watermark.

Composites the user's saved logo into the top-right of every frame. Deliberately small
in scope: one fixed corner, one fixed size, alpha-aware. A position picker and an opacity
slider are the obvious next asks, but neither belongs in the first version of a feature
whose job is to prove the brand actually reaches the frame.

Cost matters here. This runs once per frame, so a 45-second video at 30fps calls stamp()
1350 times. Everything expensive -- decoding, scaling, splitting the alpha channel -- is
done once in prepare(); stamp() is a single blend over a small slice of the frame.
"""
import logging
import os
from typing import Any, Dict, Optional

import cv2
import numpy as np

logger = logging.getLogger("uvicorn")

# Fraction of the frame width the logo spans. 12% reads as a brand mark at 1280x720
# without competing with the content -- a logo big enough to notice is big enough to annoy.
LOGO_WIDTH_FRACTION = 0.12
# Inset from the frame edge, as a fraction of width, so the mark clears the safe area on
# a 9:16 crop as well as 16:9.
LOGO_MARGIN_FRACTION = 0.025
# Slightly transparent: a watermark, not a sticker.
LOGO_OPACITY = 0.88
MIN_LOGO_WIDTH_PX = 48


class BrandLogoOverlay:
    """Prepared logo state plus the per-frame blend."""

    @staticmethod
    def prepare(logo_path: Optional[str], frame_width: int, frame_height: int) -> Optional[Dict[str, Any]]:
        """
        Decode, scale and pre-multiply the logo once for a whole render.

        Returns None -- never raises -- when there is no logo or it cannot be read. A
        brand logo is decoration: a corrupt file must cost the user a watermark, not the
        video they waited four minutes for.
        """
        if not logo_path or not os.path.exists(logo_path):
            return None

        try:
            # IMREAD_UNCHANGED keeps the alpha channel; without it a transparent PNG
            # arrives as opaque BGR and the logo lands in a black box.
            raw = cv2.imread(logo_path, cv2.IMREAD_UNCHANGED)
            if raw is None:
                logger.warning(f"BrandLogoOverlay: could not decode '{logo_path}' -- skipping watermark.")
                return None

            target_w = max(MIN_LOGO_WIDTH_PX, int(frame_width * LOGO_WIDTH_FRACTION))
            scale = target_w / float(raw.shape[1])
            target_h = max(1, int(round(raw.shape[0] * scale)))
            # INTER_AREA is the right filter for downscaling; the default would alias the
            # fine edges most logos are made of.
            interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
            resized = cv2.resize(raw, (target_w, target_h), interpolation=interp)

            if resized.shape[2] == 4:
                bgr = resized[:, :, :3].astype(np.float32)
                alpha = (resized[:, :, 3:4].astype(np.float32) / 255.0) * LOGO_OPACITY
            else:
                bgr = resized[:, :, :3].astype(np.float32)
                alpha = np.full((target_h, target_w, 1), LOGO_OPACITY, dtype=np.float32)

            margin = max(8, int(frame_width * LOGO_MARGIN_FRACTION))
            x0 = frame_width - target_w - margin
            y0 = margin
            if x0 < 0 or y0 + target_h > frame_height:
                logger.warning(
                    f"BrandLogoOverlay: logo {target_w}x{target_h} does not fit a "
                    f"{frame_width}x{frame_height} frame -- skipping watermark."
                )
                return None

            logger.info(
                f"BrandLogoOverlay: '{os.path.basename(logo_path)}' prepared at "
                f"{target_w}x{target_h}px, top-right inset {margin}px."
            )
            return {
                "bgr": bgr,
                "alpha": alpha,
                # Pre-computed so stamp() does no arithmetic beyond the blend itself.
                "inv_alpha": 1.0 - alpha,
                "premultiplied": bgr * alpha,
                "x0": x0, "y0": y0, "x1": x0 + target_w, "y1": y0 + target_h,
            }
        except Exception as e:
            logger.warning(f"BrandLogoOverlay: preparation failed for '{logo_path}' ({e}) -- skipping watermark.")
            return None

    @staticmethod
    def stamp(frame: np.ndarray, prepared: Dict[str, Any]) -> None:
        """Alpha-blend the prepared logo into `frame`, in place."""
        try:
            roi = frame[prepared["y0"]:prepared["y1"], prepared["x0"]:prepared["x1"]]
            blended = prepared["premultiplied"] + roi.astype(np.float32) * prepared["inv_alpha"]
            roi[:] = np.clip(blended, 0, 255).astype(np.uint8)
        except Exception:
            # Per-frame: a warning here would emit thousands of identical lines and bury
            # the render log. prepare() already reported anything diagnosable.
            pass
