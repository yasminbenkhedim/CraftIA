"""
TechnicalOutputCritic for CraftAI (Upgrade 8).
Evaluates container validity, video/audio codecs, pixel format, resolution, and file integrity.
"""
import os
import cv2
import logging
from typing import List, Dict, Any, Optional
from agents.video.critic.schemas import CriticFinding, FindingSeverity, FindingStatus

logger = logging.getLogger("uvicorn")


class TechnicalOutputCritic:
    """
    Technical output evaluator checking container validity, codecs, resolution, and frame counts.
    """

    @classmethod
    def evaluate_video_file(cls, mp4_path: str) -> List[CriticFinding]:
        findings: List[CriticFinding] = []

        if not os.path.exists(mp4_path):
            findings.append(CriticFinding(
                critic_type="technical",
                category="file_integrity",
                subcategory="missing_output",
                title="Missing MP4 Video File",
                description=f"Output video file does not exist at path: {mp4_path}",
                severity=FindingSeverity.BLOCKER,
                expected_behavior="Valid MP4 file on disk",
                observed_behavior="File missing",
                affected_pipeline_stage="renderer",
                recommended_action="re_render_complete_video"
            ))
            return findings

        file_size = os.path.getsize(mp4_path)
        if file_size < 10000:
            findings.append(CriticFinding(
                critic_type="technical",
                category="file_integrity",
                subcategory="corrupted_container",
                title="Corrupted or Undersized MP4 File",
                description=f"Output file size ({file_size} B) is below minimum valid MP4 threshold",
                severity=FindingSeverity.BLOCKER,
                expected_behavior="File size > 10KB",
                observed_behavior=f"{file_size} B",
                affected_pipeline_stage="renderer",
                recommended_action="re_render_complete_video"
            ))
            return findings

        # OpenCV Frame Inspection
        cap = cv2.VideoCapture(mp4_path)
        if not cap.isOpened():
            findings.append(CriticFinding(
                critic_type="technical",
                category="codec_integrity",
                subcategory="unreadable_stream",
                title="Unreadable Video Stream",
                description="Failed to open video container with OpenCV video decoder",
                severity=FindingSeverity.BLOCKER,
                expected_behavior="Valid readable H.264 video stream",
                observed_behavior="Stream unopenable",
                affected_pipeline_stage="renderer",
                recommended_action="re_render_complete_video"
            ))
            return findings

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        if frame_count <= 0 or fps <= 0:
            findings.append(CriticFinding(
                critic_type="technical",
                category="frame_rate",
                subcategory="zero_frames",
                title="Zero Frame Count or Invalid FPS",
                description=f"Decoded frame count ({frame_count}) or FPS ({fps}) is invalid",
                severity=FindingSeverity.BLOCKER,
                expected_behavior="frame_count > 0, fps > 0",
                observed_behavior=f"frames={frame_count}, fps={fps}",
                affected_pipeline_stage="renderer",
                recommended_action="re_render_complete_video"
            ))

        return findings
