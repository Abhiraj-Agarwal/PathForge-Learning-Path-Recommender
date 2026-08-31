"""Milestone timeline component: planned vs in-progress Gantt bars."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

TIMELINE_COLORS = {
    "Completed": "#0ca30c",     # status: good
    "In Progress": "#2a78d6",   # categorical slot 1
    "Upcoming": "#c3c2b7",      # muted baseline
}


def build_timeline(rows: list) -> go.Figure:
    # px.timeline mutates its "Finish" column in place -- turning it into a
    # raw millisecond duration used for the bar's x-length -- before handing
    # columns off to custom_data. Referencing "Finish" directly in
    # custom_data therefore shows that duration number, not the finish date.
    # A duplicate column under a different name survives untouched.
    df = pd.DataFrame(rows)
    df["Finish_label"] = df["Finish"]

    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Status",
        color_discrete_map=TIMELINE_COLORS,
        custom_data=["Start", "Finish_label", "Status"],
    )
    fig.update_traces(
        hovertemplate=("<b>%{y}</b><br>%{customdata[0]|%b %d, %Y} → %{customdata[1]}"
                       "<br>Status: %{customdata[2]}<extra></extra>"),
        marker=dict(line=dict(width=0)),
    )
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(137,135,129,0.2)")
    fig.update_xaxes(gridcolor="rgba(137,135,129,0.2)")
    fig.update_layout(
        margin=dict(l=10, r=20, t=40, b=20),
        xaxis_title="",
        yaxis_title="",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, title=""),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif"),
        bargap=0.35,
    )
    return fig