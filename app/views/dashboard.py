"""Dashboard view: mastery radar + milestone Gantt + headline metrics.

Mirrors the same real-vs-preview split as Roadmap: when the chat has
produced a plan (st.session_state.current_plan), the radar and timeline are
built from ITS target skills and the planner's own week estimates, anchored
to today's date. Before any goal is set, it falls back to the same labeled
demo preview mock data uses everywhere else.
"""
from datetime import date, timedelta

import streamlit as st

import mock
from components.radar import build_radar
from components.timeline import build_timeline
from core.diagnostic import is_mastered

TILE_ACCENTS = [
    ("#4F46E5", "#8B7CF6"),  # indigo
    ("#FF7A59", "#FFA26B"),  # coral
    ("#1baf7a", "#5FD8A6"),  # teal
    ("#8B5CF6", "#B7A6F7"),  # violet
]


def _stat_tile(icon: str, value: str, label: str, accent: tuple[str, str]):
    start, end = accent
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, {start}22, {end}14);
            border: 1px solid {start}33;
            border-radius: 16px;
            padding: 1.1rem 1.2rem;
            height: 100%;
        ">
            <div style="font-size:1.6rem; line-height:1;">{icon}</div>
            <div style="font-size:1.7rem; font-weight:700; margin-top:.4rem; color:#1E1B2E;">{value}</div>
            <div style="font-size:.82rem; opacity:.65; margin-top:.1rem;">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _radar_data_from_plan(plan: dict, mastery: dict) -> dict:
    graph = plan["graph"]
    top = sorted(plan["targets"], key=lambda t: -t.demand)[:6]
    if not top:
        return mock.MOCK_MASTERY
    return {
        "skills": [graph.get(t.skill_id).name for t in top],
        "current": [mastery.get(t.skill_id, 0.0) for t in top],
        "target": [t.demand for t in top],
    }


def _timeline_rows_from_plan(plan: dict) -> list[dict]:
    path = plan["path"]
    today = date.today()
    rows = []
    for milestone in path.milestones:
        if milestone.estimated_start_week is None:
            continue
        start = today + timedelta(weeks=milestone.estimated_start_week)
        finish = today + timedelta(weeks=max(milestone.estimated_end_week, milestone.estimated_start_week + 0.5))
        status = "In Progress" if milestone.index == 0 else "Upcoming"
        rows.append({
            "Task": f"Milestone {milestone.index + 1}",
            "Start": start.isoformat(),
            "Finish": finish.isoformat(),
            "Status": status,
        })
    return rows or mock.MOCK_TIMELINE


def render_dashboard():
    plan = st.session_state.get("current_plan")
    mastery = st.session_state.get("skill_mastery", {}) or {}

    st.header("📊 Skill Mastery & Progress")

    if plan:
        st.caption(f"Tracking progress for: **“{plan['goal_text'].strip()}”**")
        path = plan["path"]
        total_skills = len(path.ancestor_closure)
        gap_count = len(path.gap_nodes)
        mastered = total_skills - gap_count
        next_milestone_label = f"M{path.milestones[0].index + 1}" if path.milestones else "—"
        radar_data = _radar_data_from_plan(plan, mastery)
        timeline_rows = _timeline_rows_from_plan(plan)
    else:
        st.info("💡 No goal set yet — showing a **demo preview**. Tell the **Chat** tab your "
                "real goal to see your own numbers here.")
        path = mock.MOCK_PATH
        mastered = sum(1 for p in mastery.values() if is_mastered(p))
        total_skills = sum(len(steps) for steps in path["milestones"].values())
        next_upcoming = next(
            (m for m, steps in path["milestones"].items()
             if any(s["status"] == "upcoming" for s in steps)), "—")
        next_milestone_label = f"M{next_upcoming}"
        radar_data = mock.MOCK_MASTERY
        timeline_rows = mock.MOCK_TIMELINE

    avg = sum(mastery.values()) / len(mastery) if mastery else 0.0
    quiz_answered = (st.session_state.get("quiz") or {}).get("answered", 0)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        _stat_tile("🎯", f"{avg:.0%}", "Avg mastery", TILE_ACCENTS[0])
    with m2:
        _stat_tile("✅", f"{mastered}/{total_skills}", "Skills mastered", TILE_ACCENTS[1])
    with m3:
        _stat_tile("📚", str(total_skills), "Skills in path", TILE_ACCENTS[2])
    with m4:
        _stat_tile("🚀", next_milestone_label, "Next milestone", TILE_ACCENTS[3])

    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("🕸️ Mastery Gap")
            if quiz_answered == 0:
                st.info("🎯 This is a flat starting baseline. **Take the diagnostic quiz** in "
                        "the **Chat** tab to see your real mastery mapped against market "
                        "demand here.")
            st.plotly_chart(build_radar(radar_data), width="stretch")
            st.caption("The gap between the shapes *is* the skill gap: blue is where "
                       "you are now, orange is what the market asks for.")
    with col2:
        with st.container(border=True):
            st.subheader("🗓️ Milestone Timeline")
            st.plotly_chart(build_timeline(timeline_rows), width="stretch")
            st.caption("Planned pacing across milestones, anchored to today's date at your "
                       "stated weekly pace." if plan else
                       "Planned pacing across milestones, from foundations to production.")
