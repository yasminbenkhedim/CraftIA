"""
Figure placeholders for generated reports.

WHY THERE ARE NO GENERATED FIGURES ANY MORE
-------------------------------------------
This package used to contain DiagramGenerator and ChartGenerator. They did not draw the
user's system -- they drew *this product's* system, hardcoded. A student asking for a
report on a React/Node inventory application received an "architecture diagram" labelled
"Angular 18 Frontend / FastAPI Backend / Cognitive Planner & LLM Service / Agent Engines
(PPTX / LaTeX / MP4)", with only the caption text substituted. The charts were the same:
fixed latency numbers and a bar chart comparing this application's own three agents.

Presented inside a final-year project report, that is not a rough draft. It is a figure
of a system the student never built, with invented measurements, submitted under their
name. The correct fix is not a better diagram generator -- it is to stop fabricating.

So the figures are gone, and what stands in their place is an explicitly empty frame
saying, in the report's own language, that the student must insert their own diagram.
A blank the reader can see is honest; a plausible wrong diagram is not.

A future pass could generate a real diagram from the report's own content -- the
architecture the LLM actually described in the Conception chapter. That is worth doing,
and it is a different job from this one.
"""
from typing import Tuple


# Muted slate, so a placeholder reads as an unfinished area rather than as a design
# element someone might mistake for finished work.
FRAME_RGB: Tuple[int, int, int] = (148, 163, 184)
LABEL_RGB: Tuple[int, int, int] = (71, 85, 105)
HINT_RGB: Tuple[int, int, int] = (100, 116, 139)
FRAME_HEIGHT_MM = 58.0


def draw_placeholder(pdf, width_mm: float, label: str, hint: str) -> None:
    """
    Draw a dashed frame carrying `label` and, below it, a smaller `hint`.

    Takes the FPDF instance rather than producing an image: there is no picture to make,
    and writing a PNG of the words "insert your diagram here" would put a fake asset on
    disk for something that is deliberately absent.
    """
    x = pdf.get_x()
    y = pdf.get_y()

    # Keep the frame whole: if it will not fit, start it on the next page rather than
    # letting the auto page break slice it in half.
    if y + FRAME_HEIGHT_MM > pdf.h - pdf.b_margin:
        pdf.add_page()
        x, y = pdf.get_x(), pdf.get_y()

    pdf.set_draw_color(*FRAME_RGB)
    pdf.set_line_width(0.4)
    try:
        pdf.dashed_rect(x, y, width_mm, FRAME_HEIGHT_MM, dash_length=2.0, space_length=2.0)
    except AttributeError:
        # dashed_rect is not in every fpdf2 release; a solid frame carries the same
        # meaning and the label is what actually communicates.
        pdf.rect(x, y, width_mm, FRAME_HEIGHT_MM)

    pdf.set_xy(x, y + FRAME_HEIGHT_MM / 2 - 10)
    pdf.set_font(pdf.font_family, "B", 11)
    pdf.set_text_color(*LABEL_RGB)
    pdf.cell(width_mm, 7, label, border=0, new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_x(x)
    pdf.set_font(pdf.font_family, "", 8)
    pdf.set_text_color(*HINT_RGB)
    pdf.multi_cell(width_mm, 4.5, hint, border=0, align="C")

    # Leave the cursor below the frame regardless of how tall the hint wrapped.
    pdf.set_xy(x, y + FRAME_HEIGHT_MM + 3)
