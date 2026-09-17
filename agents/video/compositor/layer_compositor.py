"""
ProfessionalLayerCompositor & RenderGraph Engine (Upgrade 5).
Non-destructive multi-layer rendering pipeline with keyframes, stacked effects, masking, and porter-duff blending.
"""
import time
import math
import cv2
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from agents.video.compositor.schemas import (
    BaseCompositorLayer, BackgroundLayer, VideoLayer, ImageLayer, ChartLayer, CaptionLayer,
    OverlayLayer, LogoLayer, LowerThirdLayer, ShapeLayer, TitleLayer,
    BlendMode, MaskType, LayerMask, EasingType, Keyframe, AnimationTrack,
    BlurEffect, ShadowEffect, GlowEffect, ColorGradeEffect, BrightnessEffect,
    ContrastEffect, TintEffect, SharpenEffect, VignetteEffect,
    DeclarativeSceneNode, FrameRenderStatistics, CompositorDiagnosticReport
)
from agents.video.compositor.resource_manager import ResourceManager
from agents.video.python_editor.animated_visuals import AnimatedVisualsEngine
from agents.video.python_editor.text_overlays import TextOverlayEngine
from agents.video.storyboard import VisualOverlay, TextLayer

logger = logging.getLogger("uvicorn")


class KeyframeEngine:
    """Evaluates multi-property keyframe animations with configurable easing curves."""

    @classmethod
    def apply_easing(cls, t: float, easing: EasingType) -> float:
        t = max(0.0, min(1.0, t))
        if easing == EasingType.LINEAR:
            return t
        elif easing == EasingType.EASE_IN_QUAD:
            return t * t
        elif easing == EasingType.EASE_OUT_QUAD:
            return t * (2.0 - t)
        elif easing == EasingType.EASE_IN_OUT_CUBIC:
            return 4.0 * t * t * t if t < 0.5 else 1.0 - math.pow(-2.0 * t + 2.0, 3.0) / 2.0
        elif easing == EasingType.SPRING_BOUNCE:
            return math.sin(t * math.pi * 3.5) * (1.0 - t) + t
        return t

    @classmethod
    def evaluate_float(cls, tracks: List[AnimationTrack], prop_name: str, current_time: float, default_val: float) -> float:
        target_track = next((tr for tr in tracks if tr.target_property == prop_name), None)
        if not target_track or not target_track.keyframes:
            return default_val

        kfs = sorted(target_track.keyframes, key=lambda k: k.timestamp_sec)
        if current_time <= kfs[0].timestamp_sec:
            return kfs[0].value.float_val if kfs[0].value.float_val is not None else default_val
        if current_time >= kfs[-1].timestamp_sec:
            return kfs[-1].value.float_val if kfs[-1].value.float_val is not None else default_val

        for i in range(len(kfs) - 1):
            k1, k2 = kfs[i], kfs[i + 1]
            if k1.timestamp_sec <= current_time <= k2.timestamp_sec:
                t = (current_time - k1.timestamp_sec) / max(k2.timestamp_sec - k1.timestamp_sec, 0.001)
                t_eased = cls.apply_easing(t, k2.easing)
                v1 = k1.value.float_val if k1.value.float_val is not None else default_val
                v2 = k2.value.float_val if k2.value.float_val is not None else default_val
                return v1 + (v2 - v1) * t_eased
        return default_val


class EffectsEngine:
    """Applies stackable visual effects sequentially onto layer offscreen buffers."""

    @classmethod
    def apply_effect_stack(cls, buffer: np.ndarray, effects: List[Any]) -> np.ndarray:
        if not effects:
            return buffer

        res = buffer.copy()
        for fx in effects:
            if not getattr(fx, "enabled", True):
                continue
            fx_type = getattr(fx, "effect_type", None)

            if fx_type == "blur":
                r = int(getattr(fx, "radius_px", 5.0))
                if r % 2 == 0:
                    r += 1
                if r > 1:
                    res = cv2.GaussianBlur(res, (r, r), 0)

            elif fx_type == "brightness":
                delta = float(getattr(fx, "delta", 0.0)) * 255.0
                res = cv2.addWeighted(res, 1.0, res, 0, delta)

            elif fx_type == "contrast":
                factor = float(getattr(fx, "factor", 1.0))
                res = cv2.convertScaleAbs(res, alpha=factor, beta=0)

            elif fx_type == "vignette":
                h, w = res.shape[:2]
                strength = float(getattr(fx, "strength", 0.30))
                Y, X = np.ogrid[:h, :w]
                cy, cx = h / 2, w / 2
                dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
                max_dist = np.sqrt(cx ** 2 + cy ** 2)
                vignette = np.clip(1.0 - strength * (dist / max_dist) ** 2, 0, 1).astype(np.float32)
                res = (res.astype(np.float32) * np.stack([vignette] * 3, axis=-1)).clip(0, 255).astype(np.uint8)

            elif fx_type == "sharpen":
                kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
                res = cv2.filter2D(res, -1, kernel)

        return res


class MaskEngine:
    """Clips layer offscreen buffer using geometric paths or alpha mattes."""

    @classmethod
    def apply_mask(cls, buffer: np.ndarray, mask: Optional[LayerMask]) -> np.ndarray:
        if not mask:
            return buffer

        h, w = buffer.shape[:2]
        mask_mat = np.ones((h, w), dtype=np.float32)

        if mask.mask_type == MaskType.CIRCLE:
            cx, cy = w // 2, h // 2
            r = min(cx, cy)
            cv_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(cv_mask, (cx, cy), r, 255, -1)
            mask_mat = cv_mask.astype(np.float32) / 255.0

        elif mask.mask_type == MaskType.ROUNDED_RECTANGLE:
            rad = int(mask.corner_radius * min(h, w) * 0.1)
            cv_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.rectangle(cv_mask, (rad, rad), (w - rad, h - rad), 255, -1)
            mask_mat = cv_mask.astype(np.float32) / 255.0

        if mask.invert:
            mask_mat = 1.0 - mask_mat

        mask_3ch = np.stack([mask_mat] * 3, axis=-1)
        return (buffer.astype(np.float32) * mask_3ch).clip(0, 255).astype(np.uint8)


class RenderGraph:
    """Execution Graph managing layer evaluation, offscreen buffers, and alpha blending."""

    @classmethod
    def render_layer(cls, layer: BaseCompositorLayer, frame_time_sec: float, scene_progress: float, width: int, height: int) -> Tuple[np.ndarray, float]:
        """Renders individual layer into offscreen buffer and applies animation + effects + mask."""
        if not layer.visible or frame_time_sec < layer.start_sec or frame_time_sec > layer.end_sec:
            return np.zeros((height, width, 3), dtype=np.uint8), 0.0

        # Evaluate keyframe animations
        opacity = KeyframeEngine.evaluate_float(layer.animation_tracks, "opacity", frame_time_sec, layer.opacity)
        scale_x = KeyframeEngine.evaluate_float(layer.animation_tracks, "scale_x", frame_time_sec, layer.transform.scale_x)
        scale_y = KeyframeEngine.evaluate_float(layer.animation_tracks, "scale_y", frame_time_sec, layer.transform.scale_y)
        rot_deg = KeyframeEngine.evaluate_float(layer.animation_tracks, "rotation", frame_time_sec, layer.transform.rotation_deg)

        buf = np.zeros((height, width, 3), dtype=np.uint8)

        # Draw specific layer type
        if isinstance(layer, BackgroundLayer):
            if layer.fill_style == "dark":
                buf[:] = (15, 10, 5)
            elif layer.fill_style == "light":
                buf[:] = (250, 250, 250)
            else:
                top_c = tuple(int(layer.colors[0].lstrip("#")[i:i+2], 16) for i in (4, 2, 0)) if layer.colors else (42, 23, 15)
                bot_c = tuple(int(layer.colors[-1].lstrip("#")[i:i+2], 16) for i in (4, 2, 0)) if len(layer.colors) > 1 else (20, 10, 5)
                for y in range(height):
                    ratio = y / max(height - 1, 1)
                    buf[y, :] = tuple(int(top_c[c] * (1 - ratio) + bot_c[c] * ratio) for c in range(3))

        elif isinstance(layer, ImageLayer):
            tex = ResourceManager.get_image(layer.asset_path, width, height)
            if tex is not None:
                buf[:] = tex

        elif isinstance(layer, ChartLayer):
            vo = VisualOverlay(
                overlay_type=layer.chart_type,
                title=layer.title,
                data_labels=layer.labels,
                data_values=layer.data
            )
            AnimatedVisualsEngine.render_overlay(buf, vo, width, height, scene_progress)

        elif isinstance(layer, TitleLayer):
            tl = TextLayer(text=layer.title_text, position="center", font_scale=1.5, entrance="instant")
            TextOverlayEngine.render_text_layers(buf, [tl], width, height, scene_progress=scene_progress)

        elif isinstance(layer, LowerThirdLayer):
            cv2.rectangle(buf, (int(width * 0.05), int(height * 0.75)), (int(width * 0.40), int(height * 0.88)), (30, 30, 30), -1)
            cv2.putText(buf, layer.name_text, (int(width * 0.07), int(height * 0.80)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (248, 250, 252), 2, cv2.LINE_AA)
            cv2.putText(buf, layer.title_text, (int(width * 0.07), int(height * 0.85)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (148, 163, 184), 1, cv2.LINE_AA)

        elif isinstance(layer, ShapeLayer):
            x1, y1 = int(width * 0.2), int(height * 0.2)
            x2, y2 = int(width * 0.8), int(height * 0.8)
            cv2.rectangle(buf, (x1, y1), (x2, y2), (56, 189, 248), -1)

        # Apply sub-pixel scaling & rotation affine transform if non-default
        if scale_x != 1.0 or scale_y != 1.0 or rot_deg != 0.0:
            M = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), rot_deg, scale_x)
            buf = cv2.warpAffine(buf, M, (width, height), borderMode=cv2.BORDER_REFLECT_101)

        # Apply stackable visual effects
        buf = EffectsEngine.apply_effect_stack(buf, layer.effects)

        # Apply layer mask
        buf = MaskEngine.apply_mask(buf, layer.mask)

        return buf, opacity


class ProfessionalLayerCompositor:
    """
    Master Non-Destructive Multi-Layer Compositing Engine.
    Consumes declarative SceneGraph and outputs composited NumPy BGR frames.
    """

    @classmethod
    def render_scene_frame(
        cls,
        scene_node: DeclarativeSceneNode,
        local_frame: int,
        total_scene_frames: int,
        global_frame: int
    ) -> Tuple[np.ndarray, FrameRenderStatistics]:
        t0 = time.time()
        width, height = scene_node.width, scene_node.height
        scene_progress = (local_frame + 1) / max(total_scene_frames, 1)
        frame_time_sec = local_frame / max(scene_node.fps, 1)

        # 1. Collect all layers across groups and sort by z_index
        all_layers: List[BaseCompositorLayer] = []
        for grp in [
            scene_node.background_group, scene_node.media_group,
            scene_node.graphics_group, scene_node.text_group, scene_node.overlay_group
        ]:
            if grp and hasattr(grp, "layers"):
                for lyr in grp.layers:
                    if hasattr(lyr, "z_index"):
                        lyr.z_index = getattr(lyr, "z_index", 0) + grp.z_index_base
                    all_layers.append(lyr)

        all_layers.sort(key=lambda l: getattr(l, "z_index", 0))

        # 2. Composite layers sequentially onto target master frame buffer
        master_buffer = np.zeros((height, width, 3), dtype=np.uint8)
        layers_rendered = 0
        effects_rendered = 0
        blend_ops = 0
        warnings = []

        ResourceManager.reset_stats()

        for layer in all_layers:
            if not getattr(layer, "visible", True):
                continue

            offscreen, opacity = RenderGraph.render_layer(layer, frame_time_sec, scene_progress, width, height)
            if opacity <= 0.0:
                continue

            # Alpha blending
            if opacity >= 0.99 and getattr(layer, "blend_mode", BlendMode.NORMAL) == BlendMode.NORMAL:
                # Direct overwrite for opaque normal layers
                non_zero = (offscreen > 0)
                master_buffer[non_zero] = offscreen[non_zero]
            else:
                alpha_mat = opacity * (offscreen.astype(np.float32) / 255.0)
                master_buffer = (master_buffer.astype(np.float32) * (1.0 - alpha_mat) + offscreen.astype(np.float32) * alpha_mat).clip(0, 255).astype(np.uint8)

            layers_rendered += 1
            effects_rendered += len(getattr(layer, "effects", []))
            blend_ops += 1

        hits, misses = ResourceManager.get_stats()
        latency_ms = (time.time() - t0) * 1000.0

        stats = FrameRenderStatistics(
            frame_index=local_frame,
            scene_id=scene_node.scene_id,
            render_latency_ms=round(latency_ms, 2),
            cache_hits=hits,
            cache_misses=misses,
            layers_rendered=layers_rendered,
            effects_rendered=effects_rendered,
            blend_operations=blend_ops,
            memory_usage_mb=round(master_buffer.nbytes / (1024.0 * 1024.0), 2),
            warnings=warnings
        )

        return master_buffer, stats
