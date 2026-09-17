"""
Multimodal Command Processing Module for VideoAgent (Phase 7).
Normalizes text, speech transcriptions, and image references into typed EditIntent instances.
"""
import logging
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from agents.video.conversational_editor import EditIntent

logger = logging.getLogger("uvicorn")


class TextCommand(BaseModel):
    raw_text: str


class SpeechCommand(BaseModel):
    transcript: str
    confidence: float = 0.95
    language: str = "en"


class ImageReferenceCommand(BaseModel):
    image_path: str
    visual_prompt_description: str = "style_reference"


class CommandNormalizer:
    """Normalizes heterogeneous multimodal inputs into typed EditIntent instances."""

    @classmethod
    def normalize_text(cls, cmd: TextCommand) -> EditIntent:
        txt = cmd.raw_text.lower()
        if "trim" in txt or "cut" in txt:
            return EditIntent(intent_type="trim_scene", parameters={"scene_id": "scene_1", "duration": 2.0})
        elif "bright" in txt:
            return EditIntent(intent_type="adjust_brightness", parameters={"scene_id": "scene_1", "factor": 1.15})
        elif "pacing" in txt or "faster" in txt:
            return EditIntent(intent_type="playback_speed", parameters={"scene_id": "scene_1", "speed": 1.25})
        return EditIntent(intent_type="custom_edit", parameters={"raw_instruction": cmd.raw_text})

    @classmethod
    def normalize_speech(cls, cmd: SpeechCommand) -> EditIntent:
        logger.info(f"CommandNormalizer: Processing speech transcript '{cmd.transcript}' (confidence={cmd.confidence})")
        return cls.normalize_text(TextCommand(raw_text=cmd.transcript))

    @classmethod
    def normalize_image(cls, cmd: ImageReferenceCommand) -> EditIntent:
        logger.info(f"CommandNormalizer: Processing image reference '{cmd.image_path}'")
        return EditIntent(intent_type="modify_visual_style", parameters={"image_reference": cmd.image_path, "description": cmd.visual_prompt_description})


class MultimodalProcessor:
    """Unified Multimodal Command Processor."""

    @classmethod
    def process_input(cls, input_cmd: Union[TextCommand, SpeechCommand, ImageReferenceCommand]) -> EditIntent:
        if isinstance(input_cmd, TextCommand):
            return CommandNormalizer.normalize_text(input_cmd)
        elif isinstance(input_cmd, SpeechCommand):
            return CommandNormalizer.normalize_speech(input_cmd)
        elif isinstance(input_cmd, ImageReferenceCommand):
            return CommandNormalizer.normalize_image(input_cmd)
        else:
            return EditIntent(intent_type="unknown", parameters={})
