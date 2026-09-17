"""
Subtitle and SRT Caption Generator for VideoAgent.
"""
import os
from typing import List
from agents.video.caption_engine import CaptionEngine


class SubtitleGenerator:
    """
    SRT Subtitle File Generator for VideoAgent.
    """

    @classmethod
    def generate_srt(cls, narrations: List[str], scene_durations: List[float], output_srt_path: str):
        os.makedirs(os.path.dirname(os.path.abspath(output_srt_path)), exist_ok=True)
        current_time = 0.0

        with open(output_srt_path, "w", encoding="utf-8") as f:
            for i, (text, dur) in enumerate(zip(narrations, scene_durations)):
                start_sec = current_time
                end_sec = current_time + dur
                current_time = end_sec

                start_str = cls._format_timestamp(start_sec)
                end_str = cls._format_timestamp(end_sec)

                f.write(f"{i+1}\n")
                f.write(f"{start_str} --> {end_str}\n")
                f.write(f"{text}\n\n")

    @classmethod
    def _format_timestamp(cls, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
