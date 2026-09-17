"""
Per-job accent colours for the on-screen overlays.

The palette a user saves reaches a video in two ways. Scene *background* colours travel
through the Director's brief -- but every scene here is filled edge to edge with stock
footage, so that background is never actually seen. What the viewer does see is the
furniture drawn on top: the rule under a stat, the border around a text card, the
progress bar, the caption. Those were hardcoded to the app's own blue and indigo, so a
branded video looked exactly like an unbranded one apart from the logo.

This module holds the accent for the current render and hands it to those overlays.

WHY THREAD-LOCAL, NOT A PARAMETER
Renders run on the FastAPI background threadpool. A module-level colour would let two
concurrent jobs overwrite each other's brand -- the same failure the TTS engine had with
KOKORO_VOICE before per-job resolution. Passing the colour down instead would mean
threading an argument through every overlay signature and every call site, including the
ones that do not draw accents at all. The overlays already resolve their font this way
(FontManager.use), so this follows the pattern that is there.

A thread that was never given a theme reports no brand at all, and every accessor falls
back to the literal its call site passes in -- the colour that element used before brand
kits existed. An unbranded job therefore renders exactly as it did before.
"""
import colorsys
import logging
import threading
from typing import NamedTuple, Optional, Tuple

logger = logging.getLogger("uvicorn")


class BrandTheme(NamedTuple):
    """Accent colours as RGB. Call .bgr() for the OpenCV drawing paths."""
    accent: Tuple[int, int, int]
    secondary: Tuple[int, int, int]

    @staticmethod
    def bgr(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
        return (rgb[2], rgb[1], rgb[0])


# What an unbranded render uses. Deliberately NOT a single palette: the overlays never
# shared one colour before brand kits existed -- the stat rule and card border were
# #38BDF8, the progress bar #6366F1, and the progress track a slate #1E293B. Collapsing
# those into one "app default" here would restyle every unbranded video, which is exactly
# the regression this module must not cause.
#
# So each call site passes its own historical literal as the fallback, and these values
# document what those are rather than being used to draw anything.
APP_STAT_RULE = (56, 189, 248)      # #38BDF8
APP_PROGRESS_FILL = (99, 102, 241)  # #6366F1

# Present only so a caller with nothing to fall back on still gets a sane colour.
APP_DEFAULT = BrandTheme(accent=APP_STAT_RULE, secondary=APP_PROGRESS_FILL)

# Minimum relative luminance for a colour drawn over dark scrims and unpredictable
# footage. Below this an accent reads as black -- a navy brand colour on a dark panel is
# invisible, which is worse than ignoring the brand, because the element disappears
# entirely rather than looking off-brand.
_MIN_LUMINANCE = 0.22
# Above this an accent is so close to white it stops reading as a colour at all and
# competes with the caption text, which is pure white by design.
_MAX_LUMINANCE = 0.88

_local = threading.local()


def _relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """WCAG relative luminance, the standard perceptual weighting of R, G and B."""
    def channel(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ensure_visible(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """
    Nudge a colour into a luminance band where it stays visible, keeping its hue.

    Adjusts lightness in HLS rather than scaling RGB: scaling multiplies the channels
    apart and shifts the hue, so a deep maroon brightens toward orange. Saturation is
    preserved, so the result still reads as the user's colour -- a near-black navy comes
    back as a legible navy, not as a generic blue.

    Pure black and pure white have no hue to preserve, so they land on a neutral grey of
    the right lightness rather than being invented into a colour.
    """
    lum = _relative_luminance(rgb)
    if _MIN_LUMINANCE <= lum <= _MAX_LUMINANCE:
        return rgb

    r, g, b = (c / 255.0 for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)

    # HLS lightness is not luminance, so step toward the target and re-measure rather
    # than solving for it: a few iterations converge for every hue, and the loop cannot
    # run away.
    target = _MIN_LUMINANCE if lum < _MIN_LUMINANCE else _MAX_LUMINANCE
    for _ in range(24):
        out = tuple(int(round(c * 255)) for c in colorsys.hls_to_rgb(h, l, s))
        current = _relative_luminance(out)
        if abs(current - target) < 0.01:
            break
        l += 0.03 if current < target else -0.03
        l = min(1.0, max(0.0, l))

    adjusted = tuple(int(round(c * 255)) for c in colorsys.hls_to_rgb(h, l, s))
    logger.info(
        f"BrandTheme: accent {rgb} has luminance {lum:.3f}, outside the legible band "
        f"[{_MIN_LUMINANCE}, {_MAX_LUMINANCE}] -- drawn as {adjusted} "
        f"(luminance {_relative_luminance(adjusted):.3f}) so it stays visible."
    )
    return adjusted


def _parse_hex(value: Optional[str]) -> Optional[Tuple[int, int, int]]:
    raw = str(value or "").strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(c * 2 for c in raw)
    if len(raw) != 6:
        return None
    try:
        return tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def use(brand_kit: Optional[dict]) -> None:
    """
    Set the accent colours for this thread's render. None or {} restores the app default.

    Called once per render from VideoRenderer. Unparseable colours fall back to the app
    default for that slot rather than failing the render -- a brand kit is decoration,
    and a malformed hex should cost a colour, not the video.
    """
    if not brand_kit:
        _local.theme = None
        return

    accent = _parse_hex(brand_kit.get("accent_color"))
    secondary = _parse_hex(brand_kit.get("secondary_color"))
    theme = BrandTheme(
        accent=ensure_visible(accent) if accent else APP_DEFAULT.accent,
        secondary=ensure_visible(secondary) if secondary else APP_DEFAULT.secondary,
    )
    _local.theme = theme
    logger.info(
        f"BrandTheme: overlays will use accent RGB{theme.accent}, secondary RGB{theme.secondary}."
    )


def active() -> Optional[BrandTheme]:
    """The theme for this thread's render, or None when the job carries no brand kit."""
    return getattr(_local, "theme", None)


def is_branded() -> bool:
    return active() is not None


def accent_rgb(default: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """
    This job's brand accent, or `default` when it has no brand kit.

    Every caller supplies the literal it used before brand kits existed, so an unbranded
    render is pixel-identical to what it produced previously. The brand does not merely
    change these colours -- it unifies them, which is the point: a branded video's stat
    rule, card border, caption rule and progress bar all become the one accent, where an
    unbranded one keeps the three different app colours it always had.
    """
    theme = active()
    return theme.accent if theme else default


def accent_bgr(default_bgr: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """As accent_rgb, for the cv2 drawing paths. `default_bgr` is already in BGR order."""
    theme = active()
    return BrandTheme.bgr(theme.accent) if theme else default_bgr


def secondary_rgb(default: Tuple[int, int, int]) -> Tuple[int, int, int]:
    theme = active()
    return theme.secondary if theme else default


def track_bgr(default_bgr: Tuple[int, int, int], darken: float = 0.30) -> Tuple[int, int, int]:
    """
    The progress-bar track: the brand secondary, heavily darkened.

    The accent fill is drawn straight on top, so the track has to stay well below it in
    luminance or the bar's progress becomes unreadable. Darkening the brand colour keeps
    the bar tinted without turning the track into a second accent.
    """
    theme = active()
    if not theme:
        return default_bgr
    return BrandTheme.bgr(tuple(int(c * darken) for c in theme.secondary))
