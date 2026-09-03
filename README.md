# CodeAgent — Multi-Agent AI Code Review System

CodeAgent reviews Python and Java source code using a **real multi-agent
static-analysis pipeline**: a FastAPI backend runs your code through five
specialized agents (Syntax, Logic, Quality, Security, Performance) and
returns a structured, deduplicated review with a score — no mocked or
random results anywhere in the pipeline.

The frontend is a React + TypeScript + Tailwind app (originally scaffolded
with Lovable) that has been rewired end-to-end to call the real backend
instead of the placeholder in-browser regex "analysis" it shipped with.

```
+----------------------+        REST (JSON)        +----------------------------+
|   React frontend      |  ------------------------>  |   FastAPI backend           |
|   (Vite, :8080)         |  <------------------------  |   (:8000)                    |
+----------------------+                             +----------------------------+
                                                                |
                                                       +--------+--------+
                                                       |  Orchestrator      |
                                                       |  (Review Manager)  |
                                                       +--------+--------+
                                      +-------------+-----------+-----------+-------------+
                                      v             v           v           v             v
                                   Syntax        Logic       Quality     Security    Performance
                                   Agent         Agent        Agent       Agent         Agent
```

## Project structure

```
.
|-- backend/                 FastAPI multi-agent review API (see backend/README.md)
|   |-- app/
|   |   |-- analyzers/         Real Python (ast) and Java (javac/heuristics) analysis
|   |   |-- agents/             5 specialized review agents
|   |   |-- services/            Optional LLM provider layer (env-var driven)
|   |   |-- orchestrator.py       Combines + dedupes + scores
|   |   `-- main.py                FastAPI routes, CORS, error handling
|   |-- tests/                  pytest suite + sample buggy/clean fixtures
|   |-- requirements.txt
|   `-- .env.example
|-- src/                      React frontend
|   |-- lib/apiClient.ts        Typed client for the backend API
|   |-- components/
|   |   |-- CodeEditor.tsx        Code input (unchanged visual design)
|   |   `-- AgentPanel.tsx         Results panel: loading/error/empty/real states
|   `-- pages/Index.tsx           Wires the editor + panel to the backend
|-- .env.example              Frontend env template (VITE_API_URL)
`-- vite.config.ts            Dev proxy: /api -> http://localhost:8000
```

## Running it locally

You need two terminals — one for the backend, one for the frontend.

### 1. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # optional, defaults work as-is
python run.py                     # starts on http://localhost:8000
```

Verify it's up: `curl http://localhost:8000/api/health`

Full API docs: `backend/README.md` (also see the interactive Swagger UI at
`http://localhost:8000/docs` once it's running).

### 2. Frontend (Vite + React)

```bash
npm install
npm run dev                        # starts on http://localhost:8080
```

The dev server proxies `/api/*` to `http://localhost:8000` automatically
(see `vite.config.ts`), so the frontend talks to the backend with no CORS
configuration needed. Open `http://localhost:8080`, paste some Python or
Java code (or use the "Sample code" menu), and click **Analyze**.

If your backend runs on a different host/port, set `BACKEND_URL` before
starting Vite (`BACKEND_URL=http://localhost:9000 npm run dev`), or set
`VITE_API_URL` in a frontend `.env` file to point directly at a deployed
backend (see `.env.example`).

## Testing

```bash
# Backend
cd backend && pytest -v

# Frontend
npm test
```

## What changed from the original demo

The original repo was a Lovable-generated UI with `src/lib/agentEngine.ts`
performing fake, purely regex-based "analysis" entirely in the browser
(hardcoded messages, no real parsing). This upgrade:

- **Removed `agentEngine.ts` and all mock analysis** — replaced by
  `src/lib/apiClient.ts`, a typed REST client for the new backend.
- **Added a real Python backend** (`backend/`) with genuine static analysis
  (CPython's own parser/compiler for Python, `javac` + heuristics for
  Java — see `backend/README.md` for the full list of checks).
- **Implemented a real multi-agent architecture**: an orchestrator plus 5
  independent, swappable agents (Syntax, Logic, Quality, Security,
  Performance), each returning structured findings with severity,
  category, line number, explanation, and a suggested fix.
- **Kept the existing visual design** — the same card-based layout, tab
  panel, color system (error/warning/info/success), copy buttons, and
  glowing header — while updating the code so results are backend-driven.
- **Added loading, error, and empty states** to the results panel, so
  network failures or backend downtime are shown clearly instead of
  crashing or silently doing nothing.
- **Restricted the language picker to Python and Java** (what the backend
  actually supports today) instead of offering languages that were never
  really analyzed by the old mock engine.
- **Added an optional, env-var-configured LLM review agent** (Anthropic or
  OpenAI) that never blocks or breaks the pipeline if disabled or if the
  call fails — static analysis alone is always fully functional.

## Notes & honest limitations

- Java analysis uses the real `javac` compiler for syntax/compile checks
  **only if a JDK is installed** on the machine running the backend
  (`javac` on PATH). Without one, it falls back to a structural
  brace/semicolon scanner — still real analysis, just less authoritative
  than an actual compiler. `backend/app/main.py`'s `/api/health` endpoint
  reports whether `javac` (and the optional Python tools) are available.- The "Auto-Fixed Code" shown in the Report tab only applies a small set of
  unambiguous, safe mechanical fixes (e.g. trailing whitespace) — it is
  intentionally conservative rather than a full auto-repair tool.
- The LLM agent is off by default and adds, at most, a handful of
  additional findings folded into the relevant category tab (tagged `AI`
  in the UI) — it never replaces the static-analysis findings.
