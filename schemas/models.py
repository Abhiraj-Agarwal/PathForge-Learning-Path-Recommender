"""Frozen Pydantic contracts shared across core/, api/, agents/ and app/.

Field shapes here mirror the examples in schemas/examples/. Changing a
model after Day 2 needs both people at the keyboard (see PathForge-Plan.md
Section 7) since app/, agents/ and core/ all import from this file.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

SkillLevel = Literal["beginner", "intermediate", "advanced"]


# --- Skill graph ---------------------------------------------------------


class SkillNode(BaseModel):
    """One node of the prerequisite DAG in data/skills.json."""

    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    cluster: str
    prerequisites: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def no_self_prerequisite(self) -> SkillNode:
        if self.id in self.prerequisites:
            raise ValueError(f"skill {self.id!r} cannot be its own prerequisite")
        return self


# --- Course catalog --------------------------------------------------------


class Course(BaseModel):
    """One entry of the catalog in data/courses.json."""

    id: str
    title: str
    provider: str
    url: HttpUrl
    description: str
    level: SkillLevel
    rating: float = Field(ge=0, le=5)
    duration_hours: float = Field(gt=0)
    skill_tags: list[str] = Field(default_factory=list)


# --- Learner profile ---------------------------------------------------------


class LearnerProfile(BaseModel):
    """Structured output of core/profiler.py, returned by POST /profile.

    completed_skill_ids and unmapped are populated by core/skill_matcher.py
    after the LLM extraction step: matched free text becomes a canonical
    skill id, anything below the match threshold lands in unmapped instead
    of being silently dropped or guessed.
    """

    learner_id: str
    raw_text: str
    interests: list[str] = Field(default_factory=list)
    experience_level: SkillLevel | None = None
    hours_per_week: float | None = Field(default=None, gt=0)
    target_date: date | None = None
    completed_skill_ids: list[str] = Field(default_factory=list)
    unmapped: list[str] = Field(default_factory=list)
    # skill_id -> P(L), seeded 0.7 for a completed course's taught skills
    # and 0.4 for its prerequisites, then refined by the BKT diagnostic.
    mastery: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def mastery_in_unit_interval(self) -> LearnerProfile:
        for skill_id, p in self.mastery.items():
            if not 0.0 <= p <= 1.0:
                raise ValueError(f"mastery[{skill_id!r}] = {p} is outside [0, 1]")
        return self


# --- Goal translation ---------------------------------------------------------


class TargetSkill(BaseModel):
    """One row of the goal translator's output: a skill the market demands."""

    skill_id: str
    demand: float = Field(ge=0, le=1)
    evidence_count: int = Field(ge=0)


class TargetSkillsResponse(BaseModel):
    """POST /goal/translate response: the stated goal plus its weighted targets."""

    goal_text: str
    targets: list[TargetSkill]


# --- Learning path ---------------------------------------------------------


class PlannedSkill(BaseModel):
    """One skill placed in the path, with its resources attached."""

    skill_id: str
    order: int = Field(ge=0)
    demand: float | None = Field(default=None, ge=0, le=1)
    course_ids: list[str] = Field(default_factory=list)


class Milestone(BaseModel):
    """A group of 3-5 skills by graph depth, per Section 4.5 of the plan."""

    index: int = Field(ge=0)
    skills: list[PlannedSkill]
    project: str | None = None
    assessment_item_ids: list[str] = Field(default_factory=list)
    estimated_start_week: float | None = Field(default=None, ge=0)
    estimated_end_week: float | None = Field(default=None, ge=0)


class LearningPath(BaseModel):
    """POST /path/generate response: the full ordered roadmap.

    gap_nodes, ancestor_closure and ordering are exposed alongside the
    milestones (not just folded into them) because the roadmap graph
    view needs the raw sets to draw the full DAG, not only the grouped
    view (Section 4.5, "Expose the intermediates").
    """

    learner_id: str
    target_skill_ids: list[str]
    ancestor_closure: list[str]
    gap_nodes: list[str]
    ordering: list[str]
    milestones: list[Milestone]
    unsupported_targets: list[str] = Field(default_factory=list)
    generated_at: datetime

    @model_validator(mode="after")
    def ordering_matches_gap(self) -> LearningPath:
        if set(self.ordering) != set(self.gap_nodes):
            raise ValueError("ordering must be a permutation of gap_nodes")
        return self


# --- Dashboard ---------------------------------------------------------


class DashboardPayload(BaseModel):
    """GET /dashboard/{learner_id} response: everything one screen needs.

    Bundled into a single payload on purpose, so the UI never has to fire
    multiple requests to paint one page (Section 4.9).
    """

    learner_id: str
    path: LearningPath
    mastery: dict[str, float]
    demand: dict[str, float]
    next_actions: list[PlannedSkill]
    completed_skill_ids: list[str] = Field(default_factory=list)
