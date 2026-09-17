"""
Kokoro-82M Engine -- Apache-2.0 local neural speech synthesis.

Selected with TTS_ENGINE=kokoro in .env. Falls back automatically:
    kokoro -> piper -> edge
so a missing model, missing dependency, or out-of-memory GPU degrades to a working
voice instead of failing the render.

Why this engine exists
----------------------
XTTS v2 sounds excellent but its *weights* are CPML (non-commercial), and CPML extends
to the model's audio output -- every generated voiceover inherits the restriction. See
LICENSES.md R1. Kokoro-82M's weights are Apache-2.0, which is what makes it a viable
successor for a paid product.

Runtime: kokoro-onnx, not the `kokoro` package
----------------------------------------------
The reference `kokoro` package declares `requires_python <3.13` (via `misaki`), and this
project runs Python 3.13. Installing it makes pip walk back to a numpy old enough to
need a source build, which fails with no MSVC toolchain present. `kokoro-onnx` runs the
SAME Apache-2.0 Kokoro-82M weights through onnxruntime, supports <3.14, and needs only
pure-python deps -- so it integrates without disturbing the pinned torch/numpy stack.

Licensing caveat (do not skip this)
-----------------------------------
The *weights* are Apache-2.0, but grapheme-to-phoneme conversion runs through
`phonemizer` (GPL-3.0-or-later) wrapping `espeak-ng` (GPL-3.0). The reference `kokoro`
package has the identical exposure via `misaki[en]`. For a hosted-only SaaS, GPL's
distribution trigger is not met and this is acceptable; if CreateFlow AI ever ships
containers, Helm charts, or on-prem builds, this becomes a blocker exactly like
piper-tts. See LICENSES.md R6/Y14.

Trade-offs versus XTTS, stated plainly so nobody rediscovers them mid-migration:
  - No voice cloning. XTTS_SPEAKER_WAV clones an arbitrary reference clip; Kokoro
    offers a fixed roster of 54 preset voices instead (see `list_voices()`).
  - Multilingual, but unevenly. The voice-name prefix encodes the language: a/b are
    American/British English, then e=Spanish, f=French, h=Hindi, i=Italian,
    j=Japanese, p=Portuguese, z=Chinese. English has by far the most voices (28 of
    54) and the most training data; the others are single-digit rosters. Each needs a
    matching `lang` tag, so KOKORO_LANG must track KOKORO_VOICE.
  - Quieter output. Measured RMS is roughly half XTTS's on identical text, so the
    ducking/mix stage (AudioDuckingEngine) is worth re-checking after a switch --
    narration tuned against XTTS levels will sit lower against the music bed.
  - 82M parameters against XTTS's ~750M, so it is markedly faster and lighter on VRAM:
    ~5.5 s versus ~70 s for the same three-sentence line on this machine.

Word-level timestamps
---------------------
Kokoro exposes no time alignment, so word timings are estimated from the rendered audio
exactly as XTTSEngine does -- each word weighted by character count, scaled to the
measured duration. CaptionEngine refines these against the WAV envelope downstream, so
captions stay in sync without alignment metadata.

Output format
-------------
Kokoro emits 24 kHz mono float32. The pipeline's WAV concatenator copies the header of
the FIRST scene's file and appends raw frames from the rest, so mixing formats across
scenes would silently corrupt the soundtrack. Every Kokoro WAV is therefore normalized
to the canonical 48 kHz / stereo / 16-bit PCM contract.
"""
import os
import wave
import shutil
import logging
import subprocess
from typing import List, Optional, Tuple, Any

logger = logging.getLogger("uvicorn")

# Must match the Edge-TTS / Piper / XTTS output contract (see TTSEngine._convert_mp3_to_wav).
CANONICAL_SAMPLE_RATE = 48000
CANONICAL_CHANNELS = 2

DEFAULT_MODEL_DIR = os.path.join("storage", "models", "kokoro")
MODEL_FILE = "kokoro-v1.0.onnx"
VOICES_FILE = "voices-v1.0.bin"

DEFAULT_VOICE = "af_heart"
DEFAULT_LANG = "en-us"

# Voices the Kokoro authors grade highest for narration; used for the A/B shortlist.
RECOMMENDED = ["af_heart", "af_bella", "am_michael", "bf_emma"]

# Characters stripped when weighting a word for timestamp estimation.
_PUNCT = ".,!?;:'\""


class KokoroEngine:
    """Kokoro-82M synthesis (ONNX runtime) with estimated word timings."""

    # Loading the model costs a few seconds and ~350 MB, so hold one instance per process.
    _kokoro: Any = None
    _load_failed: bool = False
    _unavailable_reason: Optional[str] = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @staticmethod
    def engine_preference(override: Optional[str] = None) -> str:
        """An explicit per-job override wins over the TTS_ENGINE environment variable."""
        if override:
            return override.strip().lower()
        return (os.getenv("TTS_ENGINE") or "edge").strip().lower()

    @classmethod
    def is_selected(cls, override: Optional[str] = None) -> bool:
        return cls.engine_preference(override) == "kokoro"

    @staticmethod
    def voice_name() -> str:
        return (os.getenv("KOKORO_VOICE") or DEFAULT_VOICE).strip()

    @staticmethod
    def language() -> str:
        """espeak language tag: 'en-us' (American) or 'en-gb' (British)."""
        return (os.getenv("KOKORO_LANG") or DEFAULT_LANG).strip().lower()

    @staticmethod
    def speed() -> float:
        try:
            return float(os.getenv("KOKORO_SPEED") or "1.0")
        except ValueError:
            return 1.0

    @staticmethod
    def model_dir() -> str:
        """Resolves the model directory, honouring KOKORO_MODEL_DIR."""
        return (os.getenv("KOKORO_MODEL_DIR") or DEFAULT_MODEL_DIR).strip()

    @classmethod
    def model_paths(cls) -> Tuple[str, str]:
        d = cls.model_dir()
        return os.path.join(d, MODEL_FILE), os.path.join(d, VOICES_FILE)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    @staticmethod
    def _bind_espeak() -> None:
        """
        Points phonemizer at the espeak-ng shipped by espeakng-loader.

        Without this, phonemizer looks for a system-wide espeak-ng install, which is not
        present on a stock Windows box -- G2P then fails at synthesis time rather than at
        load, which is a much harder failure to read in a render log.
        """
        try:
            import espeakng_loader
            from phonemizer.backend.espeak.wrapper import EspeakWrapper
            EspeakWrapper.set_library(espeakng_loader.get_library_path())
            EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
        except Exception as e:
            logger.debug(f"KokoroEngine: espeak bind skipped ({type(e).__name__}: {e}).")

    @classmethod
    def _get_kokoro(cls) -> Optional[Any]:
        """Returns the cached Kokoro instance, or None when the engine is unusable."""
        if cls._kokoro is not None:
            return cls._kokoro
        if cls._load_failed:
            return None

        model_path, voices_path = cls.model_paths()
        missing = [p for p in (model_path, voices_path) if not os.path.exists(p)]
        if missing:
            cls._load_failed = True
            cls._unavailable_reason = f"model file(s) not found: {', '.join(missing)}"
            logger.warning(
                f"KokoroEngine: {cls._unavailable_reason}. "
                f"Download {MODEL_FILE} and {VOICES_FILE} into '{cls.model_dir()}'."
            )
            return None

        try:
            from kokoro_onnx import Kokoro
        except Exception as e:
            cls._load_failed = True
            cls._unavailable_reason = f"kokoro-onnx not importable ({type(e).__name__}: {e})"
            logger.warning(f"KokoroEngine: {cls._unavailable_reason}. Install with `pip install kokoro-onnx`.")
            return None

        cls._bind_espeak()
        try:
            cls._kokoro = Kokoro(model_path, voices_path)
        except Exception as e:
            cls._load_failed = True
            cls._unavailable_reason = f"{type(e).__name__}: {e}"
            logger.warning(f"KokoroEngine: Failed to load model ({cls._unavailable_reason}).", exc_info=True)
            return None

        logger.info(f"KokoroEngine: Loaded Kokoro-82M from '{model_path}'.")
        return cls._kokoro

    @classmethod
    def is_available(cls) -> bool:
        """True when the model can actually be loaded. Used by the fallback chain."""
        return cls._get_kokoro() is not None

    @classmethod
    def unavailable_reason(cls) -> Optional[str]:
        return cls._unavailable_reason

    @classmethod
    def list_voices(cls) -> List[str]:
        """Available preset voices, read from the loaded voice pack."""
        k = cls._get_kokoro()
        if k is None:
            return []
        try:
            return sorted(k.get_voices())
        except Exception as e:
            logger.warning(f"KokoroEngine: Could not list voices ({type(e).__name__}: {e}).")
            return []

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    @classmethod
    def synthesize(
        cls,
        text: str,
        output_path: str,
        voice: Optional[str] = None,
        lang: Optional[str] = None,
    ) -> Tuple[bool, float, list]:
        """
        Synthesizes `text` to `output_path` (canonical 48 kHz stereo WAV).
        `voice` and `lang` override the environment for a single call, which is what the
        A/B harness uses to render one line in several voices.
        Returns (success, duration_seconds, word_timestamps).
        """
        if not text or not text.strip():
            return False, 0.0, []

        kokoro = cls._get_kokoro()
        if kokoro is None:
            return False, 0.0, []

        voice = (voice or cls.voice_name()).strip()
        raw_path = f"{output_path}.kokoro_raw.wav"

        try:
            samples, sample_rate = kokoro.create(
                text.strip(),
                voice=voice,
                speed=cls.speed(),
                lang=(lang or cls.language()),
            )
        except Exception as e:
            logger.warning(f"KokoroEngine: Synthesis failed ({type(e).__name__}: {e}).", exc_info=True)
            return False, 0.0, []

        if samples is None or len(samples) == 0:
            logger.warning("KokoroEngine: Synthesis produced no audio.")
            return False, 0.0, []

        try:
            import soundfile as sf
            sf.write(raw_path, samples, sample_rate)
        except Exception as e:
            logger.warning(f"KokoroEngine: Could not write raw WAV ({type(e).__name__}: {e}).")
            cls._cleanup(raw_path)
            return False, 0.0, []

        if not cls._normalize_format(raw_path, output_path):
            cls._cleanup(raw_path)
            return False, 0.0, []
        cls._cleanup(raw_path)

        duration = cls._probe_duration(output_path)
        if duration <= 0:
            return False, 0.0, []

        timestamps = cls._estimate_word_timestamps(text.strip(), duration)
        logger.info(
            f"KokoroEngine: Synthesized {duration:.1f}s as '{voice}' "
            f"({len(timestamps)} estimated word timings) -> {output_path}"
        )
        return True, duration, timestamps

    # ------------------------------------------------------------------
    # Word timing estimation
    # ------------------------------------------------------------------

    @classmethod
    def _estimate_word_timestamps(cls, text: str, duration: float) -> list:
        """
        Character-proportional distribution across the measured audio duration.
        Identical approach to XTTSEngine: longer words take proportionally longer to say,
        which tracks real speech far better than an even split. CaptionEngine refines
        these against the WAV's RMS envelope downstream.
        """
        words = text.split()
        if not words or duration <= 0:
            return []

        from agents.video.tts_engine import WordTimestamp

        weights = [max(1, len(w.strip(_PUNCT))) for w in words]
        total = float(sum(weights))
        out, cursor = [], 0.0
        for w, weight in zip(words, weights):
            share = duration * (weight / total)
            out.append(WordTimestamp(word=w, offset_sec=cursor, duration_sec=share))
            cursor += share
        return out

    # ------------------------------------------------------------------
    # Audio helpers
    # ------------------------------------------------------------------

    @classmethod
    def _normalize_format(cls, src: str, dst: str) -> bool:
        """Resamples Kokoro's 24 kHz mono output to the pipeline's 48 kHz stereo contract."""
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            try:
                import imageio_ffmpeg
                ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg_bin = None

        if not ffmpeg_bin:
            logger.warning("KokoroEngine: ffmpeg unavailable -- cannot normalize audio format.")
            return False

        cmd = [
            ffmpeg_bin, "-y",
            "-i", src,
            "-acodec", "pcm_s16le",
            "-ar", str(CANONICAL_SAMPLE_RATE),
            "-ac", str(CANONICAL_CHANNELS),
            dst,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0:
                return True
            logger.warning(f"KokoroEngine: ffmpeg normalization failed (rc={res.returncode}).")
        except Exception as e:
            logger.warning(f"KokoroEngine: ffmpeg normalization error ({e}).")
        return False

    @staticmethod
    def _probe_duration(wav_path: str) -> float:
        try:
            with wave.open(wav_path, "rb") as wf:
                rate = wf.getframerate()
                return wf.getnframes() / float(rate) if rate else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def _cleanup(path: str) -> None:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
