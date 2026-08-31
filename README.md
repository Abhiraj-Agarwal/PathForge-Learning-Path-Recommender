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

Because the ordering comes from an algorithm, every explanation is grounded in something checkable: *"Docker unlocks MLOps and Model Deployment, and it appears in 68% of the job postings matched to your stated goal."*

---

## How it works

| Stage | What happens |
|---|---|
| **1. Understand the goal** | You describe your goal in chat, in plain English. It's embedded and matched against a corpus of real job descriptions; skills are extracted across the retrieved postings and weighted by how often they're actually demanded. |
| **2. Measure the learner** | A short adaptive diagnostic estimates mastery per skill using Bayesian Knowledge Tracing. |
| **3. Compute the gap** | The prerequisite closure of the target skills, minus everything already mastered. |
| **4. Order the gap** | Topological sort over the gap subgraph, with ties broken by market demand, grouped into milestones. |
| **5. Attach resources** | Courses ranked per skill by semantic similarity, rating and level fit. |
| **6. Pace and explain** | The gap is turned into a day-by-day schedule at your stated (or assumed) weekly hours, and every skill carries an evidence bundle — demand, impact, unmet prerequisites — the chat and the roadmap graph both read from. |

---

## Features

- **Conversational goal setting** — describe what you want in plain English; the chat runs the real planning pipeline live and replies with actual computed numbers, not a canned response.
- **Evidence-backed targets** — skill targets derived from real job descriptions, with demand percentages attached.
- **A real day-by-day schedule** — a full 4-week (month) plan, paced to your stated hours/week (defaults to 10 if you don't say), with course links embedded directly in the chat reply.
- **Adaptive diagnostic** — measures what you know instead of asking you to rate yourself.
- **Interactive knowledge graph** — the roadmap is a clickable, prerequisite-directed graph (not a static image): click any skill to zoom in and see why it's placed there, its relevance (market demand) and impact (how many other skills it unlocks) scores, and its top course matches.
- **Grounded explanations** — "why this?" and "why not X yet?" answered from graph facts, including which prerequisites are unmet.
- **Progress dashboard** — mastery-vs-demand radar and a milestone timeline anchored to real dates, built from your actual plan once one exists.

---

## Architecture

```
        Streamlit UI  ·  chat · roadmap · dashboard
                          │
              app/engine.py (in-process orchestration)
                          │
                LangGraph router (mode selection)
        ┌─────────┬───────┴────────┬──────────┐
        ▼         ▼                ▼          ▼
    Profiler   Goal Translator  Diagnostic  Planner   Explainer
               (JD retrieval)   (BKT)       (DAG)
        └─────────┴────────────────┴──────────┘
                          │
              Skill Graph (NetworkX) · FAISS
                          │
        skills.json · courses.json · jds.json · item_bank.json
```

`core/` is pure Python with no web-framework imports, which keeps the planning engine independently testable. There is no separate API server yet — `app/engine.py` calls `core/` directly and caches the heavy singletons (skill graph, embedder, FAISS indices) for the life of the Streamlit process. A FastAPI service sitting in front of the same `core/` code is a natural next step (see [Roadmap](#roadmap)) but isn't built yet — don't be surprised not to find an `api/` folder.

---

## Tech stack

| Layer | Tools |
|---|---|
| Interface | Streamlit, Plotly, Graphviz |
| Orchestration | LangGraph |
| Retrieval | sentence-transformers (`all-MiniLM-L6-v2`), FAISS |
| Graph | NetworkX |
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
cd PathForge-Learning-Path-Recommender

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env                # then add your API key
```

### Run

```bash
streamlit run app/main.py           # → localhost:8501
```

That's it — one command, no separate index-building step and no second server. The skill graph and the course/job FAISS indices are built in-process the first time you send a goal (or click **Load demo learner** in the sidebar), and cached for the rest of the session. That first goal message takes roughly 15–20 seconds (one-time embedding-model load); every message after that is fast.

### Environment variables

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | `groq` or `gemini` | `groq` |
| `LLM_API_KEY` | Your provider API key | — |
| `API_BASE_URL` | Optional: point the UI at a FastAPI service once one exists. Leave blank to run entirely against the local engine (the normal way to run this today). | *(blank)* |

---

## Project structure

```
PathForge-Learning-Path-Recommender/
├── app/                    # Streamlit interface + the in-process "backend"
│   ├── main.py             # entry point, theme, sidebar, tabs
│   ├── engine.py           # orchestrates core/ into one goal -> plan pipeline, cached
│   ├── schedule.py         # turns a plan into a paced day-by-day schedule
│   ├── api_client.py       # optional API wrapper (falls back to local mock if API_BASE_URL unset)
│   ├── mock.py             # fixtures used before a plan exists / as a cold-start preview
│   ├── views/              # chat · roadmap · dashboard · diagnostic
│   └── components/         # knowledge_graph · graph_view · radar · timeline · resource_card
│
├── core/                   # planning engine (no web-framework imports)
│   ├── graph.py            # skill DAG loading and validation
│   ├── planner.py          # gap → topological order → milestones
│   ├── profiler.py         # profile extraction + mastery seeding
│   ├── goal_translator.py  # job-description retrieval → target skills
│   ├── diagnostic.py       # Bayesian Knowledge Tracing + item selection
│   ├── retrieval.py        # FAISS index build / load / query
│   ├── ranker.py           # resource scoring
│   ├── skill_matcher.py    # free text → canonical skill ID
│   └── llm.py              # provider abstraction with retries
│
├── agents/                 # LangGraph router and explainer
├── schemas/                # Pydantic models + example payloads
├── data/                   # skill graph, course catalog, job descriptions, item bank
├── scripts/                # dataset generation and tag normalisation
├── tests/                  # planner, graph, matcher, BKT, agents
└── .streamlit/config.toml  # theme
```

`api/` and `db/` don't exist yet — see [Architecture](#architecture).

---

## Data

| File | Contents |
|---|---|
| `data/skills.json` | Skill nodes with aliases, clusters and prerequisite edges |
| `data/courses.json` | Course catalog tagged with canonical skill IDs |
| `data/jds.json` | Job description corpus used to derive target skills |
| `data/item_bank.json` | Reviewed multiple-choice items for the diagnostic |

---

## Testing

```bash
python -m pytest
```

Use `python -m pytest`, not a bare `pytest` — the latter doesn't add the project root to `sys.path`, so `core`/`agents`/`schemas` imports fail with `ModuleNotFoundError` even though the tests are fine.

Covers path validity (every prerequisite precedes its dependent), graph acyclicity and ancestor closure, skill matching thresholds, mastery convergence under the diagnostic model, and the router/explainer agents.

---

## Roadmap

- A FastAPI service in front of `core/` (Section 4.9 of the original plan), so the engine isn't tied to one Streamlit process
- Persistence (a learner's plan and progress currently live only in session state)
- Thompson-sampling bandit over resource modality, learned from learner feedback
- Skill decay modelling — mastery discounted by time since last use
- Multi-goal arbitration — shared prerequisite core across several simultaneous goals
- Cohort mode — batch paths and skill-gap heatmaps for a class or team
- Auto-mined prerequisite edges extracted from course descriptions

---

## License

MIT
