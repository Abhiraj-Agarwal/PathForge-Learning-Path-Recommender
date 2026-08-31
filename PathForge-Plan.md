# PathForge — AI-Powered Personalized Learning Path Recommender

**Team:** 2 · **Build:** 6 days + 1 finalize day · **Deploy:** Streamlit Cloud (UI) + Render (API)

---

## 1. What We're Building

A learner types a goal in plain English — *"I'm a CS student, decent at Python, want an AI/ML role"* — and gets back an **ordered roadmap** of skills, courses, projects and checkpoints, with a reason attached to every step.

**The key difference from a normal recommender:** most systems return a *ranked list* of relevant courses. Ours returns a *sequence*, because it models which skills must come before which others.

**One-line pitch:** *the graph decides the path; the LLM only explains it.*

---

## 2. How It Works (the core loop)

1. **Understand the goal** → pull real job descriptions matching it, extract what skills the market actually demands.
2. **Measure the learner** → short adaptive quiz estimates how well they already know each skill.
3. **Compute the gap** → target skills minus known skills.
4. **Order the gap** → walk a prerequisite graph to produce a valid learning sequence with milestones.
5. **Fill in resources** → attach courses, a project, and an assessment to each step.
6. **Explain and adapt** → justify each choice; re-plan as the learner completes things.

---

## 3. Architecture

```
   Streamlit UI  (chat · roadmap · dashboard)          [B]
             │
        FastAPI service                                 [A]
             │
        Router (picks the mode)                         [B]
   ┌─────────┼──────────┬──────────┐
   ▼         ▼          ▼          ▼
 Profiler  Goal      Diagnostic  Planner   Explainer
   [A]     Translator   +BKT      [A]        [B]
            [A]         [B]
   └─────────┴──────────┴──────────┘
             │
   Skill Graph · FAISS index · SQLite
             │
   Data: skills.json · courses.json · jds.json          [B]
```

---

## 4. Components

For each: a plain description anyone can read, then the owner's actual to-do list.

---

### 4.1 Data Layer — `[B]`

**What it is.** The raw material. Three files: a map of skills and which ones require which, a catalog of courses tagged by the skills they teach, and a pile of real job descriptions. Everything else in the system reads from these.

**Person B steps:**
1. Build `data/skills.json`: `{id, name, aliases[], cluster, prerequisites[]}`. Cover **3–4 role families** (e.g. ML Engineer, Data Analyst, Backend, Frontend) at ~60–90 skills each. Draft with LLM help, then **hand-check every prerequisite edge** — this is the single highest-value artefact in the project.
2. Build `data/courses.json` from a public Coursera/Udemy catalog dump: `{id, title, provider, url, description, level, rating, duration_hours, skill_tags[]}`.
3. Run `scripts/normalize_tags.py` to map messy `skill_tags` onto canonical skill IDs. **Untagged courses are invisible to the planner** — budget real time here.
4. Build `data/jds.json`: 300–600 job descriptions across those role families. Use a public dataset; don't scrape live this week.
5. Build `data/item_bank.json`: 3–5 multiple-choice questions per skill, generated offline with `scripts/generate_items.py`, then reviewed by hand.
6. **Ship a 200-row sample of all four by end of Day 1** so A isn't blocked.

**Depth beats breadth.** A deep 250-skill graph produces impressive roadmaps; a shallow 500-skill one produces two-step paths.

---

### 4.2 Learner Profiling — `[A]`

**What it is.** Turns the learner's self-description into structured data: interests, experience, completed courses, hours per week, deadline. Crucially, it converts "I finished Andrew Ng's ML course" into actual skill-level estimates rather than storing it as text.

**Person A steps:**
1. `core/profiler.py` → `extract_profile(text) -> LearnerProfile` using an LLM in strict JSON mode, validated by Pydantic.
2. Never let the LLM invent skill IDs. Have it emit free text, then map to canonical skills via `core/skill_matcher.py` (alias match, then embedding similarity, floor ~0.55). Unmatched terms go into an `unmapped[]` list the UI can ask about.
3. `seed_mastery(profile)`: for each completed course, set mastery **0.7** for skills it teaches and **0.4** for their prerequisites (finishing a course implies you knew its prereqs).
4. Persist to SQLite via SQLAlchemy: `learners`, `mastery`, `paths`, `progress`, `feedback`.

**Test locally:** feed 5 hand-written learner descriptions, print the parsed profile + seeded mastery.

---

### 4.3 Goal Translator — `[A]`

**What it is.** Converts a vague ambition into a concrete list of target skills, backed by evidence. Instead of asking the model "what does an ML engineer need?", it retrieves ~50 real job postings similar to the stated goal and counts which skills they actually ask for.

**Person A steps:**
1. Embed all JDs once with `sentence-transformers/all-MiniLM-L6-v2`, index with FAISS, persist to disk (`core/retrieval.py`).
2. On a goal query: embed → retrieve top 50 JDs.
3. Extract skills by **alias matching** canonical names against the JD text — not 50 LLM calls (slow, costly, non-deterministic).
4. Output `[{skill_id, demand: 0.68, evidence_count: 34}]`, dropping anything under ~0.15 demand.

**Why this matters:** it gives every downstream explanation a number to cite — *"Docker appears in 68% of the 50 postings closest to your goal."*

---

### 4.4 Adaptive Diagnostic + Mastery Model — `[B]`

**What it is.** Replaces "rate yourself: beginner/intermediate/advanced" with actual measurement. Serves 8–12 questions, picking each next question where it's least sure about the learner, and maintains a probability that they know each skill.

**Person B steps:**
1. `core/diagnostic.py`. Implement **Bayesian Knowledge Tracing** — a standard, citable technique, roughly 15 lines:
   - Params: prior `P(L₀)` from seeded mastery, learn `P(T)=0.1`, guess `P(G)=0.25`, slip `P(S)=0.1`.
   - On each answer, compute the posterior given correct/incorrect, then apply the learn-rate transition.
2. **Item selection:** pick the unasked question whose skill has mastery closest to **0.5** (maximum uncertainty). That's an adaptive test in ~10 lines.
3. Serve questions from `item_bank.json`. **Never generate questions live** — latency, cost, and a hallucinated answer key on demo day.
4. Output a mastery vector; treat `P(L) > 0.75` as mastered.

**Test locally:** simulate an all-correct learner and an all-wrong learner; mastery should converge cleanly in both directions.

---

### 4.5 Path Planner — `[A]` *(the centrepiece)*

**What it is.** The actual roadmap generator. It treats skills as a network where arrows mean "must learn this first", then finds a valid order through everything the learner is missing.

**Person A steps:**
1. `core/graph.py`: load `skills.json` into a NetworkX `DiGraph`. **Assert it's acyclic on startup** — a cycle from bad data must crash loudly at boot, not hang at demo time.
2. `core/planner.py`:
   - Take the **ancestor closure** of all target skills (everything needed first).
   - Subtract mastered skills → **the gap**.
   - **Topologically sort** the gap subgraph → a valid order.
   - Break ties by demand weight, so high-demand skills come earlier.
   - Group into **milestones** of 3–5 skills by graph depth.
   - Fit to hours/week → estimated dates.
3. Handle unreachable targets: return them under `unsupported_targets[]` instead of silently dropping them.
4. **Expose the intermediates** (`gap_nodes`, `ancestor_closure`, `ordering`) through the API — B needs them to draw the graph.

**Test locally:** `tests/fixtures/mini_graph.json` with 12 nodes; assert every prerequisite appears before its dependent.

---

### 4.6 Resource Recommender — `[A]`

**What it is.** Each skill in the roadmap needs something to actually learn it from. This picks the best course(s) per skill, plus a project per milestone and a checkpoint quiz at each milestone boundary.

**Person A steps:**
1. `core/ranker.py`: for each skill, retrieve candidate courses by tag + embedding similarity.
2. Score: `0.4 × semantic_similarity + 0.3 × normalised_rating + 0.3 × level_fit` (level fit = how close the course level is to current mastery).
3. Attach 1–2 courses per skill, one project per milestone, one assessment per milestone boundary.
4. Return empty lists gracefully — a skill with no matching course should still appear in the path.

---

### 4.7 Explainer — `[B]`

**What it is.** Answers "why this, why now, why not that?" Because the order came from a graph rather than the model's imagination, these explanations are grounded in checkable facts.

**Person B steps:**
1. `agents/explainer.py`. Build a **structured evidence bundle** from the planner output:
   `{skill, position, unlocks[], demand_pct, current_mastery, prereqs_satisfied[]}`.
2. Prompt the LLM to turn *only those facts* into two friendly sentences. Instruct it explicitly: if a fact isn't supplied, say you don't have it.
3. Add counterfactuals — *"why not start with transformers?"* → walk the ancestor chain, name the unsatisfied prerequisites. **This is the best 20 seconds of the demo video.**

---

### 4.8 Router / Orchestration — `[B]`

**What it is.** One chat box, four behaviours. This figures out whether the learner is setting a new goal, asking to re-plan, reporting progress, or just asking a question — and sends the request to the right place.

**Person B steps:**
1. `agents/router.py` with LangGraph: `classify → {profile | diagnostic | plan | explain | progress} → respond`.
2. Shared state carries `learner_id, profile, mastery, path, last_action`.
3. **The LLM routes; it does not compute.** All maths stays in A's plain-Python functions, called by nodes. Say this on the architecture slide — it reads as maturity.
4. Hard fallback: if classification fails or the provider errors, default to `explain` mode with a friendly message. Never show a stack trace to a judge.

---

### 4.9 API Service — `[A]`

**What it is.** The boundary between the two halves. B's interface talks to A's engine only through these routes, which is what lets both people build independently.

**Person A steps:**
1. `api/main.py` — FastAPI, CORS open, indices loaded once at startup.
2. Routes: `/profile`, `/goal/translate`, `/diagnostic/next`, `/diagnostic/answer`, `/path/generate`, `/path/replan`, `/explain`, `/progress`, `/feedback`, `/dashboard/{learner_id}`.
3. **`/dashboard/{id}` returns everything one screen needs in a single call** — don't make B fire six requests to paint one page.
4. **Day 1: ship all of these as stubs** returning hardcoded schema-valid JSON, so B can build the entire UI immediately.

---

### 4.10 Conversational UI — `[B]`

**What it is.** The front door: a chat window where the learner describes their goal and receives the roadmap, explanations and follow-up answers.

**Person B steps:**
1. `app/main.py` with `st.chat_input` / `st.chat_message`; history in `st.session_state`.
2. **Chat-first, not form-first.** The brief says "natural language" — a dropdown wizard reads as missing the requirement. If the API reports `missing_fields`, ask for them conversationally.
3. Three tabs: **Chat · Roadmap · Dashboard**.
4. Use `st.status()` with honest stage labels during slow calls ("Scanning 300 job descriptions…"). It makes the pipeline visible — useful in the video.
5. Add a **"Load demo learner"** button that hydrates a full profile in one click. Saves 40 seconds of your 4-minute video and hours of testing.
6. 👍/👎 on every resource card → `POST /feedback`.

---

### 4.11 Dashboard & Visualisation — `[B]`

**What it is.** Shows progress, skill growth, milestones and what to do next.

**Person B steps:**
1. **Roadmap graph** (`st.graphviz_chart`): left-to-right DAG, green = mastered / amber = in progress / grey = upcoming, milestones as clusters. **This is the money shot — give it the most time.**
2. **Mastery radar** (Plotly): current mastery overlaid on demand-weighted target. The gap between the shapes *is* the skill gap.
3. **Milestone timeline** (Plotly): planned vs completed.
4. **Next actions**: the 3 next unblocked skills with resource cards and a "Why this?" button.

Build all four against A's stubs on Day 2. Don't wait for the real engine.

---

## 5. Project Structure

`[A]` and `[B]` never edit each other's directories. `schemas/` is the only shared surface, and it's frozen after Day 2 — that's what prevents merge conflicts.

```
pathforge/
├── app/                        # Streamlit frontend                [B]
│   ├── main.py                 # entry, tabs, session bootstrap
│   ├── api_client.py           # wraps every API route
│   ├── mock.py                 # local fixtures — run UI with no backend
│   ├── views/                  # chat.py · roadmap.py · dashboard.py · diagnostic.py
│   └── components/             # graph_view.py · radar.py · timeline.py · resource_card.py
│
├── api/                        # FastAPI service                   [A]
│   ├── main.py                 # app factory, CORS, startup loading
│   ├── deps.py                 # singletons: graph, FAISS, LLM, DB
│   ├── config.py               # env settings
│   └── routes/                 # profile · goal · diagnostic · path · explain · progress · dashboard
│
├── core/                       # pure Python intelligence
│   ├── graph.py                # NetworkX load + DAG validation     [A]
│   ├── planner.py              # gap → topo sort → milestones       [A]
│   ├── profiler.py             # profile extraction + mastery seed  [A]
│   ├── goal_translator.py      # JD retrieval → target skills       [A]
│   ├── retrieval.py            # FAISS build / load / query         [A]
│   ├── ranker.py               # resource scoring                   [A]
│   ├── skill_matcher.py        # text → canonical skill_id          [A]
│   ├── diagnostic.py           # BKT + adaptive item selection      [B]
│   └── llm.py                  # provider abstraction, retries      [A]
│
├── agents/                     # orchestration                      [B]
│   ├── router.py               # LangGraph state machine
│   ├── explainer.py            # evidence bundle → explanation
│   └── prompts/                # classify · extract · explain · counterfactual
│
├── schemas/                    # FROZEN CONTRACTS            [shared]
│   ├── models.py               # all Pydantic models, single source of truth
│   └── examples/               # learner_profile · skill_node · course
│                               # target_skills · learning_path · dashboard_payload
│
├── data/                       # datasets                           [B]
│   ├── skills.json · courses.json · jds.json · item_bank.json
│   ├── raw/                    # source dumps        (gitignored)
│   └── indices/                # FAISS artefacts     (gitignored)
│
├── db/                         # SQLAlchemy models + SQLite         [A]
├── scripts/                    # build_indices · validate_graph     [A]
│                               # normalize_tags · generate_items    [B]
├── tests/                      # test_planner · test_graph          [A]
│                               # test_bkt                           [B]
├── docs/                       # solution PDF/PPT · architecture.png · screenshots
├── deploy/                     # render.yaml · Procfile · secrets example
├── .env.example                # LLM_PROVIDER · LLM_API_KEY · API_BASE_URL · USE_LOCAL_CORE
├── requirements.txt
└── README.md
```

**`core/` imports neither FastAPI nor Streamlit.** Plain functions, dicts in and out. That's what makes the offline fallback and the unit tests possible — don't let framework imports leak in.

---

## 6. Division Plan

### The split at a glance

| | **Person A — Path Engine** | **Person B — Learner Model & Experience** |
|---|---|---|
| **AI/ML** | Goal translator (RAG), profiling, retrieval + ranking | Adaptive diagnostic (BKT), explainer, router |
| **Algorithms** | Skill graph + path planner | Item selection strategy |
| **Infra** | FastAPI service, SQLite, index building | Streamlit app, deployment (Render + Streamlit Cloud) |
| **Data** | Schema definition, validation scripts | All four datasets + tag normalisation |
| **Visual** | — | Roadmap graph, radar, timeline, dashboard |
| **Tests** | planner, graph, matcher | BKT, item selection |
| **Submission** | Solution PDF/PPT + README | Demo video + screenshots |

Each side gets: a hard algorithmic piece, a retrieval/LLM piece, a piece of infrastructure, a testing surface, and one graded submission artefact.

### 6-day plan

| Day | Person A | Person B | Gate |
|---|---|---|---|
| **1** | Repo skeleton, Pydantic schemas, **stub API** | Data schemas, **200-row samples**, Streamlit shell | Contracts frozen; stubs + samples pushed |
| **2** | Graph loader + planner v1 | Chat UI on stubs; first deploy | Deployed URL live (on fake data) |
| **3** | FAISS index, goal translator, ranker | Full datasets committed + tag-normalised | A swaps samples for real data |
| **4** | Profiler + API wired to real core | Diagnostic + BKT; roadmap graph viz | **Integration day** |
| **5** | Tests, caching, error paths | Explainer + router; dashboard panels | **Feature freeze EOD** |
| **6** | Solution PDF/PPT, README | Record demo video, screenshots | All five deliverables in draft |
| **7** | *Finalize together:* edit video, QA pass, build ZIP, clean-device test | | Submission package done |

**Day 5 feature freeze is the load-bearing decision.** Two of five graded deliverables are pure production work. A team still coding on Day 6 submits a bad video, and that costs more than any missing feature.

### Cross-dependencies

| A needs from B | When | If it's late |
|---|---|---|
| `skills.json` schema + sample | Day 1 | A hand-writes 40 nodes for one role family |
| Clean `courses.json` tags | Day 3 | Planner returns skills with empty resource lists |
| `jds.json` | Day 3 | Goal translator falls back to LLM-proposed targets |

| B needs from A | When | If it's late |
|---|---|---|
| Stub endpoints | Day 1 | B uses `app/mock.py` fixtures |
| Real `/path/generate` | Day 4 | Demo runs on stubs; swap later |
| `evidence bundle` in path output | Day 5 | Explainer runs on a saved fixture |

Every fallback takes under an hour. **Nobody is ever hard-blocked.**

---

## 7. Building Separately, Then Merging

**How this works in practice:** both people build in their own directories on their own machines against fake data on the other side, and the two halves meet once, on Day 4.

**Day 1, together (~90 min):** write `schemas/models.py` and the example JSONs. Nothing else starts first. The two that actually couple you are **`skill_node`** and **`learning_path`** — freeze them; any change after Day 2 needs both people at the keyboard.

**Then, independently:**
- **A** develops `core/` and `api/` against B's 200-row sample. Verify with `pytest` and `curl` — never needs the UI running.
- **B** develops `app/` and `agents/` against `app/mock.py` fixtures. Verify in the browser — never needs the API running.

**Merge protocol:**
- `main` stays deployable from Day 2. The deployed URL is a graded deliverable.
- Branches: `feat/core-*` (A), `feat/ui-*` (B). PR, review by the other, squash merge.
- Separate directories mean conflicts are structurally near-impossible; `schemas/` is the only shared file and it's frozen.
- **Commit in small, real increments.** "Commit history should reflect the development process" is an explicit submission requirement — one giant dump on Day 6 is a self-inflicted wound.

**Day 4 integration:** B flips `API_BASE_URL` from mock to A's local server. Fix schema drift the same day. Everything after that is polish.

---

## 8. Running & Deploying

```bash
git clone <repo> && cd pathforge
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                      # add LLM key (Groq or Gemini free tier)

python scripts/build_indices.py           # FAISS + DAG validation
uvicorn api.main:app --reload --port 8000 # terminal 1
streamlit run app/main.py                 # terminal 2 → localhost:8501
```

- **API → Render** (free tier). Start: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`. Free instances cold-start — **hit the URL 5 minutes before any demo.**
- **UI → Streamlit Community Cloud.** Point at `app/main.py`; put `API_BASE_URL` and the LLM key in Secrets.
- **Safety net:** a `USE_LOCAL_CORE=true` flag makes Streamlit import `core/` directly and bypass the API. If Render is down during judging, one env var keeps you fully functional. Mention it in the README — it reads as engineering maturity.

---

## 9. Submission Checklist

| # | Deliverable | Owner | Notes |
|---|---|---|---|
| 1 | Source ZIP | A | Exclude `.venv`, `__pycache__`, `data/raw/`, `data/indices/`, `*.db` |
| 2 | GitHub repo | both | Public; meaningful commit history |
| 3 | Solution PDF/PPT | A | Problem, approach, architecture, AI/ML techniques, features, challenges |
| 4 | Demo video (3–5 min) | B | Script in §10 |
| 5 | Deployed URL | B | Plus local setup instructions in README |

**Name your techniques explicitly in the PDF** — embedding retrieval (FAISS), demand-weighted RAG extraction, Bayesian Knowledge Tracing, DAG topological planning, weighted re-ranking, LLM orchestration. The AI/ML band is 20% and graders look for named methods.

---

## 10. Demo Video Script

| Time | Beat |
|---|---|
| 0:00–0:30 | The problem: recommendation ≠ sequencing |
| 0:30–1:15 | Goal typed in plain English → JD retrieval → target skills with demand % |
| 1:15–2:00 | Adaptive quiz; mastery probabilities updating live |
| 2:00–3:00 | **Roadmap graph renders.** Zoom in, walk one milestone. Most screen time. |
| 3:00–3:40 | "Why this?" → then *"why not start with transformers?"* → names unmet prerequisites |
| 3:40–4:20 | Mark milestone complete → path re-plans → dashboard updates |
| 4:20–4:45 | Architecture slide: *the graph decides, the LLM narrates* |

Record with the demo learner pre-loaded and the API already warm.

---

## 11. Stretch Goals — Only If Day 5 Arrives Early

- **Feedback bandit:** Thompson sampling over resource type (video / text / project) learned from 👍/👎. Logging already exists, so it's contained.
- **Capstone reverse-planning:** decompose a target project into required skills and frame the path around it.
- **Cohort comparison:** "learners with your profile reached this goal in ~14 weeks."
