"""Tests for the orchestration agents: router (LangGraph) and explainer."""

import pytest

from agents.explainer import (
    ancestor_closure,
    build_evidence_bundle,
    explain,
    explain_why_not,
)
from agents.router import classify, run


# --------------------------------------------------------------------------
# router / classification
# --------------------------------------------------------------------------

class TestClassifier:
    @pytest.mark.parametrize("text,intent", [
        ("I want to become an ML engineer", "goal"),
        ("aiming for a data analyst role", "goal"),
        ("give me a quiz please", "diagnostic"),
        ("run the diagnostic", "diagnostic"),
        ("why not start with transformers?", "explain"),
        ("explain why docker comes later", "explain"),
        ("how is my progress this week", "progress"),
        ("I finished milestone 2", "progress"),
        ("??💬 totally ambiguous", "explain"),  # default fallback
    ])
    def test_classify(self, text, intent):
        assert classify(text) == intent


class TestRouterRun:
    def test_run_traverses_langgraph(self):
        result = run("I want to become an ML engineer")
        assert result["intent"] == "goal"
        assert "reply" in result
        assert not result.get("fallback")

    def test_llm_route_is_used_when_available(self):
        result = run("something", llm=lambda text: "progress")
        assert result["intent"] == "progress"
        assert not result.get("fallback")

    def test_llm_failure_falls_back_to_explain(self):
        def broken(_text):
            raise RuntimeError("provider down")

        result = run("something", llm=broken)
        assert result["intent"] == "explain"
        assert result.get("fallback") is True

    def test_llm_garbage_label_does_not_crash(self):
        result = run("something", llm=lambda text: "horses")
        assert result["intent"] in ("goal", "diagnostic", "explain", "progress")


# --------------------------------------------------------------------------
# explainer
# --------------------------------------------------------------------------

DOCKER_EVIDENCE = build_evidence_bundle(
    skill="Docker & Containers",
    demand_pct=68,
    position=3,
    unlocks=["MLOps", "Model Deployment"],
    current_mastery=0.15,
    prereqs_satisfied=["Command Line", "Git"],
    evidence_count=34,
)

SKILL_GRAPH = [
    {"id": "python_basics", "name": "Python Fundamentals", "prerequisites": []},
    {"id": "linear_algebra", "name": "Linear Algebra", "prerequisites": []},
    {"id": "ml_fundamentals", "name": "ML Fundamentals",
     "prerequisites": ["python_basics", "linear_algebra"]},
    {"id": "deep_learning", "name": "Deep Learning", "prerequisites": ["ml_fundamentals"]},
    {"id": "neural_networks", "name": "Neural Networks", "prerequisites": ["deep_learning"]},
]


class TestExplain:
    def test_two_sentences_with_citable_facts(self):
        text = explain(DOCKER_EVIDENCE)
        assert isinstance(text, str)
        sentences = [s for s in text.split(". ") if s.strip()]
        assert len(sentences) >= 2
        assert "Docker" in text and "68%" in text and "MLOps" in text

    def test_no_fabricated_facts_for_empty_bundle(self):
        text = explain({})
        assert "None" not in text
        assert "0%" not in text

    def test_llm_output_used_when_provided(self):
        text = explain(DOCKER_EVIDENCE, llm=lambda facts: "Trust me.")
        assert text == "Trust me."

    def test_llm_failure_falls_back_to_template(self):
        def broken(_facts):
            raise RuntimeError("nope")

        text = explain(DOCKER_EVIDENCE, llm=broken)
        assert "Docker" in text

    def test_missing_prereqs_are_acknowledged(self):
        bundle = dict(DOCKER_EVIDENCE)
        bundle["prereqs_missing"] = ["Kubernetes"]
        bundle["prereqs_satisfied"] = []
        text = explain(bundle)
        assert "Kubernetes" in text and "wait" in text


class TestWhyNot:
    def test_directly_blocked_skill_names_its_prereqs(self):
        text = explain_why_not("neural_networks", SKILL_GRAPH, {"python_basics": 0.9})
        assert "Neural Networks" in text
        assert "Deep Learning" in text
        assert "ML Fundamentals" in text

    def test_skill_without_prereqs_is_clear(self):
        text = explain_why_not("python_basics", SKILL_GRAPH, {})
        assert "no prerequisites" in text

    def test_fully_unblocked_target_is_positive(self):
        text = explain_why_not("ml_fundamentals", SKILL_GRAPH,
                               {"python_basics": 0.8, "linear_algebra": 0.8})
        assert "already in place" in text

    def test_unknown_skill(self):
        text = explain_why_not("cobol", SKILL_GRAPH, {})
        assert "don't have" in text


class TestAncestorClosure:
    def test_transitive_closure(self):
        closure = ancestor_closure("neural_networks", SKILL_GRAPH)
        assert {"deep_learning", "ml_fundamentals", "python_basics",
                "linear_algebra"} <= closure
        assert "neural_networks" not in closure  # only prerequisites, not itself

    def test_empty_for_root_skill(self):
        assert ancestor_closure("python_basics", SKILL_GRAPH) == set()

    def test_ignores_unknown_nodes(self):
        assert ancestor_closure("ghost", SKILL_GRAPH) == set()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])