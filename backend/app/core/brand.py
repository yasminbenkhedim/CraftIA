"""
Brand kit configuration: the fonts a video can actually be rendered in, and the rules
for the colours a user may save.

FONT INVENTORY -- read this before adding a choice to the list below.

The renderer draws text with PIL from TrueType files that ship in the repo at
agents/video/assets/fonts. Exactly one family is there: DejaVu Sans (regular and bold).
Everything else was removed during the licence remediation -- the previous "Inter" files
were Arial copied out of C:\\Windows\\Fonts and renamed, which could not be redistributed
in a commercial product (LICENSES.md R4).

So this list is short because the font inventory is short, not because the feature is
stubbed. A choice here is a promise the renderer can keep; adding one that has no TTF on
disk would silently fall back to DejaVu and make the setting a lie.

To add a real font:
  1. Drop an OFL / Apache / public-domain TTF into agents/video/assets/fonts.
  2. Add an entry below naming its files.
  3. Record it in ATTRIBUTIONS.md -- OFL requires the notice to travel with the software,
     and rendered video counts.
The frontend reads this list from GET /api/me/brand-kit/fonts, so the dropdown updates
itself with no frontend change.
"""
import re
from typing import Dict, NamedTuple, Optional


class FontChoice(NamedTuple):
    id: str
    label: str
    # Filenames inside agents/video/assets/fonts.
    regular_file: str
    bold_file: str
    # What the picker says about it, so the choice is informed rather than a guess.
    note: str


FONT_CHOICES: Dict[str, FontChoice] = {
    "dejavu_sans": FontChoice(
        id="dejavu_sans",
        label="DejaVu Sans",
        regular_file="DejaVuSans.ttf",
        bold_file="DejaVuSans-Bold.ttf",
        note="Humanist sans. Wide accent coverage — safe for French and Arabic-adjacent text.",
    ),
    # The same family drawn at its bold weight throughout. A genuinely different look on
    # screen, and one the renderer can honour today with no new files.
    "dejavu_sans_bold": FontChoice(
        id="dejavu_sans_bold",
        label="DejaVu Sans Bold",
        regular_file="DejaVuSans-Bold.ttf",
        bold_file="DejaVuSans-Bold.ttf",
        note="Heavier titles throughout. Reads better on small screens and social crops.",
    ),
}

DEFAULT_FONT = "dejavu_sans"

# Matches the palette the AI Director would otherwise invent, so an unsaved brand kit and
# a saved-but-default one render identically.
DEFAULT_PRIMARY = "#0F172A"
DEFAULT_SECONDARY = "#38BDF8"
DEFAULT_ACCENT = "#7C5CFF"

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def normalize_font(value: object) -> str:
    """Coerce a stored or submitted font id to one the renderer can actually load."""
    key = str(value or "").strip().lower()
    return key if key in FONT_CHOICES else DEFAULT_FONT


def font_files(value: object) -> FontChoice:
    return FONT_CHOICES[normalize_font(value)]


def font_catalogue() -> list:
    """[{id, label, note}] for the picker."""
    return [{"id": f.id, "label": f.label, "note": f.note} for f in FONT_CHOICES.values()]


def is_hex_color(value: object) -> bool:
    return bool(_HEX_RE.match(str(value or "").strip()))


def normalize_hex(value: object, fallback: str) -> str:
    """
    '#abc' and '#AABBCC' in, '#aabbcc' out.

    Expands the 3-digit form because the renderer parses colours two characters at a time
    and would read '#abc' as a malformed 6-digit value rather than rejecting it.
    """
    raw = str(value or "").strip()
    if not _HEX_RE.match(raw):
        return fallback
    body = raw[1:]
    if len(body) == 3:
        body = "".join(c * 2 for c in body)
    return f"#{body.lower()}"


def hex_to_bgr(value: str) -> Optional[list]:
    """
    Hex to the [B, G, R] the renderer's frame buffers use.

    The renderer writes straight into an OpenCV BGR buffer, so a naive RGB conversion
    here comes out with red and blue swapped -- a brand's navy renders as rust.
    """
    raw = str(value or "").strip().lstrip("#")
    if len(raw) != 6:
        return None
    try:
        r, g, b = (int(raw[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None
    return [b, g, r]
