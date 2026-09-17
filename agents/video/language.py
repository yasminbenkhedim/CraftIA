"""
Video language support -- one place that knows what a language code means.

The pipeline had a `language` field on VideoGenerationRequest since the beginning, but
nothing ever set it and nothing downstream of the screenwriter read it, so every video
came out English regardless. This module is the shared vocabulary that closes that gap:
the request layer, the AI Director, the storyboard and the TTS engine all resolve a
language through here rather than each carrying its own table.

Why the voice and the espeak tag must be resolved together
----------------------------------------------------------
Kokoro's voice pack and its grapheme-to-phoneme layer are independent. Selecting the
French voice while leaving the phonemiser on `en-us` produces French words pronounced
through English phoneme rules -- audible, and measurable: the same sample line renders
in 10.56s correctly paired and 12.31s mispaired. So a language never yields a voice on
its own; it always yields the (voice, espeak_tag) pair, and callers take both.

Adding a language
-----------------
Add an entry to LANGUAGES with a Kokoro voice that actually exists in the installed
voice pack (`KokoroEngine.list_voices()`), the matching espeak tag, and an Edge-TTS
voice for the fallback chain. Nothing else needs to change.
"""
from typing import Dict, List, NamedTuple, Optional


class LanguageProfile(NamedTuple):
    code: str            # ISO 639-1, the value carried on the request
    label: str           # endonym, for UI and logs
    kokoro_voice: str    # preset in the Kokoro voice pack
    kokoro_lang: str     # espeak-ng tag driving the phonemiser -- must match the voice
    edge_voice: str      # Edge-TTS voice used when Kokoro is unavailable
    speech_rate: float   # words/second, for narration duration estimates


# Kokoro-82M ships exactly one French voice (ff_siwis, female). There is no male French
# voice and no French accent variety in the pack, so 'fr' has no alternates to offer.
LANGUAGES: Dict[str, LanguageProfile] = {
    "en": LanguageProfile(
        code="en",
        label="English",
        kokoro_voice="af_heart",
        kokoro_lang="en-us",
        edge_voice="en-US-JennyNeural",
        speech_rate=2.5,
    ),
    "fr": LanguageProfile(
        code="fr",
        label="Français",
        kokoro_voice="ff_siwis",
        kokoro_lang="fr-fr",
        edge_voice="fr-FR-DeniseNeural",
        speech_rate=2.3,
    ),
}

DEFAULT_LANGUAGE = "en"


def normalize(value: Optional[str]) -> str:
    """
    Coerce anything the API or a stored job may hold into a supported code.

    Accepts 'fr', 'FR', 'fr-FR', 'fr_FR' and falls back to English rather than raising:
    an unrecognised language must not fail a render that is otherwise fine.
    """
    if not value:
        return DEFAULT_LANGUAGE
    code = str(value).strip().lower().replace("_", "-").split("-")[0]
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


def profile(value: Optional[str]) -> LanguageProfile:
    """The full profile for a language, normalized first."""
    return LANGUAGES[normalize(value)]


def supported_codes() -> List[str]:
    return list(LANGUAGES.keys())


def label(value: Optional[str]) -> str:
    return profile(value).label
