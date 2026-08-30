"""Gap computation, ordering and milestone grouping - the path engine's centerpiece.

100% deterministic: no LLM, no retrieval. Given a graph, targets and mastery,
the output ordering is always the same. See PathForge-Plan.md Section 4.5.
"""

from __future__ import annotations

import heapq
from datetime import datetime, timezone

from core.graph import SkillGraph
from schemas.models import LearningPath, Milestone, PlannedSkill, TargetSkill

DEFAULT_MASTERY_THRESHOLD = 0.75
DEFAULT_MILESTONE_SIZE = 4
DEFAULT_HOURS_PER_SKILL = 8.0


def generate_path(
    graph: SkillGraph,
    target_skills: list[TargetSkill],
    mastery: dict[str, float],
    learner_id: str,
    hours_per_week: float | None = None,
    mastery_threshold: float = DEFAULT_MASTERY_THRESHOLD,
    milestone_size: int = DEFAULT_MILESTONE_SIZE,
    hours_per_skill_estimate: float = DEFAULT_HOURS_PER_SKILL,
) -> LearningPath:
    target_ids = [t.skill_id for t in target_skills]
    supported_targets = [t for t in target_ids if t in graph]
    unsupported_targets = [t for t in target_ids if t not in graph]

    ancestor_closure: set[str] = set(supported_targets)
    for skill_id in supported_targets:
        ancestor_closure |= graph.ancestors_of(skill_id)

    mastered = {skill_id for skill_id, p in mastery.items() if p > mastery_threshold}
    gap_nodes = ancestor_closure - mastered

    demand_by_id = {t.skill_id: t.demand for t in target_skills}
    ordering = _topological_order(graph, gap_nodes, demand_by_id)
    milestones = _build_milestones(
        ordering, demand_by_id, milestone_size, hours_per_week, hours_per_skill_estimate
    )

    return LearningPath(
        learner_id=learner_id,
        target_skill_ids=target_ids,
        ancestor_closure=sorted(ancestor_closure),
        gap_nodes=sorted(gap_nodes),
        ordering=ordering,
        milestones=milestones,
        unsupported_targets=unsupported_targets,
        generated_at=datetime.now(timezone.utc),
    )


def _topological_order(
    graph: SkillGraph, gap_nodes: set[str], demand_by_id: dict[str, float]
) -> list[str]:
    """Kahn's algorithm; ties among simultaneously-ready skills go to higher demand."""
    in_degree = {n: len(graph.prerequisites_of(n) & gap_nodes) for n in gap_nodes}
    heap = [(-demand_by_id.get(n, 0.0), n) for n in gap_nodes if in_degree[n] == 0]
    heapq.heapify(heap)

    ordering: list[str] = []
    while heap:
        _, node = heapq.heappop(heap)
        ordering.append(node)
        for successor in graph.unlocks(node) & gap_nodes:
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                heapq.heappush(heap, (-demand_by_id.get(successor, 0.0), successor))
    return ordering


def _build_milestones(
    ordering: list[str],
    demand_by_id: dict[str, float],
    milestone_size: int,
    hours_per_week: float | None,
    hours_per_skill_estimate: float,
) -> list[Milestone]:
    """Chunks the ordering into consecutive groups; any contiguous chunk of a
    valid topological order is itself still prerequisite-valid."""
    weeks_per_skill = hours_per_skill_estimate / hours_per_week if hours_per_week else None
    cumulative_week = 0.0

    milestones: list[Milestone] = []
    for index, start in enumerate(range(0, len(ordering), milestone_size)):
        chunk = ordering[start : start + milestone_size]
        skills = [
            PlannedSkill(
                skill_id=skill_id,
                order=start + position,
                demand=demand_by_id.get(skill_id),
                course_ids=[],
            )
            for position, skill_id in enumerate(chunk)
        ]

        if weeks_per_skill is not None:
            estimated_start_week = cumulative_week
            cumulative_week += weeks_per_skill * len(chunk)
            estimated_end_week = cumulative_week
        else:
            estimated_start_week = None
            estimated_end_week = None

        milestones.append(
            Milestone(
                index=index,
                skills=skills,
                project=None,
                assessment_item_ids=[],
                estimated_start_week=estimated_start_week,
                estimated_end_week=estimated_end_week,
            )
        )
    return milestones
