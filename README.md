# PathForge

**An AI-powered personalized learning path recommender.**

Most learning platforms tell you *what* to study. PathForge tells you *in what order* — and why.

---

## The problem

Online platforms host thousands of courses, and recommendation engines are good at surfacing relevant ones. But a ranked list of relevant courses isn't a learning plan. Learners still have to work out what comes first, what they can safely skip, and what they're not ready for yet.

Three failures make generic roadmaps unreliable:

1. **No ordering logic.** A relevance score says a course is *related*, not that it's *next*.
2. **No real skill assessment.** "Rate yourself: beginner / intermediate / advanced" is self-report noise — and it's the single biggest input to the whole system.
3. **Unfalsifiable explanations.** If a language model writes both the plan and the justification for the plan, the justification is narration, not reasoning. Neither the learner nor anyone else can check it.

## The approach

> **The graph decides the path. The LLM only explains it.**

PathForge models the learning domain as a **directed acyclic graph of skills**, where an edge means "this must come before that." Roadmaps are produced by deterministic graph traversal — not by asking a model to guess an order. The language model is confined to what language models are actually good at: parsing messy human text into structure, and turning already-computed facts into readable sentences.

Because the ordering comes from an algorithm, every explanation is grounded in something checkable: *"Docker is step 4 because it unlocks CI/CD, and it appears in 68% of the 50 job postings closest to your stated goal."*

---

## How it works

| Stage | What happens |
|---|---|
| **1. Understand the goal** | The stated goal is embedded and matched against a corpus of real job descriptions. Skills are extracted across the retrieved postings and weighted by how often they're actually demanded. |
| **2. Measure the learner** | A short adaptive diagnostic estimates mastery per skill using Bayesian Knowledge Tracing, seeded from the learner's stated history. |
| **3. Compute the gap** | The prerequisite closure of the target skills, minus everything already mastered. |
| **4. Order the gap** | Topological sort over the gap subgraph, with ties broken by market demand, grouped into milestones by graph depth. |
| **5. Attach resources** | Courses ranked per skill by semantic similarity, rating and level fit; a project per milestone; an assessment at each boundary. |
| **6. Explain and adapt** | Every step carries an evidence bundle. Progress updates trigger a re-plan. |

---

## Features

- **Conversational goal setting** — describe what you want in plain English; no dropdowns, no forms.
- **Evidence-backed targets** — skill targets derived from real job descriptions, with demand percentages attached.
- **Adaptive diagnostic** — measures what you know instead of asking you to rate yourself.
- **Prerequisite-aware sequencing** — a valid learning order, computed over a skill graph.
- **Grounded explanations** — "why this?" and "why not X yet?" answered from graph facts, including which prerequisites are unmet.
- **Progress dashboard** — roadmap DAG, mastery-vs-demand radar, milestone timeline, next unblocked actions.
- **Adaptive re-planning** — completing or skipping a milestone reshapes what's ahead.

---

## Architecture

```
        Streamlit UI  ·  chat · roadmap · dashboard
                          │
                   FastAPI service
                          │
                LangGraph router (mode selection)
        ┌─────────┬───────┴────────┬──────────┐
        ▼         ▼                ▼          ▼
    Profiler   Goal Translator  Diagnostic  Planner   Explainer
               (JD retrieval)   (BKT)       (DAG)
        └─────────┴────────────────┴──────────┘
                          │
        Skill Graph (NetworkX) · FAISS · SQLite
                          │
        skills.json · courses.json · jds.json · item_bank.json
```

`core/` is pure Python with no web-framework imports, which keeps the planning engine independently testable and lets the UI import it directly when the API is unavailable.

---

## Tech stack

| Layer | Tools |
|---|---|
| Interface | Streamlit, Plotly, Graphviz |
| API | FastAPI, Pydantic v2 |
| Orchestration | LangGraph |
| Retrieval | sentence-transformers (`all-MiniLM-L6-v2`), FAISS |
| Graph | NetworkX |
| Persistence | SQLAlchemy, SQLite |
| LLM | Groq or Google Gemini (configurable) |

**Techniques used:** embedding-based retrieval, demand-weighted RAG extraction, Bayesian Knowledge Tracing, DAG topological planning, weighted multi-signal re-ranking, LLM-based orchestration and grounded explanation.

---

## Getting started

### Prerequisites

- Python 3.11+
- An LLM API key — [Groq](https://console.groq.com) or [Google AI Studio](https://aistudio.google.com) (both have free tiers)

### Installation

```bash
git clone <repository-url>
cd pathforge

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env                # then add your API key
```

### Build the indices

```bash
python scripts/build_indices.py     # embeds catalog + job descriptions, validates the skill graph
```

### Run

Two terminals:

```bash
uvicorn api.main:app --reload --port 8000     # API   → localhost:8000/docs
```

```bash
streamlit run app/main.py                     # UI    → localhost:8501
```

Or run the UI standalone, with the engine imported directly and no API server:

```bash
USE_LOCAL_CORE=true streamlit run app/main.py
```

### Environment variables

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | `groq` or `gemini` | `groq` |
| `LLM_API_KEY` | Your provider API key | — |
| `API_BASE_URL` | Where the UI finds the API | `http://localhost:8000` |
| `USE_LOCAL_CORE` | Bypass the API; import `core/` directly | `false` |

---

## API

Interactive docs at `/docs` once the server is running.

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/profile` | Free text → structured learner profile with seeded mastery |
| `POST` | `/goal/translate` | Goal text → demand-weighted target skills |
| `GET` | `/diagnostic/next` | Next adaptive diagnostic item |
| `POST` | `/diagnostic/answer` | Submit an answer → updated mastery |
| `POST` | `/path/generate` | Mastery + targets → full learning path |
| `POST` | `/path/replan` | Progress → updated learning path |
| `POST` | `/explain` | Skill → grounded explanation |
| `POST` | `/progress` | Mark a skill complete |
| `POST` | `/feedback` | Rate a recommended resource |
| `GET` | `/dashboard/{learner_id}` | Everything one dashboard screen needs, in one call |

---

## Project structure

```
pathforge/
├── app/                  # Streamlit interface
│   ├── main.py           # entry point, tabs, session state
│   ├── api_client.py     # API wrapper
│   ├── views/            # chat · roadmap · dashboard · diagnostic
│   └── components/       # graph_view · radar · timeline · resource_card
│
├── api/                  # FastAPI service
│   ├── main.py           # app factory, CORS, startup loading
│   ├── deps.py           # cached singletons: graph, indices, LLM, DB
│   └── routes/           # one module per endpoint group
│
├── core/                 # planning engine (no web-framework imports)
│   ├── graph.py          # skill DAG loading and validation
│   ├── planner.py        # gap → topological order → milestones
│   ├── profiler.py       # profile extraction + mastery seeding
│   ├── goal_translator.py# job-description retrieval → target skills
│   ├── diagnostic.py     # Bayesian Knowledge Tracing + item selection
│   ├── retrieval.py      # FAISS index build / load / query
│   ├── ranker.py         # resource scoring
│   ├── skill_matcher.py  # free text → canonical skill ID
│   └── llm.py            # provider abstraction with retries
│
├── agents/               # LangGraph router and explainer
├── schemas/              # Pydantic models + example payloads
├── data/                 # skill graph, course catalog, job descriptions, item bank
├── db/                   # SQLAlchemy models
├── scripts/              # index building, graph validation, tag normalisation
├── tests/                # planner, graph, matcher, BKT
└── docs/                 # solution document, architecture diagram, screenshots
```

---

## Data

| File | Contents |
|---|---|
| `data/skills.json` | Skill nodes with aliases, clusters and prerequisite edges |
| `data/courses.json` | Course catalog tagged with canonical skill IDs |
| `data/jds.json` | Job description corpus used to derive target skills |
| `data/item_bank.json` | Reviewed multiple-choice items for the diagnostic |

Generated FAISS indices and raw source dumps live under `data/indices/` and `data/raw/` and are excluded from version control.

---

## Testing

```bash
pytest
```

Covers path validity (every prerequisite precedes its dependent), graph acyclicity and ancestor closure, skill matching thresholds, and mastery convergence under the diagnostic model.

---

## Roadmap

- Thompson-sampling bandit over resource modality, learned from learner feedback
- Skill decay modelling — mastery discounted by time since last use
- Multi-goal arbitration — shared prerequisite core across several simultaneous goals
- Cohort mode — batch paths and skill-gap heatmaps for a class or team
- Auto-mined prerequisite edges extracted from course descriptions

---

## License

MIT
