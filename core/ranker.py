"""Attaches ranked course recommendations to a skill.

Score = 0.4 * semantic_similarity + 0.3 * normalised_rating + 0.3 * level_fit
(PathForge-Plan.md Section 4.6). A skill with no good match just gets an
empty list back - it still appears in the path, never a fabricated link.
"""

from __future__ import annotations

from core.retrieval import Embedder, VectorIndex
from schemas.models import Course, SkillLevel

SEMANTIC_WEIGHT = 0.4
RATING_WEIGHT = 0.3
LEVEL_FIT_WEIGHT = 0.3

MAX_RATING = 5.0
LEVEL_TIER = {"beginner": 0, "intermediate": 1, "advanced": 2}


def rank_courses_for_skill(
    skill_name: str,
    mastery: float,
    course_index: VectorIndex,
    courses_by_id: dict[str, Course],
    embedder: Embedder,
    top_n: int = 2,
    candidate_k: int = 10,
) -> list[str]:
    scored: list[tuple[float, str]] = []
    for course_id, similarity in course_index.search(skill_name, embedder, k=candidate_k):
        course = courses_by_id.get(course_id)
        if course is None:  # index and catalog have drifted apart - skip, don't crash
            continue
        score = (
            SEMANTIC_WEIGHT * similarity
            + RATING_WEIGHT * (course.rating / MAX_RATING)
            + LEVEL_FIT_WEIGHT * _level_fit(course.level, mastery)
        )
        scored.append((score, course_id))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [course_id for _score, course_id in scored[:top_n]]


def _level_fit(level: SkillLevel, mastery: float) -> float:
    """1.0 when the course's tier matches current mastery, decaying as they
    diverge. Mastery in [0,1] is bucketed into the same 3 tiers as course level."""
    mastery_tier = min(int(mastery * 3), 2)
    distance = abs(mastery_tier - LEVEL_TIER[level])
    return max(0.0, 1.0 - distance / 2)
