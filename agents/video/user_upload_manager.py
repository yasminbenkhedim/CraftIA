"""
User Upload Manager (Phase 3 Track A of VIDEO_PIPELINE_ARCHITECTURE_V2).

Analyzes user-supplied footage and turns an assigned upload into a MediaCandidate the
existing render path already knows how to consume, so uploaded clips flow through the
same decode/cover-crop pipeline as stock video instead of needing a parallel one.

Scene media priority (per spec):
  1. User-uploaded video (when the director assigned one to the scene)
  2. Pexels video clip
  3. Pexels photo + Ken Burns
  4. Procedural gradient background
"""
import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

import cv2
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class UploadedMedia(BaseModel):
    """Probed metadata for one user-uploaded file."""
    filename: str
    path: str
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    is_video: bool = True
    resolution: str = ""


class UserUploadManager:
    """Analyzes and prepares user-uploaded media for the pipeline."""

    @classmethod
    def upload_dir_for_job(cls, job_id: str, storage_root: Optional[Path] = None) -> Path:
        """Canonical on-disk location for a job's uploads."""
        if storage_root is None:
            try:
                from app.core.config import settings
                storage_root = Path(settings.STORAGE_PATH)
            except Exception:
                storage_root = Path("storage") / "artifacts"
        return Path(storage_root) / job_id / "uploads"

    @classmethod
    def analyze(cls, upload_dir: Any) -> List[UploadedMedia]:
        """
        Probes every uploaded file: duration, resolution, fps.
        Unreadable files are skipped with a warning rather than failing the whole job.
        """
        directory = Path(upload_dir)
        if not directory.exists() or not directory.is_dir():
            return []

        results: List[UploadedMedia] = []
        for f in sorted(directory.iterdir()):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext in VIDEO_EXTENSIONS:
                media = cls._probe_video(f)
            elif ext in IMAGE_EXTENSIONS:
                media = cls._probe_image(f)
            else:
                continue
            if media is not None:
                results.append(media)

        if results:
            logger.info(
                f"UserUploadManager: Analyzed {len(results)} upload(s): "
                + ", ".join(f"{m.filename} ({m.resolution}, {m.duration:.1f}s)" for m in results)
            )
        return results

    @classmethod
    def _probe_video(cls, path: Path) -> Optional[UploadedMedia]:
        cap = None
        try:
            cap = cv2.VideoCapture(str(path))
            if not cap.isOpened():
                logger.warning(f"UserUploadManager: Cannot open uploaded video '{path.name}' -- skipping.")
                return None
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = (frames / fps) if fps > 0 else 0.0

            ok, _ = cap.read()
            if not ok or width <= 0 or height <= 0:
                logger.warning(f"UserUploadManager: Uploaded video '{path.name}' has no decodable frames -- skipping.")
                return None

            return UploadedMedia(
                filename=path.name,
                path=str(path),
                duration=round(duration, 2),
                width=width,
                height=height,
                fps=round(fps, 2),
                is_video=True,
                resolution=f"{width}x{height}",
            )
        except Exception as e:
            logger.warning(f"UserUploadManager: Probe failed for '{path.name}': {e}")
            return None
        finally:
            if cap is not None:
                cap.release()

    @classmethod
    def _probe_image(cls, path: Path) -> Optional[UploadedMedia]:
        try:
            from PIL import Image
            with Image.open(path) as img:
                img.verify()
            with Image.open(path) as img:
                w, h = img.size
            if w <= 0 or h <= 0:
                return None
            return UploadedMedia(
                filename=path.name,
                path=str(path),
                duration=0.0,
                width=w,
                height=h,
                fps=0.0,
                is_video=False,
                resolution=f"{w}x{h}",
            )
        except Exception as e:
            logger.warning(f"UserUploadManager: Image probe failed for '{path.name}': {e}")
            return None

    # ------------------------------------------------------------------
    # Pipeline integration
    # ------------------------------------------------------------------

    @classmethod
    def resolve_reference(cls, uploads: List[UploadedMedia], ref: Optional[str]) -> Optional[UploadedMedia]:
        """
        Matches a director's `uploaded_file_ref` to an actual analyzed upload.
        Tolerates the LLM echoing a slightly different name (case, path prefix, or
        an index like "video1") rather than dropping the assignment entirely.
        """
        if not ref or not uploads:
            return None

        target = os.path.basename(str(ref)).strip().lower()
        if not target:
            return None

        for m in uploads:
            if m.filename.lower() == target:
                return m
        stem = os.path.splitext(target)[0]
        for m in uploads:
            if os.path.splitext(m.filename)[0].lower() == stem:
                return m
        for m in uploads:
            if stem and stem in m.filename.lower():
                return m

        # "video1" / "upload_2" style positional references.
        digits = "".join(ch for ch in stem if ch.isdigit())
        if digits:
            try:
                idx = int(digits) - 1
                if 0 <= idx < len(uploads):
                    return uploads[idx]
            except ValueError:
                pass

        logger.info(f"UserUploadManager: No upload matched director reference '{ref}'.")
        return None

    @classmethod
    def build_media_candidate(cls, media: UploadedMedia, scene_id: str, target_width: int, target_height: int):
        """
        Wraps an uploaded file as a render-ready MediaCandidate so MediaAssetLoader
        decodes it exactly like stock footage.
        """
        from agents.video.providers.base import MediaCandidate, MediaCandidateStatus, MediaType

        return MediaCandidate(
            provider_id="user_upload",
            media_type=MediaType.UPLOADED_MEDIA if not media.is_video else MediaType.STOCK_VIDEO,
            asset_path=media.path,
            remote_url=None,
            width=media.width or target_width,
            height=media.height or target_height,
            duration=media.duration or None,
            mime_type="video/mp4" if media.is_video else "image/jpeg",
            candidate_status=MediaCandidateStatus.VALIDATED_RENDER_READY,
            generation_method="user_upload",
            measured_latency_seconds=0.0,
            attribution=None,
            license_name="User-supplied asset",
            generation_metadata={
                "source": "user_upload",
                "filename": media.filename,
                "scene_id": scene_id,
                "duration": media.duration,
                "title": media.filename,
            },
        )
