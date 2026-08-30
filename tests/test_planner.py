from pathlib import Path

import pytest

from core.graph import SkillGraph
from core.planner import generate_path
from schemas.models import TargetSkill

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mini_graph.json"


@pytest.fixture
def graph() -> SkillGraph:
    return SkillGraph.from_file(FIXTURE)


def test_gap_covers_exactly_the_needed_ancestors(graph):
    targets = [
        TargetSkill(skill_id="neural-networks", demand=0.8, evidence_count=40),
        TargetSkill(skill_id="docker", demand=0.6, evidence_count=30),
    ]
    path = generate_path(graph, targets, mastery={}, learner_id="l1")

    assert set(path.gap_nodes) == {
        "neural-networks",
        "supervised-learning",
        "calculus",
        "python-basics",
        "statistics",
        "linear-algebra",
        "docker",
    }


def test_ordering_respects_every_prerequisite(graph):
    targets = [TargetSkill(skill_id="neural-networks", demand=0.8, evidence_count=40)]
    path = generate_path(graph, targets, mastery={}, learner_id="l1")

    position = {skill_id: i for i, skill_id in enumerate(path.ordering)}
    for skill_id in path.ordering:
        for prereq_id in graph.prerequisites_of(skill_id) & set(path.gap_nodes):
            assert position[prereq_id] < position[skill_id]


def test_mastered_skill_excluded_from_gap_but_kept_in_closure(graph):
    targets = [TargetSkill(skill_id="neural-networks", demand=0.8, evidence_count=40)]
    path = generate_path(
        graph, targets, mastery={"linear-algebra": 0.9}, learner_id="l1"
    )

    assert "linear-algebra" in path.ancestor_closure
    assert "linear-algebra" not in path.gap_nodes
    assert "linear-algebra" not in path.ordering


def test_mastery_at_or_below_threshold_stays_in_gap(graph):
    targets = [TargetSkill(skill_id="neural-networks", demand=0.8, evidence_count=40)]
    path = generate_path(
        graph, targets, mastery={"linear-algebra": 0.75}, learner_id="l1"
    )

    assert "linear-algebra" in path.gap_nodes


def test_unsupported_target_is_reported_not_dropped_silently(graph):
    targets = [
        TargetSkill(skill_id="docker", demand=0.5, evidence_count=10),
        TargetSkill(skill_id="quantum-computing", demand=0.9, evidence_count=5),
    ]
    path = generate_path(graph, targets, mastery={}, learner_id="l1")

    assert path.unsupported_targets == ["quantum-computing"]
    assert "quantum-computing" not in path.gap_nodes
    assert "docker" in path.gap_nodes


def test_ties_are_broken_by_higher_demand_first(graph):
    # sql and docker are both independent roots - alphabetically docker < sql,
    # so this only passes if demand, not alphabetical order, decides the tie.
    targets = [
        TargetSkill(skill_id="sql", demand=0.9, evidence_count=50),
        TargetSkill(skill_id="docker", demand=0.2, evidence_count=5),
    ]
    path = generate_path(graph, targets, mastery={}, learner_id="l1")

    assert path.ordering.index("sql") < path.ordering.index("docker")


def test_milestones_cover_the_full_gap_in_order(graph):
    targets = [TargetSkill(skill_id="neural-networks", demand=0.8, evidence_count=40)]
    path = generate_path(graph, targets, mastery={}, learner_id="l1", milestone_size=3)

    flattened = [ps.skill_id for m in path.milestones for ps in m.skills]
    assert flattened == path.ordering
    assert [m.index for m in path.milestones] == list(range(len(path.milestones)))
    assert all(1 <= len(m.skills) <= 3 for m in path.milestones)


def test_estimated_weeks_accumulate_with_hours_per_week(graph):
    targets = [TargetSkill(skill_id="neural-networks", demand=0.8, evidence_count=40)]
    path = generate_path(
        graph,
        targets,
        mastery={},
        learner_id="l1",
        milestone_size=4,
        hours_per_week=10,
        hours_per_skill_estimate=8,
    )

    first, second = path.milestones[0], path.milestones[1]
    assert first.estimated_start_week == pytest.approx(0.0)
    assert first.estimated_end_week == pytest.approx(4 * 8 / 10)
    assert second.estimated_start_week == pytest.approx(first.estimated_end_week)


def test_no_estimated_weeks_without_hours_per_week(graph):
    targets = [TargetSkill(skill_id="docker", demand=0.5, evidence_count=10)]
    path = generate_path(graph, targets, mastery={}, learner_id="l1")

    assert path.milestones[0].estimated_start_week is None
    assert path.milestones[0].estimated_end_week is None
