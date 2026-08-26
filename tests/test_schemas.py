import json
from pathlib import Path

import pytest

from schemas.models import (
    Course,
    DashboardPayload,
    LearnerProfile,
    LearningPath,
    SkillNode,
    TargetSkillsResponse,
)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "schemas" / "examples"

MODEL_BY_EXAMPLE = {
    "skill_node.json": SkillNode,
    "course.json": Course,
    "learner_profile.json": LearnerProfile,
    "target_skills.json": TargetSkillsResponse,
    "learning_path.json": LearningPath,
    "dashboard_payload.json": DashboardPayload,
}


@pytest.mark.parametrize("filename,model", MODEL_BY_EXAMPLE.items())
def test_example_matches_model(filename, model):
    data = json.loads((EXAMPLES_DIR / filename).read_text())
    model.model_validate(data)


def test_skill_node_rejects_self_prerequisite():
    with pytest.raises(ValueError):
        SkillNode(id="docker", name="Docker", cluster="devops", prerequisites=["docker"])


def test_learner_profile_rejects_mastery_out_of_range():
    with pytest.raises(ValueError):
        LearnerProfile(learner_id="x", raw_text="...", mastery={"docker": 1.4})


def test_learning_path_rejects_ordering_gap_mismatch():
    base = json.loads((EXAMPLES_DIR / "learning_path.json").read_text())
    base["ordering"] = base["ordering"][:-1]
    with pytest.raises(ValueError):
        LearningPath.model_validate(base)
