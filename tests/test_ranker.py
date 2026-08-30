import pytest

from core.ranker import _level_fit, rank_courses_for_skill
from core.retrieval import VectorIndex
from schemas.models import Course


class _FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]]):
        self._vectors = vectors

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors.get(text, [0.0, 0.0]) for text in texts]


def _course(id_: str, level: str, rating: float, description: str) -> Course:
    return Course(
        id=id_,
        title=id_,
        provider="test",
        url="https://example.com/" + id_,
        description=description,
        level=level,
        rating=rating,
        duration_hours=5,
        skill_tags=["docker"],
    )


def test_prefers_the_level_matching_course_when_similarity_and_rating_tie():
    courses_by_id = {
        "c-beginner": _course("c-beginner", "beginner", 4.0, "docker basics"),
        "c-advanced": _course("c-advanced", "advanced", 4.0, "docker basics"),
    }
    embedder = _FakeEmbedder({"docker query": [1.0, 0.0], "docker basics": [1.0, 0.0]})
    index = VectorIndex.build(list(courses_by_id), [c.description for c in courses_by_id.values()], embedder)

    result = rank_courses_for_skill("docker query", mastery=0.1, course_index=index,
                                     courses_by_id=courses_by_id, embedder=embedder, top_n=1)

    assert result == ["c-beginner"]


def test_top_n_limits_results():
    courses_by_id = {
        f"c{i}": _course(f"c{i}", "beginner", 4.0, "docker basics") for i in range(3)
    }
    embedder = _FakeEmbedder({"docker query": [1.0, 0.0], "docker basics": [1.0, 0.0]})
    index = VectorIndex.build(list(courses_by_id), [c.description for c in courses_by_id.values()], embedder)

    result = rank_courses_for_skill("docker query", mastery=0.1, course_index=index,
                                     courses_by_id=courses_by_id, embedder=embedder, top_n=2)

    assert len(result) == 2


def test_stale_index_entry_missing_from_catalog_is_skipped_not_crashed():
    courses_by_id = {"c-real": _course("c-real", "beginner", 4.0, "docker basics")}
    embedder = _FakeEmbedder({"docker query": [1.0, 0.0], "docker basics": [1.0, 0.0], "ghost course": [1.0, 0.0]})
    # index has an id ("c-ghost") that's no longer in the catalog
    index = VectorIndex.build(["c-real", "c-ghost"], ["docker basics", "ghost course"], embedder)

    result = rank_courses_for_skill("docker query", mastery=0.1, course_index=index,
                                     courses_by_id=courses_by_id, embedder=embedder)

    assert result == ["c-real"]


def test_no_candidates_returns_empty_list_gracefully():
    embedder = _FakeEmbedder({})
    empty_index = VectorIndex.build([], [], embedder)

    result = rank_courses_for_skill("anything", mastery=0.5, course_index=empty_index,
                                     courses_by_id={}, embedder=embedder)

    assert result == []


def test_level_fit_perfect_match_is_one():
    assert _level_fit("beginner", mastery=0.1) == pytest.approx(1.0)
    assert _level_fit("intermediate", mastery=0.5) == pytest.approx(1.0)
    assert _level_fit("advanced", mastery=0.9) == pytest.approx(1.0)


def test_level_fit_opposite_ends_is_zero():
    assert _level_fit("advanced", mastery=0.0) == pytest.approx(0.0)
    assert _level_fit("beginner", mastery=1.0) == pytest.approx(0.0)
