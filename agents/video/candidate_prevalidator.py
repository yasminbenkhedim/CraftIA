"""
CandidatePreValidator -- Fast Hard Policy Pre-Validation Layer for VideoAgent (Upgrade 3).
Filters candidate media before feature extraction & scoring against hard policy gates.
"""
import os
import logging
from typing import List, Tuple, Optional, Any, Set
from PIL import Image

from agents.video.media_ranking_schemas import (
    CandidateRejectionCode, RankedMediaCandidate
)
from agents.video.license_policy import LicensePolicyEvaluator

logger = logging.getLogger("uvicorn")


class CandidatePreValidator:
    """
    Pre-validation hard gates for media candidates.
    """

    APPROVED_STORAGE_SUBDIRS: Set[str] = {
        "openverse_cache", "pexels_cache", "local_asset", "storage", "temp", "cache", "vqg_gate2_proof"
    }

    SUPPORTED_MIME_TYPES: Set[str] = {
        "image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp"
    }

    SUPPORTED_VIDEO_MIME_TYPES: Set[str] = {
        "video/mp4", "video/quicktime", "video/webm"
    }
    SUPPORTED_VIDEO_EXTENSIONS: Set[str] = {".mp4", ".mov", ".webm"}

    @classmethod
    def validate_metadata(
        cls,
        candidate: Any,
        memory: Optional[Any] = None
    ) -> Tuple[bool, List[str]]:
        """
        Fast pre-download metadata check (license, ID/URL deduplication, unsafe content).
        Returns tuple of (is_eligible, rejection_reasons).
        """
        rejections: List[str] = []

        # 1. Procedural placeholder check
        status_val = getattr(getattr(candidate, "candidate_status", None), "value", "")
        if status_val == "procedural_placeholder":
            rejections.append(CandidateRejectionCode.PROCEDURAL_PLACEHOLDER.value)

        # 2. License and Attribution Check
        lic_name = getattr(candidate, "license_name", None)
        attribution = getattr(candidate, "attribution", None)
        provider_id = getattr(candidate, "provider_id", "unknown")
        lic_ok, lic_type, lic_score, lic_reason = LicensePolicyEvaluator.evaluate(lic_name, attribution, provider_id)

        if not lic_ok:
            rejections.append(lic_reason or CandidateRejectionCode.INVALID_LICENSE.value)

        # 3. Deduplication Check (exact ID / URL in SceneVisualMemory)
        remote_url = getattr(candidate, "remote_url", None)
        asset_path = getattr(candidate, "asset_path", None)

        if memory:
            if memory.is_duplicate_asset(asset_path, remote_url):
                if remote_url and remote_url in memory.used_source_urls:
                    rejections.append(CandidateRejectionCode.EXACT_DUPLICATE_SOURCE_URL.value)
                elif asset_path and asset_path in memory.used_asset_paths:
                    rejections.append(CandidateRejectionCode.EXACT_DUPLICATE_ASSET_ID.value)

        # 4. Unsafe Content Metadata Check
        meta = getattr(candidate, "generation_metadata", {}) or {}
        if meta.get("unsafe") or meta.get("nsfw"):
            rejections.append(CandidateRejectionCode.UNSAFE_CONTENT_FLAGGED.value)

        return len(rejections) == 0, rejections

    @classmethod
    def validate_downloaded_file(
        cls,
        candidate: Any,
        memory: Optional[Any] = None
    ) -> Tuple[bool, List[str]]:
        """
        Post-download file integrity and security check (path security, MIME, headers, dimensions).
        Returns tuple of (is_eligible, rejection_reasons).
        """
        rejections: List[str] = []

        asset_path = getattr(candidate, "asset_path", None)
        if not asset_path or not isinstance(asset_path, str) or len(asset_path.strip()) == 0:
            return False, [CandidateRejectionCode.MISSING_ASSET_PATH.value]

        clean_path = asset_path.strip()

        # 1. Path Security Checks
        if ".." in clean_path:
            return False, [CandidateRejectionCode.PATH_TRAVERSAL_DETECTED.value]

        norm_path = os.path.abspath(clean_path)
        if not os.path.exists(norm_path):
            return False, [CandidateRejectionCode.FILE_NOT_FOUND.value]

        # 1b. Video Files: validate via OpenCV instead of PIL (Image.open cannot decode video)
        media_type_val = getattr(getattr(candidate, "media_type", None), "value", str(getattr(candidate, "media_type", "")))
        ext = os.path.splitext(norm_path)[1].lower()
        if media_type_val in ("stock_video", "generated_video") or ext in cls.SUPPORTED_VIDEO_EXTENSIONS:
            return cls._validate_downloaded_video(candidate, norm_path)

        # 2. File Header Integrity & Dimensions Check
        try:
            with Image.open(norm_path) as img:
                img.verify()

            with Image.open(norm_path) as img:
                w, h = img.size
                mime = Image.MIME.get(img.format, "image/jpeg").lower()

                if mime not in cls.SUPPORTED_MIME_TYPES:
                    rejections.append(CandidateRejectionCode.INVALID_MIME_TYPE.value)

                if w < 100 or h < 100:
                    rejections.append(CandidateRejectionCode.DIMENSIONS_BELOW_MINIMUM.value)

                if w > 16384 or h > 16384 or (w * h) > 100_000_000:
                    rejections.append(CandidateRejectionCode.EXCESSIVE_PIXEL_COUNT.value)

                candidate.width = w
                candidate.height = h
                candidate.mime_type = mime

        except Exception as e:
            logger.warning(f"CandidatePreValidator: Header verify failed for '{clean_path}': {e}")
            rejections.append(CandidateRejectionCode.CORRUPT_IMAGE_HEADER.value)

        return len(rejections) == 0, rejections

    @classmethod
    def _validate_downloaded_video(cls, candidate: Any, norm_path: str) -> Tuple[bool, List[str]]:
        """
        Post-download integrity check for video candidates (mp4/mov/webm) via OpenCV,
        since PIL cannot decode video containers.
        """
        rejections: List[str] = []
        import cv2

        cap = None
        try:
            cap = cv2.VideoCapture(norm_path)
            if not cap.isOpened():
                rejections.append(CandidateRejectionCode.CORRUPT_IMAGE_HEADER.value)
                return False, rejections

            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            ok, _first_frame = cap.read()
            if not ok or _first_frame is None:
                rejections.append(CandidateRejectionCode.CORRUPT_IMAGE_HEADER.value)
                return False, rejections

            if w < 100 or h < 100:
                rejections.append(CandidateRejectionCode.DIMENSIONS_BELOW_MINIMUM.value)

            if w > 16384 or h > 16384 or (w * h) > 100_000_000:
                rejections.append(CandidateRejectionCode.EXCESSIVE_PIXEL_COUNT.value)

            if frame_count <= 0:
                rejections.append(CandidateRejectionCode.CORRUPT_IMAGE_HEADER.value)

            candidate.width = w
            candidate.height = h
            candidate.mime_type = "video/mp4"

        except Exception as e:
            logger.warning(f"CandidatePreValidator: Video header verify failed for '{norm_path}': {e}")
            rejections.append(CandidateRejectionCode.CORRUPT_IMAGE_HEADER.value)
        finally:
            if cap is not None:
                cap.release()

        return len(rejections) == 0, rejections
