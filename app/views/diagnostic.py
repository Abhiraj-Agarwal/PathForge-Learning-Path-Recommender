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
    st.subheader("🎯 Skill Diagnostic")

    col_a, col_b = st.columns([3, 1])
    with col_a:
        if not quiz["active"]:
            st.caption("An adaptive 8-question spot check. Each answer updates a "
                       "per-skill mastery probability (Bayesian Knowledge Tracing).")
        else:
            done = quiz["answered"] >= quiz["total"] or not get_next_question(
                quiz["mastery"], mock.MOCK_QUESTION_BANK, set(quiz["asked"]))
            if done:
                _render_summary(quiz)
            else:
                _render_question_form(quiz)
    with col_b:
        start_label = "Reset & restart" if quiz["active"] else "Start diagnostic"
        if st.button(start_label, width="stretch"):
            st.session_state.quiz = {"active": True, "mastery": {},
                                     "asked": [], "answered": 0,
                                     "total": len(mock.MOCK_QUESTION_BANK)}
            st.rerun()


def _render_question_form(quiz: dict):
    from core.diagnostic import PRIOR
    pool = mock.MOCK_QUESTION_BANK
    question = get_next_question(quiz["mastery"], pool, set(quiz["asked"]))
    if question is None:
        _render_summary(quiz)
        return

    skill = question["skill_id"]
    prior = quiz["mastery"].get(skill, PRIOR)

    st.progress(quiz["answered"] / quiz["total"], text=f"Question {quiz['answered'] + 1} of {quiz['total']}")
    with st.chat_message("assistant"):
        st.markdown(f"**{question['text']}**  \nSkill: `{skill}` · current estimate {prior:.2f}")

    with st.form(f"quiz_form_{question['id']}", clear_on_submit=True):
        answer = st.radio("Choose an answer:", question["options"], index=None,
                          label_visibility="collapsed")
        submitted = st.form_submit_button("Submit answer")
        if submitted:
            if answer is None:
                st.warning("Select an answer first.")
            else:
                is_correct = answer == question["options"][question["correct_index"]]
                quiz["mastery"][skill] = update_skill_mastery(quiz["mastery"], skill, is_correct)
                quiz["asked"].append(question["id"])
                quiz["answered"] += 1
                submit_diagnostic_answer(question["id"], skill, is_correct)
                if is_correct:
                    st.success(f"Correct. `{skill}` mastery {prior:.2f} → {quiz['mastery'][skill]:.2f}")
                else:
                    st.error(f"Not quite. `{skill}` mastery {prior:.2f} → {quiz['mastery'][skill]:.2f}")


def _render_summary(quiz: dict):
    st.success(f"Diagnostic complete — {quiz['answered']} questions answered.")
    if quiz["mastery"]:
        st.session_state.skill_mastery.update(quiz["mastery"])  # radar now reflects the quiz
        rows = sorted(quiz["mastery"].items(), key=lambda kv: -kv[1])
        for skill_id, p in rows:
            name = skill_id.replace("_", " ").title()
            flag = "mastered" if is_mastered(p) else "work on"
            st.markdown(f"`{name}` — **{p:.0%}** ({flag})")
        mastered = sum(1 for p in quiz["mastery"].values() if is_mastered(p))
        st.info(f"{mastered} of {len(quiz['mastery'])} measured skills at/beyond the "
                "0.75 mastery bar. Head to the **Roadmap** tab for what to do next.")
    else:
        st.caption("No answers recorded.")