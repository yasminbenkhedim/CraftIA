"""
Poster-frame extraction for rendered videos.

Dashboard cards need a still from the actual video. Grabbing frame 0 is the obvious
approach and the wrong one: almost every render opens on a fade-in from black, so frame 0
is a black rectangle. This samples a few candidate timestamps instead and takes the first
one that is actually a picture -- bright enough, and with enough variation to rule out a
solid-colour title card.
"""
import os
import uuid
import logging
import threading
from typing import List, Optional, Tuple

logger = logging.getLogger("uvicorn")

THUMBNAIL_FILENAME = "thumbnail.jpg"

# Decoding a video is CPU-bound, and FastAPI runs sync endpoints on a wide threadpool, so
# a dashboard whose cards are all missing posters would start one decode per card at once
# and peg every core. Capping in-flight extractions keeps the box responsive; the requests
# that wait are only queued for the fraction of a second each decode takes.
MAX_CONCURRENT_EXTRACTIONS = max(1, int(os.getenv("THUMBNAIL_MAX_CONCURRENCY", "3")))
# A decode is sub-second; waiting minutes for a slot means something is badly wrong, and
# failing to a placeholder beats holding the request open indefinitely.
SLOT_WAIT_TIMEOUT_SEC = 30.0

_slots = threading.BoundedSemaphore(MAX_CONCURRENT_EXTRACTIONS)
_gauge_lock = threading.Lock()
_inflight = 0
_peak_inflight = 0


def extraction_stats() -> dict:
    """In-flight and peak concurrent extractions, for diagnostics and tests."""
    with _gauge_lock:
        return {"inflight": _inflight, "peak": _peak_inflight, "limit": MAX_CONCURRENT_EXTRACTIONS}


def reset_extraction_stats() -> None:
    global _peak_inflight
    with _gauge_lock:
        _peak_inflight = 0

# A frame darker than this mean luminance (0-255) is a fade or a black gap.
MIN_MEAN_LUMA = 26.0
# Standard deviation below this means a flat fill -- a solid colour card, not a shot.
MIN_LUMA_STDDEV = 12.0

MAX_WIDTH = 640
JPEG_QUALITY = 82


def thumbnail_path_for(video_path: str) -> str:
    """The poster frame sits next to the video it came from."""
    return os.path.join(os.path.dirname(video_path), THUMBNAIL_FILENAME)


def _candidate_times(duration: float) -> List[float]:
    """
    Sample points, best first.

    2.5 s is past a typical fade-in but still inside the opening shot, so it usually
    matches what a viewer remembers of the video. The midpoint and quartiles are the
    backups for very short or very dark openings.
    """
    if duration <= 0:
        return [0.0]
    candidates = [2.5, duration * 0.5, duration * 0.25, duration * 0.75, 1.0, duration * 0.1, 0.0]
    seen, out = set(), []
    for t in candidates:
        t = max(0.0, min(t, max(duration - 0.05, 0.0)))
        key = round(t, 2)
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


def extract_thumbnail(video_path: str, out_path: Optional[str] = None,
                      overwrite: bool = False) -> Optional[str]:
    """
    Writes a JPEG poster frame beside `video_path`. Returns its path, or None on failure.

    Never raises: a missing thumbnail degrades the card to its gradient placeholder, which
    must not be allowed to fail a render or a request.
    """
    if not video_path or not os.path.exists(video_path):
        return None

    out_path = out_path or thumbnail_path_for(video_path)
    if _already_written(out_path, overwrite):
        return out_path

    if not _slots.acquire(timeout=SLOT_WAIT_TIMEOUT_SEC):
        logger.warning(f"Thumbnail: no extraction slot within {SLOT_WAIT_TIMEOUT_SEC:.0f}s; skipping {video_path}.")
        return None
    try:
        # Re-checked under the slot: several cards can ask for the same poster at once, and
        # whoever got here first has already written it.
        if _already_written(out_path, overwrite):
            return out_path
        _enter_gauge()
        try:
            return _extract_locked(video_path, out_path)
        finally:
            _exit_gauge()
    finally:
        _slots.release()


def _already_written(out_path: str, overwrite: bool) -> bool:
    return (not overwrite) and os.path.exists(out_path) and os.path.getsize(out_path) > 0


def _enter_gauge() -> None:
    global _inflight, _peak_inflight
    with _gauge_lock:
        _inflight += 1
        _peak_inflight = max(_peak_inflight, _inflight)


def _exit_gauge() -> None:
    global _inflight
    with _gauge_lock:
        _inflight -= 1


def _extract_locked(video_path: str, out_path: str) -> Optional[str]:
    """The decode itself. Only ever called while holding an extraction slot."""
    try:
        import cv2
        import numpy as np
    except Exception as e:
        logger.warning(f"Thumbnail: OpenCV unavailable ({e}); skipping {video_path}.")
        return None

    cap = None
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning(f"Thumbnail: could not open {video_path}.")
            return None

        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        duration = (frames / fps) if fps > 0 and frames > 0 else 0.0

        best_frame = None
        best_score = -1.0

        for t in _candidate_times(duration):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None or frame.size == 0:
                continue

            grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mean = float(np.mean(grey))
            stddev = float(np.std(grey))

            if mean >= MIN_MEAN_LUMA and stddev >= MIN_LUMA_STDDEV:
                best_frame = frame
                logger.info(
                    f"Thumbnail: frame at {t:.2f}s (luma {mean:.0f}, sd {stddev:.0f}) -> {out_path}"
                )
                break

            # Keep the least-bad candidate in case every sample is dark or flat.
            score = mean + stddev
            if score > best_score:
                best_score, best_frame = score, frame

        if best_frame is None:
            logger.warning(f"Thumbnail: no readable frame in {video_path}.")
            return None

        return _write_jpeg(best_frame, out_path)

    except Exception as e:
        logger.warning(f"Thumbnail: extraction failed for {video_path} ({type(e).__name__}: {e}).")
        return None
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass


def _write_jpeg(frame, out_path: str) -> Optional[str]:
    """Downscales to card size and encodes. Written via imencode so non-ASCII paths work."""
    import cv2

    height, width = frame.shape[:2]
    if width > MAX_WIDTH:
        scale = MAX_WIDTH / float(width)
        frame = cv2.resize(frame, (MAX_WIDTH, max(1, int(round(height * scale)))),
                           interpolation=cv2.INTER_AREA)

    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    if not ok:
        logger.warning(f"Thumbnail: JPEG encoding failed for {out_path}.")
        return None

    # Written to a temp name first so a reader never sees a half-written file. The suffix
    # is unique per writer: a shared '.part' name lets two threads targeting the same
    # poster truncate each other's buffer, and whichever replaces second fails outright.
    tmp = f"{out_path}.{uuid.uuid4().hex[:8]}.part"
    try:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(tmp, "wb") as f:
            f.write(buffer.tobytes())
        os.replace(tmp, out_path)
        return out_path
    except OSError as e:
        logger.warning(f"Thumbnail: could not write {out_path} ({e}).")
        try:
            os.remove(tmp)
        except OSError:
            pass
        return None


def find_video_for_job(job) -> Optional[str]:
    """
    The rendered MP4 for a job, if there is one.

    Prefers the recorded artifact_path, but falls back to the conventional location so a
    job whose row predates artifact_path -- or whose path moved -- still gets a poster.
    """
    from app.core.config import settings

    path = getattr(job, "artifact_path", None)
    if path and path.lower().endswith(".mp4") and os.path.exists(path):
        return path

    guess = os.path.join(settings.STORAGE_PATH, str(job.id), "video_demo.mp4")
    return guess if os.path.exists(guess) else None
