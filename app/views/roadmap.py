"""Roadmap view: the money shot -- milestone DAG + next actions + counterfactuals."""
import streamlit as st

import mock
from agents.explainer import explain_why_not
from components.graph_view import build_roadmap_graph
from components.resource_card import render_resource_cards
from core.diagnostic import PRIOR

STATUS_LEGEND = {
    "mastered": "green",
    "in_progress": "amber",
    "upcoming": "grey",
}


def _resolve_skill_id(query: str):
    query = query.strip().lower()
    for skill in mock.load_skills():
        if query == skill["id"] or query == skill["name"].lower():
            return skill["id"]
        for alias in skill.get("aliases", []):
            if query == alias.lower():
                return skill["id"]
    return None


def render_roadmap():
    st.header("Your Learning Sequence")
    st.caption(f"Goal: **{mock.MOCK_PATH['role']}** — left-to-right, milestones as clusters.")

    legend = "  ".join(f"{name.lower()} = {color}" for name, color in STATUS_LEGEND.items())
    st.caption(f"Legend: {legend}")

    graph = build_roadmap_graph(mock.MOCK_PATH)
    st.graphviz_chart(graph, width="stretch")

    # --- counterfactual explainer -----------------------------------------
    with st.container(border=True):
        st.subheader("Ask “why not start with X?”")
        c1, c2 = st.columns([3, 1])
        with c1:
            query = st.text_input("Skill name", placeholder="e.g. transformers, Kubernetes...",
                                  label_visibility="collapsed")
        with c2:
            asked = st.button("Ask why not", width="stretch")

        if asked and query:
            skill_id = _resolve_skill_id(query)
            mastery = st.session_state.get("skill_mastery", {}) or {}
            if skill_id is None:
                st.warning(f"I don't have “{query}” in the skill graph.")
            else:
                why = explain_why_not(skill_id, mock.load_skills(),
                                      {**{s: PRIOR for s in mastery}, **mastery})
                with st.chat_message("assistant"):
                    st.markdown(why)

    # --- next action resource cards ---------------------------------------
    st.markdown("---")
    st.subheader(f"Next: {mock.MOCK_NEXT_ACTION['skill']}")
    st.caption("Resource cards — tap 👍 if it looks useful, 👎 if not. Your "
               "feedback tunes future recommendations.")
    render_resource_cards(mock.MOCK_NEXT_ACTION["resources"], context="next")