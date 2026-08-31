# core/diagnostic.py

"""Bayesian Knowledge Tracing (BKT) and adaptive item selection.

Pure Python -- imports none of Streamlit, LangChain or FastAPI on purpose, so
this module runs offline and is unit-testable without a server or a UI.

The model tracks, per skill, the probability that the learner has mastered it.
Each observation (a correct/incorrect answer) updates that probability with a
Bayesian update, then the learn-rate transition nudges it upward:

    P(mastered | observation)            <- posterior via Bayes
    P(mastered next step) = posterior + (1 - posterior) * P(T)   <- learning

Parameters (spec):
    P(T) = 0.10  learn rate      - chance of learning when asked a question
    P(G) = 0.25  guess           - chance of answering correctly despite ignorance
    P(S) = 0.10  slip            - chance of answering wrong despite mastery

Item selection is adaptive: among the *unasked* questions, pick the one whose
skill's current mastery estimate is closest to 0.5 -- maximum uncertainty. That
is the question the learner's next answer tells us the most about.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set

P_TRANSITION = 0.10  # P(T): learn rate
P_GUESS = 0.25       # P(G)
P_SLIP = 0.10        # P(S)

P_LEARN = P_TRANSITION  # spec-style alias
PRIOR = 0.5             # starting mastery before any evidence
MASTERY_THRESHOLD = 0.75  # P(L) above this counts as "mastered"
CLAMP_LOW = 0.01
CLAMP_HIGH = 0.99


def update_mastery(prior: float, is_correct: bool) -> float:
    """Bayesian update for a single skill after one observation.

    Returns the new `P(mastered)` after applying the observation posterior and
    the learn-rate transition, clamped to ``[0.01, 0.99]`` so the model never
    becomes absolutely certain in a direction it cannot defend.
    """
    if prior < CLAMP_LOW:
        prior = CLAMP_LOW
    if is_correct:
        # Correct answer: either they knew it and did not slip, or they
        # guessed it while still unmastered.
        numerator = prior * (1 - P_SLIP)
        denominator = numerator + (1 - prior) * P_GUESS
    else:
        # Wrong answer: either they knew it but slipped, or they were
        # genuinely unmastered and did not guess correctly.
        numerator = prior * P_SLIP
        denominator = numerator + (1 - prior) * (1 - P_GUESS)

    posterior = numerator / denominator if denominator > 0 else 0.0

    # Even after a wrong answer the learner may have picked something up.
    p_new = posterior + (1 - posterior) * P_LEARN
    return max(CLAMP_LOW, min(CLAMP_HIGH, p_new))


def update_skill_mastery(mastery_state: Dict[str, float], skill_id: str,
                         is_correct: bool) -> float:
    """In-place per-skill mastery update; returns the new value."""
    prior = mastery_state.get(skill_id, PRIOR)
    mastery_state[skill_id] = update_mastery(prior, is_correct)
    return mastery_state[skill_id]


def is_mastered(mastery: float) -> bool:
    """Binary decision on the continuous probability estimate."""
    return mastery > MASTERY_THRESHOLD


def _question_skill(item: dict) -> str:
    return item.get("skill_id") or item.get("skill", "")


def get_next_question(
    mastery_state: Dict[str, float],
    item_bank: Iterable[dict],
    asked_ids: Optional[Set[str]] = None,
) -> Optional[dict]:
    """Pick the next diagnostic question.

    Selection rule: among items whose ``id`` is not in ``asked_ids``, return
    the one whose skill's mastery is closest to ``0.5`` (undefined skills
    default to ``0.5``, so a brand-new skill is always maximally informative).
    Ties resolve to the item that appears first in the bank.

    Returns ``None`` when every item has already been asked.
    """
    asked = set(asked_ids or ())
    best = None
    best_distance = float("inf")
    best_index = float("inf")

    for index, item in enumerate(item_bank):
        if item.get("id") in asked:
            continue
        skill_id = _question_skill(item)
        mastery = mastery_state.get(skill_id, PRIOR)
        distance = abs(mastery - PRIOR)
        if distance < best_distance or (
            distance == best_distance and index < best_index
        ):
            best_distance = distance
            best_index = index
            best = item

    return best


def run_diagnostic(mastery_state: Dict[str, float], item_bank: List[dict],
                   correct_flags: Iterable[bool]) -> Dict[str, float]:
    """Drive a whole quiz: adaptively pick each next item and observe answers.

    ``correct_flags`` is iterated in a 1:1 order with the items each call
    selects, so ``run_diagnostic(ms, bank, [True, False, True])`` answers the
    first three adaptively-chosen questions that way. Returns the updated
    mastery state (mutates the passed dict too).
    """
    asked: Set[str] = set()
    for flag in correct_flags:
        item = get_next_question(mastery_state, item_bank, asked)
        if item is None:
            break
        asked.add(item["id"])
        update_skill_mastery(mastery_state, _question_skill(item), flag)
    return mastery_state


if __name__ == "__main__":
    # Self-check: convergence in both directions.
    p = 0.5
    for i in range(5):
        p = update_mastery(p, is_correct=True)
    print(f"5 straight correct : {p:.2f}")

    q = 0.5
    for i in range(10):
        q = update_mastery(q, is_correct=False)
    print(f"10 straight wrong  : {q:.2f}")