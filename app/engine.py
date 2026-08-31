"""Wires the real core/ pipeline into the Streamlit app.

Until Person A's FastAPI service exists, this module IS the "backend": it
loads the skill graph and builds the FAISS indices once per server process
(cached), then exposes one entry point -- ``build_plan_from_goal`` -- that
runs the same deterministic sequence the API will eventually expose:

    goal text -> demand-weighted target skills (goal_translator)
              -> gap + milestone ordering        (planner)
              -> ranked course resources          (ranker)

Nothing here invents a fact: every number in the result traces back to the
skill graph, the job-description corpus or the course catalog.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import streamlit as st

from core.goal_translator import translate_goal
from core.graph import SkillGraph
from core.planner import generate_path
from core.ranker import rank_courses_for_skill
from core.retrieval import VectorIndex
from schemas.models import Course, LearningPath, TargetSkill

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_HOURS_PER_WEEK = 10.0
GOAL_TOP_K = 15  # narrower than the API default so demand reflects THIS goal, not the whole corpus

_HOURS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\s*(?:a|per|/)?\s*week", re.IGNORECASE)


class _BagOfWordsEmbedder:
    """Offline fallback used only if sentence-transformers can't reach the
    model hub (e.g. no network). Same ``.embed(texts)`` contract as the real
    embedder, just a plain term-frequency vector -- weaker retrieval, but the
    pipeline keeps working instead of failing the whole chat turn."""

    _TOKEN_RE = re.compile(r"[a-z0-9]+")

    def __init__(self, vocabulary: list[str]):
        self._vocab = {tok: i for i, tok in enumerate(vocabulary)}

    def embed(self, texts: list[str]) -> list[list[float]]:
        import numpy as np

        vectors = np.zeros((len(texts), max(len(self._vocab), 1)), dtype="float32")
        for row, text in enumerate(texts):
            for tok in self._TOKEN_RE.findall(text.lower()):
                idx = self._vocab.get(tok)
                if idx is not None:
                    vectors[row, idx] += 1.0
        return vectors.tolist()


def _build_embedder(corpus_texts: list[str]):
    try:
        from core.skill_matcher import SentenceTransformerEmbedder

        embedder = SentenceTransformerEmbedder()
        embedder.embed(["warmup"])  # force the load now so failures surface here, not mid-query
        return embedder
    except Exception:
        vocabulary: set[str] = set()
        for text in corpus_texts:
            vocabulary.update(_BagOfWordsEmbedder._TOKEN_RE.findall(text.lower()))
        return _BagOfWordsEmbedder(sorted(vocabulary))


@st.cache_resource(show_spinner="Loading the skill graph and building course/job indices (first time only)...")
def load_pipeline():
    """Heavy, process-lifetime singletons: graph + embedder + two FAISS indices."""
    graph = SkillGraph.from_file(DATA_DIR / "skills.json")

    courses_raw = json.loads((DATA_DIR / "courses.json").read_text(encoding="utf-8"))
    jds_raw = json.loads((DATA_DIR / "jds.json").read_text(encoding="utf-8"))

    courses_by_id = {c["id"]: Course.model_validate(c) for c in courses_raw}
    jd_texts = {jd["id"]: jd.get("description", "") for jd in jds_raw}
    skill_names = [graph.get(sid).name for sid in graph.skill_ids]

    corpus = [f"{c['title']} {c['description']}" for c in courses_raw] + list(jd_texts.values()) + skill_names
    embedder = _build_embedder(corpus)

    course_texts = [f"{c['title']} {c['description']}" for c in courses_raw]
    course_index = VectorIndex.build([c["id"] for c in courses_raw], course_texts, embedder)
    jd_index = VectorIndex.build(list(jd_texts.keys()), list(jd_texts.values()), embedder)

    return graph, embedder, course_index, courses_by_id, jd_index, jd_texts


def extract_hours_per_week(text: str) -> float | None:
    """Pulls an explicit '10 hours a week' style mention out of free text."""
    match = _HOURS_RE.search(text)
    return float(match.group(1)) if match else None


def build_plan_from_goal(goal_text: str, mastery: dict[str, float],
                         hours_per_week: float | None = None) -> dict:
    """Runs the full deterministic pipeline for one goal statement.

    Returns a dict bundling everything the UI needs to render both the chat
    summary and the roadmap graph, so both views describe the same plan.
    """
    graph, embedder, course_index, courses_by_id, jd_index, jd_texts = load_pipeline()

    targets_response = translate_goal(goal_text, graph, jd_index, jd_texts, embedder, top_k=GOAL_TOP_K)
    targets: list[TargetSkill] = targets_response.targets

    hours = hours_per_week or extract_hours_per_week(goal_text) or DEFAULT_HOURS_PER_WEEK

    path: LearningPath = generate_path(graph, targets, mastery, learner_id="chat_learner", hours_per_week=hours)

    for milestone in path.milestones:
        for planned in milestone.skills:
            skill_name = graph.get(planned.skill_id).name
            planned.course_ids = rank_courses_for_skill(
                skill_name, mastery.get(planned.skill_id, 0.0), course_index, courses_by_id, embedder
            )

    return {
        "goal_text": goal_text,
        "graph": graph,
        "targets": targets,
        "path": path,
        "courses_by_id": courses_by_id,
        "hours_per_week": hours,
        "demand_by_id": {t.skill_id: t.demand for t in targets},
        "evidence_by_id": {t.skill_id: t.evidence_count for t in targets},
    }


def get_graph() -> SkillGraph:
    return load_pipeline()[0]


def get_courses_for_skill(skill_id: str, mastery_value: float, top_n: int = 2) -> list[Course]:
    """On-demand course lookup for a single skill -- used by the roadmap's
    node-click detail panel, independent of whether a full goal plan exists."""
    graph, embedder, course_index, courses_by_id, _, _ = load_pipeline()
    skill_name = graph.get(skill_id).name
    course_ids = rank_courses_for_skill(
        skill_name, mastery_value, course_index, courses_by_id, embedder, top_n=top_n
    )
    return [courses_by_id[cid] for cid in course_ids if cid in courses_by_id]
