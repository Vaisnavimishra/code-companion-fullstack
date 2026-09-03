# CodeAgent Backend

Real, multi-agent static code review API built with **FastAPI**. No mocked
or randomized results — every finding comes from actually parsing/compiling
the submitted code and/or running rule-based and (optionally) third-party
analysis tools against it.

## Quick start

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # optional — defaults work with no changes
python run.py                       # or: uvicorn app.main:app --reload --port 8000
```

The API is now live at `http://localhost:8000`. Interactive docs (Swagger UI)
are at `http://localhost:8000/docs`, and the raw OpenAPI schema at
`http://localhost:8000/openapi.json`.

## Running the tests

```bash
cd backend
pytest -v
```

## Architecture

```
backend/
  app/
    main.py            FastAPI app, routes, CORS, error handling
    config.py           Environment-variable driven settings
    models.py            Pydantic request/response schemas
    orchestrator.py       The Review Manager — combines analyzers + agents
    samples.py             Bundled sample code used by /api/samples
    analyzers/
      python_analyzer.py   Real Python analysis (ast/compile + optional
                            pyflakes/bandit/radon)
      java_analyzer.py     Real Java analysis (javac when available,
                            structural + rule-based fallback otherwise)
    agents/
      base.py               BaseAgent abstraction
      agents.py              SyntaxAgent, LogicAgent, QualityAgent,
                              SecurityAgent, PerformanceAgent
    services/
      llm_service.py         Optional Anthropic/OpenAI provider layer
  tests/                   pytest suite + sample fixtures
  requirements.txt
  .env.example
  run.py
```

### Request flow

1. `POST /api/review` receives `{ code, language }`.
2. The **orchestrator** picks the right analyzer (`python_analyzer` or
   `java_analyzer`) and runs it, producing a flat list of raw findings.
3. If an LLM provider is configured (see below), the orchestrator also asks
   it for a contextual second opinion, and merges those findings in.
4. Findings are **deduplicated** (same category + line + message).
5. Each of the 5 agents (`SyntaxAgent`, `LogicAgent`, `QualityAgent`,
   `SecurityAgent`, `PerformanceAgent`) claims the findings in its category
   and wraps them with agent metadata (name, description, timing).
6. An overall score (0–100) and verdict are computed from the
   error/warning/info counts.
7. A single `ReviewResponse` is returned to the frontend.

Adding a new agent or language analyzer does **not** require touching the
orchestrator's core flow — see `app/agents/agents.py` and
`app/analyzers/` for the extension points.

## What's actually being analyzed (not mocked)

**Python** (`app/analyzers/python_analyzer.py`):
- Real syntax/compile-error detection via CPython's own `compile()`/`ast`.
- AST-walk checks: mutable default arguments, bare/broad `except`, silently
  swallowed exceptions, `eval`/`exec`, insecure deserialization
  (`pickle.loads`, unsafe `yaml.load`), `subprocess(shell=True)`,
  `os.system`, SQL built via string concatenation/f-strings, hardcoded
  secrets, unused imports, wildcard imports, cyclomatic complexity, long
  functions, missing docstrings, unmemoized recursion, nested loops
  (O(n²)+), string accumulation in loops, `while True` without a nearby
  `break`, TODO/FIXME comments, line length, trailing whitespace.
- Optional enrichment (used automatically if installed, otherwise skipped
  without error): **pyflakes** (unused vars / undefined names), **bandit**
  (security), **radon** (cyclomatic complexity cross-check).

**Java** (`app/analyzers/java_analyzer.py`):
- Real compilation checking via `javac` when a JDK is present on the host
  (parses actual compiler diagnostics into findings).
- Always-available fallback: a string/comment-aware tokenizer checks
  brace/paren/bracket balance and likely missing semicolons.
- Rule-based checks: `String == comparison` bugs, generic/empty `catch`,
  unclosed resources, `Runtime.exec`/`ProcessBuilder` command injection,
  `Statement` + concatenation SQL injection, weak hashes (MD5/SHA-1),
  insecure `Random` for secrets, hardcoded credentials, native
  deserialization (`ObjectInputStream`), nested loops, string concatenation
  in loops, long methods, missing Javadoc, `while (true)` without `break`,
  TODO/FIXME comments, line length.

Both analyzers are intentionally layered so the app is **fully useful with
zero configuration** (nothing but the Python standard library is required)
and gets **strictly better** as you install a JDK / pyflakes / bandit /
radon / configure an LLM key — none of these are required.

## Optional LLM-powered review agent

Disabled by default. To enable it, set in `backend/.env`:

```bash
LLM_PROVIDER=anthropic          # or "openai"
ANTHROPIC_API_KEY=sk-ant-...    # or OPENAI_API_KEY=sk-...
LLM_MODEL=claude-sonnet-4-6      # or e.g. gpt-4o-mini
```

When enabled, the LLM is asked to review the code for issues static
analysis is likely to miss (returns a small, strictly-parsed JSON list of
findings). If the call fails or times out for any reason, the review
proceeds using static analysis only — the LLM is additive, never a single
point of failure. **No API key is ever hardcoded** — everything is read
from environment variables via `app/config.py`.

## API reference

### `GET /api/health`
Returns service status and which optional tools/providers are active.

```json
{
  "status": "ok",
  "version": "1.0.0",
  "llm_enabled": false,
  "llm_provider": null,
  "supported_languages": ["python", "java"],
  "available_tools": {
    "javac": false,
    "pyflakes": true,
    "bandit": true,
    "radon": true,
    "llm": false
  }
}
```

### `GET /api/languages`
```json
{ "languages": ["python", "java"] }
```

### `GET /api/samples`
Returns bundled sample code snippets (buggy + clean, per language) used for
quick manual testing.

### `POST /api/review`

Request:
```json
{
  "code": "def add_item(item, items=[]):\n    items.append(item)\n    return items\n",
  "language": "python"
}
```

Response (truncated):
```json
{
  "language": "python",
  "findings": [
    {
      "id": "b6c1...",
      "agent": "Logic & Bug Detection Agent",
      "category": "logic",
      "severity": "error",
      "line": 1,
      "message": "Mutable default argument in `add_item()`",
      "explanation": "Default arguments are evaluated once; a mutable default is shared and mutated across calls.",
      "suggestion": "Use `None` as the default and initialize the mutable value inside the function body.",
      "rule": "python-mutable-default-arg",
      "source": "static-analysis"
    }
  ],
  "agents": [
    { "agent": "Syntax & Compilation Agent", "category": "syntax", "findings": [], "execution_time_ms": 0.3, "tool": "built-in analyzer" },
    { "agent": "Logic & Bug Detection Agent", "category": "logic", "findings": [ /* ... */ ], "execution_time_ms": 0.4, "tool": "built-in analyzer" },
    { "agent": "Code Quality Agent", "category": "quality", "findings": [], "execution_time_ms": 0.2 },
    { "agent": "Security Agent", "category": "security", "findings": [], "execution_time_ms": 0.2 },
    { "agent": "Performance Agent", "category": "performance", "findings": [], "execution_time_ms": 0.1 }
  ],
  "summary": { "total_findings": 1, "errors": 1, "warnings": 0, "info": 0, "success": 0, "score": 85, "verdict": "Needs work — blocking issues found" },
  "documentation": "⚠ No module-level docstring found.\n\n⚠ 0/1 function(s) have docstrings.",
  "fixed_code": "def add_item(item, items=[]):\n    items.append(item)\n    return items",
  "llm_enabled": false,
  "analyzed_at": "2026-09-03T12:00:00+00:00"
}
```

Try it with curl:
```bash
curl -X POST http://localhost:8000/api/review \
  -H "Content-Type: application/json" \
  -d '{"code": "def add(a, b):\n    return a + b\n", "language": "python"}'
```

Errors are returned as structured JSON with a 4xx/5xx status, e.g. empty
code (`422`), code over `MAX_CODE_LENGTH` (`413`), or an internal error
(`500`) — the frontend renders these as a friendly error state rather than
crashing.

## Environment variables

See `.env.example` for the full, documented list. Nothing is required for
the app to run — every variable has a sane default and the app degrades
gracefully (static analysis only) when optional integrations aren't
configured.
