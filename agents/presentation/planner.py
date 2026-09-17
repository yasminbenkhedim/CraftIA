from typing import Dict, Any, Tuple

class LayoutPlanner:
    """
    Computes exact bounding box coordinates (Inches) for presentation slide elements.
    """

    SLIDE_WIDTH = 13.333
    SLIDE_HEIGHT = 7.5

    @classmethod
    def get_header_bounds(cls) -> Tuple[float, float, float, float]:
        # (left, top, width, height)
        return (1.0, 0.6, 11.333, 1.2)

    @classmethod
    def get_content_bounds(cls) -> Tuple[float, float, float, float]:
        return (1.0, 2.1, 11.333, 4.7)

    @classmethod
    def get_kpi_card_bounds(cls, index: int, total: int = 4) -> Tuple[float, float, float, float]:
        margin_left = 1.0
        margin_top = 2.2
        card_w = 5.4
        card_h = 2.0
        gap_x = 0.5
        gap_y = 0.4

        row = index // 2
        col = index % 2
        left = margin_left + col * (card_w + gap_x)
        top = margin_top + row * (card_h + gap_y)
        return (left, top, card_w, card_h)
