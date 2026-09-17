"""
Central ResourceManager for Professional Multi-Layer Compositor (Upgrade 5).
Owns images, videos, fonts, icons, charts, and masks with multi-level RAM/texture caching.
"""
import os
import cv2
import logging
import numpy as np
from typing import Dict, Any, Optional, Tuple
from PIL import ImageFont

logger = logging.getLogger("uvicorn")


class ResourceManager:
    """
    Central asset owner and thread-safe caching manager.
    Encapsulates image loading, font caching, chart surface caching, and frame buffer pooling.
    """

    _image_cache: Dict[str, np.ndarray] = {}
    _font_cache: Dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}
    _chart_cache: Dict[str, Tuple[np.ndarray, float]] = {}  # key -> (frame, cached_progress)
    _buffer_pool: Dict[Tuple[int, int], np.ndarray] = {}
    _cache_hits: int = 0
    _cache_misses: int = 0

    @classmethod
    def reset_stats(cls):
        cls._cache_hits = 0
        cls._cache_misses = 0

    @classmethod
    def get_stats(cls) -> Tuple[int, int]:
        return cls._cache_hits, cls._cache_misses

    @classmethod
    def get_image(cls, file_path: str, target_width: int = 1920, target_height: int = 1080) -> Optional[np.ndarray]:
        """Loads or retrieves a cached BGR image texture."""
        if not file_path or not os.path.exists(file_path):
            cls._cache_misses += 1
            return None

        cache_key = f"{file_path}_{target_width}x{target_height}"
        if cache_key in cls._image_cache:
            cls._cache_hits += 1
            return cls._image_cache[cache_key].copy()

        cls._cache_misses += 1
        try:
            img = cv2.imread(file_path, cv2.IMREAD_COLOR)
            if img is None:
                return None
            img_resized = cv2.resize(img, (target_width, target_height), interpolation=cv2.INTER_AREA)
            cls._image_cache[cache_key] = img_resized
            return img_resized.copy()
        except Exception as e:
            logger.warning(f"ResourceManager: Failed to load image '{file_path}': {e}")
            return None

    @classmethod
    def get_font(cls, font_family: str, font_size: int) -> Optional[ImageFont.FreeTypeFont]:
        """Retrieves a cached PIL FreeTypeFont instance."""
        cache_key = (font_family.lower(), font_size)
        if cache_key in cls._font_cache:
            cls._cache_hits += 1
            return cls._font_cache[cache_key]

        cls._cache_misses += 1
        try:
            font_path = "arial.ttf"
            if font_family.lower() == "roboto":
                font_path = "roboto.ttf"
            font = ImageFont.truetype(font_path, font_size)
            cls._font_cache[cache_key] = font
            return font
        except Exception:
            try:
                font = ImageFont.load_default()
                cls._font_cache[cache_key] = font
                return font
            except Exception:
                return None

    @classmethod
    def get_cached_chart_surface(cls, chart_id: str, progress: float, delta_thresh: float = 0.02) -> Optional[np.ndarray]:
        """Returns cached chart surface if animation progress has not shifted significantly."""
        if chart_id in cls._chart_cache:
            cached_surface, cached_p = cls._chart_cache[chart_id]
            if abs(progress - cached_p) < delta_thresh:
                cls._cache_hits += 1
                return cached_surface.copy()

        cls._cache_misses += 1
        return None

    @classmethod
    def put_chart_surface(cls, chart_id: str, surface: np.ndarray, progress: float):
        cls._chart_cache[chart_id] = (surface.copy(), progress)

    @classmethod
    def acquire_frame_buffer(cls, width: int, height: int) -> np.ndarray:
        """Provides a zeroed NumPy BGR frame buffer from the pool."""
        key = (width, height)
        if key in cls._buffer_pool:
            buf = cls._buffer_pool[key]
            buf.fill(0)
            return buf
        buf = np.zeros((height, width, 3), dtype=np.uint8)
        cls._buffer_pool[key] = buf
        return buf
