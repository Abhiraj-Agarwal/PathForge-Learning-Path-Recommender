"""Mastery radar component: current mastery overlaid on demand-weighted target."""
import plotly.graph_objects as go

CURRENT_COLOR = "#2a78d6"  # categorical slot 1 (blue)
TARGET_COLOR = "#eb6834"   # categorical slot 2 (orange)


def build_radar(mastery: dict) -> go.Figure:
    """Build the current-vs-target radar. The gap between the shapes *is* the gap."""
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=mastery["current"],
        theta=mastery["skills"],
        fill="toself",
        name="Current mastery",
        line=dict(color=CURRENT_COLOR, width=2),
        fillcolor="rgba(42,120,214,0.28)",
        hovertemplate="%{theta}<br>Current: %{r:.0%}<extra></extra>",
    ))
    fig.add_trace(go.Scatterpolar(
        r=mastery["target"],
        theta=mastery["skills"],
        fill="toself",
        name="Target demand",
        line=dict(color=TARGET_COLOR, width=2),
        fillcolor="rgba(235,104,52,0.18)",
        hovertemplate="%{theta}<br>Target: %{r:.0%}<extra></extra>",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True, range=[0, 1],
                tickvals=[0.25, 0.5, 0.75, 1.0],
                tickformat=".0%",
                gridcolor="rgba(137,135,129,0.35)",
                linecolor="rgba(137,135,129,0.35)",
            ),
            angularaxis=dict(gridcolor="rgba(137,135,129,0.25)"),
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
        margin=dict(l=40, r=40, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif"),
    )
    return fig