"""Dashboard view: mastery radar + milestone Gantt + headline metrics."""
import streamlit as st

import mock
from components.radar import build_radar
from components.timeline import build_timeline
from core.diagnostic import is_mastered


def render_dashboard():
    mastery = st.session_state.get("skill_mastery", {}) or {}
    path = mock.MOCK_PATH

    mastered = sum(1 for p in mastery.values() if is_mastered(p))
    avg = sum(mastery.values()) / len(mastery) if mastery else 0.0
    total_skills = sum(len(steps) for steps in path["milestones"].values())
    next_milestone = next(
        (m for m, steps in path["milestones"].items()
         if any(s["status"] == "upcoming" for s in steps)), "—")

    st.header("Skill Mastery & Progress")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Avg mastery", f"{avg:.0%}")
    m2.metric("Skills mastered", f"{mastered}/{total_skills}")
    m3.metric("Skills in path", total_skills)
    m4.metric("Next milestone", f"M{next_milestone}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Mastery Gap")
        st.plotly_chart(build_radar(mock.MOCK_MASTERY), width="stretch")
    with col2:
        st.subheader("Milestone Timeline")
        st.plotly_chart(build_timeline(mock.MOCK_TIMELINE), width="stretch")

    st.caption("The gap between the radar shapes *is* the skill gap: blue is where you "
               "are now, orange is what the market asks for your target role.")