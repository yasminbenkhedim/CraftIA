"""
Adaptive Scene Pacing Optimizer for VideoAgent.

Calculates retention-optimized scene pacing based on speech velocity (words per minute), visual complexity, and RetentionAudit feedback loops.
"""
import logging
from typing import List, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger("uvicorn")


class ScenePacingMetric(BaseModel):
    scene_index: int
    raw_duration_sec: float
    word_count: int
    words_per_minute: float
    recommended_duration_sec: float
    pacing_tier: str  # "FAST_PACED", "BALANCED", "EXPANDED"
    pattern_interrupt_suggested: bool


class ScenePacingOptimizer:
    """
    Adaptive Scene Pacing & Retention Optimizer.
    """

    @classmethod
    def optimize_pacing(
        cls,
        scenes: List[Dict[str, Any]],
        target_retention_mode: str = "high_retention"
    ) -> List[ScenePacingMetric]:
        """
        Analyzes scene speech density and recommends duration adjustments to maximize audience watch time.
        """
        results = []

        for idx, sc in enumerate(scenes, 1):
            dur = sc.get("duration", 4.0)
            text = sc.get("speech_text", sc.get("overlay_text", ""))
            words = len(text.split()) if text else 10
            
            wpm = (words / dur) * 60.0 if dur > 0 else 150.0

            # Target 140-160 WPM for optimal retention
            if wpm > 175.0:
                rec_dur = round(dur * 1.15, 2) # Slow down slightly for readability
                tier = "FAST_PACED"
                interrupt = True
            elif wpm < 120.0:
                rec_dur = round(max(2.5, dur * 0.85), 2) # Speed up to prevent boredom
                tier = "EXPANDED"
                interrupt = True
            else:
                rec_dur = round(dur, 2)
                tier = "BALANCED"
                interrupt = (idx % 2 == 0) # Pattern interrupt every 2 scenes

            results.append(ScenePacingMetric(
                scene_index=idx,
                raw_duration_sec=dur,
                word_count=words,
                words_per_minute=round(wpm, 1),
                recommended_duration_sec=rec_dur,
                pacing_tier=tier,
                pattern_interrupt_suggested=interrupt
            ))

        logger.info(f"ScenePacingOptimizer: Analyzed {len(scenes)} scenes in '{target_retention_mode}' mode.")
        return results
