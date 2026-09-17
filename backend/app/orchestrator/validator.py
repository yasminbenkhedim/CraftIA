import os
import logging

logger = logging.getLogger("uvicorn")


class ArtifactValidator:
    """
    Validates deliverable artifacts prior to job completion.

    For PDF artifacts the validator goes beyond file-existence / size checks and
    performs structural PDF parsing:
      - Attempts to open the file with pypdf.PdfReader
      - Rejects if the file cannot be parsed as a valid PDF
      - Rejects if page_count == 0
    """

    @classmethod
    def validate_artifact(cls, artifact_path: str, agent_type: str) -> bool:
        if not artifact_path or not os.path.exists(artifact_path):
            logger.error(f"Validation failed: Artifact file missing at {artifact_path}")
            return False

        size_bytes = os.path.getsize(artifact_path)
        if size_bytes == 0:
            logger.error(f"Validation failed: Artifact file at {artifact_path} is 0 bytes.")
            return False

        if agent_type == "presentation" and not artifact_path.endswith(".pptx"):
            logger.error("Validation failed: Expected .pptx extension for presentation agent.")
            return False
        elif agent_type == "latex" and not artifact_path.endswith(".pdf"):
            logger.error("Validation failed: Expected .pdf extension for latex agent.")
            return False
        elif agent_type == "video" and not artifact_path.endswith(".mp4"):
            logger.error("Validation failed: Expected .mp4 extension for video agent.")
            return False

        # ---- MP4 structural validation (video agent only) ----
        if agent_type == "video":
            ok, duration, err = cls._validate_mp4_structure(artifact_path)
            if not ok:
                logger.error(
                    f"Validation failed: MP4 structural check failed for {artifact_path} — {err}"
                )
                return False
            logger.info(
                f"Artifact validation passed for {agent_type}: {artifact_path} "
                f"({size_bytes} bytes, {duration:.1f}s decodable)"
            )
            return True

        # ---- PDF structural validation (latex agent only) ----
        if agent_type == "latex":
            ok, page_count, err = cls._validate_pdf_structure(artifact_path)
            if not ok:
                logger.error(
                    f"Validation failed: PDF structural check failed for {artifact_path} — {err}"
                )
                return False
            logger.info(
                f"Artifact validation passed for {agent_type}: {artifact_path} "
                f"({size_bytes} bytes, {page_count} pages)"
            )
            return True

        logger.info(
            f"Artifact validation passed for {agent_type}: {artifact_path} ({size_bytes} bytes)"
        )
        return True

    # ------------------------------------------------------------------
    # MP4 structural validation
    # ------------------------------------------------------------------

    @classmethod
    def _validate_mp4_structure(cls, mp4_path: str):
        """
        Decode the container and verify it holds a real, finished video stream.

        Existence and size are not enough to say a render finished. ffmpeg writes the moov
        atom last, so a run that was killed, timed out, or crashed mid-encode leaves a
        multi-megabyte file that passes both checks and is still unplayable -- which is
        exactly what "the UI says complete but the video is still processing" looks like
        from the outside. Muxing failures are logged and swallowed in VideoRenderer, so
        nothing upstream of here would have caught it either.

        Returns:
            (True,  duration_seconds, None)   on success
            (False, 0.0,              reason) on failure
        """
        try:
            import imageio_ffmpeg
        except ImportError:
            # No probe available: fall back to checking for the moov atom directly rather
            # than silently accepting whatever is on disk.
            logger.warning(
                "ArtifactValidator: imageio-ffmpeg not installed; falling back to moov atom check."
            )
            return cls._validate_mp4_binary(mp4_path)

        try:
            probe = imageio_ffmpeg.read_frames(mp4_path)
            meta = next(probe)
            probe.close()
        except Exception as exc:
            return False, 0.0, f"container not decodable: {exc}"

        if not isinstance(meta, dict):
            return False, 0.0, "probe returned no stream metadata"

        width, height = meta.get("size", (0, 0))
        if not width or not height:
            return False, 0.0, "no video stream in container"

        duration = float(meta.get("duration") or 0.0)
        if duration <= 0:
            return False, 0.0, "video stream reports zero duration (likely truncated)"

        # The header alone cannot prove the encode finished. VideoRenderer sets
        # -movflags +faststart, which relocates the moov atom to the FRONT of the file, so
        # a half-written render still parses and still reports its full intended duration.
        # Only decoding the packets reveals that the frames are not there.
        ok, err = cls._decodes_to_end(mp4_path)
        if not ok:
            return False, 0.0, err

        return True, duration, None

    @classmethod
    def _decodes_to_end(cls, mp4_path: str):
        """Decodes every packet to /dev/null; any decode error means an unfinished file."""
        import shutil as _shutil
        import subprocess

        ffmpeg_bin = _shutil.which("ffmpeg")
        if not ffmpeg_bin:
            try:
                import imageio_ffmpeg
                ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg_bin = None
        if not ffmpeg_bin:
            logger.warning("ArtifactValidator: no ffmpeg for decode check; skipping.")
            return True, None

        cmd = [ffmpeg_bin, "-v", "error", "-xerror", "-i", mp4_path, "-f", "null", "-"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            return False, "decode check timed out"
        except Exception as exc:
            logger.warning(f"ArtifactValidator: decode check could not run ({exc}); skipping.")
            return True, None

        if res.returncode != 0 or (res.stderr or "").strip():
            detail = (res.stderr or "").strip().splitlines()
            first = detail[0] if detail else f"exit {res.returncode}"
            return False, f"decode failed — file is incomplete ({first})"
        return True, None

    @classmethod
    def _validate_mp4_binary(cls, mp4_path: str):
        """
        Fallback when imageio-ffmpeg is unavailable: require the moov atom.

        ffmpeg writes moov last (or relocates it to the front with -movflags +faststart,
        which the renderer sets), so its absence means the encode never finished.
        """
        try:
            with open(mp4_path, "rb") as f:
                head = f.read(8)
                if len(head) < 8 or head[4:8] not in (b"ftyp", b"moov", b"free", b"mdat"):
                    return False, 0.0, "missing MP4 container signature"
                f.seek(0)
                content = f.read()
        except OSError as exc:
            return False, 0.0, f"cannot read file: {exc}"

        if b"moov" not in content:
            return False, 0.0, "no moov atom — encode did not finish"
        return True, 0.0, None

    # ------------------------------------------------------------------
    # PDF structural validation
    # ------------------------------------------------------------------

    @classmethod
    def _validate_pdf_structure(cls, pdf_path: str):
        """
        Parse the PDF with pypdf.PdfReader and verify page count > 0.

        Returns:
            (True,  page_count, None)   on success
            (False, 0,          reason) on failure
        """
        try:
            from pypdf import PdfReader
        except ImportError:
            # pypdf not installed — fall back to a minimal header/marker check
            logger.warning(
                "ArtifactValidator: pypdf not installed; falling back to binary marker check."
            )
            return cls._validate_pdf_binary(pdf_path)

        try:
            reader = PdfReader(pdf_path)
            page_count = len(reader.pages)
        except Exception as exc:
            return False, 0, f"pypdf parse error: {exc}"

        if page_count == 0:
            return False, 0, "PDF parsed successfully but contains 0 pages"

        return True, page_count, None

    @classmethod
    def _validate_pdf_binary(cls, pdf_path: str):
        """
        Minimal fallback when pypdf is unavailable.

        Checks:
          1. %PDF- header
          2. xref table present
          3. At least 2 leaf /Page objects (a 1-page blank shell only has /MediaBox,
             no /Contents stream; a real report has cover + TOC + content pages)
          4. At least one /Font object (blank shells have no fonts)
          5. At least one /Contents stream reference

        A 298-byte minimal PDF shell passes header/xref but has exactly 1 blank
        page with no fonts or content streams — all three additional checks catch it.
        """
        import re
        try:
            with open(pdf_path, "rb") as f:
                content = f.read()
        except OSError as exc:
            return False, 0, f"cannot read file: {exc}"

        if not content.startswith(b"%PDF-"):
            return False, 0, "missing %PDF- header"
        if b"xref" not in content:
            return False, 0, "missing xref table"

        # Count leaf /Page objects (not /Pages)
        page_objs = re.findall(b"/Type\\s*/Page[^s]", content)
        page_count = len(page_objs)
        if page_count == 0:
            counts = re.findall(b"/Count\\s+(\\d+)", content)
            page_count = sum(int(c) for c in counts)
        if page_count == 0:
            return False, 0, "no page objects found in PDF structure"

        # Require at least 2 pages (cover + at least one content page)
        MIN_PAGES = 2
        if page_count < MIN_PAGES:
            return (
                False, page_count,
                f"only {page_count} page(s) found; a real report needs at least {MIN_PAGES}"
            )

        # Require at least one /Font resource (blank shells have none)
        if b"/Font" not in content:
            return False, page_count, "no /Font resources in PDF — likely a blank shell"

        # Require at least one /Contents stream (blank pages have no /Contents)
        if b"/Contents" not in content:
            return False, page_count, "no /Contents streams in PDF — pages have no rendered content"

        return True, page_count, None
