import pytest

from core.retrieval import VectorIndex


class _FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]]):
        self._vectors = vectors

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors[text] for text in texts]


VECTORS = {
    "docker basics": [1.0, 0.0],
    "sql fundamentals": [0.0, 1.0],
    "kubernetes deep dive": [0.9, 0.1],
    "containerize an app": [1.0, 0.0],
}


@pytest.fixture
def embedder() -> _FakeEmbedder:
    return _FakeEmbedder(VECTORS)


@pytest.fixture
def index(embedder) -> VectorIndex:
    ids = ["doc-docker", "doc-sql", "doc-k8s"]
    texts = ["docker basics", "sql fundamentals", "kubernetes deep dive"]
    return VectorIndex.build(ids, texts, embedder)


def test_search_returns_closest_match_first(index, embedder):
    results = index.search("containerize an app", embedder, k=3)
    assert results[0][0] == "doc-docker"
    assert results[0][1] == pytest.approx(1.0, abs=1e-4)


def test_search_respects_k(index, embedder):
    results = index.search("containerize an app", embedder, k=1)
    assert len(results) == 1


def test_search_k_larger_than_index_size_is_capped(index, embedder):
    results = index.search("containerize an app", embedder, k=100)
    assert len(results) == 3


def test_build_rejects_mismatched_lengths(embedder):
    with pytest.raises(ValueError, match="same length"):
        VectorIndex.build(["a", "b"], ["only one text"], embedder)


def test_search_on_empty_index_returns_nothing(embedder):
    empty = VectorIndex.build([], [], embedder)
    assert empty.search("anything", embedder) == []


def test_save_and_load_round_trip(index, embedder, tmp_path):
    index.save(tmp_path)
    reloaded = VectorIndex.load(tmp_path)

    results = reloaded.search("containerize an app", embedder, k=1)
    assert results[0][0] == "doc-docker"
