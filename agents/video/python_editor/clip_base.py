"""
Base Clip Abstractions – inspired by MoviePy's VideoClip.py architecture.

Provides lightweight clip data-classes that the renderer consumes.
Unlike MoviePy we keep clips as pure data objects (no lazy frame
generators) so rendering stays deterministic and easy to debug.
"""
from typing import List, Optional, Tuple


class ClipLayer:
    """A single renderable layer inside a frame (text, rectangle, image)."""

    def __init__(self, layer_type: str, **kwargs):
        self.layer_type = layer_type    # "text", "rect", "gradient"
        self.props = kwargs             # type-specific properties

    def __repr__(self):
        return f"<ClipLayer type={self.layer_type} props={list(self.props.keys())}>"


class VideoClip:
    """
    A time-bound clip composing one or more layers.
    Mirrors MoviePy's VideoClip concept: a clip owns a start/end time,
    resolution, and an ordered stack of layers.
    """

    def __init__(self, clip_id: str, start_sec: float, end_sec: float,
                 width: int = 1280, height: int = 720):
        self.clip_id = clip_id
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.duration_sec = end_sec - start_sec
        self.width = width
        self.height = height
        self.layers: List[ClipLayer] = []
        self.transition: str = "cut"
        self.narration_text: Optional[str] = None

    def add_layer(self, layer: ClipLayer):
        self.layers.append(layer)

    def __repr__(self):
        return (f"<VideoClip {self.clip_id} "
                f"{self.start_sec:.1f}s–{self.end_sec:.1f}s "
                f"layers={len(self.layers)}>")
