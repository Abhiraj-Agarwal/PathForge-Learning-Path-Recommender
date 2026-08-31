"""Roadmap view: an interactive knowledge graph of the (real or preview) plan.

When the chat has produced a plan (st.session_state.current_plan, built by
engine.build_plan_from_goal), this renders THAT exact graph: every skill in
its ancestor closure, colored by current mastery, positioned by prerequisite
depth. Before any goal has been set it falls back to a labeled demo preview
so the tab isn't empty on first load.

Clicking a node re-renders the graph zoomed around it and opens a detail
panel: the graph-grounded reasoning for its placement, its market demand
(when a real plan is active) and its ranked course links -- computed on
demand via engine.get_courses_for_skill, so this works even before a full
plan exists.
"""
import streamlit as st

import engine
import mock
from agents.explainer import explain_why_not
from components.knowledge_graph import build_knowledge_graph
from components.resource_card import render_resource_cards
from core.diagnostic import PRIOR

STATUS_LEGEND = {
    "mastered": ("✅", "green"),
    "in progress": ("🛠️", "orange"),
    "upcoming": ("⏳", "gray"),
}


def _status_for(skill_id: str, mastery: dict) -> str:
    p = mastery.get(skill_id, 0.0)
    if p > 0.75:
        return "mastered"
    if p > 0:
        return "in_progress"
    return "upcoming"


def _graph_data_from_plan(plan: dict, mastery: dict):
    graph = plan["graph"]
    ids = plan["path"].ancestor_closure
    id_set = set(ids)
    nodes = [{"id": sid, "name": graph.get(sid).name, "status": _status_for(sid, mastery)} for sid in ids]
    edges = [
        (prereq, sid)
        for sid in ids
        for prereq in graph.prerequisites_of(sid)
        if prereq in id_set
    ]
    return nodes, edges


def _graph_data_from_mock():
    nodes = [
        {"id": step["skill_id"], "name": step["name"], "status": step["status"]}
        for steps in mock.MOCK_PATH["milestones"].values()
        for step in steps
    ]
    return nodes, list(mock.MOCK_PATH["edges"])


def _resolve_skill_id(query: str):
    query = query.strip().lower()
    for skill in mock.load_skills():
        if query == skill["id"] or query == skill["name"].lower():
            return skill["id"]
        for alias in skill.get("aliases", []):
            if query == alias.lower():
                return skill["id"]
    return None


def _extract_clicked_skill(event) -> str | None:
    if not event:
        return None
    points = event.get("selection", {}).get("points", []) if isinstance(event, dict) else []
    if not points:
        return None
    customdata = points[0].get("customdata")
    if isinstance(customdata, (list, tuple)):
        return customdata[0] if customdata else None
    return customdata


def _impact_within(skill_id: str, graph, scope_ids: set[str]) -> int:
    """How many other skills IN THIS GRAPH become reachable once this one is
    done -- a transitive count via graph.unlocks(), not a fabricated score."""
    seen: set[str] = set()
    stack = [skill_id]
    while stack:
        current = stack.pop()
        for nxt in graph.unlocks(current):
            if nxt in scope_ids and nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return len(seen)


def _render_node_detail(skill_id: str, plan: dict | None, mastery: dict, scope_ids: set[str]):
    skills_raw = mock.load_skills()
    by_id = {s["id"]: s for s in skills_raw}
    node = by_id.get(skill_id)
    if node is None:
        st.warning("No graph data for this skill.")
        return

    status = _status_for(skill_id, mastery)
    icon, color = STATUS_LEGEND.get(status.replace("_", " "), ("⏳", "gray"))

    with st.container(border=True):
        top = st.columns([3, 1], vertical_alignment="center")
        top[0].subheader(f"🔎 {node['name']}")
        top[1].badge(status.replace("_", " "), icon=icon, color=color)

        reasoning = explain_why_not(skill_id, skills_raw, mastery)
        st.markdown(reasoning)

        graph = engine.get_graph()
        impact = _impact_within(skill_id, graph, scope_ids)
        score_cols = st.columns(2)
        if plan is not None and plan["demand_by_id"].get(skill_id) is not None:
            demand = plan["demand_by_id"][skill_id]
            evidence = plan["evidence_by_id"].get(skill_id, 0)
            score_cols[0].badge(f"Relevance: {demand:.0%} ({evidence} postings)",
                                icon="📈", color="blue")
        else:
            score_cols[0].badge("Relevance: not a direct goal target", icon="📈", color="gray")
        score_cols[1].badge(
            f"Impact: unlocks {impact} skill{'s' if impact != 1 else ''} in this plan"
            if impact else "Impact: no further skills depend on this yet",
            icon="🔗", color="violet",
        )

        st.markdown("**📚 Course links**")
        courses = engine.get_courses_for_skill(skill_id, mastery.get(skill_id, 0.0))
        if not courses:
            st.caption("No strong course match in the catalog for this skill yet.")
        else:
            resources = [
                {
                    "id": c.id,
                    "title": c.title,
                    "provider": c.provider,
                    "url": str(c.url),
                    "type": "course",
                    "rating": c.rating,
                    "skill_id": skill_id,
                    "justification": f"Ranked for {node['name']} by semantic fit, rating and level match.",
                }
                for c in courses
            ]
            render_resource_cards(resources, context=f"node_{skill_id}")


def render_roadmap():
    plan = st.session_state.get("current_plan")
    mastery = st.session_state.get("skill_mastery", {}) or {}

    st.header("🗺️ Your Learning Sequence")

    if plan:
        st.caption(f"Your plan for: **“{plan['goal_text'].strip()}”** · "
                   f"pace ~{plan['hours_per_week']:.0f} hrs/week")
        nodes, edges = _graph_data_from_plan(plan, mastery)
    else:
        st.info("💡 No goal set yet — this is a **demo preview**. Tell the **Chat** tab your "
                "real learning goal (or load the demo learner in the sidebar) to replace this "
                "with your own computed plan.")
        nodes, edges = _graph_data_from_mock()

    legend_cols = st.columns(len(STATUS_LEGEND) + 2)
    for col, (name, (icon, color)) in zip(legend_cols, STATUS_LEGEND.items()):
        with col:
            st.badge(name, icon=icon, color=color)

    if not nodes:
        st.success("Nothing left in the gap for this goal — you're already there!")
        return

    st.session_state.setdefault("kg_reset_counter", 0)
    chart_key = f"kg_chart_{st.session_state.kg_reset_counter}"
    prior_event = st.session_state.get(chart_key)
    focus_id = _extract_clicked_skill(prior_event)

    # Full-width graph -- the node detail renders below it, not beside it,
    # so the graph itself has all the room it needs to stay legible.
    with st.container(border=True):
        st.caption("💡 Click any node — its details appear just below the graph. "
                   "Scroll to zoom, drag to pan.")
        fig = build_knowledge_graph(nodes, edges, focus_id=focus_id)
        event = st.plotly_chart(
            fig, key=chart_key, on_select="rerun", selection_mode="points",
            config={"scrollZoom": True}, width="stretch",
        )
        if focus_id and st.button("🔭 Show full graph", key="kg_reset_btn"):
            st.session_state.kg_reset_counter += 1
            st.rerun()

    clicked = _extract_clicked_skill(event) or focus_id

    if clicked:
        _render_node_detail(clicked, plan, mastery, {n["id"] for n in nodes})
    else:
        st.info("👆 Click a node above to see why it's placed there, its relevance and "
                "impact scores, and its top course matches.")

    # --- counterfactual explainer -----------------------------------------
    with st.container(border=True):
        st.subheader("🤔 Ask “why not start with X?”")
        st.caption("Curious about the sequencing? Name any skill and see the graph-backed reason.")
        c1, c2 = st.columns([3, 1])
        with c1:
            query = st.text_input("Skill name", placeholder="e.g. transformers, Kubernetes...",
                                  label_visibility="collapsed")
        with c2:
            asked = st.button("Ask why not", width="stretch")

        if asked and query:
            skill_id = _resolve_skill_id(query)
            if skill_id is None:
                st.warning(f"I don't have “{query}” in the skill graph.")
            else:
                why = explain_why_not(skill_id, mock.load_skills(),
                                      {**{s: PRIOR for s in mastery}, **mastery})
                with st.chat_message("assistant", avatar="🗺️"):
                    st.markdown(why)

    # --- next action resource cards ---------------------------------------
    with st.container(border=True):
        if plan and plan["path"].ordering:
            next_id = plan["path"].ordering[0]
            next_name = plan["graph"].get(next_id).name
            st.subheader(f"📚 Next up: {next_name}")
            st.caption("Resource cards — tap 👍 if it looks useful, 👎 if not. Your "
                       "feedback tunes future recommendations.")
            courses = engine.get_courses_for_skill(next_id, mastery.get(next_id, 0.0))
            resources = [
                {
                    "id": c.id, "title": c.title, "provider": c.provider, "url": str(c.url),
                    "type": "course", "rating": c.rating, "skill_id": next_id,
                    "justification": f"Ranked for {next_name} by semantic fit, rating and level match.",
                }
                for c in courses
            ]
            render_resource_cards(resources, context="next")
        else:
            st.subheader(f"📚 Next: {mock.MOCK_NEXT_ACTION['skill']}")
            st.caption("Resource cards — tap 👍 if it looks useful, 👎 if not. Your "
                       "feedback tunes future recommendations.")
            render_resource_cards(mock.MOCK_NEXT_ACTION["resources"], context="next")
