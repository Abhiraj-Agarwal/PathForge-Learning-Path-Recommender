"""Diagnostic view: a form-based adaptive quiz driven by core/diagnostic.py.

Served inside the Chat tab. Each answer updates the per-skill Bayesian mastery
estimate, and the next item is chosen adaptively (skill closest to 0.5).
"""
import streamlit as st

import mock
from core.diagnostic import get_next_question, is_mastered, update_skill_mastery

try:
    from api_client import get_next_diagnostic_question, submit_diagnostic_answer
except Exception:
    def get_next_diagnostic_question(_m, _a):
        return None

    def submit_diagnostic_answer(*_args):
        return True


def _quiz() -> dict:
    return st.session_state.setdefault("quiz", {
        "active": False,
        "mastery": {},
        "asked": [],
        "answered": 0,
        "total": len(mock.MOCK_QUESTION_BANK),
    })


def render_diagnostic_quiz():
    """Render the adaptive quiz inside the Chat tab."""
    quiz = _quiz()
    st.markdown("---")

    with st.container(border=True):
        col_a, col_b = st.columns([3, 1], vertical_alignment="center")
        with col_a:
            st.subheader("🎯 Skill Diagnostic")
            if not quiz["active"]:
                st.caption("An adaptive 8-question spot check. Each answer updates a "
                           "per-skill mastery probability (Bayesian Knowledge Tracing).")
        with col_b:
            start_label = "🔁 Reset & restart" if quiz["active"] else "▶️ Start diagnostic"
            if st.button(start_label, width="stretch"):
                st.session_state.quiz = {"active": True, "mastery": {},
                                         "asked": [], "answered": 0,
                                         "total": len(mock.MOCK_QUESTION_BANK)}
                st.rerun()

        if quiz["active"]:
            done = quiz["answered"] >= quiz["total"] or not get_next_question(
                quiz["mastery"], mock.MOCK_QUESTION_BANK, set(quiz["asked"]))
            if done:
                _render_summary(quiz)
            else:
                _render_question_form(quiz)


def _render_question_form(quiz: dict):
    from core.diagnostic import PRIOR
    pool = mock.MOCK_QUESTION_BANK
    question = get_next_question(quiz["mastery"], pool, set(quiz["asked"]))
    if question is None:
        _render_summary(quiz)
        return

    skill = question["skill_id"]
    prior = quiz["mastery"].get(skill, PRIOR)
    skill_label = skill.replace("_", " ").title()

    st.progress(quiz["answered"] / quiz["total"], text=f"Question {quiz['answered'] + 1} of {quiz['total']}")
    with st.chat_message("assistant", avatar="🗺️"):
        st.markdown(f"**{question['text']}**")
        st.badge(f"{skill_label} · current estimate {prior:.0%}", icon="🧩", color="violet")

    with st.form(f"quiz_form_{question['id']}", clear_on_submit=True):
        answer = st.radio("Choose an answer:", question["options"], index=None,
                          label_visibility="collapsed")
        submitted = st.form_submit_button("Submit answer", width="stretch")
        if submitted:
            if answer is None:
                st.warning("Select an answer first.")
            else:
                is_correct = answer == question["options"][question["correct_index"]]
                quiz["mastery"][skill] = update_skill_mastery(quiz["mastery"], skill, is_correct)
                quiz["asked"].append(question["id"])
                quiz["answered"] += 1
                submit_diagnostic_answer(question["id"], skill, is_correct)
                new_val = quiz["mastery"][skill]
                if is_correct:
                    st.success(f"✅ Correct — **{skill_label}** mastery {prior:.0%} → {new_val:.0%}")
                else:
                    st.error(f"❌ Not quite — **{skill_label}** mastery {prior:.0%} → {new_val:.0%}")


def _render_summary(quiz: dict):
    if not quiz.get("_celebrated"):
        st.balloons()
        quiz["_celebrated"] = True
    st.success(f"🎉 Diagnostic complete — {quiz['answered']} questions answered.")
    if quiz["mastery"]:
        st.session_state.skill_mastery.update(quiz["mastery"])  # radar now reflects the quiz
        rows = sorted(quiz["mastery"].items(), key=lambda kv: -kv[1])
        for skill_id, p in rows:
            name = skill_id.replace("_", " ").title()
            col_name, col_bar, col_flag = st.columns([2, 3, 1.3], vertical_alignment="center")
            col_name.markdown(f"**{name}**")
            col_bar.progress(p)
            if is_mastered(p):
                col_flag.badge("mastered", icon="✅", color="green")
            else:
                col_flag.badge("keep working", icon="🔧", color="orange")
        mastered = sum(1 for p in quiz["mastery"].values() if is_mastered(p))
        st.info(f"📈 {mastered} of {len(quiz['mastery'])} measured skills at/beyond the "
                "75% mastery bar. Head to the **Roadmap** tab for what to do next.")
    else:
        st.caption("No answers recorded.")