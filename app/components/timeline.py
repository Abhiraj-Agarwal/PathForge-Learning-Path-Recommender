"""Milestone timeline component: planned vs in-progress Gantt bars."""
import plotly.express as px

TIMELINE_COLORS = {
    "Completed": "#00cc96",
    "In Progress": "#636efa",
    "Upcoming": "#b0b0b0",
}


def build_timeline(rows: list) -> px.Figure:
    fig = px.timeline(
        rows,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Status",
        color_discrete_map=TIMELINE_COLORS,
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        margin=dict(l=40, r=20, t=20, b=20),
        xaxis_title="",
        yaxis_title="",
        showlegend=True,
    )
    return fig