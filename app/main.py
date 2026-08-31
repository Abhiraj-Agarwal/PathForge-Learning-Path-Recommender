"""PathForge -- Streamlit entry point.

Session bootstrap + three tabs. The real planning pipeline runs in-process
via ``engine.py`` (no separate API server yet); ``mock`` supplies fixtures
for the parts of the UI a plan hasn't been generated for yet.
"""
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))          # for: mock, views, components, api_client
sys.path.insert(0, str(APP_DIR.parent))   # for: core, agents, schemas

import streamlit as st  # noqa: E402

import mock  # noqa: E402
from core.diagnostic import is_mastered  # noqa: E402

# --------------------------------------------------------------------------
# page + session bootstrap
# --------------------------------------------------------------------------

st.set_page_config(page_title="PathForge", page_icon="🗺️", layout="wide")

st.markdown("""
<style>
/* tighten the default top padding so the hero sits closer to the header */
.block-container { padding-top: 2rem; }

.pf-hero {
    background: linear-gradient(120deg, #4F46E5 0%, #6D5EF0 55%, #FF7A59 130%);
    border-radius: 20px;
    padding: 2rem 2.2rem;
    margin-bottom: 1.4rem;
    box-shadow: 0 8px 24px rgba(79,70,229,0.22);
}
.pf-hero h1 { margin: 0 0 .35rem 0; font-size: 2rem; line-height: 1.2; color: #FFFFFF; }
.pf-hero p { margin: 0; opacity: .92; font-size: 1.03rem; color: #F5F3FF; max-width: 46rem; }

/* --- modern chat bubbles: soft indigo for the assistant, clean white for you --- */
div[data-testid="stChatMessage"] {
    border-radius: 18px;
    padding: 0.85rem 1.05rem;
    margin-bottom: 0.55rem;
    box-shadow: 0 1px 4px rgba(30,27,46,0.07);
}
div[data-testid="stChatMessage"]:nth-of-type(odd) {
    background: linear-gradient(135deg, rgba(79,70,229,0.10), rgba(79,70,229,0.03));
    border: 1px solid rgba(79,70,229,0.14);
}
div[data-testid="stChatMessage"]:nth-of-type(even) {
    background: #FFFFFF;
    border: 1px solid rgba(30,27,46,0.08);
}
[data-testid="stChatMessageAvatarCustom"] {
    background: linear-gradient(135deg, #4F46E5, #8B7CF6) !important;
    border-radius: 50%;
}
div[data-testid="stChatMessage"]:nth-of-type(even) [data-testid="stChatMessageAvatarCustom"] {
    background: linear-gradient(135deg, #FF7A59, #FFA26B) !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    """
    <div class="pf-hero">
        <h1>🗺️ PathForge</h1>
        <p>Your learning path, forged by evidence — not a guess. Tell the chat your
        goal, take the adaptive diagnostic, and let the skill graph do the sequencing.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


def _bootstrap():
    st.session_state.setdefault("messages", [
        {"role": "assistant",
         "content": "Hi! I'm PathForge. What role are you aiming for, and what's your "
                    "current experience? e.g. *'I know some Python, want to get into ML.'*"}
    ])
    st.session_state.setdefault("skill_mastery", dict(mock.MOCK_MASTERY_BY_SKILL))
    st.session_state.setdefault("quiz", {
        "active": False, "mastery": {}, "asked": [], "answered": 0,
        "total": len(mock.MOCK_QUESTION_BANK),
    })
    st.session_state.setdefault("feedback", [])
    st.session_state.setdefault("demo_loaded", False)


DEMO_GOAL_TEXT = ("I'm a CS grad, comfortable with Python and some data analysis. I want to "
                  "become a Machine Learning Engineer, and I can put in about 8 hours a week.")


def _load_demo_learner():
    """Runs the exact same real pipeline as a typed chat message, with a
    preset persona -- so a first-time visitor can see a finished plan without
    typing anything. Not a separate mock universe: same engine, same code path."""
    st.session_state.skill_mastery = dict(mock.MOCK_MASTERY_BY_SKILL)
    st.session_state.quiz = {"active": False, "mastery": {}, "asked": [], "answered": 0,
                             "total": len(mock.MOCK_QUESTION_BANK)}

    from views.chat import _build_goal_reply
    with st.spinner("Running the planning pipeline for the demo persona..."):
        reply = _build_goal_reply(DEMO_GOAL_TEXT)

    st.session_state.messages = [
        {"role": "assistant", "content": "👋 Demo learner loaded — here's what a finished "
                                          "conversation looks like:"},
        {"role": "user", "content": DEMO_GOAL_TEXT},
        {"role": "assistant", "content": reply},
    ]
    st.session_state.demo_loaded = True


_bootstrap()

# --------------------------------------------------------------------------
# sidebar
# --------------------------------------------------------------------------

RESET_KEYS = ("messages", "skill_mastery", "quiz", "feedback", "demo_loaded", "current_plan",
             "hours_per_week", "roadmap_focus_skill", "kg_reset_counter", "quick_replies")

with st.sidebar:
    st.markdown(
        "<div style='display:flex; align-items:center; gap:.6rem; padding:.2rem 0 1rem 0;'>"
        "<div style='font-size:1.9rem; line-height:1;'>🗺️</div>"
        "<div>"
        "<div style='font-weight:700; font-size:1.05rem; line-height:1.1;'>PathForge</div>"
        "<div style='font-size:.75rem; opacity:.6;'>Your learning copilot</div>"
        "</div></div>",
        unsafe_allow_html=True,
    )

    plan = st.session_state.get("current_plan")
    mastery = st.session_state.get("skill_mastery", {}) or {}
    avg_mastery = sum(mastery.values()) / len(mastery) if mastery else 0.0
    mastered_count = sum(1 for p in mastery.values() if is_mastered(p))

    head = st.columns([5, 1], vertical_alignment="center")
    head[0].markdown("**📊 Your progress**")
    with head[1]:
        with st.popover("ℹ️", width="content"):
            st.caption("A live readout of the skills you've measured so far — via the "
                       "diagnostic quiz or a stated goal. Updates instantly as either changes.")
    st.progress(avg_mastery, text=f"{avg_mastery:.0%} average mastery")
    st.caption(f"✅ {mastered_count}/{len(mastery)} skills at the mastery bar")
    if plan:
        goal_preview = plan["goal_text"][:48] + ("…" if len(plan["goal_text"]) > 48 else "")
        st.caption(f"🎯 *{goal_preview}*")
    else:
        st.caption("No goal set yet — head to **Chat** to start one.")

    st.divider()

    head2 = st.columns([5, 1], vertical_alignment="center")
    head2[0].markdown("**🧪 Try it out**")
    with head2[1]:
        with st.popover("ℹ️", width="content"):
            st.caption("Load a ready-made example learner to see a full plan instantly — it "
                       "runs the exact same engine as typing your own goal, just with preset "
                       "answers. Reset wipes everything and starts clean.")
    col_demo, col_reset = st.columns(2)
    with col_demo:
        if st.button("🚀 Demo", key="load_demo", width="stretch",
                    help="Runs the real planning pipeline with a preset persona so you can see "
                         "a finished plan immediately, without typing your own goal first."):
            _load_demo_learner()
            st.rerun()
    with col_reset:
        if st.button("🔄 Reset", key="reset_session", width="stretch",
                    help="Clears your chat history, mastery data, quick replies and current "
                         "plan — starts completely fresh."):
            for k in RESET_KEYS:
                st.session_state.pop(k, None)
            st.rerun()
    if st.session_state.demo_loaded:
        st.badge("Demo learner active", icon="🧪", color="blue")

    st.divider()

    st.markdown("**🔌 Connection**")
    env = __import__("os").environ.get("API_BASE_URL", "")
    if env:
        st.badge(f"Backend: {env}", icon="🟢", color="green")
    else:
        st.badge("Running the engine locally", icon="🟡", color="orange")
    n_feedback = len(st.session_state.get("feedback", []))
    st.caption(f"💬 Feedback logged this session: **{n_feedback}**")

# --------------------------------------------------------------------------
# main tabs
# --------------------------------------------------------------------------

from views.chat import render_chat  # noqa: E402
from views.dashboard import render_dashboard  # noqa: E402
from views.roadmap import render_roadmap  # noqa: E402

tab_chat, tab_roadmap, tab_dash = st.tabs(["💬 Chat", "🗺️ Roadmap", "📊 Dashboard"])

with tab_chat:
    render_chat()

with tab_roadmap:
    render_roadmap()

with tab_dash:
    render_dashboard()