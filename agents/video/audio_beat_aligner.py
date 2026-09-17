"""
Production-Grade Audio Onset & Beat-Matched Transition Scheduler for VideoAgent.

Performs STFT spectral flux waveform analysis, peak onset detection, and dynamic tempo estimation
using NumPy and SciPy to align video scene transitions with music transients.
Supports duration preservation policy, non-WAV audio conversion via FFmpeg, and strict timeline invariants.
"""
import os
import wave
import time
import tempfile
import subprocess
import logging
import numpy as np
import scipy.signal
import scipy.io.wavfile
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


# ============================================================================
# CONFIGURABLE DURATION POLICY & TYPED SCHEMAS
# ============================================================================

class DurationPreservationMode(str, Enum):
    PRESERVE_FINAL_END = "preserve_final_end"
    ALLOW_TIMELINE_DRIFT = "allow_timeline_drift"


class DetectedBeat(BaseModel):
    timestamp: float
    confidence: float = Field(ge=0.0, le=1.0)
    source: str  # "detected", "extrapolated", "fallback_grid"


class SceneBeatAlignment(BaseModel):
    scene_index: int
    original_start: float
    original_end: float
    target_end: float
    aligned_start: float
    aligned_end: float
    candidate_beat: Optional[float] = None
    selected_beat: Optional[float] = None
    candidate_delta: Optional[float] = None
    alignment_delta: float = 0.0
    snap_delta: float = 0.0
    snap_applied: bool
    preservation_reason: str

    def __getitem__(self, item: str) -> Any:
        """Backward compatibility for dictionary indexing."""
        mapping = {
            "scene_index": self.scene_index,
            "start_time": self.aligned_start,
            "end_time": self.aligned_end,
            "duration": round(self.aligned_end - self.aligned_start, 3),
            "beat_snap_delta_ms": round(self.alignment_delta * 1000, 1),
            "original_start": self.original_start,
            "original_end": self.original_end,
            "target_end": self.target_end,
            "candidate_beat": self.candidate_beat,
            "selected_beat": self.selected_beat,
            "candidate_delta": self.candidate_delta,
            "alignment_delta": self.alignment_delta,
            "snap_delta": self.alignment_delta,
            "snap_applied": self.snap_applied,
            "preservation_reason": self.preservation_reason,
            "beat_confidence": 1.0 if self.selected_beat is not None else None
        }
        if item in mapping:
            return mapping[item]
        raise KeyError(f"Invalid key '{item}' for SceneBeatAlignment")


class BeatAlignmentResult(BaseModel):
    estimated_bpm: Optional[float] = None
    detection_method: str  # "spectral_flux_onset", "fallback_grid"
    detected_beats: List[DetectedBeat] = Field(default_factory=list)
    scene_alignments: List[SceneBeatAlignment] = Field(default_factory=list)
    fallback_used: bool = False
    original_source_path: Optional[str] = None
    duration_preservation_mode: DurationPreservationMode = DurationPreservationMode.PRESERVE_FINAL_END
    warnings: List[str] = Field(default_factory=list)

    def __len__(self) -> int:
        """Backward compatibility: returns count of scene alignments."""
        return len(self.scene_alignments)

    def __getitem__(self, index: int) -> Dict[str, Any]:
        """Backward compatibility: returns dictionary representation of alignment at index."""
        item = self.scene_alignments[index]
        return {
            "scene_index": item.scene_index,
            "start_time": item.aligned_start,
            "end_time": item.aligned_end,
            "duration": round(item.aligned_end - item.aligned_start, 3),
            "beat_snap_delta_ms": round(item.snap_delta * 1000, 1)
        }

    def __iter__(self):
        """Backward compatibility: iterate over legacy dictionary representations."""
        for item in self.scene_alignments:
            yield {
                "scene_index": item.scene_index,
                "start_time": item.aligned_start,
                "end_time": item.aligned_end,
                "duration": round(item.aligned_end - item.aligned_start, 3),
                "beat_snap_delta_ms": round(item.snap_delta * 1000, 1)
            }


# ============================================================================
# CORE WAVEFORM ALIGNER
# ============================================================================

class AudioBeatAligner:
    """
    Production-Grade Audio Beat Aligner supporting STFT Spectral Flux Waveform Analysis.
    """

    @classmethod
    def convert_audio_to_pcm_wav(
        cls,
        input_audio_path: str,
        target_sample_rate: int = 22050
    ) -> tuple[str, bool]:
        """
        Converts non-WAV audio (MP3, AAC, M4A, OGG) to temporary 16-bit mono PCM WAV using imageio_ffmpeg.
        Returns (temp_wav_path, is_temporary).
        """
        path_str = str(input_audio_path)
        if not os.path.exists(path_str):
            raise FileNotFoundError(f"Audio file not found: '{path_str}'")

        # If already a valid PCM WAV, return directly
        if path_str.lower().endswith(".wav"):
            try:
                with wave.open(path_str, "rb") as wf:
                    if wf.getsampwidth() in (2, 3, 4):
                        return path_str, False
            except Exception:
                pass

        # Use imageio_ffmpeg utility to convert to PCM WAV
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_exe = "ffmpeg"

        temp_wav = tempfile.NamedTemporaryFile(suffix="_converted.wav", delete=False)
        temp_wav.close()

        cmd = [
            ffmpeg_exe,
            "-y",
            "-i", path_str,
            "-vn",
            "-ac", "1",
            "-ar", str(target_sample_rate),
            "-sample_fmt", "s16",
            temp_wav.name
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            logger.info(f"AudioBeatAligner: Converted '{path_str}' to temporary WAV via FFmpeg -> '{temp_wav.name}'")
            return temp_wav.name, True
        except Exception as e:
            if os.path.exists(temp_wav.name):
                try:
                    os.remove(temp_wav.name)
                except Exception:
                    pass
            raise ValueError(f"FFmpeg audio conversion failed for '{path_str}': {e}")

    @classmethod
    def load_and_preprocess_audio(
        cls,
        audio_path: Union[str, Path],
        target_sample_rate: int = 22050
    ) -> tuple[np.ndarray, int, float, str, bool]:
        """
        Loads audio file, converts stereo to mono, resamples to target_sample_rate, and normalizes.
        Returns (waveform, sample_rate, duration_sec, actual_wav_path, is_temp_file).
        """
        orig_path = str(audio_path)
        actual_wav_path, is_temp = cls.convert_audio_to_pcm_wav(orig_path, target_sample_rate=target_sample_rate)

        try:
            sr, data = scipy.io.wavfile.read(actual_wav_path)
        except Exception:
            with wave.open(actual_wav_path, "rb") as wf:
                sr = wf.getframerate()
                n_channels = wf.getnchannels()
                n_frames = wf.getnframes()
                frames = wf.readframes(n_frames)
                if wf.getsampwidth() == 2:
                    data = np.frombuffer(frames, dtype=np.int16)
                else:
                    data = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128
                if n_channels > 1:
                    data = data.reshape(-1, n_channels)

        # Convert to float32
        data = data.astype(np.float32)

        # Stereo to Mono
        if data.ndim > 1:
            data = np.mean(data, axis=1)

        # Resample if sample rates differ
        if sr != target_sample_rate and len(data) > 0:
            num_samples = int(round(len(data) * float(target_sample_rate) / sr))
            data = scipy.signal.resample(data, num_samples)
            sr = target_sample_rate

        # Normalize waveform to [-1.0, 1.0]
        max_amp = np.max(np.abs(data))
        if max_amp > 0:
            data = data / max_amp

        duration_sec = len(data) / float(sr) if sr > 0 else 0.0
        return data, sr, duration_sec, actual_wav_path, is_temp

    @classmethod
    def compute_spectral_flux_onsets(
        cls,
        waveform: np.ndarray,
        sample_rate: int,
        fft_window_size: int = 1024,
        hop_length: int = 512,
        spectral_flux_threshold: float = 0.1,
        min_onset_interval_sec: float = 0.2
    ) -> tuple[List[DetectedBeat], Optional[float]]:
        """
        Computes STFT, calculates spectral flux onset envelope, detects peak timestamps, and estimates BPM.
        """
        if len(waveform) < fft_window_size:
            return [], None

        freqs, times, Zxx = scipy.signal.stft(
            waveform,
            fs=sample_rate,
            nperseg=fft_window_size,
            noverlap=fft_window_size - hop_length
        )

        spectrogram = np.abs(Zxx)
        diff = np.diff(spectrogram, axis=1)
        flux = np.maximum(0, diff)
        onset_envelope = np.sum(flux, axis=0)

        max_flux = np.max(onset_envelope)
        if max_flux > 0:
            onset_envelope = onset_envelope / max_flux

        frame_rate = float(sample_rate) / hop_length
        min_distance_frames = max(1, int(round(min_onset_interval_sec * frame_rate)))

        peaks, properties = scipy.signal.find_peaks(
            onset_envelope,
            height=spectral_flux_threshold,
            distance=min_distance_frames
        )

        detected_beats = []
        peak_times = []

        for p in peaks:
            timestamp = round(float(p) * hop_length / float(sample_rate), 3)
            confidence = round(float(onset_envelope[p]), 3)
            peak_times.append(timestamp)
            detected_beats.append(DetectedBeat(
                timestamp=timestamp,
                confidence=confidence,
                source="detected"
            ))

        estimated_bpm = None
        if len(peak_times) >= 2:
            intervals = np.diff(peak_times)
            valid_intervals = intervals[(intervals >= 0.3) & (intervals <= 1.0)]
            if len(valid_intervals) > 0:
                median_interval = float(np.median(valid_intervals))
                if median_interval > 0:
                    estimated_bpm = round(60.0 / median_interval, 1)

        return detected_beats, estimated_bpm

    @classmethod
    def align_scenes_to_beats(
        cls,
        scene_durations: List[float],
        audio_path: Optional[Union[str, Path]] = None,
        target_bpm: Optional[float] = None,
        max_snap_seconds: float = 0.25,
        min_scene_duration: float = 1.0,
        duration_mode: DurationPreservationMode = DurationPreservationMode.PRESERVE_FINAL_END,
        analysis_sample_rate: int = 22050,
        fft_window_size: int = 1024,
        hop_length: int = 512,
        spectral_flux_threshold: float = 0.1,
        min_onset_interval_sec: float = 0.2
    ) -> BeatAlignmentResult:
        """
        Aligns scene boundaries to real audio waveform onset beats or mathematical BPM grid.
        Rounds to nearest eligible beat within max_snap_seconds, enforces min_scene_duration,
        and respects configured DurationPreservationMode.
        """
        t0 = time.time()
        warnings = []
        fallback_used = False
        detection_method = "spectral_flux_onset"
        detected_beats: List[DetectedBeat] = []
        estimated_bpm: Optional[float] = target_bpm
        actual_temp_wav: Optional[str] = None
        is_temp_file: bool = False

        total_original_duration = round(sum(scene_durations), 3)
        num_scenes = len(scene_durations)

        # Stage 1: Try real audio waveform analysis if audio_path is supplied
        if audio_path is not None:
            try:
                waveform, sr, dur, actual_temp_wav, is_temp_file = cls.load_and_preprocess_audio(
                    audio_path, target_sample_rate=analysis_sample_rate
                )
                logger.info(f"AudioBeatAligner: Loaded '{audio_path}' ({dur:.2f}s, {sr}Hz, waveform len={len(waveform)})")

                beats, est_bpm = cls.compute_spectral_flux_onsets(
                    waveform,
                    sample_rate=sr,
                    fft_window_size=fft_window_size,
                    hop_length=hop_length,
                    spectral_flux_threshold=spectral_flux_threshold,
                    min_onset_interval_sec=min_onset_interval_sec
                )

                if beats:
                    detected_beats = beats
                    if not target_bpm and est_bpm:
                        estimated_bpm = est_bpm
                    logger.info(f"AudioBeatAligner: Detected {len(detected_beats)} onset beats. Estimated BPM: {estimated_bpm}")
                else:
                    warnings.append("No onset peaks detected in audio waveform. Falling back to mathematical grid.")
                    fallback_used = True
            except Exception as exc:
                warnings.append(f"Audio analysis failed ({exc}). Falling back to mathematical grid.")
                fallback_used = True
            finally:
                if is_temp_file and actual_temp_wav and os.path.exists(actual_temp_wav):
                    try:
                        os.remove(actual_temp_wav)
                    except Exception:
                        pass
        else:
            warnings.append("No audio_path provided. Using mathematical BPM grid alignment.")
            fallback_used = True

        # Stage 2: Fallback to mathematical grid if no real beats detected
        if fallback_used or not detected_beats:
            detection_method = "fallback_grid"
            bpm = target_bpm or 120.0
            estimated_bpm = bpm
            sec_per_beat = 60.0 / bpm
            
            detected_beats = []
            t_beat = 0.0
            while t_beat <= total_original_duration + 5.0:
                detected_beats.append(DetectedBeat(
                    timestamp=round(t_beat, 3),
                    confidence=1.0,
                    source="fallback_grid"
                ))
                t_beat += sec_per_beat

        # Stage 3: Align Scene Boundaries (Nearest Eligible Beat Rounding & Timeline Invariants)
        scene_alignments: List[SceneBeatAlignment] = []
        current_aligned_start = 0.0
        cumulative_original_start = 0.0

        for idx, raw_dur in enumerate(scene_durations, 1):
            original_start = round(cumulative_original_start, 3)
            original_end = round(original_start + raw_dur, 3)
            target_cut_time = round(current_aligned_start + raw_dur, 3)

            is_final_scene = (idx == num_scenes)

            # Evaluate beats for rounding to nearest eligible beat
            candidate_beat_val: Optional[float] = None
            selected_beat_val: Optional[float] = None
            snap_applied = False
            preservation_reason = ""

            # Find all beats within max_snap_seconds that satisfy min_scene_duration
            eligible_beats = [
                b for b in detected_beats
                if (b.timestamp - current_aligned_start) >= min_scene_duration
                and abs(b.timestamp - target_cut_time) <= max_snap_seconds
            ]

            if eligible_beats:
                nearest_b = min(eligible_beats, key=lambda b: abs(b.timestamp - target_cut_time))
                candidate_beat_val = nearest_b.timestamp

            # Calculate candidate_delta and alignment_delta explicitly
            cand_delta = round(candidate_beat_val - target_cut_time, 3) if candidate_beat_val is not None else None

            # Check if this is the final scene under PRESERVE_FINAL_END policy
            if is_final_scene and duration_mode == DurationPreservationMode.PRESERVE_FINAL_END:
                aligned_end = total_original_duration
                selected_beat_val = None
                snap_applied = False
                preservation_reason = "final_endpoint_preserved_by_duration_policy"
            else:
                if candidate_beat_val is not None:
                    aligned_end = candidate_beat_val
                    selected_beat_val = candidate_beat_val
                    snap_applied = True
                    preservation_reason = "snapped_to_nearest_beat"
                else:
                    aligned_end = round(max(current_aligned_start + min_scene_duration, target_cut_time), 3)
                    selected_beat_val = None
                    snap_applied = False
                    preservation_reason = "candidate_exceeded_max_snap_seconds_or_min_duration"

            align_delta = round(aligned_end - target_cut_time, 3)

            scene_alignments.append(SceneBeatAlignment(
                scene_index=idx,
                original_start=original_start,
                original_end=original_end,
                target_end=target_cut_time,
                aligned_start=round(current_aligned_start, 3),
                aligned_end=round(aligned_end, 3),
                candidate_beat=candidate_beat_val,
                selected_beat=selected_beat_val,
                candidate_delta=cand_delta,
                alignment_delta=align_delta,
                snap_delta=align_delta,
                snap_applied=snap_applied,
                preservation_reason=preservation_reason
            ))

            current_aligned_start = aligned_end
            cumulative_original_start += raw_dur

        # Stage 4: Strict Timeline Invariants Validation
        assert abs(scene_alignments[0].aligned_start) < 1e-5, "Invariant violated: aligned_start[0] != 0"
        for i in range(len(scene_alignments)):
            assert scene_alignments[i].aligned_end > scene_alignments[i].aligned_start, f"Invariant violated: scene {i+1} has non-positive duration"
            if i > 0:
                assert abs(scene_alignments[i].aligned_start - scene_alignments[i-1].aligned_end) < 1e-5, f"Invariant violated: gap/overlap between scene {i} and {i+1}"

        if duration_mode == DurationPreservationMode.PRESERVE_FINAL_END:
            assert abs(scene_alignments[-1].aligned_end - total_original_duration) < 1e-5, "Invariant violated: final duration != total original duration under PRESERVE_FINAL_END"

        dt = time.time() - t0
        logger.info(f"AudioBeatAligner: Aligned {num_scenes} scenes in {dt:.3f}s. Fallback: {fallback_used}. Mode: {duration_mode.value}")

        return BeatAlignmentResult(
            estimated_bpm=estimated_bpm,
            detection_method=detection_method,
            detected_beats=detected_beats,
            scene_alignments=scene_alignments,
            fallback_used=fallback_used,
            original_source_path=str(audio_path) if audio_path else None,
            duration_preservation_mode=duration_mode,
            warnings=warnings
        )
