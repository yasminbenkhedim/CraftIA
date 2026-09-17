"""
Smart Silence & Filler Trimming Engine for VideoAgent.
"""
import os
import wave
import numpy as np
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("uvicorn")


class SmartAudioTrimmer:
    """
    Automated Amplitude-Threshold Silencer for speech narration.
    Strips silent pauses (>300ms) while preserving speech boundaries via a keep-silence buffer.
    """

    DETECTION_METHOD = "Amplitude-threshold silence detection"

    @classmethod
    def trim_silence_from_wav(
        cls,
        input_wav_path: str,
        output_wav_path: str,
        min_silence_len_ms: int = 300,
        silence_thresh_db: float = -40.0,
        keep_silence_ms: int = 100
    ) -> Dict[str, Any]:
        """
        Trims silence pauses from WAV audio file and records removed intervals.
        """
        os.makedirs(os.path.dirname(output_wav_path), exist_ok=True)

        trimmed_via_pydub = False
        trimmed_duration = 0.0
        original_duration = 0.0
        removed_intervals: List[Tuple[float, float]] = []

        try:
            from pydub import AudioSegment
            from pydub.silence import split_on_silence

            sound = AudioSegment.from_wav(input_wav_path)
            original_duration = len(sound) / 1000.0

            chunks = split_on_silence(
                sound,
                min_silence_len=min_silence_len_ms,
                silence_thresh=sound.dBFS + silence_thresh_db if sound.dBFS > -90 else silence_thresh_db,
                keep_silence=keep_silence_ms
            )

            if chunks:
                trimmed_sound = AudioSegment.empty()
                for chunk in chunks:
                    trimmed_sound += chunk
                trimmed_sound.export(output_wav_path, format="wav")
                trimmed_duration = len(trimmed_sound) / 1000.0
                trimmed_via_pydub = True
        except ImportError:
            logger.info("pydub not installed; using amplitude-threshold SciPy/NumPy energy fallback.")

        if not trimmed_via_pydub:
            original_duration, trimmed_duration, removed_intervals = cls._trim_silence_numpy_energy(
                input_wav_path, output_wav_path, min_silence_len_ms, silence_thresh_db, keep_silence_ms
            )

        timing_delta = round(original_duration - trimmed_duration, 3)

        return {
            "detection_method": cls.DETECTION_METHOD,
            "input_wav_path": input_wav_path,
            "output_wav_path": output_wav_path,
            "min_silence_len_ms": min_silence_len_ms,
            "silence_thresh_db": silence_thresh_db,
            "keep_silence_ms": keep_silence_ms,
            "original_duration_seconds": round(original_duration, 3),
            "trimmed_duration_seconds": round(trimmed_duration, 3),
            "timing_delta_seconds": timing_delta,
            "removed_intervals_count": len(removed_intervals),
            "removed_intervals": removed_intervals
        }

    @classmethod
    def _trim_silence_numpy_energy(
        cls,
        input_path: str,
        output_path: str,
        min_silence_len_ms: int,
        silence_thresh_db: float,
        keep_silence_ms: int
    ) -> Tuple[float, float, List[Tuple[float, float]]]:
        with wave.open(input_path, 'rb') as wf:
            params = wf.getparams()
            frames = wf.readframes(params.nframes)

        sample_width = params.sampwidth
        n_channels = params.nchannels
        framerate = params.framerate

        data = np.frombuffer(frames, dtype=np.int16 if sample_width == 2 else np.int8)
        orig_dur = len(data) / (framerate * n_channels)

        if len(data) == 0:
            with wave.open(output_path, 'wb') as wf:
                wf.setparams(params)
                wf.writeframes(frames)
            return orig_dur, orig_dur, []

        frame_size = int(framerate * 0.02 * n_channels)  # 20ms frame
        num_frames = len(data) // frame_size

        if num_frames == 0:
            with wave.open(output_path, 'wb') as wf:
                wf.setparams(params)
                wf.writeframes(frames)
            return orig_dur, orig_dur, []

        data_frames = data[:num_frames * frame_size].reshape(num_frames, frame_size)
        rms = np.sqrt(np.mean(data_frames.astype(np.float32) ** 2, axis=1))
        max_rms = np.max(rms) + 1e-6

        thresh_rms = max_rms * (10 ** (silence_thresh_db / 20.0))
        active_indices = np.where(rms > thresh_rms)[0]

        removed_intervals = []
        if len(active_indices) == 0:
            keep_frames = data_frames
        else:
            buffer_frames = int((keep_silence_ms / 1000.0) / 0.02)
            first_idx = max(0, active_indices[0] - buffer_frames)
            last_idx = min(num_frames, active_indices[-1] + buffer_frames)

            if first_idx > 0:
                removed_intervals.append((0.0, round(first_idx * 0.02, 3)))
            if last_idx < num_frames:
                removed_intervals.append((round(last_idx * 0.02, 3), round(num_frames * 0.02, 3)))

            keep_frames = data_frames[first_idx:last_idx]

        trimmed_data = keep_frames.flatten()
        trimmed_dur = len(trimmed_data) / (framerate * n_channels)

        with wave.open(output_path, 'wb') as wf:
            wf.setparams((params.nchannels, params.sampwidth, params.framerate, len(trimmed_data) // params.nchannels, params.comptype, params.compname))
            wf.writeframes(trimmed_data.tobytes())

        return orig_dur, trimmed_dur, removed_intervals


# Alias for pipeline compatibility
VADTrimmer = SmartAudioTrimmer
