"""
Multi-Language Neural TTS Engine for VideoAgent.

Supports multi-language speech generation (English, French, German, Spanish, Italian, Japanese) via Edge-TTS with automatic voice fallback.
"""
import os
import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("uvicorn")

VOICE_MAP: Dict[str, Dict[str, str]] = {
    "en": {"female": "en-US-JennyNeural", "male": "en-US-GuyNeural"},
    "fr": {"female": "fr-FR-VivienneNeural", "male": "fr-FR-HenriNeural"},
    "de": {"female": "de-DE-KatjaNeural", "male": "de-DE-ConradNeural"},
    "es": {"female": "es-ES-ElviraNeural", "male": "es-ES-AlvaroNeural"},
    "it": {"female": "it-IT-ElsaNeural", "male": "it-IT-DiegoNeural"},
    "ja": {"female": "ja-JP-NanamiNeural", "male": "ja-JP-KeitaNeural"}
}

DEFAULT_VOICE = "en-US-JennyNeural"


class MultilingualTTSEngine:
    """
    Multilingual TTS Engine wrapper.
    """

    @classmethod
    def resolve_voice(cls, language_code: str = "en", gender: str = "female") -> str:
        lang = language_code.lower()[:2]
        gen = gender.lower()
        if lang in VOICE_MAP and gen in VOICE_MAP[lang]:
            return VOICE_MAP[lang][gen]
        logger.warning(f"Voice for lang '{language_code}', gender '{gender}' not found. Falling back to default '{DEFAULT_VOICE}'.")
        return DEFAULT_VOICE

    @classmethod
    def generate_speech_sync(
        cls,
        text: str,
        output_path: str,
        language_code: str = "en",
        gender: str = "female"
    ) -> str:
        voice = cls.resolve_voice(language_code, gender)
        
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice)
            asyncio.run(communicate.save(output_path))
            logger.info(f"MultilingualTTSEngine: Generated speech ({language_code}/{voice}) -> {output_path}")
            return output_path
        except Exception as e:
            logger.warning(f"MultilingualTTSEngine: Edge-TTS error ({e}), generating silent fallback WAV.")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
            return output_path
