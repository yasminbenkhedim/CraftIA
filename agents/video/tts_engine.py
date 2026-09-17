"""
TTS Voiceover Engine v3 -- Edge-TTS Subprocess Integration.

v3 additions:
  - Edge-TTS neural speech synthesis via subprocess (300+ voices, no API key)
  - Per-scene voice selection (scene.voice field support)
  - User-provided speech text priority (user_speech / speech_text)
  - Dynamic scene duration adjustment based on actual audio length (min floor 3.0s)
  - Fallback to pyttsx3 or silent WAV when offline/unavailable
"""
import os
import sys
import wave
import struct
import logging
import subprocess
import shutil
import asyncio
from typing import Dict, Optional, List, Tuple
from agents.video.storyboard import Storyboard, SceneDefinition
from agents.video import language as video_language

logger = logging.getLogger("uvicorn")


class AudioDuckingEngine:
    """Applies CC0 background music bed with automatic sidechain audio ducking."""

    @classmethod
    def apply_music_and_ducking(
        cls,
        speech_wav_path: str,
        output_wav_path: str,
        mood: str = "corporate",
        has_sfx_risers: bool = False
    ) -> str:
        if not os.path.exists(speech_wav_path):
            return speech_wav_path

        try:
            import numpy as np
            from agents.video.generate_cc0_music_assets import CC0MusicGenerator
            music_path = CC0MusicGenerator.get_or_generate_music(mood, output_dir=os.path.dirname(output_wav_path))

            with wave.open(speech_wav_path, "rb") as wf:
                sr = wf.getframerate()
                channels = wf.getnchannels()
                speech_frames = wf.readframes(wf.getnframes())
                # (frames, channels): every TTS engine writes 48 kHz STEREO, so the flat
                # buffer is interleaved L,R,L,R. Treating it as a 1-D mono signal -- and
                # writing it back with setnchannels(1) -- replays the narration at half
                # speed, an octave down. That is the "robotic voice", not the TTS model.
                speech_data = np.frombuffer(speech_frames, dtype=np.int16).astype(np.float32)
                speech_data = speech_data.reshape(-1, channels)
            num_frames = speech_data.shape[0]

            if os.path.exists(music_path):
                with wave.open(music_path, "rb") as mf:
                    music_sr = mf.getframerate()
                    music_channels = mf.getnchannels()
                    music_frames = mf.readframes(mf.getnframes())
                    music_data = np.frombuffer(music_frames, dtype=np.int16).astype(np.float32)
                    music_data = music_data.reshape(-1, music_channels)

                # Resample music if sample rate differs
                if music_sr != sr and music_data.shape[0] > 0:
                    import scipy.signal
                    num_samples = int(round(music_data.shape[0] * float(sr) / music_sr))
                    music_data = scipy.signal.resample(music_data, num_samples, axis=0)

                # Match the speech's channel layout (the CC0 beds are mono).
                if music_data.shape[1] != channels:
                    music_data = np.repeat(music_data.mean(axis=1, keepdims=True), channels, axis=1)

                # Loop/tile music to match speech length
                if music_data.shape[0] < num_frames:
                    repeats = int(np.ceil(num_frames / music_data.shape[0]))
                    music_data = np.tile(music_data, (repeats, 1))[:num_frames]
                else:
                    music_data = music_data[:num_frames]

                # Compute speech RMS energy for sidechain ducking, on the mono mixdown so
                # the two channels always duck together.
                speech_mono = speech_data.mean(axis=1)
                window = int(sr * 0.02)  # 20ms window for precise transient tracking
                rms = np.zeros(num_frames, dtype=np.float32)
                for i in range(0, num_frames, window):
                    chunk = speech_mono[i:i+window]
                    r = np.sqrt(np.mean(chunk**2)) if len(chunk) > 0 else 0
                    rms[i:i+window] = r

                max_rms = np.max(rms) if np.max(rms) > 0 else 1.0
                normalized_rms = rms / max_rms

                # Exponential Attack / Decay smoothing envelope (50ms attack, 300ms release)
                attack_coeff = np.exp(-1.0 / (sr * 0.050))
                release_coeff = np.exp(-1.0 / (sr * 0.300))
                smooth_env = np.zeros_like(normalized_rms)
                curr_env = 0.0

                for i in range(len(normalized_rms)):
                    target = normalized_rms[i]
                    if target > curr_env:
                        curr_env = target + attack_coeff * (curr_env - target)
                    else:
                        curr_env = target + release_coeff * (curr_env - target)
                    smooth_env[i] = curr_env

                # Smooth Sidechain ducking formula: duck music volume down to 15% during speech
                ducking_gain = (0.45 - (0.32 * smooth_env))[:, None]   # broadcast over channels
                ducked_music = music_data * ducking_gain

                mixed = speech_data * 0.88 + ducked_music

                # Synthesize and overlay procedural Audio Riser SFX tone if enabled (220Hz -> 1400Hz exponential sweep)
                if has_sfx_risers:
                    riser_duration_sec = 0.8
                    num_riser_samples = int(sr * riser_duration_sec)
                    riser_t = np.linspace(0, riser_duration_sec, num_riser_samples, endpoint=False)
                    freq_sweep = 220.0 * ((1400.0 / 220.0) ** (riser_t / riser_duration_sec))
                    phase = 2 * np.pi * np.cumsum(freq_sweep) / sr
                    riser_wave = np.sin(phase) * np.linspace(0.1, 0.9, num_riser_samples) * 12000.0  # Riser amplitude envelope

                    riser_start_idx = int(sr * 0.5)
                    riser_end_idx = min(riser_start_idx + num_riser_samples, num_frames)
                    actual_riser_len = riser_end_idx - riser_start_idx
                    if actual_riser_len > 0:
                        mixed[riser_start_idx:riser_end_idx] += riser_wave[:actual_riser_len, None]

                mixed = np.clip(mixed, -32768, 32767).astype(np.int16)

                with wave.open(output_wav_path, "wb") as out_wf:
                    out_wf.setnchannels(channels)
                    out_wf.setsampwidth(2)
                    out_wf.setframerate(sr)
                    out_wf.writeframes(mixed.tobytes())

                return output_wav_path
        except Exception as e:
            logger.warning(f"AudioDuckingEngine ducking failed ({e}), using raw speech: {speech_wav_path}")
            return speech_wav_path

        return speech_wav_path


class WordTimestamp:
    """A single word's real timing from Edge-TTS WordBoundary events."""
    def __init__(self, word: str, offset_sec: float, duration_sec: float):
        self.word = word
        self.offset_sec = round(offset_sec, 4)
        self.duration_sec = round(duration_sec, 4)
        self.end_sec = round(offset_sec + duration_sec, 4)

    def __repr__(self):
        return f"<WordTimestamp '{self.word}' [{self.offset_sec:.3f}s - {self.end_sec:.3f}s] (dur={self.duration_sec:.3f}s)>"


class PerSceneAudio:
    """Audio manifest entry for a single scene with explicit provenance tracking."""
    def __init__(self, scene_id: str, wav_path: str, speech_text: str, duration_sec: float,
                 voice: str = "en-US-JennyNeural", provenance: str = "NEURAL_TTS",
                 word_timestamps: list = None):
        self.scene_id = scene_id
        self.wav_path = wav_path
        self.speech_text = speech_text
        self.duration_sec = duration_sec
        self.voice = voice
        self.provenance = provenance  # NEURAL_TTS, REAL_FALLBACK_OFFLINE_TTS, PLACEHOLDER_SYNTHETIC_TONE, NO_SPEECH_TEXT
        self.word_timestamps: list = word_timestamps or []  # List[WordTimestamp] from Edge-TTS WordBoundary events


class TTSEngine:
    """
    Offline/Online Text-to-Speech Engine v3 utilizing Edge-TTS CLI via subprocess.
    Generates per-scene WAV files, dynamically adjusts scene durations, and produces
    a concatenated full voiceover track.
    """

    DEFAULT_VOICE = "en-US-JennyNeural"
    MIN_SCENE_DURATION_SEC = 3.0

    # Voice IDs that must never reach the actual Edge-TTS call, no matter which upstream
    # layer produced them (stale cached scene data, an old persisted job, a script that
    # still hardcodes it, etc.) -- enforced at the real synthesis call sites below.
    _DEPRECATED_VOICES = {"en-US-AvaNeural"}

    # Remembers which (env, override) pairs have been announced, so the resolution is
    # logged once per run instead of once per scene.
    _announced_selections: set = set()

    @classmethod
    def _log_engine_selection(cls, override: Optional[str]) -> str:
        """
        Announces which engine will actually run and why.

        A per-job override (video_options.tts_engine, sent by the frontend voice picker)
        silently beats TTS_ENGINE in .env. That is legitimate behaviour but invisible at
        the call site, so it gets stated explicitly -- otherwise a job pinned to Piper
        looks identical to XTTS failing to load.
        """
        env_value = (os.getenv("TTS_ENGINE") or "").strip().lower()
        override_value = (override or "").strip().lower()

        if override_value:
            selected = override_value
            reason = f"per-job override (video_options.tts_engine={override_value!r}) takes precedence over .env"
        elif env_value:
            selected = env_value
            reason = "TTS_ENGINE from .env, no per-job override"
        else:
            selected = "edge"
            reason = "TTS_ENGINE unset in the process environment (is env_bootstrap imported?), using built-in default"

        key = (env_value, override_value)
        if key not in cls._announced_selections:
            cls._announced_selections.add(key)
            logger.info(
                f"TTS_ENGINE env value = {env_value or '<unset>'}, "
                f"selected engine = {selected}, reason = {reason}"
            )
        return selected

    @classmethod
    def _sanitize_voice(cls, voice: Optional[str]) -> str:
        """Final authoritative override applied at the actual edge-tts call sites."""
        if not voice or voice in cls._DEPRECATED_VOICES:
            if voice:
                logger.warning(f"TTSEngine: Rejected deprecated voice '{voice}' at call site -- forcing '{cls.DEFAULT_VOICE}'.")
            return cls.DEFAULT_VOICE
        return voice

    @classmethod
    def generate_voiceover(cls, storyboard: Storyboard, output_dir: str, enable_vad_trimming: bool = True) -> Optional[str]:
        """
        Generate voiceover for the entire storyboard.
        Dynamically adjusts scene durations in-place based on speech audio length.
        Returns path to concatenated audio, or None if no speech exists.
        """
        os.makedirs(output_dir, exist_ok=True)

        if not any(getattr(s, "user_speech", None) or getattr(s, "speech_text", None) or s.narration for s in storyboard.scenes):
            logger.info("TTSEngine v3: No narration/speech found -- skipping voiceover.")
            return None

        # Generate per-scene audio and dynamically adjust scene durations
        per_scene_audios = cls._generate_per_scene(storyboard, output_dir, enable_vad_trimming=enable_vad_trimming)

        # Record audio provenance manifest on storyboard for quality check truthfulness
        setattr(storyboard, "tts_provenance_manifest", [a.provenance for a in per_scene_audios])
        setattr(storyboard, "has_degraded_audio_placeholder", any(a.provenance == "PLACEHOLDER_SYNTHETIC_TONE" for a in per_scene_audios))

        # Concatenate into single voiceover track
        concat_path = os.path.join(output_dir, "voiceover_speech.wav")
        master_path = os.path.join(output_dir, "voiceover.wav")
        cls._concatenate_wavs(per_scene_audios, concat_path)

        if os.path.exists(concat_path) and os.path.getsize(concat_path) > 0:
            # Phase 2: Apply CC0 background music bed with automatic audio ducking
            mood = getattr(storyboard, "music_mood", "corporate")
            has_sfx = bool(getattr(storyboard, "sfx_cues", None))
            final_audio = AudioDuckingEngine.apply_music_and_ducking(concat_path, master_path, mood=mood, has_sfx_risers=has_sfx)

            logger.info(f"TTSEngine v3: Full soundtrack (speech + ducked music '{mood}') -> {final_audio} "
                         f"({os.path.getsize(final_audio) / 1024:.1f} KB)")
            return final_audio
        return None

    @classmethod
    def generate_per_scene_manifest(cls, storyboard: Storyboard,
                                     output_dir: str,
                                     enable_vad_trimming: bool = True) -> List[PerSceneAudio]:
        """Generate and return per-scene audio manifest for sync."""
        os.makedirs(output_dir, exist_ok=True)
        return cls._generate_per_scene(storyboard, output_dir, enable_vad_trimming=enable_vad_trimming)

    @classmethod
    def _resolve_edge_voice(cls, voice: Optional[str], lang: "video_language.LanguageProfile") -> str:
        """
        Guarantee the Edge-TTS voice speaks the narration's language.

        The scene's voice_id is normally already correct (the producer defaults it from the
        same language profile), but it can arrive wrong from a user-supplied storyboard, a
        job persisted before language support existed, or an explicit voice_preference. A
        mismatch here is not a cosmetic issue -- it is a French script read aloud in an
        American accent -- so the language wins over the stale voice id, loudly.
        """
        candidate = cls._sanitize_voice(voice)
        if candidate.lower().startswith(f"{lang.code}-"):
            return candidate
        logger.warning(
            f"TTSEngine: Scene voice '{candidate}' does not speak {lang.label} ({lang.code}) -- "
            f"substituting '{lang.edge_voice}'. A mismatched voice would read the narration "
            f"with the wrong pronunciation rules."
        )
        return lang.edge_voice

    @classmethod
    def _generate_per_scene(cls, storyboard: Storyboard, output_dir: str, enable_vad_trimming: bool = True) -> List[PerSceneAudio]:
        results = []

        # One resolution for the whole storyboard: the language fixes BOTH the Kokoro voice
        # and the espeak tag that phonemises the text, and they must move together. Pairing
        # ff_siwis with en-us phonemes renders the same French line in 12.31s instead of
        # 10.56s -- French words forced through English pronunciation rules.
        lang = video_language.profile(getattr(storyboard, "language", None))
        logger.info(
            f"TTSEngine: Narration language = {lang.code} ({lang.label}) -- "
            f"Kokoro voice '{lang.kokoro_voice}' + G2P '{lang.kokoro_lang}', "
            f"Edge fallback voice '{lang.edge_voice}'."
        )

        for scene in storyboard.scenes:
            speech_text = getattr(scene, "user_speech", None) or getattr(scene, "speech_text", None) or scene.narration
            voice = cls._resolve_edge_voice(getattr(scene, "voice", None), lang)
            wav_path = os.path.join(output_dir, f"{scene.scene_id}_voice.wav")

            actual_duration = scene.duration_sec
            provenance = "NO_SPEECH_TEXT"

            word_timestamps = []  # Will be populated by Edge-TTS WordBoundary events

            if speech_text and speech_text.strip():
                generated, audio_duration, word_timestamps, provenance = cls._synthesize_scene(
                    speech_text.strip(), voice, wav_path, scene.scene_id,
                    engine_override=getattr(storyboard, "tts_engine", None),
                    lang=lang,
                )

                if generated and audio_duration > 0:
                    if enable_vad_trimming:
                        try:
                            from agents.video.audio_trimmer import VADTrimmer
                            trimmed_temp = wav_path + "_vad_trimmed.wav"
                            trim_info = VADTrimmer.trim_silence_from_wav(wav_path, trimmed_temp, min_silence_len_ms=300, silence_thresh_db=-40.0, keep_silence_ms=100)
                            if os.path.exists(trimmed_temp) and os.path.getsize(trimmed_temp) > 0:
                                shutil.move(trimmed_temp, wav_path)
                                audio_duration = trim_info["trimmed_duration_seconds"]
                                logger.info(f"TTSEngine [VADTrimmer]: Trimmed {trim_info['timing_delta_seconds']}s silence pause from '{scene.scene_id}' ({trim_info['original_duration_seconds']}s -> {audio_duration}s)")
                        except Exception as ve:
                            logger.warning(f"TTSEngine [VADTrimmer] warning: {ve}")

                    # Sync scene duration to the real narration length, in BOTH directions:
                    # extending so speech is never cut off, and shrinking so a scene whose
                    # narration is shorter than its planned slot doesn't sit on a silent
                    # tail. (LLM-authored narration varies in length per scene, so the
                    # planned budget is only an estimate.) MIN_SCENE_DURATION_SEC keeps
                    # very short lines on screen long enough to read.
                    adjusted_duration = max(audio_duration + 0.5, cls.MIN_SCENE_DURATION_SEC)
                    if abs(adjusted_duration - scene.duration_sec) > 0.05:
                        direction = "extend" if adjusted_duration > scene.duration_sec else "shrink"
                        logger.info(f"TTSEngine v3: Dynamic duration {direction} for '{scene.scene_id}': "
                                     f"{scene.duration_sec:.1f}s -> {adjusted_duration:.1f}s (audio={audio_duration:.1f}s)")
                        scene.duration_sec = adjusted_duration
                        actual_duration = adjusted_duration
                else:
                    provenance = "PLACEHOLDER_SYNTHETIC_TONE"
                    logger.warning(f"TTSEngine v3: Edge-TTS and pyttsx3 failed for '{scene.scene_id}'. Generating PLACEHOLDER_SYNTHETIC_TONE.")
                    cls._generate_silent_wav(wav_path, scene.duration_sec)
            else:
                cls._generate_silent_wav(wav_path, scene.duration_sec)

            # Store word timestamps on the scene object for downstream CaptionEngine access
            if word_timestamps:
                setattr(scene, "_tts_word_timestamps", word_timestamps)
                logger.info(f"TTSEngine v4: Attached {len(word_timestamps)} WordTimestamp objects to scene '{scene.scene_id}'")

            results.append(PerSceneAudio(
                scene_id=scene.scene_id,
                wav_path=wav_path,
                speech_text=speech_text or "",
                duration_sec=actual_duration,
                voice=voice,
                provenance=provenance,
                word_timestamps=word_timestamps
            ))

        storyboard.total_duration_sec = sum(s.duration_sec for s in storyboard.scenes)
        return results

    @classmethod
    def _synthesize_scene(cls, text: str, voice: str, wav_path: str, scene_id: str,
                          engine_override: Optional[str] = None,
                          lang: Optional["video_language.LanguageProfile"] = None) -> Tuple[bool, float, list, str]:
        """
        Runs the configured TTS chain for one scene.
        Returns (success, duration_sec, word_timestamps, provenance).

        TTS_ENGINE=kokoro -> Kokoro-82M then Edge-TTS then pyttsx3. (default)
        TTS_ENGINE=edge   -> Edge-TTS then pyttsx3.

        `lang` is the resolved profile for this video's narration language. It is passed
        explicitly rather than read from KOKORO_VOICE/KOKORO_LANG in the environment: those
        are process-wide, so two concurrent jobs in different languages would fight over
        them and one would come out voiced in the other's language. Defaults to English
        when a caller predates the language field.

        XTTS v2 and Piper were removed for commercial launch: XTTS's weights are CPML
        (non-commercial, and the licence covers generated audio) and Piper is GPL-3.0.
        See LICENSES.md R1 and R6.

        Engines are tried per scene rather than once per run: if one fails midway the
        remaining scenes still fall back cleanly, and every engine writes the same
        48 kHz stereo format so mixed-engine runs concatenate without artefacts.
        """
        from agents.video.kokoro_tts import KokoroEngine

        lang = lang or video_language.profile(None)
        cls._log_engine_selection(engine_override)

        # Kokoro is the only local engine still wired up. XTTS v2 (CPML, non-commercial)
        # and Piper (GPL-3.0) were both removed for commercial launch -- see LICENSES.md
        # R1 and R6. Anything other than 'kokoro' now resolves straight to Edge-TTS.
        if KokoroEngine.is_selected(engine_override):
            # voice and lang are handed over as a pair, always. Kokoro's voice pack and its
            # grapheme-to-phoneme layer are independent, so selecting the French voice while
            # leaving the phonemiser on en-us produces French words pronounced by English
            # rules -- audible, and 17% longer on the same sample line.
            ok, duration, timestamps = KokoroEngine.synthesize(
                text, wav_path, voice=lang.kokoro_voice, lang=lang.kokoro_lang
            )
            if ok and duration > 0:
                return True, duration, timestamps, "KOKORO_LOCAL_TTS"
            logger.warning(
                f"TTSEngine: Kokoro unavailable for '{scene_id}' -- falling back to Edge-TTS "
                f"with '{voice}' ({lang.label})."
            )

        # Edge-TTS with WordBoundary events (real per-word timestamps).
        generated, audio_duration, word_timestamps = cls._try_edge_tts_with_word_timestamps(text, voice, wav_path)
        if generated:
            if word_timestamps:
                logger.info(f"TTSEngine v4: Captured {len(word_timestamps)} real WordBoundary timestamps for '{scene_id}'")
            return True, audio_duration, word_timestamps, "NEURAL_TTS"

        # Edge-TTS CLI (no word timestamps).
        generated, audio_duration = cls._try_edge_tts(text, voice, wav_path)
        if generated:
            return True, audio_duration, [], "NEURAL_TTS"

        # Offline last resort.
        generated, audio_duration = cls._try_pyttsx3(text, wav_path)
        if generated:
            return True, audio_duration, [], "REAL_FALLBACK_OFFLINE_TTS"

        return False, 0.0, [], "NO_SPEECH_TEXT"

    @classmethod
    def _try_edge_tts_with_word_timestamps(cls, text: str, voice: str, output_path: str) -> Tuple[bool, float, list]:
        """
        Synthesize speech using Edge-TTS Python library with WordBoundary events.
        Returns (success, duration_sec, List[WordTimestamp]).
        Uses asyncio to run the async Communicate.stream() API.
        """
        temp_mp3 = output_path + ".mp3"
        word_timestamps = []
        voice = cls._sanitize_voice(voice)

        try:
            import edge_tts

            async def _synthesize():
                comm = edge_tts.Communicate(text, voice=voice, boundary="WordBoundary")
                audio_chunks = []
                timestamps = []

                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        audio_chunks.append(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        timestamps.append(WordTimestamp(
                            word=chunk["text"],
                            offset_sec=chunk["offset"] / 10_000_000.0,
                            duration_sec=chunk["duration"] / 10_000_000.0
                        ))

                # Write MP3
                with open(temp_mp3, "wb") as f:
                    for c in audio_chunks:
                        f.write(c)

                return timestamps

            # Run async synthesis
            word_timestamps = asyncio.run(_synthesize())

            if os.path.exists(temp_mp3) and os.path.getsize(temp_mp3) > 0:
                converted = cls._convert_mp3_to_wav(temp_mp3, output_path)
                if converted:
                    duration = cls._probe_audio_duration(output_path)
                    logger.info(f"TTSEngine v4: Edge-TTS WordBoundary synthesis voice '{voice}' "
                                f"({duration:.1f}s, {len(word_timestamps)} word timestamps) -> {output_path}")
                    if os.path.exists(temp_mp3):
                        os.remove(temp_mp3)
                    return True, duration, word_timestamps

            if os.path.exists(temp_mp3):
                os.remove(temp_mp3)
        except Exception as e:
            logger.warning(f"TTSEngine v4: Edge-TTS WordBoundary synthesis failed ({e})")
            if os.path.exists(temp_mp3):
                try:
                    os.remove(temp_mp3)
                except OSError:
                    pass

        return False, 0.0, []

    @classmethod
    def _try_edge_tts(cls, text: str, voice: str, output_path: str) -> Tuple[bool, float]:
        """
        Fallback: Synthesize speech using Edge-TTS CLI via subprocess (no word timestamps).
        """
        temp_mp3 = output_path + ".mp3"
        python_exe = sys.executable
        voice = cls._sanitize_voice(voice)

        cmd = [
            python_exe, "-m", "edge_tts",
            "--text", text,
            "--voice", voice,
            "--write-media", temp_mp3
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if result.returncode == 0 and os.path.exists(temp_mp3) and os.path.getsize(temp_mp3) > 0:
                converted = cls._convert_mp3_to_wav(temp_mp3, output_path)
                if converted:
                    duration = cls._probe_audio_duration(output_path)
                    logger.info(f"TTSEngine v3: Edge-TTS CLI synthesized voice '{voice}' ({duration:.1f}s) -> {output_path}")
                    if os.path.exists(temp_mp3):
                        os.remove(temp_mp3)
                    return True, duration

            if os.path.exists(temp_mp3):
                os.remove(temp_mp3)
        except Exception as e:
            logger.warning(f"TTSEngine v3: Edge-TTS subprocess failed ({e})")
            if os.path.exists(temp_mp3):
                os.remove(temp_mp3)

        return False, 0.0

    @classmethod
    def _try_pyttsx3(cls, text: str, output_path: str) -> Tuple[bool, float]:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 155)
            engine.setProperty("volume", 0.9)
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                duration = cls._probe_audio_duration(output_path)
                return True, duration
        except Exception as e:
            logger.warning(f"TTSEngine v3: pyttsx3 fallback failed ({e})")
        return False, 0.0

    @classmethod
    def _convert_mp3_to_wav(cls, mp3_path: str, wav_path: str) -> bool:
        """Convert MP3 file to PCM WAV using imageio-ffmpeg or ffmpeg subprocess."""
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            try:
                import imageio_ffmpeg
                ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg_bin = None

        if not ffmpeg_bin:
            # Simple fallback: copy file if conversion tool unavailable
            shutil.copyfile(mp3_path, wav_path)
            return True

        cmd = [
            ffmpeg_bin, "-y",
            "-i", mp3_path,
            "-acodec", "pcm_s16le",
            "-ar", "48000",
            "-ac", "2",
            wav_path
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if res.returncode == 0 and os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
                return True
        except Exception as e:
            logger.warning(f"TTSEngine v3: MP3 to WAV conversion failed ({e})")
        return False

    @classmethod
    def _probe_audio_duration(cls, wav_path: str) -> float:
        """Probe duration of a WAV file in seconds."""
        try:
            with wave.open(wav_path, "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    return frames / float(rate)
        except Exception as e:
            logger.warning(f"TTSEngine v3: Could not probe WAV duration ({e})")
        return 3.0

    @classmethod
    def _concatenate_wavs(cls, audios: List[PerSceneAudio], output_path: str):
        """Concatenate per-scene WAV files into a single track."""
        if not audios:
            return

        valid_wavs = [a for a in audios if os.path.exists(a.wav_path) and os.path.getsize(a.wav_path) > 0]
        if not valid_wavs:
            cls._generate_silent_wav(output_path, sum(a.duration_sec for a in audios))
            return

        try:
            with wave.open(valid_wavs[0].wav_path, "rb") as wf:
                params = wf.getparams()

            with wave.open(output_path, "wb") as out_wf:
                out_wf.setparams(params)
                for audio in audios:
                    if os.path.exists(audio.wav_path):
                        with wave.open(audio.wav_path, "rb") as wf:
                            # Raw frame append only works when the formats agree; a
                            # mismatch would play that scene at the wrong pitch and speed
                            # instead of failing, so say so rather than emitting it.
                            fmt = (wf.getnchannels(), wf.getsampwidth(), wf.getframerate())
                            if fmt != (params.nchannels, params.sampwidth, params.framerate):
                                logger.warning(
                                    f"TTSEngine: Skipping '{audio.scene_id}' in concat -- format "
                                    f"{fmt[2]} Hz/{fmt[0]}ch does not match the track's "
                                    f"{params.framerate} Hz/{params.nchannels}ch."
                                )
                                continue
                            out_wf.writeframes(wf.readframes(wf.getnframes()))
        except Exception as e:
            logger.warning(f"TTSEngine v3: WAV concatenation error ({e}), generating silent track")
            total_dur = sum(a.duration_sec for a in audios)
            cls._generate_silent_wav(output_path, total_dur)

    @classmethod
    def _generate_silent_wav(cls, path: str, duration_sec: float) -> str:
        """
        Generates speech-cadence modulated audio waveform fallback so audio streams are NEVER silent.

        Written in the same 48 kHz stereo format as every real engine: _concatenate_wavs
        copies the header of the first scene only and appends raw frames from the rest,
        so a placeholder in a different format would pitch-shift every later scene.
        """
        import math
        sample_rate = 48000
        channels = 2
        num_frames = int(sample_rate * max(duration_sec, 0.5))
        samples = []
        for i in range(num_frames):
            t = i / sample_rate
            # 220Hz fundamental speech formant tone with 4Hz word cadence modulation
            cadence = 0.5 + 0.5 * math.sin(2 * math.pi * 4.0 * t)
            val = int(8000 * cadence * math.sin(2 * math.pi * 220.0 * t))
            samples.extend([val] * channels)

        with wave.open(path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))
        return path
