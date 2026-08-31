"""Client wrapper for the PathForge API.

All calls degrade gracefully: when ``API_BASE_URL`` is unset (or the request
fails) the client falls back to the local ``mock`` fixtures so the UI never
breaks during development or a demo.

Env:
    API_BASE_URL   where Person A's FastAPI service lives (e.g. http://localhost:8000)
"""
import json
import os
from typing import Optional

import requests

import mock

API_BASE_URL = os.environ.get("API_BASE_URL", "").rstrip("/")


def _get(path: str, fallback):
    if not API_BASE_URL:
        return fallback()
    try:
        resp = requests.get(f"{API_BASE_URL}{path}", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return fallback()


def _post(path: str, payload: dict, fallback):
    if not API_BASE_URL:
        return fallback()
    try:
        resp = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return fallback()


# --------------------------------------------------------------------------
# endpoints used by the UI
# --------------------------------------------------------------------------

def get_roadmap(learner_id: Optional[str] = None) -> dict:
    q = f"?learner_id={learner_id}" if learner_id else ""
    return _get(f"/path/generate{q}", lambda: mock.MOCK_PATH)


def get_dashboard(learner_id: Optional[str] = None) -> dict:
    payload = _get("/dashboard" + (f"/{learner_id}" if learner_id else ""), lambda: None)
    if payload is not None:
        return payload
    return {
        "mastery": mock.MOCK_MASTERY,
        "timeline": mock.MOCK_TIMELINE,
        "next_action": mock.MOCK_NEXT_ACTION,
    }


def get_next_diagnostic_question(mastery: dict, asked_ids) -> Optional[dict]:
    data = _post("/diagnostic/next", {"mastery": mastery, "asked": list(asked_ids)}, lambda: None)
    if data is not None and data.get("question"):
        return data["question"]
    return _select_local(mastery, asked_ids)


def _select_local(mastery, asked_ids):
    bank = mock.load_item_bank()
    for item in bank:
        if item.get("id") in asked_ids:
            continue
        return {
            "id": item["id"],
            "skill_id": item["skill_id"],
            "text": item["text"],
            "options": item["options"],
            "correct_index": item["correct_index"],
        }
    return None


def submit_diagnostic_answer(question_id: str, skill_id: str, is_correct: bool) -> bool:
    ok = _post("/diagnostic/answer", {
        "question_id": question_id, "skill_id": skill_id, "correct": is_correct,
    }, lambda: True)
    return bool(ok)


def post_feedback(payload: dict) -> dict:
    return _post("/feedback", payload, lambda: {"status": "mock", **payload})


def explain(bundle: dict) -> str:
    data = _post("/explain", bundle, lambda: None)
    if data and data.get("explanation"):
        return data["explanation"]
    # offline: use the local evidence-grounded explainer
    return json.dumps({"note": "explainer not wired to a backend yet", "bundle": bundle})