"""
CandidateFeatureExtractor -- Deterministic Technical Computer Vision Feature Extractor (Upgrade 3).
Extracts blur, brightness, contrast, color harmony, and perceptual hashes (aHash/dHash/SHA-256)
on proportionally downsampled images.
"""
import os
import time
import hashlib
import logging
from typing import Optional, Tuple, List, Dict, Any
import numpy as np
import cv2
from PIL import Image, ImageOps

from agents.video.media_ranking_schemas import CandidateFeatures

logger = logging.getLogger("uvicorn")


class CandidateFeatureExtractor:
    """
    Deterministic Computer Vision Feature Extractor.
    Downsamples images (max side 1024px) before computing features.
    """

    MAX_DOWNSAMPLE_SIDE = 1024

    @classmethod
    def extract_features(
        cls,
        canonical_key: str,
        asset_path: str,
        max_downsample_side: int = 1024
    ) -> Optional[CandidateFeatures]:
        """
        Safely extracts technical features from an image file.
        Returns CandidateFeatures or None on error.
        """
        if not asset_path or not os.path.exists(asset_path):
            return None

        t0 = time.time()
        try:
            # 1. Compute SHA-256 of file content
            content_sha256 = cls._compute_sha256(asset_path)
            file_size = os.path.getsize(asset_path)

            # 2. Open with PIL and handle EXIF rotation
            with Image.open(asset_path) as raw_img:
                src_w, src_h = raw_img.size
                mime_type = Image.MIME.get(raw_img.format, "image/jpeg").lower()
                img = ImageOps.exif_transpose(raw_img)

            # 3. Compute Orientation & Aspect Ratio
            aspect_ratio = src_w / max(src_h, 1)
            if aspect_ratio >= 1.2:
                orientation = "landscape"
            elif aspect_ratio <= 0.8:
                orientation = "portrait"
            else:
                orientation = "square"

            megapixels = (src_w * src_h) / 1_000_000.0

            # 4. Proportional Downsampling (preserve aspect ratio, max side 1024)
            scale = min(1.0, max_downsample_side / float(max(src_w, src_h)))
            if scale < 1.0:
                ds_w = max(1, int(src_w * scale))
                ds_h = max(1, int(src_h * scale))
                img_ds = img.resize((ds_w, ds_h), Image.Resampling.LANCZOS)
            else:
                img_ds = img

            # Convert to RGB array
            if img_ds.mode != "RGB":
                img_ds = img_ds.convert("RGB")

            rgb_arr = np.array(img_ds, dtype=np.uint8)
            has_alpha = raw_img.mode in ("RGBA", "LA") or (raw_img.mode == "P" and "transparency" in raw_img.info)

            # 5. Compute Grayscale Array & OpenCV Metrics
            gray_arr = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2GRAY)

            # Blur Score (Variance of Laplacian)
            blur_score = float(cv2.Laplacian(gray_arr, cv2.CV_64F).var())

            # Exposure (Brightness, Contrast, Dynamic Range)
            brightness = float(np.mean(gray_arr))
            contrast = float(np.std(gray_arr))
            dynamic_range = float(np.ptp(gray_arr))  # max - min

            # Grayscale Shannon Entropy
            hist, _ = np.histogram(gray_arr, bins=256, range=(0, 256))
            probs = hist / float(gray_arr.size)
            probs = probs[probs > 0]
            grayscale_entropy = float(-np.sum(probs * np.log2(probs)))

            # Unique Color Ratio (Deterministic 10k sample)
            sample_size = min(10000, rgb_arr.shape[0] * rgb_arr.shape[1])
            flat_rgb = rgb_arr.reshape(-1, 3)
            sample_indices = np.linspace(0, len(flat_rgb) - 1, num=sample_size, dtype=int)
            unique_colors = len(np.unique(flat_rgb[sample_indices], axis=0))
            unique_color_ratio = float(unique_colors / float(sample_size))

            # 6. Dominant Colors (Quantized Color Sampling)
            dominant_colors = cls._extract_dominant_colors(rgb_arr)

            # 7. Perceptual Hashes (dHash and aHash)
            ahash = cls.compute_ahash(gray_arr)
            dhash = cls.compute_dhash(gray_arr)

            elapsed_ms = (time.time() - t0) * 1000.0

            return CandidateFeatures(
                canonical_key=canonical_key,
                width=src_w,
                height=src_h,
                megapixels=megapixels,
                aspect_ratio=aspect_ratio,
                orientation=orientation,
                file_size_bytes=file_size,
                mime_type=mime_type,
                brightness=brightness,
                contrast=contrast,
                dynamic_range=dynamic_range,
                blur_score=blur_score,
                dominant_colors=dominant_colors,
                unique_color_ratio=unique_color_ratio,
                grayscale_entropy=grayscale_entropy,
                has_alpha=has_alpha,
                ahash=ahash,
                dhash=dhash,
                content_sha256=content_sha256,
                extraction_latency_ms=elapsed_ms
            )

        except Exception as e:
            logger.error(f"CandidateFeatureExtractor: Feature extraction failed for '{asset_path}': {e}")
            return None

    @classmethod
    def compute_ahash(cls, gray_arr: np.ndarray, hash_size: int = 8) -> str:
        """Average Hash (aHash): 8x8 resize -> mean thresholding -> 64-bit hex."""
        resized = cv2.resize(gray_arr, (hash_size, hash_size), interpolation=cv2.INTER_AREA)
        avg = np.mean(resized)
        bits = resized > avg
        return f"{sum(2 ** i for (i, v) in enumerate(bits.flatten()) if v):016x}"

    @classmethod
    def compute_dhash(cls, gray_arr: np.ndarray, hash_size: int = 8) -> str:
        """Difference Hash (dHash): 9x8 resize -> horizontal gradient -> 64-bit hex."""
        resized = cv2.resize(gray_arr, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
        diff = resized[:, 1:] > resized[:, :-1]
        return f"{sum(2 ** i for (i, v) in enumerate(diff.flatten()) if v):016x}"

    @classmethod
    def _extract_dominant_colors(cls, rgb_arr: np.ndarray, k: int = 3) -> List[Tuple[int, int, int]]:
        """Extracts top K dominant colors using 3D spatial binning (fast & deterministic)."""
        flat = rgb_arr.reshape(-1, 3)
        # Quantize to 32-level bins (8x8x8 color cube)
        quantized = (flat // 32) * 32 + 16
        unique_bins, counts = np.unique(quantized, axis=0, return_counts=True)
        sorted_indices = np.argsort(-counts)

        dom_colors: List[Tuple[int, int, int]] = []
        for idx in sorted_indices[:k]:
            c = unique_bins[idx]
            dom_colors.append((int(c[0]), int(c[1]), int(c[2])))
        return dom_colors

    @classmethod
    def _compute_sha256(cls, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
