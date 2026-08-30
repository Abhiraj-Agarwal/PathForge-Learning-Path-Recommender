from pathlib import Path

import pytest

from core.goal_translator import translate_goal
from core.graph import SkillGraph
from core.retrieval import VectorIndex

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mini_graph.json"

JD_TEXTS = {
    "jd1": "We need someone who knows Docker and SQL for this DevOps role.",
    "jd2": "Docker experience required. Also familiar with CI/CD pipelines.",
    "jd3": "Looking for a data analyst skilled in SQL and Statistics.",
    "jd4": "Machine learning engineer needed - supervised learning, statistics, linear algebra.",
}


class _UniformEmbedder:
    """Every text gets the same vector, so all JDs retrieve with equal
    similarity - isolates translate_goal's own logic from FAISS ranking,
    which is already covered by test_retrieval.py."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]


@pytest.fixture
def graph() -> SkillGraph:
    return SkillGraph.from_file(FIXTURE)


@pytest.fixture
def jd_index() -> VectorIndex:
    return VectorIndex.build(list(JD_TEXTS.keys()), list(JD_TEXTS.values()), _UniformEmbedder())


def test_demand_and_evidence_count_match_real_mentions(graph, jd_index):
    result = translate_goal("I want an AI/ML role", graph, jd_index, JD_TEXTS, _UniformEmbedder())
    by_id = {t.skill_id: t for t in result.targets}

    assert by_id["docker"].evidence_count == 2
    assert by_id["docker"].demand == pytest.approx(0.5)
    assert by_id["sql"].evidence_count == 2
    assert by_id["ci-cd"].evidence_count == 1
    assert by_id["ci-cd"].demand == pytest.approx(0.25)
    assert by_id["statistics"].evidence_count == 2
    assert by_id["supervised-learning"].evidence_count == 1
    assert by_id["linear-algebra"].evidence_count == 1


def test_unmentioned_skills_are_dropped_below_threshold(graph, jd_index):
    result = translate_goal("I want an AI/ML role", graph, jd_index, JD_TEXTS, _UniformEmbedder())
    mentioned_ids = {t.skill_id for t in result.targets}

    assert "python-oop" not in mentioned_ids  # never mentioned in any JD
    assert "neural-networks" not in mentioned_ids


def test_targets_are_sorted_by_demand_descending(graph, jd_index):
    result = translate_goal("I want an AI/ML role", graph, jd_index, JD_TEXTS, _UniformEmbedder())
    demands = [t.demand for t in result.targets]
    assert demands == sorted(demands, reverse=True)


def test_higher_min_demand_filters_more_aggressively(graph, jd_index):
    result = translate_goal(
        "I want an AI/ML role", graph, jd_index, JD_TEXTS, _UniformEmbedder(), min_demand=0.6
    )
    assert result.targets == []


def test_goal_text_is_preserved_on_the_response(graph, jd_index):
    result = translate_goal("a very specific goal", graph, jd_index, JD_TEXTS, _UniformEmbedder())
    assert result.goal_text == "a very specific goal"


def test_empty_jd_index_returns_no_targets(graph):
    empty_index = VectorIndex.build([], [], _UniformEmbedder())
    result = translate_goal("anything", graph, empty_index, JD_TEXTS, _UniformEmbedder())
    assert result.targets == []
