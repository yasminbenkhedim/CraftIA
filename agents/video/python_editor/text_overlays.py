"""
Animated Text Overlay Engine v4 -- PIL TrueType Typography & Multi-Line Text Wrapping.
Inspired by MoviePy TextClip & NativePPTXEngine card containers.

v4 additions:
  - PIL TrueType font rendering with anti-aliasing (DejaVuSans & Inter)
  - Pixel-accurate multi-line auto-wrapping based on container width
  - NativePPTXEngine rounded card background containers (corner_radius=12, padding=16)
  - Full Unicode / accented character support (e.g. Écosystème & Intelligence Artificielle)
  - Damped spring-physics easing: f(t) = 1 - exp(-ζωt) * cos(ω * sqrt(1-ζ²) * t)
  - Lower-thirds banner overlay & radial progress ring indicator
"""
import os
import math
import logging
import cv2
import numpy as np
import threading
from typing import List, Tuple, Optional, Any

from PIL import Image, ImageDraw, ImageFont

from agents.video.python_editor import brand_theme
from agents.video.storyboard import TextLayer
from agents.video.scene_composer import SceneComposer, TextEntranceSchedule

logger = logging.getLogger("uvicorn")

FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts")

# (regular, bold) filenames per brand-kit font id. Mirrors FONT_CHOICES in
# backend/app/core/brand.py, which is the list the picker offers; kept as a plain dict
# here so the renderer never has to import the web application to draw a frame.
_FONT_FILES = {
    "dejavu_sans": ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
    "dejavu_sans_bold": ("DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"),
}
DEFAULT_FONT_CHOICE = "dejavu_sans"


def spring_ease(t: float, zeta: float = 0.5, omega: float = 12.0) -> float:
    """
    Damped spring-physics oscillator equation:
    f(t) = 1 - exp(-ζ * ω * t) * cos(ω * sqrt(1 - ζ²) * t)
    """
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    wd = omega * math.sqrt(max(0.001, 1.0 - zeta ** 2))
    val = 1.0 - math.exp(-zeta * omega * t) * math.cos(wd * t)
    return float(val)


class FontManager:
    """
    Loads and caches PIL TrueType fonts, honouring the active job's brand typeface.

    The choice is held in a thread-local, not a class attribute. Renders run on the
    FastAPI background threadpool, so a process-wide setting would let two concurrent
    jobs overwrite each other's typeface -- the same failure the TTS engine had with
    KOKORO_VOICE before per-job resolution. A thread that was never given a choice falls
    back to the default, so any code path that predates brand kits is unaffected.
    """
    _cache = {}
    _local = threading.local()

    @classmethod
    def use(cls, font_choice: Optional[str]) -> None:
        """Set the typeface for the current thread's render. None restores the default."""
        cls._local.font_choice = font_choice or None

    @classmethod
    def active_choice(cls) -> str:
        return getattr(cls._local, "font_choice", None) or DEFAULT_FONT_CHOICE

    @classmethod
    def _files_for(cls, choice: str) -> tuple:
        """(regular, bold) filenames for a choice, falling back to DejaVu."""
        return _FONT_FILES.get(choice, _FONT_FILES[DEFAULT_FONT_CHOICE])

    @classmethod
    def get_font(cls, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        choice = cls.active_choice()
        key = (choice, size, bold)
        if key in cls._cache:
            return cls._cache[key]

        # Only fonts that ship in the repo. The former "Inter-*.ttf" fallback was actually
        # Arial (Monotype, All Rights Reserved) copied out of C:\Windows\Fonts and
        # renamed -- it could not be redistributed in a commercial product, so it was
        # deleted (LICENSES.md R4). DejaVu is Bitstream Vera + public-domain terms; if a
        # file ever goes missing the code below falls through to PIL's built-in bitmap
        # font rather than silently reaching for a system font of unknown licence.
        regular_file, bold_file = cls._files_for(choice)
        font_file = bold_file if bold else regular_file
        font_path = os.path.join(FONTS_DIR, font_file)

        try:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, size)
            else:
                font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        cls._cache[key] = font
        return font


class TextOverlayEngine:
    """
    Renders TextLayer objects onto video frames using PIL TrueType fonts,
    multi-line auto-wrapping, NativePPTXEngine rounded card containers,
    and spring-physics motion graphics.
    """

    @classmethod
    def wrap_text(cls, text: str, font: ImageFont.FreeTypeFont, max_width_px: int) -> List[str]:
        """
        Wraps text into multiple lines based on actual pixel width of rendered font.
        """
        words = text.split(" ")
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = font.getbbox(test_line)
            line_w = bbox[2] - bbox[0]
            if line_w <= max_width_px or not current_line:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        return lines

    @classmethod
    def render_text_layers(cls, frame: np.ndarray,
                            layers: List[TextLayer],
                            width: int, height: int,
                            scene_progress: float = 1.0,
                            entrance_schedules: List[TextEntranceSchedule] = None):
        """
        Draw all text layers with spring-physics entrance animations using PIL TrueType fonts.
        """
        for i, layer in enumerate(layers):
            if entrance_schedules and i < len(entrance_schedules):
                sched = entrance_schedules[i]
                if scene_progress < sched.start_frac:
                    continue
                raw_progress = min(1.0, (scene_progress - sched.start_frac) / max(sched.duration_frac, 0.01))
                eased_progress = spring_ease(raw_progress)

                # Fade out after the hold window instead of staying on screen for the
                # rest of the scene -- prevents on-screen titles/hooks from lingering
                # alongside the bottom narration captions like a second subtitle bar.
                exit_start_frac = sched.start_frac + sched.duration_frac + sched.hold_frac
                if scene_progress >= exit_start_frac:
                    raw_exit = min(1.0, (scene_progress - exit_start_frac) / max(sched.exit_frac, 0.01))
                    eased_progress = max(0.0, eased_progress * (1.0 - spring_ease(raw_exit)))
                    if eased_progress <= 0.01:
                        continue
            else:
                raw_progress = min(1.0, scene_progress / 0.5) if scene_progress < 0.5 else 1.0
                eased_progress = spring_ease(raw_progress)

            cls._render_single_layer_pil(frame, layer, width, height, eased_progress)

    @classmethod
    def _render_single_layer_pil(cls, frame: np.ndarray, layer: TextLayer,
                                  width: int, height: int, progress: float):
        text = layer.text
        entrance = getattr(layer, "entrance", "typewriter")

        scale_h = height / 1080.0

        # Compute font size in points scaled proportionally with canvas resolution
        font_size = int(28 * scale_h * layer.font_scale)
        font = FontManager.get_font(font_size, bold=layer.bold)

        # Max width constraint: 80% of frame width
        max_w = int(width * 0.80)
        lines = cls.wrap_text(text, font, max_w)

        # Handle typewriter entrance
        if entrance == "typewriter" and progress < 1.0:
            full_text = "\n".join(lines)
            visible_chars = max(1, int(len(full_text) * progress))
            text_sub = full_text[:visible_chars]
            lines = text_sub.split("\n")

        # Convert OpenCV BGR to PIL Image RGB
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img, "RGBA")

        # Measure total multiline dimensions
        line_heights = []
        line_widths = []
        for line in lines:
            bbox = font.getbbox(line) if line else (0, 0, 0, 0)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1] + int(6 * scale_h))

        total_w = max(line_widths) if line_widths else 0
        total_h = sum(line_heights) if line_heights else 0

        cx, cy = SceneComposer.resolve_text_positions(layer, width, height)

        # Slide-up offset with spring physics
        if entrance == "slide_up" and progress < 1.0:
            cy += int((1.0 - progress) * 45 * scale_h)

        pad_x = int(16 * scale_h)
        pad_y = int(12 * scale_h)
        card_x1 = cx - total_w // 2 - pad_x
        card_y1 = cy - total_h // 2 - pad_y
        card_x2 = cx + total_w // 2 + pad_x
        card_y2 = cy + total_h // 2 + pad_y

        # Draw NativePPTXEngine style rounded card background container
        card_bg = (15, 23, 42, int(220 * progress))
        # The card keeps its dark backing and light text; only the border carries the
        # brand. Tinting the fill would put arbitrary brand colour behind text whose
        # contrast is already tuned against this near-black.
        border_col = (*brand_theme.accent_rgb((59, 130, 246)), int(240 * progress))
        border_w = max(1, int(2 * scale_h))
        corner_r = max(4, int(12 * scale_h))
        draw.rounded_rectangle([card_x1, card_y1, card_x2, card_y2], radius=corner_r, fill=card_bg, outline=border_col, width=border_w)

        # Text color
        base_rgb = tuple(layer.color) if len(layer.color) == 3 else (248, 250, 252)
        alpha = int(255 * (progress if entrance == "fade_in" else 1.0))
        text_rgba = (base_rgb[0], base_rgb[1], base_rgb[2], alpha)
        shadow_rgba = (0, 0, 0, int(180 * (alpha / 255.0)))

        curr_y = cy - total_h // 2
        for i, line in enumerate(lines):
            line_w = line_widths[i]
            line_x = cx - line_w // 2

            # Drop shadow
            draw.text((line_x + 2, curr_y + 2), line, font=font, fill=shadow_rgba)
            # Main text
            draw.text((line_x, curr_y), line, font=font, fill=text_rgba)
            curr_y += line_heights[i]

        # Convert back to OpenCV BGR frame
        frame[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    @classmethod
    def render_lower_third_banner(cls, frame: np.ndarray, title: str, subtitle: str,
                                   width: int, height: int, progress: float,
                                   banner_color: Tuple[int, int, int] = (15, 23, 42)):
        """
        Renders a cinematic lower-third banner with spring-physics slide entrance.
        """
        scale_h = height / 1080.0
        if progress <= 0.0:
            return
        eased = spring_ease(progress)
        banner_h = int(75 * scale_h)
        banner_y = int(height * 0.78)

        target_w = int(width * 0.45)
        current_w = int(target_w * eased)
        if current_w <= 10:
            return

        overlay = frame.copy()
        cv2.rectangle(overlay, (40, banner_y), (40 + current_w, banner_y + banner_h), banner_color, -1)
        cv2.rectangle(overlay, (40, banner_y), (46, banner_y + banner_h), (59, 130, 246), -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

        if eased > 0.4:
            pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(pil_img, "RGBA")
            font_title = FontManager.get_font(int(20 * scale_h), bold=True)
            font_sub = FontManager.get_font(int(14 * scale_h), bold=False)

            draw.text((60, banner_y + int(12 * scale_h)), title, font=font_title, fill=(248, 250, 252, 255))
            if subtitle:
                draw.text((60, banner_y + int(42 * scale_h)), subtitle, font=font_sub, fill=(148, 163, 184, 255))

            frame[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    @classmethod
    def render_radial_progress_ring(cls, frame: np.ndarray, progress: float,
                                     width: int, height: int,
                                     center: Tuple[int, int] = None,
                                     radius: int = 22,
                                     ring_color: Tuple[int, int, int] = (59, 130, 246)):
        scale_h = height / 1080.0
        if center is None:
            center = (width - int(45 * scale_h), int(45 * scale_h))
        cx, cy = center
        scaled_r = int(radius * scale_h)
        cv2.circle(frame, (cx, cy), scaled_r, (40, 50, 65), max(1, int(3 * scale_h)), cv2.LINE_AA)
        angle = int(360 * progress)
        if angle > 0:
            cv2.ellipse(frame, (cx, cy), (scaled_r, scaled_r), -90, 0, angle, ring_color, max(1, int(3 * scale_h)), cv2.LINE_AA)

    @classmethod
    def render_scene_title_bar(cls, frame: np.ndarray, title: str,
                                width: int, height: int,
                                bar_color: Tuple[int, int, int] = (99, 102, 241)):
        scale_h = height / 1080.0
        bar_h = int(50 * scale_h)
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (width, bar_h), bar_color, -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img, "RGBA")
        font = FontManager.get_font(int(22 * scale_h), bold=True)
        draw.text((int(20 * scale_h), int(12 * scale_h)), title, font=font, fill=(255, 255, 255, 255))
        frame[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    @classmethod
    def render_animated_word_captions(cls, frame: np.ndarray, word_timeline: List[Any],
                                       current_sec: float, width: int, height: int):
        """
        Renders a single clean caption line, bottom-center, inside the reserved Caption
        Safe-Zone (y in [0.82H, 0.95H]): large uniform white text on a subtle dark
        semi-transparent background, matching a professional single-line subtitle look.
        """
        if not word_timeline:
            return

        scale_h = height / 1080.0

        # Find current active utterance window
        active_idx = -1
        for i, w in enumerate(word_timeline):
            if w.start_sec <= current_sec <= w.end_sec:
                active_idx = i
                break
            elif current_sec < w.start_sec:
                break

        if active_idx == -1:
            # If between words, highlight the word closest to current_sec
            active_idx = min(range(len(word_timeline)), key=lambda i: abs(word_timeline[i].start_sec - current_sec))

        # Show a short sliding window around the active word -- kept to a single line
        win_start = max(0, active_idx - 2)
        win_end = min(len(word_timeline), active_idx + 4)
        window_words = word_timeline[win_start:win_end]

        if not window_words:
            return

        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img, "RGBA")
        font = FontManager.get_font(int(34 * scale_h), bold=True)

        caption_text = " ".join(w.word for w in window_words)
        bbox = font.getbbox(caption_text)
        total_caption_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        caption_y = int(height * 0.87)  # Bottom-center, within the reserved safe zone
        start_x = (width - total_caption_w) // 2

        # Subtle dark backdrop -- no border, softly rounded, single flat card
        pad_x, pad_y = int(22 * scale_h), int(14 * scale_h)
        card_x1 = max(20, start_x - pad_x)
        card_y1 = caption_y - pad_y
        card_x2 = min(width - 20, start_x + total_caption_w + pad_x)
        card_y2 = caption_y + text_h + pad_y
        draw.rounded_rectangle([card_x1, card_y1, card_x2, card_y2], radius=int(10 * scale_h),
                               fill=(10, 10, 14, 165))

        # Brand accent as a rule along the bottom of the caption card.
        #
        # Drawn ONLY for a branded job. Unlike the other accents -- which recolour
        # something already on screen -- this adds an element that was not there before,
        # so drawing it unconditionally would change how every unbranded video looks.
        #
        # Deliberately NOT applied to the caption text. Subtitles are the one element
        # that must stay readable at a glance over any footage, and white on this dark
        # scrim is what guarantees that -- a pale or low-contrast brand colour would make
        # the narration hard to read, which no amount of on-brand is worth. The rule
        # carries the colour instead, and the scrim stays exactly as it was.
        if brand_theme.is_branded():
            rule_h = max(2, int(3 * scale_h))
            rule_inset = int(10 * scale_h)
            draw.rounded_rectangle(
                [card_x1 + rule_inset, card_y2 - rule_h, card_x2 - rule_inset, card_y2],
                radius=rule_h // 2,
                fill=(*brand_theme.accent_rgb(brand_theme.APP_STAT_RULE), 230),
            )

        # Single uniform white line -- no per-word color cycling, clean professional look
        draw.text((start_x + 1, caption_y + 1), caption_text, font=font, fill=(0, 0, 0, 160))  # drop shadow
        draw.text((start_x, caption_y), caption_text, font=font, fill=(255, 255, 255, 255))

        frame[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    @classmethod
    def render_progress_bar(cls, frame: np.ndarray, progress: float,
                             width: int, height: int,
                             bar_color: Optional[Tuple[int, int, int]] = None,
                             track_color: Optional[Tuple[int, int, int]] = None):
        """
        Scene progress bar along the bottom edge.

        Both colours are BGR, because this draws with cv2 rather than PIL. None means
        "this job's brand", which resolves to the app's own colours when no kit is
        active. The track is a heavily darkened secondary so the fill stays readable
        against it -- see brand_theme.track_bgr.
        """
        bar_color = bar_color or brand_theme.accent_bgr((241, 102, 99))
        track_color = track_color or brand_theme.track_bgr((59, 41, 30))
        bar_y = int(height * 0.96)
        bar_h = 6
        margin = int(width * 0.06)
        track_w = width - 2 * margin

        cv2.rectangle(frame, (margin, bar_y), (margin + track_w, bar_y + bar_h),
                      track_color, -1)
        fill_w = int(track_w * progress)
        if fill_w > 0:
            cv2.rectangle(frame, (margin, bar_y), (margin + fill_w, bar_y + bar_h),
                          bar_color, -1)

    @classmethod
    def render_scene_counter(cls, frame: np.ndarray, scene_num: int, total_scenes: int,
                              width: int, height: int):
        text = f"{scene_num}/{total_scenes}"
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img, "RGBA")
        font = FontManager.get_font(16, bold=False)
        draw.text((width - 80, height - 25), text, font=font, fill=(148, 163, 184, 255))
        frame[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
