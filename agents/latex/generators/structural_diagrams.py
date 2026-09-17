"""
Draws the structural diagrams described in a DiagramSet.

Purely mechanical: every label here comes from the spec, which was extracted from the
report's own text and then verified against it. Nothing in this module knows anything
about inventory systems, React, or any other subject -- if it did, it would be the
hardcoded-template bug again.

matplotlib rather than fpdf2 primitives: the three layouts need text measurement, arrow
routing and rotated labels, all of which matplotlib already does well, and it renders the
accented French labels correctly with its bundled DejaVu.
"""
import logging
import os
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")           # headless: no display on a server
import matplotlib.patches as patches
import matplotlib.pyplot as plt

from agents.latex.diagram_spec import ArchitectureSpec, ERSpec, SequenceSpec

logger = logging.getLogger("uvicorn")

DPI = 200
INK = "#0F172A"
MUTED = "#475569"
LINE = "#94A3B8"
TIER_FILL = ["#EFF6FF", "#F0FDF4", "#FEF3C7", "#FAF5FF", "#FFF1F2"]
TIER_EDGE = ["#1D4ED8", "#15803D", "#B45309", "#7E22CE", "#BE123C"]


def _fig(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    return fig, ax


def _save(fig, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _wrap(text, width):
    """Naive word wrap -- labels are short, so this is enough and keeps it dependency-free."""
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = f"{cur} {w}".strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Architecture: stacked tiers with flows between them
# ---------------------------------------------------------------------------

def render_architecture(spec: ArchitectureSpec, path: str) -> Optional[str]:
    if not spec or not spec.is_renderable():
        return None
    tiers = spec.tiers[:5]
    n = len(tiers)
    fig, ax = _fig(9, 1.7 * n + 1.2)

    gap = 4.0
    band_h = (100.0 - gap * (n - 1)) / n
    centres = {}
    for i, tier in enumerate(tiers):
        # Drawn top-down so the client tier sits at the top, as architecture diagrams read.
        y = 100.0 - (i + 1) * band_h - i * gap
        centres[tier.name] = y + band_h / 2.0
        ax.add_patch(patches.FancyBboxPatch(
            (4, y), 92, band_h, boxstyle="round,pad=0.6,rounding_size=2",
            linewidth=1.4, edgecolor=TIER_EDGE[i % len(TIER_EDGE)],
            facecolor=TIER_FILL[i % len(TIER_FILL)]))
        ax.text(8, y + band_h - 5.5, tier.name, fontsize=11, fontweight="bold",
                color=TIER_EDGE[i % len(TIER_EDGE)], va="top", ha="left")

        comps = tier.components[:4]
        if comps:
            slot = 86.0 / len(comps)
            for j, comp in enumerate(comps):
                cx = 9 + slot * j
                ax.add_patch(patches.FancyBboxPatch(
                    (cx, y + 3), slot - 3, band_h - 13,
                    boxstyle="round,pad=0.3,rounding_size=1.2",
                    linewidth=1.0, edgecolor=LINE, facecolor="white"))
                ax.text(cx + (slot - 3) / 2.0, y + 3 + (band_h - 13) / 2.0,
                        _wrap(comp, 22), fontsize=8.5, color=INK,
                        ha="center", va="center")

    for flow in spec.flows[:6]:
        if len(flow) < 2:
            continue
        src, dst = flow[0], flow[1]
        label = flow[2] if len(flow) > 2 else ""
        if src not in centres or dst not in centres:
            continue
        y0, y1 = centres[src], centres[dst]
        # Arrows run down the right-hand gutter so they never cross a component box.
        ax.annotate("", xy=(98.5, y1), xytext=(98.5, y0),
                    arrowprops=dict(arrowstyle="-|>", color=MUTED, linewidth=1.3,
                                    shrinkA=2, shrinkB=2,
                                    connectionstyle="arc3,rad=0.28"))
        if label:
            ax.text(99.5, (y0 + y1) / 2.0, _wrap(label, 16), fontsize=7.5, color=MUTED,
                    ha="left", va="center", rotation=90)

    if spec.title:
        ax.set_title(spec.title, fontsize=12, fontweight="bold", color=INK, pad=12)
    return _save(fig, path)


# ---------------------------------------------------------------------------
# Entity-relationship: entity boxes with their attributes, joined by relations
# ---------------------------------------------------------------------------

def _edge_point(box, tx, ty):
    """
    Where the line from a box's centre toward (tx, ty) crosses that box's border.

    box is (cx, cy, x, y, w, h). Scaling the direction vector by the smaller of the two
    axis ratios lands the point on whichever side the line actually exits through.
    """
    cx, cy, _x, _y, w, h = box
    dx, dy = tx - cx, ty - cy
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return cx, cy
    sx = (w / 2.0) / abs(dx) if abs(dx) > 1e-9 else float("inf")
    sy = (h / 2.0) / abs(dy) if abs(dy) > 1e-9 else float("inf")
    t = min(sx, sy)
    return cx + dx * t, cy + dy * t


def render_er(spec: ERSpec, path: str) -> Optional[str]:
    if not spec or not spec.is_renderable():
        return None
    entities = spec.entities[:6]
    n = len(entities)
    cols = 2 if n <= 4 else 3
    rows = (n + cols - 1) // cols
    fig, ax = _fig(9, 1.2 * rows + 0.9 + 0.09 * rows * max(len(e.attributes[:6]) for e in entities))

    box_w = 88.0 / cols - 6.0
    # Height follows the fullest entity rather than a fixed slot, so a box with three
    # attributes is not drawn as a mostly-empty rectangle.
    max_attrs = max((len(e.attributes[:6]) for e in entities), default=0)
    box_h = min(88.0 / rows - 8.0, 14.0 + max_attrs * 5.2)
    pos = {}
    for i, ent in enumerate(entities):
        r, c = divmod(i, cols)
        x = 6 + c * (box_w + 8)
        y = 92 - (r + 1) * box_h - r * 8
        pos[ent.name] = (x + box_w / 2.0, y + box_h / 2.0, x, y, box_w, box_h)

        ax.add_patch(patches.FancyBboxPatch(
            (x, y), box_w, box_h, boxstyle="round,pad=0.3,rounding_size=1.2",
            linewidth=1.3, edgecolor="#1D4ED8", facecolor="white"))
        # Header band carries the entity name, as in a UML class box.
        ax.add_patch(patches.Rectangle((x, y + box_h - 7), box_w, 7,
                                       linewidth=0, facecolor="#EFF6FF"))
        ax.text(x + box_w / 2.0, y + box_h - 3.5, ent.name, fontsize=9.5,
                fontweight="bold", color="#1D4ED8", ha="center", va="center")
        attrs = ent.attributes[:6]
        for k, a in enumerate(attrs):
            ax.text(x + 2.5, y + box_h - 11 - k * 4.6, f"· {str(a)[:26]}",
                    fontsize=7.5, color=MUTED, ha="left", va="center")

    for rel in spec.relations[:8]:
        if rel.source not in pos or rel.target not in pos:
            continue
        # Join the box EDGES, not the centres.
        #
        # matplotlib's shrinkA/shrinkB are in points, which has no fixed relationship to
        # these data units -- a single shrink value left the connector running through the
        # middle of both entity boxes. Clipping the centre-to-centre segment against each
        # rectangle puts the endpoints exactly on the borders, whatever the box size.
        x0, y0 = _edge_point(pos[rel.source], pos[rel.target][0], pos[rel.target][1])
        x1, y1 = _edge_point(pos[rel.target], pos[rel.source][0], pos[rel.source][1])
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-", color=LINE, linewidth=1.2,
                                    shrinkA=0, shrinkB=0))
        mid_x, mid_y = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        caption = " ".join(p for p in (rel.cardinality, rel.label) if p)
        if caption:
            ax.text(mid_x, mid_y, caption[:26], fontsize=7.5, color=INK,
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                              edgecolor=LINE, linewidth=0.7))

    if spec.title:
        ax.set_title(spec.title, fontsize=12, fontweight="bold", color=INK, pad=12)
    return _save(fig, path)


# ---------------------------------------------------------------------------
# Sequence: lifelines with ordered messages
# ---------------------------------------------------------------------------

def render_sequence(spec: SequenceSpec, path: str) -> Optional[str]:
    if not spec or not spec.is_renderable():
        return None
    actors = spec.actors[:5]
    messages = spec.messages[:10]
    fig, ax = _fig(9, 1.0 + 0.62 * len(messages) + 1.2)

    slot = 100.0 / len(actors)
    xs = {a: slot * (i + 0.5) for i, a in enumerate(actors)}
    top, bottom = 90.0, 8.0

    for a in actors:
        x = xs[a]
        ax.add_patch(patches.FancyBboxPatch(
            (x - slot * 0.42, top), slot * 0.84, 8,
            boxstyle="round,pad=0.3,rounding_size=1.2",
            linewidth=1.2, edgecolor="#1D4ED8", facecolor="#EFF6FF"))
        ax.text(x, top + 4, _wrap(a, 16), fontsize=8, fontweight="bold",
                color="#1D4ED8", ha="center", va="center")
        # The lifeline.
        ax.plot([x, x], [bottom, top], linestyle=(0, (3, 3)), color=LINE, linewidth=1.0)

    step = (top - bottom - 4) / max(len(messages), 1)
    for i, msg in enumerate(messages):
        if msg.source not in xs or msg.target not in xs:
            continue
        y = top - 4 - (i + 1) * step
        x0, x1 = xs[msg.source], xs[msg.target]
        if abs(x1 - x0) < 0.1:
            continue                    # a self-call needs a loop; skip rather than mislead
        ax.annotate("", xy=(x1, y), xytext=(x0, y),
                    arrowprops=dict(arrowstyle="-|>", color=MUTED, linewidth=1.2,
                                    linestyle="--" if msg.is_return else "-",
                                    shrinkA=1, shrinkB=1))
        ax.text((x0 + x1) / 2.0, y + 1.6, _wrap(msg.label, 34), fontsize=7.5,
                color=INK, ha="center", va="bottom")

    if spec.title:
        ax.set_title(spec.title, fontsize=12, fontweight="bold", color=INK, pad=12)
    return _save(fig, path)


def _labels_of(item) -> List[str]:
    """Every label a diagram draws -- used to decide which chapter it belongs in."""
    out = [getattr(item, "title", "") or ""]
    tiers = getattr(item, "tiers", None)
    if tiers:
        for t in tiers:
            out.append(t.name)
            out.extend(t.components)
    entities = getattr(item, "entities", None)
    if entities:
        for e in entities:
            out.append(e.name)
            out.extend(e.attributes[:4])
    actors = getattr(item, "actors", None)
    if actors:
        out.extend(actors)
        for m in getattr(item, "messages", [])[:6]:
            out.append(m.label)
    return [x for x in out if x]


def render_all(spec, out_dir: str) -> List[tuple]:
    """
    Render everything renderable. Returns [(image_path, caption, labels)] in reading order.

    `labels` travels with each image so the report can place it in the chapter that
    actually discusses it, rather than dropping every figure into the first chapter that
    happens to be flagged for one.

    Any single diagram that fails is skipped with a warning rather than failing the
    report: a missing figure is a gap the student can fill, while a failed job is a lost
    render and a wasted credit.
    """
    made = []
    jobs = []
    if spec.architecture and spec.architecture.is_renderable():
        jobs.append(("architecture.png", spec.architecture,
                     render_architecture, spec.architecture.title))
    if spec.er and spec.er.is_renderable():
        jobs.append(("data_model.png", spec.er, render_er, spec.er.title))
    for i, seq in enumerate(spec.sequences[:2], start=1):
        if seq.is_renderable():
            jobs.append((f"sequence_{i}.png", seq, render_sequence, seq.title))

    for filename, item, fn, title in jobs:
        path = os.path.join(out_dir, filename)
        try:
            if fn(item, path):
                made.append((path, title, _labels_of(item)))
                logger.info(f"StructuralDiagrams: rendered {filename} ({title!r})")
        except Exception as exc:
            logger.warning(f"StructuralDiagrams: could not render {filename} ({exc}); skipping.")
    return made
