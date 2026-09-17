"""
Report figure helpers.

DiagramGenerator and ChartGenerator were removed: they rendered this product's own
architecture and invented benchmark numbers into whatever report was being generated.
See figure_placeholder.py for the reasoning and for what replaced them.
"""
from agents.latex.generators.figure_placeholder import draw_placeholder

__all__ = ["draw_placeholder"]
