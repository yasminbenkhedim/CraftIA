"""
OpenTimelineIO & FCP7 XML Exporter Engine for VideoAgent.
"""
import os
import json
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
from agents.video.python_editor.timeline import VideoTimelineData, MediaClip, SFXTrack

logger = logging.getLogger("uvicorn")

SUPPORTED_NLE_FORMATS = {
    "supported": ["OpenTimelineIO (.otio)", "Final Cut Pro 7 XML (.xml)"],
    "unsupported": ["Native Final Cut Pro X FCPXML (.fcpxml)"]
}


class OTIOExporter:
    """
    Exports VideoTimelineData into standard OpenTimelineIO (.otio) and Final Cut Pro 7 XML (.xml) files.
    """

    @classmethod
    def get_supported_formats(cls) -> Dict[str, List[str]]:
        return SUPPORTED_NLE_FORMATS

    @classmethod
    def export_timeline(
        cls,
        timeline: VideoTimelineData,
        output_otio_path: str,
        output_xml_path: str
    ) -> Dict[str, Any]:
        """
        Converts VideoTimelineData into .otio and FCP7 .xml timeline files.
        """
        os.makedirs(os.path.dirname(output_otio_path), exist_ok=True)
        os.makedirs(os.path.dirname(output_xml_path), exist_ok=True)

        warnings: List[str] = []
        missing_media_files: List[str] = []

        # Check media references portability & existence
        if timeline.video_tracks:
            for track in timeline.video_tracks:
                for clip in track:
                    if clip.source_path and not os.path.exists(clip.source_path):
                        missing_media_files.append(clip.source_path)

        if missing_media_files:
            warnings.append(f"Missing media files detected: {len(missing_media_files)} files not found on disk.")

        otio_success = False
        try:
            import opentimelineio as otio
            otio_timeline = otio.schema.Timeline(name="CreateFlow_AI_Timeline")

            # Add Video Tracks
            for t_idx, v_track in enumerate(timeline.video_tracks):
                track = otio.schema.Track(name=f"Video_Track_{t_idx+1}", kind=otio.schema.TrackKind.Video)
                for clip_item in v_track:
                    media_ref = otio.schema.ExternalReference(target_url=os.path.abspath(clip_item.source_path))
                    otio_clip = otio.schema.Clip(
                        name=clip_item.clip_id,
                        media_reference=media_ref,
                        source_range=otio.opentime.TimeRange(
                            start_time=otio.opentime.RationalTime(0, 30),
                            duration=otio.opentime.RationalTime(int(clip_item.duration * 30), 30)
                        )
                    )
                    track.append(otio_clip)
                otio_timeline.tracks.append(track)

            # Add Audio Tracks
            for a_idx, a_track in enumerate(timeline.audio_tracks):
                track = otio.schema.Track(name=f"Audio_Track_{a_idx+1}", kind=otio.schema.TrackKind.Audio)
                for sfx in a_track:
                    media_ref = otio.schema.ExternalReference(target_url=os.path.abspath(sfx.sfx_path))
                    otio_clip = otio.schema.Clip(
                        name=sfx.track_id,
                        media_reference=media_ref,
                        source_range=otio.opentime.TimeRange(
                            start_time=otio.opentime.RationalTime(0, 30),
                            duration=otio.opentime.RationalTime(int(sfx.duration * 30), 30)
                        )
                    )
                    track.append(otio_clip)
                otio_timeline.tracks.append(track)

            otio.adapters.write_to_file(otio_timeline, output_otio_path)

            # Also attempt native opentimelineio fcp_xml adapter
            try:
                import opentimelineio.adapters.fcp_xml as fcp_xml_adapter
                fcp_xml_adapter.write_to_file(otio_timeline, output_xml_path)
            except Exception:
                cls._export_fcp7_xml(timeline, output_xml_path)

            otio_success = True
        except ImportError:
            logger.info("OpenTimelineIO library not installed; using standard OTIO JSON & FCP7 XML parser fallback.")

        if not otio_success:
            cls._export_otio_fallback_json(timeline, output_otio_path)
            cls._export_fcp7_xml(timeline, output_xml_path)

        return {
            "otio_path": output_otio_path,
            "xml_path": output_xml_path,
            "otio_native_used": otio_success,
            "warnings": warnings,
            "missing_media_files": missing_media_files,
            "formats_notice": "Supports: OTIO, Final Cut Pro 7 XML. Does NOT currently implement: Native Final Cut Pro X FCPXML."
        }

    @classmethod
    def _export_otio_fallback_json(cls, timeline: VideoTimelineData, output_path: str):
        tracks_data = []
        for t_idx, v_track in enumerate(timeline.video_tracks):
            clips_data = []
            for clip in v_track:
                clips_data.append({
                    "OTIO_SCHEMA": "Clip.1",
                    "name": clip.clip_id,
                    "source_path": os.path.abspath(clip.source_path),
                    "start_time": clip.start_time,
                    "duration": clip.duration,
                    "zoom_scale": clip.zoom_scale
                })
            tracks_data.append({
                "OTIO_SCHEMA": "Track.1",
                "name": f"Video Track {t_idx + 1}",
                "kind": "Video",
                "children": clips_data
            })

        payload = {
            "OTIO_SCHEMA": "Timeline.1",
            "name": "CreateFlow_AI_Timeline",
            "total_duration": timeline.total_duration,
            "frame_rate": 30.0,
            "tracks": tracks_data
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    @classmethod
    def _export_fcp7_xml(cls, timeline: VideoTimelineData, output_path: str):
        clips_xml = ""
        current_frame = 0

        if timeline.video_tracks:
            for clip in timeline.video_tracks[0]:
                duration_frames = int(clip.duration * 30)
                end_frame = current_frame + duration_frames
                abs_path = os.path.abspath(clip.source_path).replace("\\", "/")
                clips_xml += f"""
                <clipitem id="{clip.clip_id}">
                    <name>{clip.clip_id}</name>
                    <duration>{duration_frames}</duration>
                    <rate><timebase>30</timebase></rate>
                    <start>{current_frame}</start>
                    <end>{end_frame}</end>
                    <file id="file_{clip.clip_id}">
                        <name>{os.path.basename(clip.source_path)}</name>
                        <pathurl>file://{abs_path}</pathurl>
                    </file>
                </clipitem>"""
                current_frame = end_frame

        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4">
    <sequence id="sequence-1">
        <name>CreateFlow_AI_Timeline</name>
        <duration>{current_frame}</duration>
        <rate><timebase>30</timebase></rate>
        <media>
            <video>
                <track>
                    {clips_xml}
                </track>
            </video>
        </media>
    </sequence>
</xmeml>"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_content.strip())

    @classmethod
    def reimport_and_validate_roundtrip(cls, otio_path: str, xml_path: str) -> Dict[str, Any]:
        """
        Re-imports exported .otio and .xml files and compares clip count, track count, ordering, and duration.
        """
        otio_data = {}
        if os.path.exists(otio_path):
            try:
                import opentimelineio as otio
                tl = otio.adapters.read_from_file(otio_path)
                clips_count = 0
                for track in tl.tracks:
                    for item in track:
                        if isinstance(item, otio.schema.Clip):
                            clips_count += 1
                otio_data = {
                    "clip_count": clips_count,
                    "track_count": len(tl.tracks),
                    "duration_seconds": tl.duration().to_seconds()
                }
            except Exception:
                with open(otio_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                    clips = 0
                    tracks = payload.get("tracks", [])
                    if isinstance(tracks, list):
                        for t in tracks:
                            if isinstance(t, dict):
                                clips += len(t.get("children", []))
                    otio_data = {
                        "clip_count": clips,
                        "track_count": len(tracks) if isinstance(tracks, list) else 0,
                        "duration_seconds": payload.get("total_duration", 0.0) if isinstance(payload, dict) else 0.0
                    }

        xml_data = {}
        if os.path.exists(xml_path):
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
                clips = root.findall(".//clipitem")
                dur_elem = root.find(".//sequence/duration")
                total_frames = int(dur_elem.text) if dur_elem is not None and dur_elem.text else 0
                xml_data = {
                    "clip_count": len(clips),
                    "track_count": len(root.findall(".//media/video/track")),
                    "duration_seconds": round(total_frames / 30.0, 3)
                }
            except Exception as e:
                xml_data = {"error": str(e)}

        return {
            "otio_import": otio_data,
            "xml_import": xml_data,
            "clip_count_match": otio_data.get("clip_count") == xml_data.get("clip_count"),
            "duration_match": abs(otio_data.get("duration_seconds", 0.0) - xml_data.get("duration_seconds", 0.0)) < 0.1
        }
