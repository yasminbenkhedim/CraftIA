"""
Motion Graphics Engine (Phase 3C of VIDEO_PIPELINE_ARCHITECTURE_V2).

Renders animated typography overlays composited over the video track:
  - Animated stat counters ("85% improvement" counting up from zero)
  - Lower-third banners
  - Animated section titles

Everything draws directly onto the BGR frame buffer via PIL/OpenCV -- no external
renderer, no transparent PNG sequences on disk, since the compositor already owns the
frame and an in-place draw avoids a full RGBA round-trip per frame.

All geometry is resolution-relative (fractions of frame width/height) so overlays land
identically at 720p, 1080p and 4K.
"""
import re
import math
import logging
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw

from agents.video.python_editor import brand_theme
from agents.video.python_editor.text_overlays import FontManager, spring_ease

logger = logging.getLogger("uvicorn")


# Splits "85% improvement" -> ("", "85", "% improvement"); "3x faster" -> ("", "3", "x faster")
_STAT_PATTERN = re.compile(r"^(?P<prefix>[^\d\-+]*)(?P<number>[-+]?\d[\d,]*\.?\d*)(?P<suffix>.*)$")


class StatValue:
    """A parsed numeric stat, so the number can be animated independently of its label."""

    def __init__(self, prefix: str, number: float, suffix: str, decimals: int, raw: str):
        self.prefix = prefix
        self.number = number
        self.suffix = suffix
        self.decimals = decimals
        self.raw = raw

    def format_at(self, fraction: float) -> str:
        """Renders the stat with its number scaled to `fraction` of the final value."""
        current = self.number * max(0.0, min(1.0, fraction))
        if self.decimals > 0:
            num_str = f"{current:.{self.decimals}f}"
        else:
            num_str = f"{int(round(current)):,}"
        return f"{self.prefix}{num_str}{self.suffix}"


class MotionGraphicsOverlayEngine:
    """
    Frame-level animated text overlays for stats, lower-thirds and section titles.

    Distinct from agents.video.motion_graphics.engine.MotionGraphicsEngine, which plans
    declarative motion-graphics nodes at the scene-graph level; this one rasterizes
    overlays directly onto frame buffers during the render pass.
    """

    # ------------------------------------------------------------------
    # Stat parsing
    # ------------------------------------------------------------------

    @classmethod
    def parse_stat(cls, text: str) -> Optional[StatValue]:
        """
        Extracts the leading number from a stat string so it can count up.
        Returns None when there's no number to animate (caller then draws it statically).
        """
        if not text or not text.strip():
            return None
        m = _STAT_PATTERN.match(text.strip())
        if not m:
            return None
        raw_num = m.group("number").replace(",", "")
        try:
            value = float(raw_num)
        except ValueError:
            return None
        decimals = len(raw_num.split(".")[1]) if "." in raw_num else 0
        return StatValue(m.group("prefix"), value, m.group("suffix"), decimals, text.strip())

    # ------------------------------------------------------------------
    # Stat counter
    # ------------------------------------------------------------------

    @classmethod
    def render_stat_counter(
        cls,
        frame: np.ndarray,
        stats: List[str],
        width: int,
        height: int,
        progress: float,
        count_up_fraction: float = 0.45,
    ) -> None:
        """
        Draws up to 3 stats stacked at frame right, numbers counting up over the first
        `count_up_fraction` of the scene then holding, with a fade-out at the end so the
        overlay never collides with the closing transition.

        `progress` is scene progress in [0, 1].
        """
        if not stats:
            return

        # Entrance / exit envelope: slide+fade in, hold, fade out.
        if progress < 0.08:
            return
        entrance = min(1.0, (progress - 0.08) / 0.12)
        alpha_scale = spring_ease(entrance)
        if progress > 0.88:
            alpha_scale *= max(0.0, 1.0 - (progress - 0.88) / 0.12)
        if alpha_scale <= 0.01:
            return

        count_fraction = min(1.0, max(0.0, (progress - 0.08) / max(count_up_fraction, 0.01)))
        eased_count = spring_ease(count_fraction) if count_fraction < 1.0 else 1.0

        scale_h = height / 1080.0
        num_font = FontManager.get_font(int(58 * scale_h), bold=True)
        label_font = FontManager.get_font(int(22 * scale_h), bold=False)

        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img, "RGBA")

        right_margin = int(width * 0.06)
        block_gap = int(28 * scale_h)
        y = int(height * 0.24)

        for stat_text in stats[:3]:
            parsed = cls.parse_stat(stat_text)
            if parsed is None:
                # No number to count up: this is a headline the model put in the stats
                # field, not a statistic. Rendering it here would paint a large title
                # across the top of the frame -- exactly the top-of-frame text the
                # design eliminates -- so skip it entirely.
                logger.debug(f"MotionGraphicsOverlayEngine: Skipping non-numeric stat {stat_text!r}.")
                continue

            display = parsed.format_at(eased_count)
            # Split so the number renders large and its label smaller beneath it.
            number_part = f"{parsed.prefix}{display[len(parsed.prefix):].split(' ')[0]}"
            label_part = display[len(number_part):].strip()

            num_bbox = num_font.getbbox(number_part)
            num_w = num_bbox[2] - num_bbox[0]
            num_h = num_bbox[3] - num_bbox[1]
            x = width - right_margin - num_w

            a = int(255 * alpha_scale)
            draw.text((x + 2, y + 2), number_part, font=num_font, fill=(0, 0, 0, int(150 * alpha_scale)))
            draw.text((x, y), number_part, font=num_font, fill=(255, 255, 255, a))

            # Accent rule under the number ties the stat block together visually, and is
            # the most visible brand surface in a footage-filled scene -- the number
            # itself stays white, because it sits directly on unpredictable video and
            # needs the contrast of white-plus-shadow to stay readable.
            rule_y = y + num_h + int(10 * scale_h)
            draw.rectangle(
                [x, rule_y, width - right_margin, rule_y + max(2, int(3 * scale_h))],
                fill=(*brand_theme.accent_rgb(brand_theme.APP_STAT_RULE), a),
            )

            label_h = 0
            if label_part:
                lb = label_font.getbbox(label_part)
                label_w = lb[2] - lb[0]
                label_h = lb[3] - lb[1]
                lx = width - right_margin - label_w
                ly = rule_y + int(12 * scale_h)
                draw.text((lx + 1, ly + 1), label_part, font=label_font, fill=(0, 0, 0, int(130 * alpha_scale)))
                draw.text((lx, ly), label_part, font=label_font, fill=(226, 232, 240, a))

            y = rule_y + int(20 * scale_h) + label_h + block_gap

        frame[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    # ------------------------------------------------------------------
    # Lower third
    # ------------------------------------------------------------------

    @classmethod
    def render_lower_third(
        cls,
        frame: np.ndarray,
        title: str,
        subtitle: str,
        width: int,
        height: int,
        progress: float,
        accent_color: Optional[Tuple[int, int, int]] = None,
    ) -> None:
        """
        Clean lower-third: accent bar + title + optional subtitle, wiping in from the left
        and out again. Sits above the caption safe zone so it never overlaps subtitles.
        """
        if not title or progress <= 0.0:
            return

        # None means "this job's brand accent", which is the app default when no kit is
        # active. An explicit colour still wins, so callers that care can override.
        accent_color = accent_color or brand_theme.accent_rgb(brand_theme.APP_STAT_RULE)

        if progress < 0.05:
            return
        entrance = min(1.0, (progress - 0.05) / 0.15)
        eased = spring_ease(entrance)
        if progress > 0.80:
            eased *= max(0.0, 1.0 - (progress - 0.80) / 0.15)
        if eased <= 0.02:
            return

        scale_h = height / 1080.0
        title_font = FontManager.get_font(int(34 * scale_h), bold=True)
        sub_font = FontManager.get_font(int(20 * scale_h), bold=False)

        left = int(width * 0.06)
        # Keep clear of the caption zone (captions sit at ~0.87H).
        band_y = int(height * 0.68)

        t_bbox = title_font.getbbox(title)
        t_w, t_h = t_bbox[2] - t_bbox[0], t_bbox[3] - t_bbox[1]
        s_w = s_h = 0
        if subtitle:
            s_bbox = sub_font.getbbox(subtitle)
            s_w, s_h = s_bbox[2] - s_bbox[0], s_bbox[3] - s_bbox[1]

        pad_x, pad_y = int(24 * scale_h), int(16 * scale_h)
        bar_w = max(4, int(6 * scale_h))
        content_w = max(t_w, s_w)
        panel_w = int((content_w + pad_x * 2 + bar_w) * eased)
        panel_h = t_h + (s_h + int(10 * scale_h) if subtitle else 0) + pad_y * 2

        if panel_w <= bar_w + 4:
            return

        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img, "RGBA")

        a = int(215 * eased)
        draw.rectangle([left, band_y, left + panel_w, band_y + panel_h], fill=(10, 12, 20, a))
        draw.rectangle([left, band_y, left + bar_w, band_y + panel_h],
                       fill=(*accent_color, int(255 * eased)))

        # Only draw text once the panel is wide enough to contain it.
        if eased > 0.55:
            text_a = int(255 * min(1.0, (eased - 0.55) / 0.35))
            tx = left + bar_w + pad_x
            ty = band_y + pad_y
            draw.text((tx, ty), title, font=title_font, fill=(255, 255, 255, text_a))
            if subtitle:
                draw.text((tx, ty + t_h + int(10 * scale_h)), subtitle,
                          font=sub_font, fill=(203, 213, 225, text_a))

        frame[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    # ------------------------------------------------------------------
    # Section title
    # ------------------------------------------------------------------

    @classmethod
    def render_section_title(
        cls,
        frame: np.ndarray,
        title: str,
        width: int,
        height: int,
        progress: float,
    ) -> None:
        """Large centered section title that fades and drifts upward, then clears."""
        if not title or progress <= 0.0:
            return

        entrance = min(1.0, progress / 0.18)
        eased = spring_ease(entrance)
        if progress > 0.45:
            eased *= max(0.0, 1.0 - (progress - 0.45) / 0.20)
        if eased <= 0.02:
            return

        scale_h = height / 1080.0
        font = FontManager.get_font(int(64 * scale_h), bold=True)

        bbox = font.getbbox(title)
        t_w, t_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        cx = (width - t_w) // 2
        drift = int((1.0 - eased) * 30 * scale_h)
        cy = int(height * 0.42) + drift

        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img, "RGBA")

        a = int(255 * eased)
        draw.text((cx + 3, cy + 3), title, font=font, fill=(0, 0, 0, int(160 * eased)))
        draw.text((cx, cy), title, font=font, fill=(255, 255, 255, a))

        rule_w = int(t_w * 0.35 * eased)
        if rule_w > 4:
            rule_x = (width - rule_w) // 2
            rule_y = cy + t_h + int(18 * scale_h)
            draw.rectangle([rule_x, rule_y, rule_x + rule_w, rule_y + max(2, int(4 * scale_h))],
                           fill=(*brand_theme.accent_rgb(brand_theme.APP_STAT_RULE), a))

        frame[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
