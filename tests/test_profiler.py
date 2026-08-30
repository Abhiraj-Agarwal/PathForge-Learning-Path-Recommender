import json
from datetime import date
from pathlib import Path

import pytest

from core.graph import SkillGraph
from core.profiler import ProfileExtractionError, extract_profile, seed_mastery

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mini_graph.json"


@pytest.fixture
def graph() -> SkillGraph:
    return SkillGraph.from_file(FIXTURE)


class _FakeCompleter:
    def __init__(self, response: str):
        self._response = response

    def complete(self, prompt: str, system: str | None = None, temperature: float = 0.2) -> str:
        return self._response


class _FakeEmbedder:
    """Every text defaults to the zero vector, so any embedding-fallback
    match scores 0.0 similarity - below threshold, i.e. always unmapped."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0, 0.0] for _ in texts]


VALID_RESPONSE = json.dumps(
    {
        "interests": ["machine-learning", "ai"],
        "experience_level": "beginner",
        "hours_per_week": 10,
        "target_date": "2026-12-25",
        "completed_skills": ["Docker", "Python Basics"],
    }
)


def test_extract_profile_happy_path(graph):
    profile = extract_profile(
        "I know Docker and Python basics",
        learner_id="l1",
        llm=_FakeCompleter(VALID_RESPONSE),
        graph=graph,
        embedder=_FakeEmbedder(),
    )

    assert profile.learner_id == "l1"
    assert profile.raw_text == "I know Docker and Python basics"
    assert profile.interests == ["machine-learning", "ai"]
    assert profile.experience_level == "beginner"
    assert profile.hours_per_week == 10
    assert profile.target_date == date(2026, 12, 25)
    assert profile.completed_skill_ids == ["docker", "python-basics"]
    assert profile.unmapped == []
    assert profile.mastery["docker"] == pytest.approx(0.7)
    assert profile.mastery["python-basics"] == pytest.approx(0.7)


def test_unmatched_mention_goes_to_unmapped(graph):
    response = json.dumps({"completed_skills": ["underwater basket weaving"]})
    profile = extract_profile(
        "...", learner_id="l1", llm=_FakeCompleter(response), graph=graph, embedder=_FakeEmbedder()
    )

    assert profile.completed_skill_ids == []
    assert profile.unmapped == ["underwater basket weaving"]


def test_malformed_json_raises_profile_extraction_error(graph):
    with pytest.raises(ProfileExtractionError):
        extract_profile(
            "...", learner_id="l1", llm=_FakeCompleter("not json at all"), graph=graph, embedder=_FakeEmbedder()
        )


def test_json_wrapped_in_markdown_fence_still_parses(graph):
    fenced = f"```json\n{VALID_RESPONSE}\n```"
    profile = extract_profile(
        "...", learner_id="l1", llm=_FakeCompleter(fenced), graph=graph, embedder=_FakeEmbedder()
    )
    assert profile.completed_skill_ids == ["docker", "python-basics"]


def test_missing_optional_fields_default_sensibly(graph):
    profile = extract_profile(
        "...", learner_id="l1", llm=_FakeCompleter("{}"), graph=graph, embedder=_FakeEmbedder()
    )

    assert profile.interests == []
    assert profile.experience_level is None
    assert profile.hours_per_week is None
    assert profile.target_date is None
    assert profile.completed_skill_ids == []
    assert profile.unmapped == []
    assert profile.mastery == {}


def test_seed_mastery_sets_completed_and_implied_prerequisites(graph):
    mastery = seed_mastery(graph, ["supervised-learning"])

    assert mastery["supervised-learning"] == pytest.approx(0.7)
    assert mastery["python-basics"] == pytest.approx(0.4)
    assert mastery["statistics"] == pytest.approx(0.4)
    assert mastery["linear-algebra"] == pytest.approx(0.4)


def test_seed_mastery_keeps_the_higher_value_on_overlap(graph):
    mastery = seed_mastery(graph, ["python-basics", "supervised-learning"])

    # python-basics is both directly completed (0.7) and an implied
    # prerequisite of supervised-learning (0.4) - higher value must win.
    assert mastery["python-basics"] == pytest.approx(0.7)
