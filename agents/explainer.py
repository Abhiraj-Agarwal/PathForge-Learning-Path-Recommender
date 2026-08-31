"""Evidence-grounded learning path explanations.

The path was planned by a deterministic graph algorithm -- not by an LLM -- so
every explanation here is grounded in facts we can cite. There are two jobs:

* ``explain(bundle)`` turns a structured *evidence bundle* into two friendly
  sentences ("why this, why now").
* ``explain_why_not(...)`` answers counterfactuals ("why not start with X?")
  by walking the prerequisite ancestor chain and naming unmet prerequisites.

The main functions are pure and offline-safe. An optional ``llm`` callable can
be injected -- the model gets the same facts and is explicitly told to say so
when a fact is missing, never to invent one. The LLM narrates; it does not
compute.
"""

from __future__ import annotations

from collections import deque
from typing import Callable, Dict, List, Optional

VALID_KEYS = {"skill", "position", "unlocks", "demand_pct", "evidence_count",
              "current_mastery", "prereqs_satisfied", "prereqs_missing"}


def build_evidence_bundle(skill: str, demand_pct: float, position: int,
                          unlocks: Optional[List[str]] = None,
                          current_mastery: Optional[float] = None,
                          prereqs_satisfied: Optional[List[str]] = None,
                          evidence_count: Optional[int] = None,
                          prereqs_missing: Optional[List[str]] = None) -> dict:
    """Assemble the facts the explainer is allowed to cite."""
    return {
        "skill": skill,
        "position": position,
        "unlocks": unlocks or [],
        "demand_pct": demand_pct,
        "evidence_count": evidence_count,
        "current_mastery": current_mastery,
        "prereqs_satisfied": prereqs_satisfied or [],
        "prereqs_missing": prereqs_missing or [],
    }


def _prettify(items: List[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def explain(bundle: dict, llm: Optional[Callable] = None) -> str:
    """Turn the evidence bundle into two friendly sentences.

    The LLM (if provided) receives only the supplied facts and a hard rule:
    *don't offer a fact that isn't in the bundle.*
    """
    if llm is not None:
        try:
            facts = {k: v for k, v in bundle.items() if k in VALID_KEYS and v}
            reply = llm(
                "Explain why THIS skill is the right next step, in at most two "
                "friendly sentences. Use ONLY these facts:\n" + repr(facts) +
                "\nIf a fact is missing, say you don't have it. Do not invent data."
            )
            if isinstance(reply, str) and reply.strip():
                return reply.strip()
        except Exception:
            pass
    return _template_explanation(bundle)


def _template_explanation(bundle: dict) -> str:
    skill = bundle.get("skill") or "this skill"
    demand = bundle.get("demand_pct")
    unlocks = _prettify(bundle.get("unlocks") or [])
    satisfied = _prettify(bundle.get("prereqs_satisfied") or [])
    missing = _prettify(bundle.get("prereqs_missing") or [])
    position = bundle.get("position")

    s1_bits = [f"{skill} is step {position} toward your goal" if position else f"{skill} is a core step toward your goal"]
    if demand is not None:
        s1_bits.append(f"{demand:.0f}% of relevant job postings ask for it" if isinstance(demand, float)
                       else f"{demand}% of relevant job postings ask for it")
    if unlocks:
        s1_bits.append(f"and it unlocks {unlocks}")
    sentence1 = ", ".join(s1_bits) + "."

    if missing:
        sentence2 = (f"It can wait: {missing} {'is' if bundle.get('prereqs_missing') and len(bundle['prereqs_missing']) == 1 else 'are'} "
                     f"still missing, so we sequenced it later.")
    else:
        points = []
        if satisfied:
            points.append(f"its prerequisites ({satisfied}) are already in place")
        mastery = bundle.get("current_mastery")
        if mastery is not None:
            points.append(f"your mastery there is only {mastery:.0%}")
        sentence2 = "That makes it the highest-leverage next step."
        if points:
            sentence2 = "That makes it the highest-leverage next step: " + "; ".join(points) + "."
    return f"{sentence1} {sentence2}"


def ancestor_closure(skill_id: str, skills: List[dict]) -> set:
    """All skills required (transitively) before ``skill_id``."""
    by_id = {s["id"]: s for s in skills}
    closure: set = set()
    queue = deque([skill_id])
    while queue:
        current = queue.popleft()
        node = by_id.get(current)
        if node is None:
            continue
        for prereq in node.get("prerequisites", []):
            if prereq not in closure:
                closure.add(prereq)
                queue.append(prereq)
    return closure


def explain_why_not(asked_skill_id: str, skills: List[dict],
                    mastery_state: Optional[Dict[str, float]] = None) -> str:
    """Why not start the path with X? Uses only the DAG and observed mastery.

    * X is not on the path to the goal        -> it's a detour, not a shortcut.
    * X is on the path but has missing prereqs -> we name the nearest unmet one.
    * X is fully unblocked                     -> you probably can, it is ready.
    """
    if mastery_state is None:
        mastery_state = {}
    by_id = {s["id"]: s for s in skills}
    node = by_id.get(asked_skill_id)
    if node is None:
        return f"I don't have \"{asked_skill_id}\" in the skill graph, so I can't justify its placement."

    unmet = [p for p in node.get("prerequisites", []) if (mastery_state.get(p, 0.0) or 0.0) < 0.75]

    if not node.get("prerequisites"):
        return (f"Actually, {node['name']} has no prerequisites, so nothing blocks it -- "
                "we simply scheduled it where the demand-weighted sequence puts it.")

    if unmet:
        chain = _nearest_unmet_chain(node["id"], by_id, mastery_state)
        if len(chain) == 1:
            reason = (f"it builds directly on {chain[0]}, which isn't demonstrated yet")
        else:
            reason = (f"it sits downstream of {_prettify(chain)} -- none of which are "
                      f"demonstrated yet")
        return (f"We can't start with {node['name']} because {reason}. Learning it now "
                "would mean jumping the queue, so we won't sequence it early.")

    return (f"Good news: everything {node['name']} needs is already in place "
            "(your reported mastery clears the 0.75 bar), so you could start near it -- "
            "we only placed it later because higher-demand skills are unblocked first.")


def _nearest_unmet_chain(skill_id: str, by_id: dict, mastery_state: Dict[str, float]) -> List[str]:
    """Names the unmet ancestors of ``skill_id``, walking its first unmet prereq."""
    chain: List[str] = []
    seen = set()
    node = by_id.get(skill_id)
    while node is not None and node["id"] not in seen:
        seen.add(node["id"])
        unmet = [p for p in node.get("prerequisites", []) if (mastery_state.get(p, 0.0) or 0.0) < 0.75]
        if not unmet:
            break
        nxt = unmet[0]
        chain.append(by_id[nxt]["name"])
        node = by_id.get(nxt)
    return chain