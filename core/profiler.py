"""Free text -> LearnerProfile.

The LLM only ever emits free text for what the learner mentioned; it never
invents a skill id (PathForge-Plan.md Section 4.2). Every mention gets
resolved through core/skill_matcher.py, and anything that doesn't match
confidently lands in `unmapped` instead of being guessed.
"""

from __future__ import annotations

import json
import re
from typing import Protocol

from core.graph import SkillGraph
from core.skill_matcher import DEFAULT_SIMILARITY_THRESHOLD, Embedder, match_skill
from schemas.models import LearnerProfile

MASTERY_FOR_COMPLETED_SKILL = 0.7
MASTERY_FOR_IMPLIED_PREREQUISITE = 0.4

SYSTEM_PROMPT = """You extract structured facts from a learner's self-description.
Output STRICT JSON only, no markdown, no commentary, matching exactly this shape:
{
  "interests": [string, ...],
  "experience_level": "beginner" | "intermediate" | "advanced" | null,
  "hours_per_week": number | null,
  "target_date": "YYYY-MM-DD" | null,
  "completed_skills": [string, ...]
}
"completed_skills" is free text for anything the learner says they already know
or finished (a course name, a skill, a technology) - write down what they said,
do not invent or normalize skill names yourself."""


class Completer(Protocol):
    def complete(self, prompt: str, system: str | None = None, temperature: float = 0.2) -> str: ...


class ProfileExtractionError(Exception):
    """Raised when the LLM's response can't be parsed as the expected JSON shape."""


def extract_profile(
    text: str,
    learner_id: str,
    llm: Completer,
    graph: SkillGraph,
    embedder: Embedder,
    match_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> LearnerProfile:
    raw = llm.complete(prompt=text, system=SYSTEM_PROMPT, temperature=0.0)
    extracted = _parse_llm_json(raw)

    completed_skill_ids: list[str] = []
    unmapped: list[str] = []
    for mention in extracted.get("completed_skills", []):
        skill_id = match_skill(mention, graph, embedder, match_threshold)
        if skill_id is not None:
            completed_skill_ids.append(skill_id)
        else:
            unmapped.append(mention)

    return LearnerProfile.model_validate(
        {
            "learner_id": learner_id,
            "raw_text": text,
            "interests": extracted.get("interests", []),
            "experience_level": extracted.get("experience_level"),
            "hours_per_week": extracted.get("hours_per_week"),
            "target_date": extracted.get("target_date"),
            "completed_skill_ids": sorted(set(completed_skill_ids)),
            "unmapped": unmapped,
            "mastery": seed_mastery(graph, completed_skill_ids),
        }
    )


def seed_mastery(graph: SkillGraph, completed_skill_ids: list[str]) -> dict[str, float]:
    """0.7 for a directly completed skill, 0.4 for everything it implies -
    finishing a course implies you knew its prerequisites too."""
    mastery: dict[str, float] = {}
    for skill_id in completed_skill_ids:
        if skill_id not in graph:
            continue
        mastery[skill_id] = max(mastery.get(skill_id, 0.0), MASTERY_FOR_COMPLETED_SKILL)
        for prereq_id in graph.ancestors_of(skill_id):
            mastery[prereq_id] = max(mastery.get(prereq_id, 0.0), MASTERY_FOR_IMPLIED_PREREQUISITE)
    return mastery


_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _parse_llm_json(raw: str) -> dict:
    cleaned = _CODE_FENCE.sub("", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ProfileExtractionError(f"LLM did not return valid JSON: {raw!r}") from exc
