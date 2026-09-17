"""
Ken Burns Motion Engine v1 (Resolution-Relative Affine Camera Motion)
Applies sub-pixel camera zooms and pans to video frame buffers using cv2.warpAffine
and smooth cosine easing S(t) = (1 - cos(pi * t)) / 2.

All spatial offsets and center pivots are strictly resolution-relative (computed as
fractions of frame width and height), ensuring identical motion relative to the canvas
at 360p, 720p, 1080p, and 4K resolutions.
"""
import math
import cv2
import numpy as np
import logging

logger = logging.getLogger("uvicorn")


class KenBurnsMotionEngine:
    """
    Sub-pixel Resolution-Relative Ken Burns Camera Motion Engine.
    Computes progressive zoom scaling z(t) and pan offsets (dx(t), dy(t))
    using smooth cosine easing S(t) = (1 - cos(pi * t)) / 2.
    """

    @classmethod
    def apply_motion(
        cls,
        frame: np.ndarray,
        progress: float,
        motion_profile: str = "zoom_in",
        motion_zoom: float = 1.08
    ) -> np.ndarray:
        """
        Applies resolution-relative Ken Burns affine transform (zoom/pan) to frame.
        progress: float in [0.0, 1.0]
        motion_profile: 'zoom_in', 'zoom_out', 'pan_left_to_right', 'pan_right_to_left'
        motion_zoom: float (e.g. 1.08)
        """
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return frame

        h, w = frame.shape[:2]
        progress = max(0.0, min(1.0, float(progress)))

        # Cosine Easing S(t) in [0.0, 1.0]: Zero initial and final acceleration
        s_t = (1.0 - math.cos(math.pi * progress)) / 2.0

        # Base parameters (Resolution-relative)
        cx, cy = w / 2.0, h / 2.0
        max_z = float(motion_zoom)

        # If motion_zoom <= 1.0, no camera motion — return frame unchanged
        if max_z <= 1.0:
            return frame

        scale = 1.00
        dx_frac = 0.00
        dy_frac = 0.00

        profile = (motion_profile or "zoom_in").lower()

        if "zoom_out" in profile or "pull_out" in profile:
            scale = max_z - (max_z - 1.00) * s_t
        elif "pan_left" in profile:
            scale = max(1.06, max_z * 0.98)
            dx_frac = -0.035 + 0.070 * s_t  # Pan across 7% frame width
        elif "pan_right" in profile:
            scale = max(1.06, max_z * 0.98)
            dx_frac = 0.035 - 0.070 * s_t   # Pan across 7% frame width
        elif "pan_up" in profile:
            scale = max(1.06, max_z * 0.98)
            dy_frac = 0.025 - 0.050 * s_t   # Tilt up 5% height
        elif "pan_down" in profile:
            scale = max(1.06, max_z * 0.98)
            dy_frac = -0.025 + 0.050 * s_t  # Tilt down 5% height
        elif "diagonal" in profile:
            scale = 1.00 + (max_z - 1.00) * s_t
            dx_frac = -0.02 + 0.04 * s_t
            dy_frac = -0.015 + 0.03 * s_t
        else:
            # Default: 'zoom_in' / 'dolly_push'
            scale = 1.00 + (max_z - 1.00) * s_t

        # Compute resolution-proportional pixel shift
        dx_px = w * dx_frac
        dy_px = h * dy_frac

        # 2x3 Affine Transformation Matrix around center (cx, cy)
        M = np.float32([
            [scale, 0, (1.0 - scale) * cx + dx_px],
            [0, scale, (1.0 - scale) * cy + dy_px]
        ])

        # Sub-pixel cubic warping for pristine motion clarity
        transformed = cv2.warpAffine(
            frame,
            M,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REFLECT_101
        )
        return transformed
