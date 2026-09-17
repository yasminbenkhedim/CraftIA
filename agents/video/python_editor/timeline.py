"""
Actionable Video Timeline Data Structures for VideoAgent Python Editor.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MediaClip(BaseModel):
    clip_id: str
    source_path: str
    start_time: float
    duration: float
    zoom_scale: float = 1.0
    rotation: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SFXTrack(BaseModel):
    track_id: str
    sfx_path: str
    start_time: float
    volume_db: float = 0.0
    duration: float = 1.0


class VideoTimelineData(BaseModel):
    total_duration: float
    video_tracks: List[List[MediaClip]] = Field(default_factory=list)
    audio_tracks: List[List[SFXTrack]] = Field(default_factory=list)

    def add_clip(self, track_index: int, clip: MediaClip):
        while len(self.video_tracks) <= track_index:
            self.video_tracks.append([])
        self.video_tracks[track_index].append(clip)

    def add_sfx(self, track_index: int, sfx: SFXTrack):
        while len(self.audio_tracks) <= track_index:
            self.audio_tracks.append([])
        self.audio_tracks[track_index].append(sfx)
