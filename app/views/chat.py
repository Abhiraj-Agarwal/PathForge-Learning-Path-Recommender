"""Chat view: persistent conversation + the embedded diagnostic quiz."""
import time

import streamlit as st

import mock
from agents.explainer import explain
from agents.router import run as route_message
from core.diagnostic import is_mastered
from views.diagnostic import render_diagnostic_quiz


def _mastery_summary() -> str:
    mastery = st.session_state.get("skill_mastery", {})
    if not mastery:
        return "I don't have a mastery profile for you yet — take the diagnostic below to get one."
    avg = sum(mastery.values()) / len(mastery)
    mastered = sum(1 for p in mastery.values() if is_mastered(p))
    return (f"Across the skills we've measured, your average mastery is **{avg:.0%}** "
            f"with **{mastered}** at or beyond the 0.75 mastered bar.")


def _reply_for(intent: str, prompt: str) -> str:
    if intent == "goal":
        return ("Got it — I'll search recent job postings for that role and extract the "
                "skills the market actually asks for. Meanwhile, the **Roadmap** tab shows "
                "a suggested path, and the diagnostic below can confirm what you already know.")
    if intent == "diagnostic":
        return ("Happy to. Use the adaptive quiz below — each answer updates a per-skill "
                "mastery probability, and the next question is picked where I'm least sure.")
    if intent == "explain":
        explanation = explain(mock.MOCK_EVIDENCE)
        return (f"“{prompt}” — good question. {explanation} Want me to walk a specific "
                "branch, or explain why we didn't start with something else?")
    if intent == "progress":
        return f"Here's where you stand. {_mastery_summary()}"
    return _reply_for("explain", prompt)


def render_chat():
    messages = st.session_state.setdefault("messages", [])
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("e.g. I know some Python and want to get into Machine Learning..."):
        messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.status("Routing your request...", expanded=True) as status:
                st.write("Classifying intent...")
                time.sleep(0.4)
                result = route_message(prompt)
                intent = result.get("intent", "explain")
                st.write(f"Intent: **{intent}**")
                if intent != "explain":
                    status.update(label=f"Routed to {intent}.", state="running")
                if intent == "goal":
                    status.update(label="Scanning market demand for that role...", state="running")
                    st.write("Scanning job descriptions...")
                    time.sleep(0.5)
                status.update(label="Done.", state="complete", expanded=False)

            reply = _reply_for(intent, prompt)
            if result.get("fallback"):
                reply = (f"Let me explain where that leaves us. {explain(mock.MOCK_EVIDENCE)} "
                         "If you meant something else, just rephrase.")
            st.markdown(reply)
        messages.append({"role": "assistant", "content": reply})

    render_diagnostic_quiz()