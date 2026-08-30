from pathlib import Path

import pytest

from core.graph import SkillGraph
from core.skill_matcher import _cosine_similarity, match_skill
from schemas.models import SkillNode

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mini_graph.json"


@pytest.fixture
def graph() -> SkillGraph:
    return SkillGraph.from_file(FIXTURE)


class _ExplodingEmbedder:
    """Proves alias matches short-circuit before any embedding call happens."""

    def embed(self, texts):
        raise AssertionError("embedder should not be called when an alias match exists")


class _FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]]):
        self._vectors = vectors

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors.get(text, [0.0, 0.0]) for text in texts]


def test_exact_name_match_short_circuits_embedding(graph):
    assert match_skill("Docker", graph, _ExplodingEmbedder()) == "docker"


def test_alias_match_is_case_and_whitespace_insensitive(graph):
    assert match_skill("  docker  ", graph, _ExplodingEmbedder()) == "docker"


def test_registered_alias_is_matched():
    nodes = [SkillNode(id="ml-basics", name="Machine Learning Basics", aliases=["ML"], cluster="x")]
    graph = SkillGraph(nodes)
    assert match_skill("ml", graph, _ExplodingEmbedder()) == "ml-basics"


def test_falls_back_to_embedding_when_no_alias_matches(graph):
    embedder = _FakeEmbedder(
        {
            "learn how to containerize apps": [1.0, 0.0],
            "Docker": [1.0, 0.0],
            "SQL": [0.0, 1.0],
        }
    )
    result = match_skill("learn how to containerize apps", graph, embedder)
    assert result == "docker"


def test_below_threshold_embedding_match_returns_none(graph):
    embedder = _FakeEmbedder(
        {
            "something vaguely related": [1.0, 0.1],
            "Docker": [0.0, 1.0],
        }
    )
    result = match_skill("something vaguely related", graph, embedder, threshold=0.55)
    assert result is None


def test_cosine_similarity_basic_cases():
    assert _cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert _cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert _cosine_similarity([0, 0], [1, 0]) == 0.0
