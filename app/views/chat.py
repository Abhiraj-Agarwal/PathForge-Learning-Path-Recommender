"""Chat view: persistent conversation + the embedded diagnostic quiz.

The "goal" intent doesn't just point the learner at the Roadmap tab anymore --
it runs the real core/ pipeline (engine.build_plan_from_goal) right here and
writes a grounded, personalized reply: which skills the market actually
demands, the size of the gap against current mastery, and a day-by-day
schedule at the learner's stated (or assumed) weekly pace. The Roadmap tab
then visualizes the exact same plan, stored in st.session_state.current_plan.
"""
import time

import streamlit as st

import engine
import mock
import schedule as schedule_mod
from agents.explainer import build_evidence_bundle, explain
from agents.router import run as route_message
from core.diagnostic import is_mastered
from views.diagnostic import render_diagnostic_quiz

AVATARS = {"user": "🧑‍🎓", "assistant": "🗺️"}

SUGGESTIONS = [
    "I know some Python, want to get into ML",
    "I want to learn probability & statistics, about 4 hours a week",
    "Quiz me on what I know",
    "How far along am I?",
]

INTENT_BADGES = {
    "goal": ("🎯", "blue"),
    "diagnostic": ("🧭", "violet"),
    "explain": ("💡", "orange"),
    "progress": ("📈", "green"),
}


def _mastery_summary() -> str:
    mastery = st.session_state.get("skill_mastery", {})
    if not mastery:
        return "I don't have a mastery profile for you yet — take the diagnostic below to get one."
    avg = sum(mastery.values()) / len(mastery)
    mastered = sum(1 for p in mastery.values() if is_mastered(p))
    return (f"Across the skills we've measured, your average mastery is **{avg:.0%}** "
            f"with **{mastered}** at or beyond the 0.75 mastered bar.")


def _evidence_bundle_for(skill_id: str, plan: dict) -> dict:
    graph = plan["graph"]
    path = plan["path"]
    node = graph.get(skill_id)
    mastery = st.session_state.get("skill_mastery", {}) or {}

    position = path.ordering.index(skill_id) + 1 if skill_id in path.ordering else None
    unlocks = [graph.get(u).name for u in graph.unlocks(skill_id) if u in path.ancestor_closure]
    prereqs = graph.prerequisites_of(skill_id)
    satisfied = [graph.get(p).name for p in prereqs if mastery.get(p, 0.0) > 0.75]
    missing = [graph.get(p).name for p in prereqs if mastery.get(p, 0.0) <= 0.75]

    return build_evidence_bundle(
        skill=node.name,
        demand_pct=round(plan["demand_by_id"].get(skill_id, 0.0) * 100),
        position=position or 0,
        unlocks=unlocks,
        current_mastery=mastery.get(skill_id),
        prereqs_satisfied=satisfied,
        evidence_count=plan["evidence_by_id"].get(skill_id),
        prereqs_missing=missing,
    )


def _format_targets_line(plan: dict) -> str:
    graph = plan["graph"]
    top = sorted(plan["targets"], key=lambda t: -t.demand)[:6]
    if not top:
        return ("_Couldn't find enough matching postings for that phrasing — try naming a "
                "specific role, e.g. 'become a backend developer'._")
    return "\n".join(
        f"- **{graph.get(t.skill_id).name}** — {t.demand:.0%} of matched postings ask for it"
        for t in top
    )


def _build_goal_reply(prompt: str) -> str:
    mastery = st.session_state.get("skill_mastery", {}) or {}
    explicit_hours = engine.extract_hours_per_week(prompt)
    hours = explicit_hours or st.session_state.get("hours_per_week") or engine.DEFAULT_HOURS_PER_WEEK

    try:
        plan = engine.build_plan_from_goal(prompt, mastery, hours_per_week=hours)
    except Exception:
        return ("I hit a snag analyzing the job market for that goal, so I can't build a fresh "
                f"plan right now. {explain(mock.MOCK_EVIDENCE)}")

    st.session_state.current_plan = plan
    st.session_state.hours_per_week = plan["hours_per_week"]
    st.session_state.roadmap_focus_skill = None

    graph = plan["graph"]
    path = plan["path"]

    if not path.ordering:
        return ("Good news — based on what you've told me, you already cover everything the "
                "market asks for on this goal. Nothing left in the gap! Head to **Roadmap** to "
                "see the full picture.")

    gap_count = len(path.gap_nodes)
    mastered_in_closure = len(path.ancestor_closure) - gap_count
    next_skill = graph.get(path.ordering[0])

    hours_note = (f"you mentioned **{explicit_hours:.0f} hrs/week**" if explicit_hours
                  else f"assuming **~{hours:.0f} hrs/week** — tell me your real number, e.g. "
                       "'I have 5 hours a week', and I'll replan")

    weeks, is_complete = schedule_mod.build_day_schedule(
        path, graph, plan["courses_by_id"], hours, max_weeks=4
    )
    schedule_preview = schedule_mod.format_schedule_markdown(
        weeks, graph, is_complete, len(path.ordering), hours
    )

    st.session_state.quick_replies = [
        ("🧭 Quiz me on what I know", "Quiz me on what I know"),
        ("📈 How am I doing overall?", "How far along am I?"),
        (f"🤔 Why {next_skill.name} first?", f"Why is {next_skill.name} first?"),
    ]

    return "\n".join([
        f"Here's what the market actually asks for on **“{prompt.strip()}”**, ranked by "
        "how often it showed up across matched job postings:",
        "",
        _format_targets_line(plan),
        "",
        f"You've already got **{mastered_in_closure}** of the **{len(path.ancestor_closure)}** "
        f"skills this goal touches. That leaves **{gap_count} skills** to close, starting with "
        f"**{next_skill.name}**.",
        "",
        f"**Your first month** ({hours_note}), with course links:",
        "",
        schedule_preview,
        "Open the **🗺️ Roadmap** tab for the full interactive graph — click any node to see its "
        "relevance score, impact score, why it's placed there, and its course links.",
    ])


def _reply_for(intent: str, prompt: str) -> str:
    plan = st.session_state.get("current_plan")

    if intent == "goal":
        return _build_goal_reply(prompt)
    if intent == "diagnostic":
        return ("Happy to. Use the adaptive quiz below — each answer updates a per-skill "
                "mastery probability, and the next question is picked where I'm least sure.")
    if intent == "explain":
        bundle = _evidence_bundle_for(plan["path"].ordering[0], plan) if plan and plan["path"].ordering else mock.MOCK_EVIDENCE
        explanation = explain(bundle)
        return (f"“{prompt}” — good question. {explanation} Want me to walk a specific "
                "branch, or explain why we didn't start with something else?")
    if intent == "progress":
        reply = f"Here's where you stand. {_mastery_summary()}"
        if plan and plan["path"].ordering:
            next_name = plan["graph"].get(plan["path"].ordering[0]).name
            reply += (f" Your next recommended skill is **{next_name}** — see the **Roadmap** "
                      "tab for the full picture.")
        return reply
    return _reply_for("explain", prompt)


def _handle_prompt(prompt: str, messages: list):
    st.session_state.quick_replies = []
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=AVATARS["user"]):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        with st.status("Routing your request...", expanded=True) as status:
            st.write("Classifying intent...")
            time.sleep(0.3)
            result = route_message(prompt)
            intent = result.get("intent", "explain")
            icon, color = INTENT_BADGES.get(intent, INTENT_BADGES["explain"])
            st.badge(f"Routed to: {intent}", icon=icon, color=color)

            if intent == "goal":
                status.update(label="Scanning job postings for market demand...", state="running")
                st.write("Matching postings, computing your skill gap, ranking courses...")

            reply = _reply_for(intent, prompt)
            if result.get("fallback"):
                reply = (f"Let me explain where that leaves us. {explain(mock.MOCK_EVIDENCE)} "
                         "If you meant something else, just rephrase.")

            status.update(label="Plan ready." if intent == "goal" else "Done.",
                         state="complete", expanded=False)

        st.markdown(reply)
    messages.append({"role": "assistant", "content": reply})


def render_chat():
    messages = st.session_state.setdefault("messages", [])

    if len(messages) <= 1:
        st.caption("👋 New here? Try one of these to get started:")
        cols = st.columns(len(SUGGESTIONS))
        for col, suggestion in zip(cols, SUGGESTIONS):
            with col:
                if st.button(suggestion, key=f"suggest_{suggestion}", width="stretch"):
                    _handle_prompt(suggestion, messages)
                    st.rerun()

    for message in messages:
        with st.chat_message(message["role"], avatar=AVATARS.get(message["role"])):
            st.markdown(message["content"])

    quick_replies = st.session_state.get("quick_replies") or []
    if quick_replies:
        st.caption("💬 Quick replies:")
        cols = st.columns(len(quick_replies))
        for col, (label, reply_text) in zip(cols, quick_replies):
            with col:
                if st.button(label, key=f"qr_{label}", width="stretch"):
                    _handle_prompt(reply_text, messages)
                    st.rerun()

    if prompt := st.chat_input("e.g. I know some Python and want to get into Machine Learning..."):
        _handle_prompt(prompt, messages)

    render_diagnostic_quiz()
