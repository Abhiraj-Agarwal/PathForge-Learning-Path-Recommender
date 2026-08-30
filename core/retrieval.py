"""Generic embed-and-search helper over FAISS.

Reused for job-description search (goal translator) and course search
(ranker) - same mechanism, pointed at a different pre-built index
(PathForge-Plan.md Section 4.3: "Embed all JDs once ... index with FAISS,
persist to disk").
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import faiss
import numpy as np


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class VectorIndex:
    """A FAISS index of embedded texts, addressable by caller-supplied ids.

    Vectors are L2-normalized before indexing so inner product = cosine
    similarity, matching the similarity notion used in core/skill_matcher.py.
    """

    def __init__(self, ids: list[str], index: faiss.Index) -> None:
        self._ids = ids
        self._index = index

    @classmethod
    def build(cls, ids: list[str], texts: list[str], embedder: Embedder) -> VectorIndex:
        if len(ids) != len(texts):
            raise ValueError("ids and texts must be the same length")
        if not ids:
            return cls([], faiss.IndexFlatIP(1))  # dimension is unused - search() short-circuits on empty
        vectors = _normalize(np.array(embedder.embed(texts), dtype="float32"))
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        return cls(list(ids), index)

    def search(self, query: str, embedder: Embedder, k: int = 10) -> list[tuple[str, float]]:
        k = min(k, len(self._ids))
        if k == 0:
            return []
        query_vector = _normalize(np.array(embedder.embed([query]), dtype="float32"))
        scores, positions = self._index.search(query_vector, k)
        return [
            (self._ids[position], float(score))
            for position, score in zip(positions[0], scores[0])
            if position != -1
        ]

    def save(self, dir_path: str | Path) -> None:
        dir_path = Path(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(dir_path / "index.faiss"))
        (dir_path / "ids.json").write_text(json.dumps(self._ids))

    @classmethod
    def load(cls, dir_path: str | Path) -> VectorIndex:
        dir_path = Path(dir_path)
        index = faiss.read_index(str(dir_path / "index.faiss"))
        ids = json.loads((dir_path / "ids.json").read_text())
        return cls(ids, index)


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms
