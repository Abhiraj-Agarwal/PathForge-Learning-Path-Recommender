from pathlib import Path

import pytest

from core.graph import GraphValidationError, SkillGraph
from schemas.models import SkillNode

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mini_graph.json"


@pytest.fixture
def graph() -> SkillGraph:
    return SkillGraph.from_file(FIXTURE)


def test_loads_all_nodes(graph):
    assert len(graph) == 12
    assert "supervised-learning" in graph
    assert "not-a-real-skill" not in graph


def test_get_returns_the_node(graph):
    node = graph.get("supervised-learning")
    assert node.cluster == "machine-learning"


def test_get_missing_skill_raises_key_error(graph):
    with pytest.raises(KeyError):
        graph.get("not-a-real-skill")


def test_prerequisites_of_is_direct_only(graph):
    assert graph.prerequisites_of("supervised-learning") == {
        "python-basics",
        "statistics",
        "linear-algebra",
    }
    # neural-networks depends on calculus, not directly on linear-algebra
    assert graph.prerequisites_of("neural-networks") == {"supervised-learning", "calculus"}


def test_ancestors_of_is_transitive(graph):
    # neural-networks -> supervised-learning -> {python-basics, statistics, linear-algebra}
    # neural-networks -> calculus -> linear-algebra
    assert graph.ancestors_of("neural-networks") == {
        "supervised-learning",
        "calculus",
        "python-basics",
        "statistics",
        "linear-algebra",
    }


def test_ancestors_of_root_skill_is_empty(graph):
    assert graph.ancestors_of("python-basics") == set()


def test_unlocks_is_direct_only(graph):
    assert graph.unlocks("supervised-learning") == {"unsupervised-learning", "neural-networks"}
    assert graph.unlocks("docker") == {"ci-cd"}


def test_rejects_dangling_prerequisite():
    nodes = [SkillNode(id="a", name="A", cluster="x", prerequisites=["ghost"])]
    with pytest.raises(GraphValidationError, match="unknown skill ids"):
        SkillGraph(nodes)


def test_rejects_cycle():
    nodes = [
        SkillNode(id="a", name="A", cluster="x", prerequisites=["b"]),
        SkillNode(id="b", name="B", cluster="x", prerequisites=["a"]),
    ]
    with pytest.raises(GraphValidationError, match="cycle"):
        SkillGraph(nodes)
