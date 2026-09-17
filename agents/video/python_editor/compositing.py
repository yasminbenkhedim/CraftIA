"""
Layer Compositing Engine v3 -- 12 Transitions & Floating Particle Physics.
Inspired by MoviePy compositing/ and vanta transition modules.

12 Transition Types:
  1. fade           - smooth alpha cross-fade
  2. slide_left     - horizontal push left
  3. slide_right    - horizontal push right
  4. slide_up       - vertical push up
  5. slide_down     - vertical push down
  6. iris_circle    - radial expanding circle mask
  7. whip_pan_blur  - high-speed motion-blur pan
  8. morph_crossfade- non-linear smooth S-curve cross-fade
  9. zoom_in        - scaling camera zoom in
  10. zoom_out      - scaling camera zoom out
  11. dissolve      - noise-blended pixel dissolve
  12. wipe          - diagonal split wipe
"""
import logging
import math
import cv2
import numpy as np
from typing import Tuple

logger = logging.getLogger("uvicorn")


class Compositor:
    """
    Frame compositor with 12 cinematic transitions, background fills,
    procedural floating particles, and vignette effects.
    """

    @staticmethod
    def fill_background(frame: np.ndarray, color_bgr: Tuple[int, int, int]):
        frame[:] = color_bgr

    @staticmethod
    def apply_gradient_overlay(frame: np.ndarray,
                                top_color: Tuple[int, int, int] = (42, 23, 15),
                                bottom_color: Tuple[int, int, int] = (20, 10, 5)):
        h = frame.shape[0]
        for y in range(h):
            ratio = y / max(h - 1, 1)
            blended = tuple(int(top_color[c] * (1 - ratio) + bottom_color[c] * ratio) for c in range(3))
            frame[y, :] = blended

    @staticmethod
    def apply_light_background(frame: np.ndarray):
        frame[:] = (250, 250, 250)

    @staticmethod
    def apply_dark_background(frame: np.ndarray):
        frame[:] = (15, 10, 5)

    @classmethod
    def apply_dense_noise_background(cls, frame: np.ndarray, progress: float = 0.5):
        h, w = frame.shape[:2]
        np.random.seed(int(progress * 1000) % 99991)
        noise = np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)
        grid_x, grid_y = np.meshgrid(np.linspace(0, 100, w), np.linspace(0, 100, h))
        grid_pattern = ((np.sin(grid_x + progress * 2.0) * np.cos(grid_y + progress * 2.0) + 1.0) * 127.5).astype(np.uint8)
        frame[:] = cv2.addWeighted(noise, 0.70, cv2.cvtColor(grid_pattern, cv2.COLOR_GRAY2BGR), 0.30, 0)

    # ---------------------------------------------------------------------------
    # Floating Particle Physics
    # ---------------------------------------------------------------------------

    @classmethod
    def apply_floating_particles(cls, frame: np.ndarray, progress: float,
                                 num_particles: int = 35):
        """
        Renders floating glowing particles drifting upward with sine-wave horizontal drift.
        """
        h, w = frame.shape[:2]
        np.random.seed(42)  # Deterministic particle seed per video
        base_x = np.random.uniform(0, w, num_particles)
        base_speed = np.random.uniform(0.3, 1.2, num_particles)
        radii = np.random.randint(2, 6, num_particles)
        alphas = np.random.uniform(0.3, 0.7, num_particles)

        overlay = frame.copy()
        for i in range(num_particles):
            # Upward vertical movement
            y = int((h - (progress * h * base_speed[i] * 1.5 + i * 20)) % h)
            # Sine-wave horizontal drift
            x = int((base_x[i] + math.sin(progress * 4 * math.pi + i) * 25) % w)
            radius = radii[i]
            color = (int(220 * alphas[i]), int(180 * alphas[i]), int(255 * alphas[i]))
            cv2.circle(overlay, (x, y), radius, color, -1, cv2.LINE_AA)

        # Alpha blend particle layer
        cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)

    # ---------------------------------------------------------------------------
    # 12 Cinematic Transitions
    # ---------------------------------------------------------------------------

    @staticmethod
    def apply_fade(frame: np.ndarray, alpha: float):
        """1. Fade transition."""
        if alpha < 1.0:
            frame[:] = (frame.astype(np.float32) * alpha).clip(0, 255).astype(np.uint8)

    @classmethod
    def apply_slide_left(cls, frame: np.ndarray, alpha: float):
        """2. Slide-left: content translates from right to final position via cv2.warpAffine.
        tx = w * (1 - alpha): at alpha=0 content is fully offscreen-right, at alpha=1 content is at rest.
        All offsets are resolution-relative (fraction of frame width)."""
        if alpha >= 1.0:
            return
        h, w = frame.shape[:2]
        tx = w * (1.0 - alpha)  # Resolution-relative horizontal offset
        M = np.float32([[1, 0, tx], [0, 1, 0]])
        frame[:] = cv2.warpAffine(frame, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))

    @classmethod
    def apply_slide_right(cls, frame: np.ndarray, alpha: float):
        """3. Slide-right: content translates from left to final position via cv2.warpAffine.
        tx = -w * (1 - alpha): at alpha=0 content is fully offscreen-left, at alpha=1 content is at rest.
        All offsets are resolution-relative (fraction of frame width)."""
        if alpha >= 1.0:
            return
        h, w = frame.shape[:2]
        tx = -w * (1.0 - alpha)  # Resolution-relative horizontal offset
        M = np.float32([[1, 0, tx], [0, 1, 0]])
        frame[:] = cv2.warpAffine(frame, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))

    @classmethod
    def apply_slide_up(cls, frame: np.ndarray, alpha: float):
        """4. Slide-up: content translates from below to final position via cv2.warpAffine.
        ty = h * (1 - alpha): at alpha=0 content is fully offscreen-bottom, at alpha=1 content is at rest.
        All offsets are resolution-relative (fraction of frame height)."""
        if alpha >= 1.0:
            return
        h, w = frame.shape[:2]
        ty = h * (1.0 - alpha)  # Resolution-relative vertical offset
        M = np.float32([[1, 0, 0], [0, 1, ty]])
        frame[:] = cv2.warpAffine(frame, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))

    @classmethod
    def apply_slide_down(cls, frame: np.ndarray, alpha: float):
        """5. Slide-down: content translates from above to final position via cv2.warpAffine.
        ty = -h * (1 - alpha): at alpha=0 content is fully offscreen-top, at alpha=1 content is at rest.
        All offsets are resolution-relative (fraction of frame height)."""
        if alpha >= 1.0:
            return
        h, w = frame.shape[:2]
        ty = -h * (1.0 - alpha)  # Resolution-relative vertical offset
        M = np.float32([[1, 0, 0], [0, 1, ty]])
        frame[:] = cv2.warpAffine(frame, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))

    @classmethod
    def apply_iris_circle(cls, frame: np.ndarray, progress: float):
        """6. Iris-circle radial expanding reveal."""
        if progress >= 1.0:
            return
        h, w = frame.shape[:2]
        max_r = int(math.sqrt(w ** 2 + h ** 2) / 2)
        r = int(max_r * progress)
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, (w // 2, h // 2), r, 255, -1)
        mask_3ch = np.stack([mask] * 3, axis=-1) / 255.0
        frame[:] = (frame.astype(np.float32) * mask_3ch).astype(np.uint8)

    @classmethod
    def apply_whip_pan_blur(cls, frame: np.ndarray, progress: float):
        """7. Whip-pan horizontal motion blur transition."""
        if progress >= 1.0 or progress <= 0.0:
            return
        blur_k = int(max(1, (1.0 - progress) * 31))
        if blur_k % 2 == 0:
            blur_k += 1
        frame[:] = cv2.GaussianBlur(frame, (blur_k, 1), 0)
        cls.apply_fade(frame, progress)

    @classmethod
    def apply_morph_crossfade(cls, frame: np.ndarray, progress: float):
        """8. Morph crossfade: non-linear smooth S-curve transition."""
        s_curve = 3 * (progress ** 2) - 2 * (progress ** 3)  # Smoothstep
        cls.apply_fade(frame, s_curve)

    @classmethod
    def apply_zoom_in(cls, frame: np.ndarray, progress: float, max_zoom: float = 1.15, mode: str = "transition"):
        """9. Zoom-in scaling transition: smooth center-pivot scale from max_zoom down to 1.0
        as progress goes 0->1. At progress=0, content is zoomed in (max_zoom scale),
        at progress=1, content is at rest (1.0 scale). Uses cv2.warpAffine for
        sub-pixel resolution-relative center-pivot scaling.
        Distinct from Ken Burns (which is persistent scene-long zoom)."""
        h, w = frame.shape[:2]
        if mode == "punch_in":
            scale = max_zoom if progress >= 0.30 else 1.0
        else:
            # Smooth transition: scale decreases from max_zoom to 1.0 as progress 0->1
            scale = max_zoom - (max_zoom - 1.0) * progress

        if scale <= 1.001:
            return
        # Resolution-relative center-pivot affine transform
        cx, cy = w / 2.0, h / 2.0
        M = np.float32([
            [scale, 0, (1.0 - scale) * cx],
            [0, scale, (1.0 - scale) * cy]
        ])
        frame[:] = cv2.warpAffine(frame, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)

    @classmethod
    def apply_zoom_out(cls, frame: np.ndarray, progress: float, max_zoom: float = 1.2):
        """10. Zoom-out scaling transition: smooth center-pivot scale from 1.0 up to max_zoom
        as progress goes 0->1. Uses cv2.warpAffine for resolution-relative sub-pixel scaling."""
        h, w = frame.shape[:2]
        scale = 1.0 + (max_zoom - 1.0) * progress
        if scale <= 1.001:
            return
        cx, cy = w / 2.0, h / 2.0
        M = np.float32([
            [scale, 0, (1.0 - scale) * cx],
            [0, scale, (1.0 - scale) * cy]
        ])
        frame[:] = cv2.warpAffine(frame, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)

    @classmethod
    def apply_dissolve(cls, frame: np.ndarray, alpha: float):
        """11. Dissolve noise cross-blend."""
        if alpha >= 1.0:
            return
        h, w = frame.shape[:2]
        noise = np.random.random((h, w)).astype(np.float32)
        mask = (noise < alpha).astype(np.float32)
        mask_3ch = np.stack([mask] * 3, axis=-1)
        frame[:] = (frame.astype(np.float32) * mask_3ch).clip(0, 255).astype(np.uint8)

    @classmethod
    def apply_wipe(cls, frame: np.ndarray, progress: float):
        """12. Diagonal split wipe transition."""
        if progress >= 1.0:
            return
        h, w = frame.shape[:2]
        Y, X = np.ogrid[:h, :w]
        mask = ((X + Y) / float(w + h)) <= progress
        mask_3ch = np.stack([mask.astype(np.float32)] * 3, axis=-1)
        frame[:] = (frame.astype(np.float32) * mask_3ch).astype(np.uint8)

    @classmethod
    def apply_vignette(cls, frame: np.ndarray, strength: float = 0.3):
        """Subtle vignette darkening at frame edges for cinematic look."""
        h, w = frame.shape[:2]
        Y, X = np.ogrid[:h, :w]
        cy, cx = h / 2, w / 2
        dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
        max_dist = np.sqrt(cx ** 2 + cy ** 2)
        vignette = 1.0 - strength * (dist / max_dist) ** 2
        vignette = np.clip(vignette, 0, 1).astype(np.float32)
        vignette_3ch = np.stack([vignette] * 3, axis=-1)
        frame[:] = (frame.astype(np.float32) * vignette_3ch).clip(0, 255).astype(np.uint8)

    @classmethod
    def compute_transition_alpha(cls, frame_idx: int, segment_frame_count: int,
                                  transition_frames: int,
                                  transition_type: str = "fade") -> float:
        if transition_type == "cut":
            return 1.0

        alpha = 1.0
        if frame_idx < transition_frames and transition_frames > 0:
            alpha = frame_idx / transition_frames
        remaining = segment_frame_count - frame_idx
        if remaining < transition_frames and transition_frames > 0:
            alpha = min(alpha, remaining / transition_frames)

        return max(0.0, min(1.0, alpha))
