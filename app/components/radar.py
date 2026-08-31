"""Mastery radar component: current mastery overlaid on demand-weighted target."""
import plotly.graph_objects as go


def build_radar(mastery: dict) -> go.Figure:
    """Build the current-vs-target radar. The gap between the shapes *is* the gap."""
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=mastery["current"],
        theta=mastery["skills"],
        fill="toself",
        name="Current Mastery",
        line_color="#1f77b4",
        opacity=0.55,
    ))
    fig.add_trace(go.Scatterpolar(
        r=mastery["target"],
        theta=mastery["skills"],
        fill="toself",
        name="Target Demand",
        line_color="#ff7f0e",
        opacity=0.35,
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1], tickvals=[0.25, 0.5, 0.75, 1.0])),
        showlegend=True,
        margin=dict(l=40, r=40, t=20, b=20),
    )
    return fig