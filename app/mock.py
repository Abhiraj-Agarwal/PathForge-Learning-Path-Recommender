"""Local fixtures: run the whole Streamlit UI with no backend.

Every screen consumes data from this module. When Person A's API is ready,
`app/api_client.py` will expose the same-shaped functions and the views can
swap `mock` for `api_client` in one place.

Data files (data/*.json) are loaded when present and the module falls back to
self-contained fixtures when they are missing or empty, so the UI can render
on a fresh checkout before the generator has been run.
"""
import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# --------------------------------------------------------------------------
# data file loaders with graceful fallbacks
# --------------------------------------------------------------------------

def _load(name, default):
    path = DATA_DIR / f"{name}.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        return rows if isinstance(rows, list) and rows else default
    except (OSError, json.JSONDecodeError):
        return default


@lru_cache(maxsize=1)
def load_skills():
    return _load("skills", _FALLBACK_SKILLS)


@lru_cache(maxsize=1)
def load_courses():
    return _load("courses", _FALLBACK_COURSES)


@lru_cache(maxsize=1)
def load_jds():
    return _load("jds", _FALLBACK_JDS)


@lru_cache(maxsize=1)
def load_item_bank():
    return _load("item_bank", _FALLBACK_ITEMS)


def load_item(skill_id):
    bank = load_item_bank()
    for item in bank:
        if item.get("skill_id") == skill_id:
            return item
    return None


# --------------------------------------------------------------------------
# roadmap DAG, grouped by milestone (real skill ids from data/skills.json)
# --------------------------------------------------------------------------

MOCK_PATH = {
    "role": "ML Engineer",
    "milestones": {
        1: [
            {"skill_id": "python_basics", "name": "Python Fundamentals", "status": "mastered"},
            {"skill_id": "git_github", "name": "Git & GitHub", "status": "mastered"},
            {"skill_id": "linear_algebra", "name": "Linear Algebra", "status": "in_progress"},
            {"skill_id": "probability_statistics", "name": "Probability & Statistics", "status": "in_progress"},
        ],
        2: [
            {"skill_id": "python_ml_tooling", "name": "Python for Data (NumPy/Pandas)", "status": "mastered"},
            {"skill_id": "sql_basics", "name": "SQL Basics", "status": "in_progress"},
            {"skill_id": "data_visualization", "name": "Data Visualization", "status": "upcoming"},
        ],
        3: [
            {"skill_id": "ml_fundamentals", "name": "ML Fundamentals", "status": "upcoming"},
            {"skill_id": "supervised_learning", "name": "Supervised Learning", "status": "upcoming"},
            {"skill_id": "model_evaluation", "name": "Model Evaluation", "status": "upcoming"},
            {"skill_id": "feature_engineering", "name": "Feature Engineering", "status": "upcoming"},
        ],
        4: [
            {"skill_id": "deep_learning", "name": "Deep Learning", "status": "upcoming"},
            {"skill_id": "neural_networks", "name": "Neural Networks (PyTorch/TF)", "status": "upcoming"},
        ],
        5: [
            {"skill_id": "docker", "name": "Docker & Containers", "status": "upcoming"},
            {"skill_id": "mlops", "name": "MLOps", "status": "upcoming"},
            {"skill_id": "model_deployment", "name": "Model Deployment", "status": "upcoming"},
        ],
    },
    "edges": [
        ("python_basics", "python_ml_tooling"),
        ("python_ml_tooling", "data_visualization"),
        ("python_ml_tooling", "ml_fundamentals"),
        ("linear_algebra", "ml_fundamentals"),
        ("probability_statistics", "ml_fundamentals"),
        ("ml_fundamentals", "supervised_learning"),
        ("supervised_learning", "model_evaluation"),
        ("python_ml_tooling", "feature_engineering"),
        ("data_visualization", "feature_engineering"),
        ("supervised_learning", "deep_learning"),
        ("deep_learning", "neural_networks"),
        ("docker", "mlops"),
        ("model_evaluation", "mlops"),
        ("mlops", "model_deployment"),
    ],
}

# --------------------------------------------------------------------------
# dashboard: mastery radar + milestone gantt timeline
# --------------------------------------------------------------------------

MOCK_MASTERY = {
    "skills": ["Python", "Linear Algebra", "Probability", "SQL", "ML Fundamentals", "Docker"],
    "current": [0.8, 0.5, 0.3, 0.4, 0.1, 0.0],
    "target": [0.9, 0.8, 0.7, 0.5, 0.9, 0.6],
}

# skill_id -> mastery, mirrors MOCK_MASTERY["current"] for the BKT engine
MOCK_MASTERY_BY_SKILL = {
    "python_basics": 0.8,
    "linear_algebra": 0.5,
    "probability_statistics": 0.3,
    "sql_basics": 0.4,
    "ml_fundamentals": 0.1,
    "docker": 0.0,
}

MOCK_TIMELINE = [
    {"Task": "Milestone 1: Foundations", "Start": "2026-09-01", "Finish": "2026-09-15", "Status": "In Progress"},
    {"Task": "Milestone 2: Data Tooling", "Start": "2026-09-16", "Finish": "2026-10-05", "Status": "In Progress"},
    {"Task": "Milestone 3: Core ML", "Start": "2026-10-06", "Finish": "2026-11-15", "Status": "Upcoming"},
    {"Task": "Milestone 4: Deep Learning", "Start": "2026-11-16", "Finish": "2026-12-20", "Status": "Upcoming"},
    {"Task": "Milestone 5: Production & MLOps", "Start": "2026-12-21", "Finish": "2027-01-31", "Status": "Upcoming"},
]

# --------------------------------------------------------------------------
# diagnostic quiz fixtures (serve from the real item bank when available)
# --------------------------------------------------------------------------

MOCK_QUESTION = {
    "skill_id": "python_basics",
    "text": "Which data structure is immutable in Python?",
    "options": ["List", "Dictionary", "Set", "Tuple"],
    "correct_index": 3,
}

MOCK_QUESTION_BANK = [
    {"id": "q_python_1", "skill_id": "python_basics", "text": "Which data structure is immutable in Python?",
     "options": ["List", "Dictionary", "Set", "Tuple"], "correct_index": 3, "difficulty": "easy"},
    {"id": "q_git_1", "skill_id": "git_github", "text": "Which command saves your changes to the local repository?",
     "options": ["git push", "git commit", "git add", "git clone"], "correct_index": 1, "difficulty": "easy"},
    {"id": "q_sql_1", "skill_id": "sql_basics", "text": "Which clause filters rows BEFORE grouping?",
     "options": ["WHERE", "HAVING", "GROUP BY", "ORDER BY"], "correct_index": 0, "difficulty": "medium"},
    {"id": "q_linear_1", "skill_id": "linear_algebra", "text": "Which mathematics deals with vectors and matrices?",
     "options": ["Calculus", "Linear algebra", "Number theory", "Trigonometry"], "correct_index": 1, "difficulty": "easy"},
    {"id": "q_stats_1", "skill_id": "probability_statistics", "text": "What does a p-value below 0.05 typically suggest?",
     "options": ["The result is unlikely under the null hypothesis", "The sample size is too large",
                 "The experiment is definitely correct", "The data has no variance"],
     "correct_index": 0, "difficulty": "medium"},
    {"id": "q_ml_1", "skill_id": "ml_fundamentals", "text": "Which term describes learning from unlabelled data?",
     "options": ["Supervised learning", "Unsupervised learning", "Reinforcement learning", "Transfer learning"],
     "correct_index": 1, "difficulty": "medium"},
    {"id": "q_sl_1", "skill_id": "supervised_learning", "text": "Which problem is classification?",
     "options": ["Predicting a house price", "Detecting whether an email is spam",
                 "Estimating revenue next quarter", "Forecasting temperature"],
     "correct_index": 1, "difficulty": "medium"},
    {"id": "q_docker_1", "skill_id": "docker", "text": "What does a Docker container primarily provide?",
     "options": ["An isolated environment with the app and its dependencies",
                 "A hosted git repository", "A SQL database engine", "A JavaScript runtime"],
     "correct_index": 0, "difficulty": "easy"},
]

# --------------------------------------------------------------------------
# roadmap "next action" resource cards  (👍 / 👎 targeting through app/api_client)
# --------------------------------------------------------------------------

MOCK_NEXT_ACTION = {
    "milestone": 3,
    "skill": "ML Fundamentals",
    "resources": [
        {
            "id": "c014",
            "title": "Machine Learning Specialization",
            "provider": "DeepLearning.AI",
            "type": "course",
            "url": "https://www.deeplearning.ai",
            "justification": "It is the most common on-ramp: module 1 alone covers the model pipeline you are missing.",
        },
        {
            "id": "c015",
            "title": "Applied Machine Learning with scikit-learn",
            "provider": "edX",
            "type": "course",
            "url": "https://www.edx.org",
            "justification": "Hands-on and shorter than the specialization -- good for verifying Linear Algebra before you move on.",
        },
    ],
}

MOCK_EVIDENCE = {
    "skill": "Docker & Containers",
    "skill_id": "docker",
    "position": 3,
    "unlocks": ["mlops", "model_deployment"],
    "demand_pct": 68,
    "evidence_count": 34,
    "current_mastery": 0.15,
    "prereqs_satisfied": ["command_line", "git_github"],
    "prereqs_missing": ["kubernetes"],
}

# --------------------------------------------------------------------------
# demo learner (one-command hydrates a full profile for demos/tests)
# --------------------------------------------------------------------------

MOCK_PROFILE = {
    "learner_id": "learner_demo_001",
    "name": "Demo Learner",
    "goal": "Become an ML Engineer",
    "experience": "CS undergrad, comfortable with Python, some data analysis.",
    "hours_per_week": 8,
    "deadline": "2027-01-31",
}

# --------------------------------------------------------------------------
# hand-written fallbacks when data/ is empty (blank/new checkout)
# --------------------------------------------------------------------------

_FALLBACK_SKILLS = [
    {"id": "python_basics", "name": "Python Fundamentals",
     "aliases": ["python"], "cluster": "foundations", "prerequisites": []},
    {"id": "ml_fundamentals", "name": "Machine Learning Fundamentals",
     "aliases": ["machine learning"], "cluster": "ml_engineer",
     "prerequisites": ["python_basics"]},
]

_FALLBACK_COURSES = [
    {"id": "c001", "title": "Python for Everybody", "provider": "Coursera",
     "url": "https://www.py4e.com", "description": "Intro Python.",
     "level": "beginner", "rating": 4.8, "duration_hours": 60,
     "skill_tags": ["python"], "skill_ids": ["python_basics"]},
]

_FALLBACK_JDS = [
    {"id": "jd000", "title": "Machine Learning Engineer", "company": "Acme",
     "role_family": "ml_engineer", "location": "Remote", "seniority": "Mid-level",
     "description": "Build ML systems in Python.", "skills": ["python_basics", "ml_fundamentals"]},
]

_FALLBACK_ITEMS = [MOCK_QUESTION]