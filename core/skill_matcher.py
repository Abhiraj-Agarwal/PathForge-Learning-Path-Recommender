"""Free text -> canonical skill id.

Never lets the LLM invent skill ids (PathForge-Plan.md Section 4.2): text is
matched against real skills by exact alias match first, then by embedding
similarity. If neither is confident enough, returns None so the caller can
route it into an "unmapped" list instead of guessing.
"""

from __future__ import annotations

from typing import Protocol

from core.graph import SkillGraph

DEFAULT_SIMILARITY_THRESHOLD = 0.55


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def match_skill(
    text: str,
    graph: SkillGraph,
    embedder: Embedder,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> str | None:
    alias_hit = _match_by_alias(text, graph)
    if alias_hit is not None:
        return alias_hit
    return _match_by_embedding(text, graph, embedder, threshold)


def _match_by_alias(text: str, graph: SkillGraph) -> str | None:
    normalized = _normalize(text)
    for skill_id in graph.skill_ids:
        node = graph.get(skill_id)
        if any(_normalize(candidate) == normalized for candidate in [node.name, *node.aliases]):
            return skill_id
    return None


def _match_by_embedding(
    text: str, graph: SkillGraph, embedder: Embedder, threshold: float
) -> str | None:
    skill_ids = sorted(graph.skill_ids)
    candidate_names = [graph.get(skill_id).name for skill_id in skill_ids]

    vectors = embedder.embed([text, *candidate_names])
    query_vector, skill_vectors = vectors[0], vectors[1:]

    best_id, best_score = None, -1.0
    for skill_id, vector in zip(skill_ids, skill_vectors):
        score = _cosine_similarity(query_vector, vector)
        if score > best_score:
            best_id, best_score = skill_id, score

    return best_id if best_score >= threshold else None


def _normalize(text: str) -> str:
    return text.strip().lower()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SentenceTransformerEmbedder:
    """Real Embedder backed by sentence-transformers/all-MiniLM-L6-v2 (README tech stack).

    Lazy-imported so building/testing the matching logic above never requires
    the model to be installed or downloaded - same pattern as core/llm.py's
    provider calls.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts).tolist()
