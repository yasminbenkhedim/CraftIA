"""
Pipeline progress reporting.

The job row carries `progress_percent` / `current_step`, which the UI polls. Before this
module the video agent reported those from `VideoAgent.execute()` -- a loop that slept
0.25 s between hardcoded percentages and reached 100% in about two seconds, while the real
work happened afterwards in `generate_artifact()` with no reporting at all. The bar was
therefore always full and always wrong.

Stage order
-----------
The checkpoints below run in the pipeline's real execution order, which puts the voiceover
BEFORE media collection: TTSEngine measures each rendered line and rewrites
`scene.duration_sec` from it, and media selection needs those final durations to pick and
trim clips. Reporting "collecting footage" first would mean walking the bar backwards.

Percentages are monotonic by construction here, and `PipelineProgress` enforces that at
runtime too, so a retry or a fallback path can never make the bar jump back.
"""
from typing import Callable, Optional, Tuple

# stage key -> (percent, label shown under the bar)
STAGES = {
    "director":     (10,  "AI Director planning..."),
    "screenwriter": (25,  "Writing narration script..."),
    "voiceover":    (45,  "Generating voiceover..."),
    "footage":      (65,  "Collecting video footage..."),
    "compositing":  (85,  "Compositing scenes..."),
    "finalizing":   (97,  "Finalizing video..."),
    "complete":     (100, "Complete!"),
}

# Scene-by-scene compositing is the longest single phase of a render, so the bar is
# interpolated across it instead of resting on 85 for minutes.
_COMPOSITING_SPAN = (STAGES["compositing"][0], STAGES["finalizing"][0])

ProgressCallback = Callable[[int, str], None]


class PipelineProgress:
    """Reports named pipeline stages to an optional callback. A no-op when unset."""

    def __init__(self, callback: Optional[ProgressCallback] = None):
        self._callback = callback
        self._last_percent = -1

    def report(self, stage: str, detail: Optional[str] = None) -> None:
        """Reports a named stage from STAGES; `detail` replaces the default label."""
        percent, label = STAGES.get(stage, (self._last_percent, stage))
        self._emit(percent, detail or label)

    def report_scene(self, done: int, total: int) -> None:
        """Interpolates within the compositing stage as individual scenes finish."""
        if total <= 0:
            return
        lo, hi = _COMPOSITING_SPAN
        percent = lo + int((hi - lo) * (min(done, total) / total))
        self._emit(percent, f"Compositing scene {min(done + 1, total)} of {total}...")

    def _emit(self, percent: int, label: str) -> None:
        if not self._callback:
            return
        # Never walk backwards: a fallback path or a retry re-entering an earlier stage
        # would otherwise look to the user like the job had restarted.
        percent = max(int(percent), self._last_percent)
        self._last_percent = percent
        try:
            self._callback(percent, label)
        except Exception:
            # Progress is cosmetic; a failing sink must never abort a render.
            pass


def stage(name: str) -> Tuple[int, str]:
    """(percent, label) for a stage, for callers that only need the values."""
    return STAGES[name]
