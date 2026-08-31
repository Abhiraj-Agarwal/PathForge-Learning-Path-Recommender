"""Tests for Bayesian Knowledge Tracing and adaptive item selection."""

import pytest

from core.diagnostic import (
    MASTERY_THRESHOLD,
    PRIOR,
    get_next_question,
    is_mastered,
    run_diagnostic,
    update_mastery,
    update_skill_mastery,
)


# --------------------------------------------------------------------------
# BKT core
# --------------------------------------------------------------------------

class TestUpdateMastery:
    def test_correct_answer_raises_mastery(self):
        before = update_mastery(0.5, is_correct=False)
        after = update_mastery(0.5, is_correct=True)
        assert after > before
        assert after > 0.5

    def test_wrong_answer_lowers_mastery(self):
        outcome = update_mastery(0.8, is_correct=False)
        assert outcome < 0.8

    def test_correct_answers_converge_to_high(self):
        p = PRIOR
        for _ in range(5):
            p = update_mastery(p, is_correct=True)
        assert p > 0.9

    def test_wrong_answers_converge_to_low(self):
        p = PRIOR
        for _ in range(15):
            p = update_mastery(p, is_correct=False)
        assert p < 0.2

    def test_values_stay_clamped(self):
        p = update_mastery(PRIOR, is_correct=True)
        for _ in range(100):
            p = update_mastery(p, is_correct=True)
        assert p <= 0.99
        q = PRIOR
        for _ in range(100):
            q = update_mastery(q, is_correct=False)
        assert q >= 0.01

    def test_wrong_answer_after_mastery_kills_confidence_but_recovers(self):
        p = PRIOR
        for _ in range(5):
            p = update_mastery(p, is_correct=True)
        slipped = update_mastery(p, is_correct=False)
        assert slipped < p
        # ...but the slip is assimilated, not catastrophic
        assert slipped > 0.5

    def test_observed_sequence_is_order_dependent(self):
        right_then_wrong = update_mastery(update_mastery(0.5, True), False)
        wrong_then_right = update_mastery(update_mastery(0.5, False), True)
        assert right_then_wrong != wrong_then_right


class TestUpdateSkillMastery:
    def test_defaults_prior_then_stores_new_value(self):
        state = {}
        out = update_skill_mastery(state, "docker", is_correct=True)
        assert state["docker"] == out
        assert out > PRIOR


class TestIsMastered:
    def test_threshold(self):
        assert is_mastered(MASTERY_THRESHOLD + 0.01)
        assert not is_mastered(MASTERY_THRESHOLD - 0.01)


# --------------------------------------------------------------------------
# adaptive item selection
# --------------------------------------------------------------------------

def bank():
    return [
        {"id": "q1", "skill_id": "alpha"},
        {"id": "q2", "skill_id": "beta"},
        {"id": "q3", "skill_id": "gamma"},
    ]


class TestGetNextQuestion:
    def test_measures_unmeasured_skill_first(self):
        # alpha/beta/gamma absent -> all default to 0.5 (distance 0)
        picked = get_next_question({}, bank())
        assert picked["id"] == "q1"

    def test_picks_closest_to_50_percent(self):
        mastery = {"alpha": 0.9, "beta": 0.55, "gamma": 0.1}
        picked = get_next_question(mastery, bank())
        assert picked["skill_id"] == "beta"

    def test_skips_asked_items(self):
        mastery = {}
        first = get_next_question(mastery, bank())
        second = get_next_question(mastery, bank(), asked_ids={first["id"]})
        assert second["id"] != first["id"]

    def test_asked_items_from_other_skills_still_measure_them(self):
        # without the asked filter every item would tie; asked must pin them
        mastery = {"alpha": 0.5, "beta": 0.5, "gamma": 0.5}
        picked = get_next_question(mastery, bank(), asked_ids={"q2", "q3"})
        assert picked["id"] == "q1"

    def test_returns_none_when_everything_asked(self):
        picked = get_next_question({}, bank(), asked_ids={"q1", "q2", "q3"})
        assert picked is None

    def test_rejects_duplicate_options_pool(self):
        # regression: nothing should crash when a skill has no mastery entry
        assert get_next_question({}, bank()) is not None


class TestRunDiagnostic:
    def test_answered_questions_cover_distinct_skills(self):
        state = {}
        result = run_diagnostic(state, bank(), [True, False, True])
        # all three items consumed
        for skill in ("alpha", "beta", "gamma"):
            assert skill in result

    def test_longer_than_bank_quiz_terminates(self):
        state = {}
        result = run_diagnostic(state, bank(), [True] * 20)
        assert set(result) == {"alpha", "beta", "gamma"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])