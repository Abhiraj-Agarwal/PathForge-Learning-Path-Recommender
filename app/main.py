"""PathForge -- Streamlit entry point.

Session bootstrap + three tabs. Every view consumes fixtures from ``mock``
until Person A's FastAPI backend is wired through ``api_client``.
"""
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))          # for: mock, views, components, api_client
sys.path.insert(0, str(APP_DIR.parent))   # for: core, agents, schemas

import streamlit as st  # noqa: E402

import mock  # noqa: E402


# --------------------------------------------------------------------------
# page + session bootstrap
# --------------------------------------------------------------------------

st.set_page_config(page_title="PathForge", page_icon="🗺️", layout="wide")
st.title("PathForge — your learning path, forged by evidence")


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


def _load_demo_learner():
    st.session_state.messages = [
        {"role": "assistant",
         "content": "Demo learner loaded — an ML engineer aspirant with solid Python and "
                    "some data analysis. Check the **Roadmap** and **Dashboard** tabs."}
    ]
    st.session_state.skill_mastery = dict(mock.MOCK_MASTERY_BY_SKILL)
    st.session_state.quiz = {"active": False, "mastery": {}, "asked": [], "answered": 0,
                             "total": len(mock.MOCK_QUESTION_BANK)}
    st.session_state.demo_loaded = True


_bootstrap()

# --------------------------------------------------------------------------
# sidebar
# --------------------------------------------------------------------------

with st.sidebar:
    st.subheader("🧪 Demo controls")
    if st.button("Load demo learner", key="load_demo", width="stretch"):
        _load_demo_learner()
        st.rerun()
    if st.session_state.demo_loaded:
        st.caption("Demo learner active")

    st.divider()
    env = __import__("os").environ.get("API_BASE_URL", "")
    st.caption("Backend: " + (env if env else "mock fixtures (offline)"))
    st.caption("Feedback logged so far: "
               f"{len(st.session_state.get('feedback', []))} 👍👎")

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