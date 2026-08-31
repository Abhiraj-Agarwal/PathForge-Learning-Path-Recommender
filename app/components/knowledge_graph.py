"""Interactive knowledge-graph view of a learning path.

Circular nodes, one per skill -- always the REAL skills in the active plan's
ancestor closure (or the demo preview's), never a fixed/hardcoded set; colors
reflect the learner's actual current mastery, so anything already mastered
stays green regardless of how the rest of the graph is laid out. Edges are
real prerequisite relationships pulled straight from the skill DAG
(core/graph.py).

Layout, top to bottom like a conventional DAG diagram: topological depth
(longest path from a root skill) maps to a ROW, so foundational skills sit at
the top and everything that depends on them cascades downward. Within a row,
a one-pass barycenter heuristic orders nodes by the average column position
of their already-placed predecessors -- the standard Sugiyama-layout trick
for cutting down edge crossings, since naive alphabetical ordering scatters
predecessors/successors with no relation to each other and makes the graph
read as tangled. Row/column spacing scales with how crowded the busiest row
is, and node labels are truncated (full name still lives in the hover
tooltip and the click-through detail panel) -- both specifically to stop
long skill names from bleeding into neighboring columns.

Each edge is drawn as a gentle quadratic-bezier arc (straight, overlapping
lines are what makes a layered graph look like a plate of noodles) and capped
with a small arrowhead annotation near the destination end, so prerequisite
direction is visible at a glance.

Rendered through st.plotly_chart(..., on_select="rerun"), so a click returns
the tapped node's skill_id to Python -- the caller uses that to show a detail
panel and to re-render this figure with ``focus_id`` set, which narrows the
axis ranges around that node for a "zoom in" effect. ``layout.transition`` is
set so that re-range happens as a smooth animated tween (Plotly.react keeps
the same trace identity across a Streamlit rerun with an unchanged widget
key), not a hard jump cut.
"""

from __future__ import annotations

import math
from collections import defaultdict

import plotly.graph_objects as go

STATUS_STYLE = {
    "mastered": dict(fill="#8FE3A8", line="#0ca30c", label="Mastered"),
    "in_progress": dict(fill="#FFCC66", line="#c98500", label="In progress"),
    "upcoming": dict(fill="#D9D6E8", line="#8b86a8", label="Upcoming"),
}
EDGE_COLOR = "rgba(79,70,229,0.35)"
FONT_FAMILY = "system-ui, -apple-system, Segoe UI, sans-serif"

COL_SPACING = 2.6
ROW_SPACING = 3.2
MAX_LABEL_CHARS = 16
ZOOM_TRANSITION_MS = 650

# Where along each bezier arc the visible "shaft" stops, and where the short
# arrowhead segment sits -- both short of t=1 (the node center) so the
# arrowhead doesn't disappear under the marker.
SHAFT_END_T = 0.80
ARROW_TAIL_T = 0.76
ARROW_HEAD_T = 0.90


def _truncate(name: str) -> str:
    return name if len(name) <= MAX_LABEL_CHARS else name[: MAX_LABEL_CHARS - 1] + "…"


def _depths(node_ids: set[str], prereqs_of: dict[str, set[str]]) -> dict[str, int]:
    depth: dict[str, int] = {}

    def compute(node: str, stack: set[str]) -> int:
        if node in depth:
            return depth[node]
        preds = [p for p in prereqs_of.get(node, ()) if p in node_ids]
        if not preds or node in stack:
            depth[node] = 0
        else:
            depth[node] = 1 + max(compute(p, stack | {node}) for p in preds)
        return depth[node]

    for node in node_ids:
        compute(node, set())
    return depth


def _layout(nodes: list[dict], edges: list[tuple[str, str]]):
    """Top-down layered layout: depth -> row, barycenter-ordered column."""
    node_ids = {n["id"] for n in nodes}
    prereqs_of: dict[str, set[str]] = defaultdict(set)
    for src, dst in edges:
        prereqs_of[dst].add(src)

    depth = _depths(node_ids, prereqs_of)
    by_depth: dict[int, list[str]] = defaultdict(list)
    for node in nodes:
        by_depth[depth[node["id"]]].append(node["id"])

    positions: dict[str, tuple[float, float]] = {}
    col_slot: dict[str, float] = {}

    for d in sorted(by_depth):
        ids = by_depth[d]
        if d == 0:
            ids.sort()  # stable starting order for root skills
        else:
            def barycenter(node_id: str) -> float:
                preds = [p for p in prereqs_of.get(node_id, ()) if p in col_slot]
                return sum(col_slot[p] for p in preds) / len(preds) if preds else 0.0

            ids.sort(key=lambda nid: (barycenter(nid), nid))

        n = len(ids)
        for i, node_id in enumerate(ids):
            slot = i - (n - 1) / 2
            col_slot[node_id] = slot
            positions[node_id] = (slot * COL_SPACING, -float(d) * ROW_SPACING)

    max_row_width = max((len(ids) for ids in by_depth.values()), default=1)
    return positions, len(by_depth), max_row_width


def _bezier_arc(p0: tuple[float, float], p1: tuple[float, float],
                curvature: float = 0.10, steps: int = 20) -> tuple[list[float], list[float]]:
    """Quadratic-bezier points from p0 to p1, bowed perpendicular to the
    segment -- softens overlapping straight edges into legible arcs."""
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    dist = math.hypot(dx, dy) or 1.0
    ox, oy = -dy / dist, dx / dist  # unit perpendicular
    cx = (x0 + x1) / 2 + ox * dist * curvature
    cy = (y0 + y1) / 2 + oy * dist * curvature

    xs, ys = [], []
    for i in range(steps + 1):
        t = i / steps
        xs.append((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t ** 2 * x1)
        ys.append((1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t ** 2 * y1)
    return xs, ys


def _point_at(p0, p1, curvature, t):
    xs, ys = _bezier_arc(p0, p1, curvature=curvature, steps=40)
    idx = min(int(round(t * 40)), 40)
    return xs[idx], ys[idx]


def build_knowledge_graph(nodes: list[dict], edges: list[tuple[str, str]],
                          focus_id: str | None = None) -> go.Figure:
    """``nodes`` = [{"id", "name", "status"}, ...]; ``edges`` = [(prereq_id, dependent_id), ...]."""
    positions, n_rows, max_row_width = _layout(nodes, edges)
    fig = go.Figure()

    edge_x, edge_y = [], []
    annotations = []
    for src, dst in edges:
        if src not in positions or dst not in positions:
            continue
        p0, p1 = positions[src], positions[dst]
        xs, ys = _bezier_arc(p0, p1)
        shaft_cut = int(round(SHAFT_END_T * len(xs)))
        edge_x += xs[: shaft_cut + 1] + [None]
        edge_y += ys[: shaft_cut + 1] + [None]

        tail = _point_at(p0, p1, 0.10, ARROW_TAIL_T)
        head = _point_at(p0, p1, 0.10, ARROW_HEAD_T)
        annotations.append(dict(
            x=head[0], y=head[1], ax=tail[0], ay=tail[1],
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=2, arrowsize=0.9, arrowwidth=1.3,
            arrowcolor=EDGE_COLOR, standoff=0, opacity=0.9,
        ))

    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y, mode="lines",
        line=dict(color=EDGE_COLOR, width=1.6, shape="spline"),
        hoverinfo="skip", showlegend=False,
    ))

    by_status: dict[str, list[dict]] = defaultdict(list)
    for node in nodes:
        by_status[node.get("status", "upcoming")].append(node)

    for status in ("upcoming", "in_progress", "mastered"):  # draw back-to-front by salience
        group = by_status.get(status)
        if not group:
            continue
        style = STATUS_STYLE.get(status, STATUS_STYLE["upcoming"])
        xs = [positions[n["id"]][0] for n in group]
        ys = [positions[n["id"]][1] for n in group]
        sizes = [42 if n["id"] == focus_id else 32 for n in group]
        line_widths = [5 if n["id"] == focus_id else 2 for n in group]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers+text",
            marker=dict(size=sizes, color=style["fill"], opacity=0.95,
                       line=dict(color=style["line"], width=line_widths)),
            text=[_truncate(n["name"]) for n in group],
            textposition="top center",
            textfont=dict(size=11, family=FONT_FAMILY, color="#1E1B2E"),
            customdata=[n["id"] for n in group],
            name=style["label"],
            hovertext=[n["name"] for n in group],
            hovertemplate="<b>%{hovertext}</b><extra></extra>",
        ))

    height = max(480, min(900, 170 * n_rows + 120))
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, title=""),
        margin=dict(l=30, r=30, t=40, b=20),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_FAMILY),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=height,
        dragmode="pan",
        annotations=annotations,
        transition=dict(duration=ZOOM_TRANSITION_MS, easing="cubic-in-out"),
    )

    if focus_id and focus_id in positions:
        fx, fy = positions[focus_id]
        fig.update_layout(
            xaxis=dict(visible=False, range=[fx - 3.2, fx + 3.2]),
            yaxis=dict(visible=False, range=[fy - 3.2, fy + 3.2]),
        )

    return fig
