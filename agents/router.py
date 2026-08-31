"""LangGraph conversation router.

One chat box, four behaviours. The router decides -- with a keyword classifier
locally, or an injected LLM -- whether the learner is:

    goal        setting/updating their target
    diagnostic  asking to be quizzed or assessed
    progress    reporting or asking about progress
    explain     asking why / why not / what's next          (default)

Rule: *the LLM routes; it does not compute.* All maths lives in pure-Python
functions called by later nodes. And the hard rule for a live demo: a failed
classification must produce the friendly ``explain`` fallback, never a traceback.
"""

from __future__ import annotations

from typing import Callable, Optional, TypedDict

INTENTS = ("goal", "diagnostic", "explain", "progress")

_DIAGNOSTIC_HINTS = ("quiz", "diagnostic", "assess", "assessment", "test me",
                     "test my", "take a quiz", "what do i know", "baseline")
_EXPLAIN_HINTS = ("why", "explain", "how come", "reason", "because", "is that right")
_GOAL_HINTS = ("want", "aim", "goal", "become", "role", "career", "target",
               "job", "plan to", "get into", "interested in", "switch to")
_PROGRESS_HINTS = ("progress", "status", "how far", "on track", "milestone",
                   "done", "finished", "completed", "am i")


def _hits(text: str, hints) -> bool:
    return any(hint in text for hint in hints)


def classify(text: str) -> str:
    """Deterministic keyword classifier (offline default classifier)."""
    lowered = f" {text.lower()} "
    # Longest, most specific intent first.
    if _hits(lowered, _DIAGNOSTIC_HINTS):
        return "diagnostic"
    if _hits(lowered, _EXPLAIN_HINTS):
        return "explain"
    if _hits(lowered, _GOAL_HINTS):
        return "goal"
    if _hits(lowered, _PROGRESS_HINTS):
        return "progress"
    return "explain"


def _validate(label) -> str:
    if label in INTENTS:
        return label
    if label == "profile":  # A-side synonym for the same conversation move
        return "goal"
    return "explain"


if __name__ != "__main__":
    # Build the LangGraph only when it is importable; otherwise the router
    # still works as a plain function (see ``run`` below).
    try:
        from langgraph.graph import END, StateGraph

        class RouterState(TypedDict, total=False):
            input: str
            intent: str
            reply: str
            fallback: bool

        def _make_classify_node(llm: Optional[Callable]):
            def classify_node(state: RouterState) -> RouterState:
                text = state.get("input", "")
                intent, fallback = "explain", True
                try:
                    label = llm(text) if llm else classify(text)
                    intent = _validate(label)
                    fallback = bool(llm) and label not in INTENTS
                except Exception:
                    intent = "explain"
                return {"intent": intent, "fallback": fallback}

            return classify_node

        def _respond_node(state: RouterState) -> RouterState:
            intent = state.get("intent", "explain")
            replies = {
                "goal": ("Got it -- I'll treat that as your target and look at what the "
                         "market asks for in that role."),
                "diagnostic": ("Let's measure where you are. Use the diagnostic quiz below; "
                               "each answer moves a per-skill mastery estimate."),
                "explain": ("Good question. Let me walk through the evidence behind the "
                            "suggested order."),
                "progress": ("Here's where you stand against the plan."),
            }
            return {"reply": replies.get(intent, replies["explain"])}

        def build_graph(llm: Optional[Callable] = None):
            graph = StateGraph(RouterState)
            graph.add_node("classify", _make_classify_node(llm))
            graph.add_node("respond", _respond_node)
            graph.add_edge("classify", "respond")
            graph.add_edge("respond", END)
            graph.set_entry_point("classify")
            return graph

    except ImportError:  # pragma: no cover - langgraph not installed
        def build_graph(llm: Optional[Callable] = None):  # type: ignore[misc]
            class _SimpleGraph:
                def invoke(self, state: dict, config=None) -> dict:
                    return router_lite(state.get("input", ""), llm)

            return _SimpleGraph()


def router_lite(text: str, llm: Optional[Callable] = None) -> dict:
    """Single-shot classification without walking the graph (used as fallback)."""
    intent, fallback = "explain", False
    try:
        intent = _validate(llm(text)) if llm else classify(text)
        fallback = bool(llm) and intent not in INTENTS
    except Exception:
        intent, fallback = "explain", True
    return {"input": text, "intent": intent, "fallback": fallback,
            "reply": f"routed to: {intent}"}


def run(text: str, llm: Optional[Callable] = None) -> dict:
    """Classify ``text`` and produce a routing response. Never raises."""
    try:
        graph = build_graph(llm).compile()
        result = graph.invoke({"input": text})
        if not result.get("intent"):
            result = router_lite(text, llm)
        return result
    except Exception:
        return router_lite(text, llm)