"""Goal text -> demand-weighted target skills.

No LLM call anywhere in here (PathForge-Plan.md Section 4.3): retrieve the
job postings closest to the stated goal via FAISS, then count which real
skills actually appear in that real text via plain alias matching. This is
what lets the explainer later cite a number: "Docker appears in 68% of the
50 postings closest to your goal."
"""

from __future__ import annotations

from core.graph import SkillGraph
from core.retrieval import Embedder, VectorIndex
from schemas.models import SkillNode, TargetSkill, TargetSkillsResponse

DEFAULT_TOP_K = 50
DEFAULT_MIN_DEMAND = 0.15


def translate_goal(
    goal_text: str,
    graph: SkillGraph,
    jd_index: VectorIndex,
    jd_texts: dict[str, str],
    embedder: Embedder,
    top_k: int = DEFAULT_TOP_K,
    min_demand: float = DEFAULT_MIN_DEMAND,
) -> TargetSkillsResponse:
    retrieved_ids = [jd_id for jd_id, _score in jd_index.search(goal_text, embedder, k=top_k)]
    retrieved_texts = [jd_texts[jd_id] for jd_id in retrieved_ids if jd_id in jd_texts]

    if not retrieved_texts:
        return TargetSkillsResponse(goal_text=goal_text, targets=[])

    targets = []
    for skill_id in graph.skill_ids:
        node = graph.get(skill_id)
        evidence_count = _count_mentions(node, retrieved_texts)
        demand = evidence_count / len(retrieved_texts)
        if demand >= min_demand:
            targets.append(TargetSkill(skill_id=skill_id, demand=demand, evidence_count=evidence_count))

    targets.sort(key=lambda t: t.demand, reverse=True)
    return TargetSkillsResponse(goal_text=goal_text, targets=targets)


def _count_mentions(node: SkillNode, texts: list[str]) -> int:
    candidates = [candidate.lower() for candidate in [node.name, *node.aliases]]
    return sum(1 for text in texts if any(candidate in text.lower() for candidate in candidates))
