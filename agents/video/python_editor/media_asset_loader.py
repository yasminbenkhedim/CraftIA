"""
MediaAssetLoader — Production-grade media asset loading, validation, and preparation
for the VideoRenderer compositing pipeline.

Decoding pipeline:
  candidate validation
  → secure path validation
  → MIME/type detection
  → safe decoding (Pillow Image.open + verify)
  → EXIF transpose (ImageOps.exif_transpose)
  → RGB normalization
  → quality validation (variance, entropy, unique-color ratio)
  → aspect-ratio-preserving cover crop
  → renderer format conversion (RGB → BGR for OpenCV/FFmpeg)
  → structured LoadedMediaAsset result
"""

import os
import time
import hashlib
import logging
import mimetypes
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Set

import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger("uvicorn")


# ============================================================================
# TYPED MODELS
# ============================================================================

class MediaLoadStatus(str, Enum):
    """Exhaustive enumeration of all possible load outcomes."""
    LOADED = "loaded"
    FALLBACK_NO_CANDIDATE = "fallback_no_candidate"
    FALLBACK_NONE_PATH = "fallback_none_path"
    FALLBACK_PATH_OUTSIDE_ROOT = "fallback_path_outside_root"
    FALLBACK_FILE_MISSING = "fallback_file_missing"
    FALLBACK_UNSUPPORTED_MIME = "fallback_unsupported_mime"
    FALLBACK_FILE_TOO_LARGE = "fallback_file_too_large"
    FALLBACK_DIMENSIONS_TOO_LARGE = "fallback_dimensions_too_large"
    FALLBACK_DECODE_ERROR = "fallback_decode_error"
    FALLBACK_ZERO_DIMENSIONS = "fallback_zero_dimensions"
    FALLBACK_LOW_INFORMATION = "fallback_low_information"
    FALLBACK_STOCK_VIDEO = "fallback_stock_video"
    FALLBACK_PLACEHOLDER = "fallback_placeholder"


@dataclass
class AssetAttribution:
    """Attribution metadata preserved from the provider for the final manifest."""
    provider_id: str = ""
    source_url: Optional[str] = None
    creator: Optional[str] = None
    license_name: Optional[str] = None
    license_url: Optional[str] = None
    attribution_text: Optional[str] = None


@dataclass
class LoadedMediaAsset:
    """Structured result from MediaAssetLoader.load()."""
    path: Optional[str] = None
    provider_id: str = ""
    media_type: str = ""
    source_width: int = 0
    source_height: int = 0
    output_width: int = 0
    output_height: int = 0
    channels: int = 3
    mime_type: Optional[str] = None
    file_size_bytes: int = 0
    pixel_variance: float = 0.0
    grayscale_entropy: float = 0.0
    unique_color_ratio: float = 0.0
    load_status: MediaLoadStatus = MediaLoadStatus.FALLBACK_NO_CANDIDATE
    fallback_reason: Optional[str] = None
    frame: Optional[np.ndarray] = None  # BGR frame ready for renderer, or None
    is_video: bool = False
    video_frames: Optional[List[np.ndarray]] = None  # Decoded BGR clip frames, or None for stills
    video_source_fps: float = 0.0
    attribution: AssetAttribution = field(default_factory=AssetAttribution)
    load_latency_ms: float = 0.0
    transform_latency_ms: float = 0.0


# ============================================================================
# CONFIGURABLE SAFETY LIMITS
# ============================================================================

@dataclass
class MediaAssetLoaderConfig:
    """All safety thresholds and limits — configurable, not hardcoded."""
    # File size limits
    max_file_size_bytes: int = 100 * 1024 * 1024  # 100 MB

    # Dimension limits
    max_source_width: int = 16384
    max_source_height: int = 16384
    max_decoded_pixel_count: int = 100_000_000  # 100 megapixels

    # Supported MIME types
    supported_mime_types: Set[str] = field(default_factory=lambda: {
        "image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp",
    })

    # Supported video MIME types / extensions (routed to the video decode path)
    supported_video_mime_types: Set[str] = field(default_factory=lambda: {
        "video/mp4", "video/quicktime", "video/webm", "video/x-msvideo",
    })
    supported_video_extensions: Set[str] = field(default_factory=lambda: {
        ".mp4", ".mov", ".webm", ".avi",
    })

    # Video decode limits
    max_video_file_size_bytes: int = 200 * 1024 * 1024  # 200 MB
    max_video_decode_frames: int = 450  # ~15s at 30fps -- caps decode time/memory for a clip

    # Quality thresholds (low-information detection)
    min_pixel_variance: float = 10.0     # Reject near-solid-color images
    min_grayscale_entropy: float = 1.5   # Reject near-uniform grayscale distributions
    min_unique_color_ratio: float = 0.001  # Reject images with <0.1% unique colors

    # Approved asset directories (empty = allow all — for backward compatibility)
    approved_asset_roots: List[str] = field(default_factory=list)

    # Interpolation
    downscale_interpolation: int = 1   # PIL.Image.LANCZOS
    upscale_interpolation: int = 1     # PIL.Image.LANCZOS


# Singleton default config — can be replaced at application startup
_default_config = MediaAssetLoaderConfig()


def get_config() -> MediaAssetLoaderConfig:
    return _default_config


def set_config(config: MediaAssetLoaderConfig):
    global _default_config
    _default_config = config


# ============================================================================
# MEDIA ASSET LOADER
# ============================================================================

class MediaAssetLoader:
    """
    Production media asset loader with explicit staged pipeline.
    Loads once per scene, caches nothing inside the loader itself —
    the renderer is responsible for reusing the returned frame across frames.
    """

    @classmethod
    def load(
        cls,
        candidate,  # MediaCandidate or None
        width: int,
        height: int,
        config: Optional[MediaAssetLoaderConfig] = None,
    ) -> LoadedMediaAsset:
        """
        Full staged loading pipeline. Returns LoadedMediaAsset with either
        a renderer-ready BGR frame or None (fallback to procedural).
        """
        cfg = config or get_config()
        t_start = time.perf_counter()
        result = LoadedMediaAsset(output_width=width, output_height=height)

        # ── Stage 1: Candidate Validation ──
        status, reason = cls._validate_candidate(candidate)
        if status is not None:
            result.load_status = status
            result.fallback_reason = reason
            if candidate is not None:
                result.provider_id = getattr(candidate, "provider_id", "")
                result.media_type = cls._get_media_type_str(candidate)
                result.attribution = cls._extract_attribution(candidate)
            result.load_latency_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"MediaAssetLoader: {status.value} — {reason}")
            return result

        # Candidate is valid, extract metadata
        asset_path = candidate.asset_path
        result.provider_id = getattr(candidate, "provider_id", "")
        result.media_type = cls._get_media_type_str(candidate)
        result.path = asset_path
        result.attribution = cls._extract_attribution(candidate)

        # ── Stage 2: Secure Path Validation ──
        status, reason = cls._validate_path_security(asset_path, cfg)
        if status is not None:
            result.load_status = status
            result.fallback_reason = reason
            result.load_latency_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"MediaAssetLoader: {status.value} — {reason}")
            return result

        # ── Stage 3: MIME/Type Detection ──
        mime_type = cls._detect_mime_type(asset_path)
        result.mime_type = mime_type

        ext = os.path.splitext(asset_path)[1].lower()
        media_type_val = cls._get_media_type_str(candidate)
        if mime_type in cfg.supported_video_mime_types or ext in cfg.supported_video_extensions or media_type_val in ("stock_video", "generated_video"):
            return cls._load_video(asset_path, width, height, cfg, result, t_start)

        if mime_type not in cfg.supported_mime_types:
            result.load_status = MediaLoadStatus.FALLBACK_UNSUPPORTED_MIME
            result.fallback_reason = f"MIME type '{mime_type}' not in supported set {cfg.supported_mime_types}"
            result.load_latency_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
            return result

        # ── Stage 4: File Size Check ──
        try:
            file_size = os.path.getsize(asset_path)
        except OSError as e:
            result.load_status = MediaLoadStatus.FALLBACK_FILE_MISSING
            result.fallback_reason = f"Cannot stat file: {e}"
            result.load_latency_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
            return result

        result.file_size_bytes = file_size
        if file_size > cfg.max_file_size_bytes:
            result.load_status = MediaLoadStatus.FALLBACK_FILE_TOO_LARGE
            result.fallback_reason = f"File size {file_size} bytes exceeds limit {cfg.max_file_size_bytes}"
            result.load_latency_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
            return result

        t_decode_start = time.perf_counter()

        # ── Stage 5: Safe Decoding ──
        try:
            img = Image.open(asset_path)
            img.verify()  # Check file integrity without fully loading
            img = Image.open(asset_path)  # Re-open after verify (verify invalidates)
        except Exception as e:
            result.load_status = MediaLoadStatus.FALLBACK_DECODE_ERROR
            result.fallback_reason = f"Pillow decode/verify failed: {e}"
            result.load_latency_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
            return result

        # Check source dimensions before full load
        src_w, src_h = img.size
        result.source_width = src_w
        result.source_height = src_h

        if src_w == 0 or src_h == 0:
            img.close()
            result.load_status = MediaLoadStatus.FALLBACK_ZERO_DIMENSIONS
            result.fallback_reason = f"Image has zero dimensions ({src_w}x{src_h})"
            result.load_latency_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
            return result

        if src_w > cfg.max_source_width or src_h > cfg.max_source_height:
            img.close()
            result.load_status = MediaLoadStatus.FALLBACK_DIMENSIONS_TOO_LARGE
            result.fallback_reason = f"Source dimensions {src_w}x{src_h} exceed limits {cfg.max_source_width}x{cfg.max_source_height}"
            result.load_latency_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
            return result

        if src_w * src_h > cfg.max_decoded_pixel_count:
            img.close()
            result.load_status = MediaLoadStatus.FALLBACK_DIMENSIONS_TOO_LARGE
            result.fallback_reason = f"Pixel count {src_w * src_h} exceeds limit {cfg.max_decoded_pixel_count}"
            result.load_latency_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
            return result

        # ── Stage 6: EXIF Transpose ──
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass  # Non-fatal: if EXIF data is malformed, proceed with original orientation

        # Update dimensions after possible rotation
        src_w, src_h = img.size
        result.source_width = src_w
        result.source_height = src_h

        # ── Stage 7: RGB Normalization ──
        if img.mode == "RGBA":
            # Composite onto white background
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Convert to numpy array for quality metrics
        rgb_array = np.array(img)
        result.channels = rgb_array.shape[2] if len(rgb_array.shape) == 3 else 1

        # ── Stage 8: Quality Validation ──
        pixel_variance = float(np.var(rgb_array.astype(np.float32)))
        result.pixel_variance = round(pixel_variance, 4)

        # Grayscale entropy
        gray = np.mean(rgb_array.astype(np.float32), axis=2).astype(np.uint8) if len(rgb_array.shape) == 3 else rgb_array
        hist, _ = np.histogram(gray.ravel(), bins=256, range=(0, 256))
        hist = hist.astype(np.float64)
        hist = hist[hist > 0]
        total_px = gray.size
        probs = hist / total_px
        entropy = -np.sum(probs * np.log2(probs))
        result.grayscale_entropy = round(float(entropy), 4)

        # Unique color ratio (sample for performance on large images)
        sample_size = min(100_000, rgb_array.shape[0] * rgb_array.shape[1])
        if rgb_array.shape[0] * rgb_array.shape[1] > sample_size:
            flat = rgb_array.reshape(-1, 3)
            indices = np.random.default_rng(42).choice(flat.shape[0], size=sample_size, replace=False)
            sample = flat[indices]
        else:
            sample = rgb_array.reshape(-1, 3)
        unique_colors = len(np.unique(sample, axis=0))
        result.unique_color_ratio = round(unique_colors / max(sample.shape[0], 1), 6)

        if pixel_variance < cfg.min_pixel_variance:
            img.close()
            result.load_status = MediaLoadStatus.FALLBACK_LOW_INFORMATION
            result.fallback_reason = f"Pixel variance {pixel_variance:.4f} below threshold {cfg.min_pixel_variance}"
            result.load_latency_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
            return result

        if entropy < cfg.min_grayscale_entropy:
            img.close()
            result.load_status = MediaLoadStatus.FALLBACK_LOW_INFORMATION
            result.fallback_reason = f"Grayscale entropy {entropy:.4f} below threshold {cfg.min_grayscale_entropy}"
            result.load_latency_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
            return result

        if result.unique_color_ratio < cfg.min_unique_color_ratio:
            img.close()
            result.load_status = MediaLoadStatus.FALLBACK_LOW_INFORMATION
            result.fallback_reason = f"Unique color ratio {result.unique_color_ratio:.6f} below threshold {cfg.min_unique_color_ratio}"
            result.load_latency_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
            return result

        # ── Stage 9: Aspect-Ratio-Preserving Cover Crop ──
        t_transform_start = time.perf_counter()

        # Determine scaling: cover the target dimensions (no black bars)
        scale = max(width / float(src_w), height / float(src_h))
        new_w = int(round(src_w * scale))
        new_h = int(round(src_h * scale))

        # Choose interpolation based on scaling direction
        if scale < 1.0:
            # Downscaling: use LANCZOS for quality
            resample = Image.LANCZOS
        else:
            # Upscaling: use LANCZOS (high quality)
            resample = Image.LANCZOS

        img_resized = img.resize((new_w, new_h), resample=resample)
        img.close()

        # Center crop to exact target dimensions
        left = (new_w - width) // 2
        top = (new_h - height) // 2
        img_cropped = img_resized.crop((left, top, left + width, top + height))
        img_resized.close()

        # ── Stage 10: Renderer Format Conversion (RGB → BGR) ──
        rgb_final = np.array(img_cropped)
        img_cropped.close()

        # Convert RGB to BGR for OpenCV/FFmpeg pipeline
        bgr_frame = rgb_final[:, :, ::-1].copy()

        # Apply subtle unsharp mask filter for crisp 1080p/4K presentation
        try:
            import cv2
            gaussian_blur = cv2.GaussianBlur(bgr_frame, (0, 0), sigmaX=1.2)
            bgr_frame = cv2.addWeighted(bgr_frame, 1.25, gaussian_blur, -0.25, 0)
        except Exception as e:
            logger.debug(f"MediaAssetLoader: Sharpening skipped: {e}")

        result.frame = bgr_frame
        result.output_width = bgr_frame.shape[1]
        result.output_height = bgr_frame.shape[0]
        result.load_status = MediaLoadStatus.LOADED
        result.fallback_reason = None

        t_end = time.perf_counter()
        result.transform_latency_ms = round((t_end - t_transform_start) * 1000, 2)
        result.load_latency_ms = round((t_end - t_start) * 1000, 2)

        logger.info(
            f"MediaAssetLoader: LOADED '{asset_path}' "
            f"({result.source_width}x{result.source_height} → {width}x{height}) "
            f"provider={result.provider_id} "
            f"variance={result.pixel_variance:.1f} entropy={result.grayscale_entropy:.2f} "
            f"unique_ratio={result.unique_color_ratio:.4f} "
            f"load={result.load_latency_ms:.1f}ms transform={result.transform_latency_ms:.1f}ms"
        )

        return result

    @classmethod
    def _load_video(
        cls,
        asset_path: str,
        width: int,
        height: int,
        cfg: MediaAssetLoaderConfig,
        result: LoadedMediaAsset,
        t_start: float,
    ) -> LoadedMediaAsset:
        """
        Decodes a short stock-video clip (mp4/mov/webm) into a sequence of renderer-ready
        BGR frames, cover-cropped to (width, height). Used in place of a single static
        image so a scene shows genuine footage motion instead of a Ken-Burns-panned photo.
        """
        import cv2

        try:
            file_size = os.path.getsize(asset_path)
        except OSError as e:
            result.load_status = MediaLoadStatus.FALLBACK_FILE_MISSING
            result.fallback_reason = f"Cannot stat file: {e}"
            result.load_latency_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
            return result

        result.file_size_bytes = file_size
        if file_size > cfg.max_video_file_size_bytes:
            result.load_status = MediaLoadStatus.FALLBACK_FILE_TOO_LARGE
            result.fallback_reason = f"Video file size {file_size} bytes exceeds limit {cfg.max_video_file_size_bytes}"
            result.load_latency_ms = (time.perf_counter() - t_start) * 1000
            logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
            return result

        t_decode_start = time.perf_counter()
        cap = cv2.VideoCapture(asset_path)
        try:
            if not cap.isOpened():
                result.load_status = MediaLoadStatus.FALLBACK_DECODE_ERROR
                result.fallback_reason = "OpenCV could not open the video container"
                result.load_latency_ms = (time.perf_counter() - t_start) * 1000
                logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
                return result

            src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            result.source_width = src_w
            result.source_height = src_h

            if src_w <= 0 or src_h <= 0:
                result.load_status = MediaLoadStatus.FALLBACK_ZERO_DIMENSIONS
                result.fallback_reason = f"Video has zero/invalid dimensions ({src_w}x{src_h})"
                result.load_latency_ms = (time.perf_counter() - t_start) * 1000
                logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
                return result

            result.video_source_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)

            # Aspect-ratio-preserving cover crop, computed once for the whole clip
            scale = max(width / float(src_w), height / float(src_h))
            new_w = max(1, int(round(src_w * scale)))
            new_h = max(1, int(round(src_h * scale)))
            left = max(0, (new_w - width) // 2)
            top = max(0, (new_h - height) // 2)
            interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LANCZOS4

            frames: List[np.ndarray] = []
            while len(frames) < cfg.max_video_decode_frames:
                ok, raw_frame = cap.read()
                if not ok or raw_frame is None:
                    break
                resized = cv2.resize(raw_frame, (new_w, new_h), interpolation=interp)
                cropped = resized[top:top + height, left:left + width]
                frames.append(cropped)

            if not frames:
                result.load_status = MediaLoadStatus.FALLBACK_DECODE_ERROR
                result.fallback_reason = "Video container opened but no frames could be decoded"
                result.load_latency_ms = (time.perf_counter() - t_start) * 1000
                logger.info(f"MediaAssetLoader: {result.load_status.value} — {result.fallback_reason}")
                return result

            result.frame = frames[0]
            result.video_frames = frames
            result.is_video = True
            result.output_width = width
            result.output_height = height
            result.load_status = MediaLoadStatus.LOADED
            result.fallback_reason = None

            t_end = time.perf_counter()
            result.transform_latency_ms = round((t_end - t_decode_start) * 1000, 2)
            result.load_latency_ms = round((t_end - t_start) * 1000, 2)

            logger.info(
                f"MediaAssetLoader: LOADED video '{asset_path}' "
                f"({result.source_width}x{result.source_height} → {width}x{height}, "
                f"{len(frames)} frames @ {result.video_source_fps:.1f}fps source) "
                f"provider={result.provider_id} "
                f"load={result.load_latency_ms:.1f}ms transform={result.transform_latency_ms:.1f}ms"
            )
            return result
        finally:
            cap.release()

    # ──────────────────────────────────────────────────────────────────────
    # Stage Helpers
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_candidate(candidate) -> tuple:
        """Stage 1: Validate the MediaCandidate object itself."""
        if candidate is None:
            return MediaLoadStatus.FALLBACK_NO_CANDIDATE, "No media candidate attached to segment"

        # Check candidate_status
        status_val = getattr(candidate.candidate_status, "value", str(candidate.candidate_status))
        if status_val in ("procedural_placeholder", "PROCEDURAL_PLACEHOLDER"):
            return MediaLoadStatus.FALLBACK_PLACEHOLDER, f"Candidate status is {status_val} (stub provider)"

        # Check asset_path
        asset_path = getattr(candidate, "asset_path", None)
        if not asset_path:
            return MediaLoadStatus.FALLBACK_NONE_PATH, "Candidate has no asset_path"

        # Check render-ready status
        if status_val not in ("validated_render_ready", "VALIDATED_RENDER_READY"):
            return MediaLoadStatus.FALLBACK_DECODE_ERROR, f"Candidate status '{status_val}' is not render-ready"

        return None, None  # Valid

    @staticmethod
    def _validate_path_security(asset_path: str, cfg: MediaAssetLoaderConfig) -> tuple:
        """Stage 2: Validate path security — prevent traversal and unauthorized access."""
        try:
            resolved = os.path.realpath(asset_path)
        except (ValueError, OSError) as e:
            return MediaLoadStatus.FALLBACK_PATH_OUTSIDE_ROOT, f"Cannot resolve path: {e}"

        # Path traversal detection
        if ".." in Path(asset_path).parts:
            return MediaLoadStatus.FALLBACK_PATH_OUTSIDE_ROOT, f"Path contains '..' traversal: {asset_path}"

        # Check against approved roots (if configured)
        if cfg.approved_asset_roots:
            allowed = False
            for root in cfg.approved_asset_roots:
                try:
                    resolved_root = os.path.realpath(root)
                    if resolved.startswith(resolved_root):
                        allowed = True
                        break
                except (ValueError, OSError):
                    continue
            if not allowed:
                return MediaLoadStatus.FALLBACK_PATH_OUTSIDE_ROOT, f"Path '{resolved}' not under any approved root: {cfg.approved_asset_roots}"

        # File existence
        if not os.path.isfile(resolved):
            return MediaLoadStatus.FALLBACK_FILE_MISSING, f"File does not exist: {resolved}"

        return None, None

    @staticmethod
    def _detect_mime_type(asset_path: str) -> str:
        """Stage 3: Detect MIME type from file extension."""
        mime, _ = mimetypes.guess_type(asset_path)
        return mime or "application/octet-stream"

    @staticmethod
    def _get_media_type_str(candidate) -> str:
        """Extract media_type as string from candidate."""
        mt = getattr(candidate, "media_type", None)
        if mt is None:
            return ""
        return getattr(mt, "value", str(mt))

    @staticmethod
    def _extract_attribution(candidate) -> AssetAttribution:
        """Extract attribution metadata from candidate for manifest preservation."""
        meta = getattr(candidate, "generation_metadata", {}) or {}
        return AssetAttribution(
            provider_id=getattr(candidate, "provider_id", ""),
            source_url=getattr(candidate, "remote_url", None),
            creator=meta.get("creator") or meta.get("author"),
            license_name=getattr(candidate, "license_name", None),
            license_url=meta.get("license_url"),
            attribution_text=getattr(candidate, "attribution", None),
        )

    @classmethod
    def compute_cache_key(cls, asset_path: str, width: int, height: int) -> str:
        """Compute a deterministic cache key from path + dimensions + mtime."""
        try:
            mtime = os.path.getmtime(asset_path)
            file_size = os.path.getsize(asset_path)
        except OSError:
            mtime = 0.0
            file_size = 0
        raw = f"{os.path.realpath(asset_path)}|{width}x{height}|{mtime}|{file_size}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @classmethod
    def diagnostics_dict(cls, result: LoadedMediaAsset) -> Dict[str, Any]:
        """Return structured diagnostics for logging/manifest."""
        return {
            "path": result.path,
            "provider_id": result.provider_id,
            "media_type": result.media_type,
            "source_dimensions": f"{result.source_width}x{result.source_height}",
            "output_dimensions": f"{result.output_width}x{result.output_height}",
            "channels": result.channels,
            "mime_type": result.mime_type,
            "file_size_bytes": result.file_size_bytes,
            "pixel_variance": result.pixel_variance,
            "grayscale_entropy": result.grayscale_entropy,
            "unique_color_ratio": result.unique_color_ratio,
            "load_status": result.load_status.value,
            "fallback_reason": result.fallback_reason,
            "has_frame": result.frame is not None,
            "is_video": result.is_video,
            "video_frame_count": len(result.video_frames) if result.video_frames else 0,
            "video_source_fps": result.video_source_fps,
            "load_latency_ms": result.load_latency_ms,
            "transform_latency_ms": result.transform_latency_ms,
            "attribution": {
                "provider_id": result.attribution.provider_id,
                "source_url": result.attribution.source_url,
                "creator": result.attribution.creator,
                "license_name": result.attribution.license_name,
                "license_url": result.attribution.license_url,
                "attribution_text": result.attribution.attribution_text,
            },
        }
