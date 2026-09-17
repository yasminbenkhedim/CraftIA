"""
Word-Level Caption Timing Engine -- Priority 3 Integration.
Combines utterance timestamps, character-proportional weighting, punctuation pause padding,
natural speech pause gaps, hard 150ms minimum duration floor, and DSP WAV waveform RMS silence-gap refinement.
"""
import os
import wave
import logging
import numpy as np
from typing import List, Dict, Any, Optional

logger = logging.getLogger("uvicorn")


class WordCaption:
    def __init__(self, word: str, start_sec: float, end_sec: float, scene_id: str):
        self.word = word
        self.start_sec = round(float(start_sec), 3)
        self.end_sec = round(float(end_sec), 3)
        self.scene_id = scene_id

    @property
    def duration_sec(self) -> float:
        return round(self.end_sec - self.start_sec, 3)

    def __repr__(self):
        return f"<WordCaption '{self.word}' [{self.start_sec:.3f}s - {self.end_sec:.3f}s] (dur={self.duration_sec:.3f}s)>"


class CaptionEngine:
    """
    Computes precise word-level caption timelines with punctuation pause gaps,
    DSP silence-gap refinement, and hard 150ms duration floor enforcement.
    """

    MIN_WORD_FLOOR_SEC = 0.150       # 150ms minimum duration floor per word
    PUNCTUATION_PERIOD_GAP_SEC = 0.250 # 250ms natural speech pause gap after . ! ?
    PUNCTUATION_COMMA_GAP_SEC = 0.150  # 150ms natural speech pause gap after , ; :

    @classmethod
    def generate_word_timeline(cls, speech_text: str, start_sec: float, end_sec: float,
                                scene_id: str, wav_path: Optional[str] = None,
                                tts_word_timestamps: Optional[List] = None) -> List[WordCaption]:
        if not speech_text or not speech_text.strip():
            return []

        words = speech_text.strip().split()
        if not words:
            return []

        # PRIMARY PATH: Use real TTS word timestamps when available. These come from
        # Edge-TTS WordBoundary events or Piper phoneme alignments depending on the
        # configured engine -- both produce the same WordTimestamp shape.
        if tts_word_timestamps and len(tts_word_timestamps) > 0:
            timeline = cls._build_from_real_timestamps(words, tts_word_timestamps, start_sec, scene_id)
            if timeline:
                logger.info(f"CaptionEngine: Using {len(timeline)} REAL TTS word timestamps for '{scene_id}' (primary path)")

                # Apply DSP silence-gap refinement as secondary polish on top of real timestamps
                if wav_path and os.path.exists(wav_path):
                    p_gaps = cls._compute_punctuation_gaps(words)
                    cls._apply_dsp_silence_refinement(timeline, wav_path, start_sec, end_sec, p_gaps)

                # Enforce hard floors
                p_gaps = cls._compute_punctuation_gaps(words)
                cls._enforce_hard_floors_and_continuity(timeline, p_gaps)
                return timeline

        # FALLBACK PATH: Character-proportional estimation (no real timestamps available)
        logger.info(f"CaptionEngine: No real TTS timestamps for '{scene_id}' — using character-proportional estimation (fallback path)")

        # 1. Compute total required punctuation pause time
        p_gaps = cls._compute_punctuation_gaps(words)
        total_pause_sec = sum(p_gaps)

        # Subtract total pause time from speech budget to get pure word speech duration
        available_speech_duration = max(end_sec - start_sec - total_pause_sec, len(words) * cls.MIN_WORD_FLOOR_SEC)

        # 2. Character-proportional weighting
        char_counts = [max(1, len(w.rstrip(".,!?;:"))) for w in words]
        total_chars = sum(char_counts)
        raw_durations = [(c / total_chars) * available_speech_duration for c in char_counts]

        # 3. Build baseline timeline with punctuation pause gaps
        timeline: List[WordCaption] = []
        curr = start_sec
        for i, w in enumerate(words):
            dur = max(raw_durations[i], cls.MIN_WORD_FLOOR_SEC)
            end = curr + dur
            timeline.append(WordCaption(w, curr, end, scene_id))
            # Advance time by word duration + punctuation pause gap
            curr = end + p_gaps[i]

        # 4. DSP WAV Waveform RMS Silence-Gap Refinement (if WAV available)
        if wav_path and os.path.exists(wav_path):
            cls._apply_dsp_silence_refinement(timeline, wav_path, start_sec, end_sec, p_gaps)

        # 5. HARD POST-PROCESSING PASS: Guarantee >= 150ms floor and preserve intended pause gaps
        cls._enforce_hard_floors_and_continuity(timeline, p_gaps)

        return timeline

    @classmethod
    def _build_from_real_timestamps(cls, words: List[str], tts_timestamps: List, start_sec: float,
                                     scene_id: str) -> Optional[List[WordCaption]]:
        """
        Build word timeline from real Edge-TTS WordBoundary timestamps.
        Aligns TTS timestamp words to speech_text words by position.
        """
        timeline = []

        # Match by position — TTS may strip punctuation from word text
        for i, word in enumerate(words):
            if i < len(tts_timestamps):
                ts = tts_timestamps[i]
                # Use real offset + duration from Edge-TTS, shifted by scene start_sec
                word_start = start_sec + ts.offset_sec
                word_end = start_sec + ts.end_sec
                # Ensure minimum floor
                if word_end - word_start < cls.MIN_WORD_FLOOR_SEC:
                    word_end = word_start + cls.MIN_WORD_FLOOR_SEC
                timeline.append(WordCaption(word, word_start, word_end, scene_id))
            else:
                # More words in text than TTS timestamps — estimate remainder
                if timeline:
                    prev_end = timeline[-1].end_sec
                else:
                    prev_end = start_sec
                timeline.append(WordCaption(word, prev_end, prev_end + cls.MIN_WORD_FLOOR_SEC, scene_id))

        return timeline if timeline else None

    @classmethod
    def _compute_punctuation_gaps(cls, words: List[str]) -> List[float]:
        """Compute punctuation pause gaps for each word."""
        p_gaps = []
        for w in words:
            gap = 0.0
            if w.endswith((".", "!", "?")):
                gap = cls.PUNCTUATION_PERIOD_GAP_SEC
            elif w.endswith((",", ";", ":")):
                gap = cls.PUNCTUATION_COMMA_GAP_SEC
            p_gaps.append(gap)
        return p_gaps

    @classmethod
    def _apply_dsp_silence_refinement(cls, timeline: List[WordCaption], wav_path: str,
                                       start_sec: float, end_sec: float, p_gaps: List[float]):
        try:
            with wave.open(wav_path, "rb") as wf:
                sr = wf.getframerate()
                nframes = wf.getnframes()
                frames = wf.readframes(nframes)
                samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)

            idx_start = int(start_sec * sr)
            idx_end = min(int(end_sec * sr), len(samples))
            if idx_end <= idx_start:
                return

            utterance_samples = samples[idx_start:idx_end]
            window_samples = int(sr * 0.015)  # 15ms windows
            num_windows = len(utterance_samples) // window_samples
            if num_windows < 2:
                return

            rms_env = []
            for w in range(num_windows):
                chunk = utterance_samples[w * window_samples:(w + 1) * window_samples]
                rms = np.sqrt(np.mean(chunk ** 2)) if len(chunk) > 0 else 0
                rms_env.append(rms)

            rms_env = np.array(rms_env)
            threshold = np.mean(rms_env) * 0.25
            silence_windows = np.where(rms_env < threshold)[0]

            for i in range(len(timeline) - 1):
                item = timeline[i]
                target_end = item.end_sec
                target_win = int((target_end - start_sec) / 0.015)

                nearby_dips = [w for w in silence_windows if abs(w - target_win) <= 4]
                if nearby_dips:
                    best_dip = min(nearby_dips, key=lambda w: abs(w - target_win))
                    adjusted_end = round(start_sec + best_dip * 0.015, 3)

                    # Only adjust if new end time preserves >= 150ms floor
                    if adjusted_end >= item.start_sec + cls.MIN_WORD_FLOOR_SEC:
                        diff = adjusted_end - item.end_sec
                        item.end_sec = adjusted_end

                        # Ripple shift start of next word accounting for punctuation pause gap
                        intended_gap = p_gaps[i]
                        timeline[i + 1].start_sec = item.end_sec + intended_gap
                        timeline[i + 1].end_sec = max(
                            timeline[i + 1].end_sec + diff,
                            timeline[i + 1].start_sec + cls.MIN_WORD_FLOOR_SEC
                        )

        except Exception as e:
            logger.warning(f"CaptionEngine: DSP silence refinement exception ({e})")

    @classmethod
    def _enforce_hard_floors_and_continuity(cls, timeline: List[WordCaption], p_gaps: List[float]):
        """
        Hard post-processing pass enforcing:
          1. Duration >= 0.150s (150ms floor) for EVERY word without exception.
          2. Preserves intended punctuation pause gaps (150ms for comma, 250ms for period).
          3. Corrects negative gaps / overlaps (next.start < curr.end).
        """
        if not timeline:
            return

        # Pass 1: Hard floor per word
        for item in timeline:
            if item.duration_sec < cls.MIN_WORD_FLOOR_SEC:
                item.end_sec = round(item.start_sec + cls.MIN_WORD_FLOOR_SEC, 3)

        # Pass 2: Continuity with punctuation pause gaps
        for i in range(len(timeline) - 1):
            curr_item = timeline[i]
            next_item = timeline[i + 1]
            intended_gap = p_gaps[i]

            min_allowed_start = curr_item.end_sec + intended_gap

            # Fix overlap or missing gap
            if next_item.start_sec < min_allowed_start:
                diff = min_allowed_start - next_item.start_sec
                next_item.start_sec = min_allowed_start
                next_item.end_sec = round(next_item.end_sec + diff, 3)

            if next_item.duration_sec < cls.MIN_WORD_FLOOR_SEC:
                next_item.end_sec = round(next_item.start_sec + cls.MIN_WORD_FLOOR_SEC, 3)
