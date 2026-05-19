# Markov Agent + Observability Implementation Plan

**Goal:** Replace the two-phase planner/executor with a Markov Chain iterative agent loop, instrument it with OpenTelemetry, and store traces in SQLite.

**Architecture:** Each LLM call receives goal + scratchpad memory + last 3 steps + current page state. The agent maintains a scratchpad it writes to after every step, accumulating what it has learned and dropping what is stale. Every LLM response includes four fields: an evaluation of the last action, an updated memory, a next sub-goal, and a concrete action. The executor owns the rolling state (memory string + recent_steps list) and passes it into every call. Observability flows through OTel SDK — SQLite is populated by an OTel SpanExporter, not by direct writes in the executor.

**Tech Stack:** Python, FastAPI, Playwright, Pydantic, google-genai, OpenTelemetry SDK, SQLite, Docker Compose

---

## Slicing Strategy

Each slice is a **complete, demonstrable vertical feature**. You can stop after any slice and have a working system. Slices build on each other — don't skip ahead.

```text
Slice 1: Core Markov Loop        → Agent works (basic tasks)
Slice 2: Smart DOM + Resilience  → Agent works well (real websites)
Slice 3: Trace Storage           → Runs are inspectable
Slice 4: OTel Instrumentation   → System is observable
Slice 5: Token & Cost Tracking  → Costs are visible
Slice 6: Docker + Production    → Local dev matches production
```

---

## Slice 1: Core Markov Loop

### What

Replace the two-phase planner with a single-step LLM call with adaptive memory. The agent loop becomes: `goal + memory + recent_steps + page_state → LLM → evaluation + updated_memory + next_goal + action → execute → repeat`.

### What Changes

**Delete:**

- `app/planner.py` — no more upfront planning
- `app/llm/base.py` → remove `generate_plan()` method
- `app/llm/gemini.py` → remove `generate_plan()` method
- `app/llm/schemas.py` → remove `_PLAN_RESPONSE_SCHEMA`
- `app/llm/prompts.py` → remove `PLANNER_SYSTEM_PROMPT`

**Modify:**

- `app/model.py` — add `DoneAction` and `AgentOutput` (evaluation, memory, next_goal, action fields), remove unused action types (`select`, `back`, `hover`, `upload_file`, `confirm_human_checkpoint`), update `Action` union to 7 types only
- `app/llm/base.py` — update `decide_next_action()` signature to `(goal, memory, recent_steps, page_state)`
- `app/llm/gemini.py` — implement new `decide_next_action()` with adaptive memory signature; build user prompt from all four inputs
- `app/llm/prompts.py` — replace with single unified system prompt instructing the LLM to: (1) evaluate the previous action honestly, (2) update memory with only what's still relevant — drop stale facts, don't restate the goal verbatim, never write credentials, stay under 600 chars, (3) set a concrete next_goal, (4) output a single action
- `app/llm/schemas.py` — update `_ACTION_RESPONSE_SCHEMA`: wrap action in `AgentOutput` with `evaluation` (str, max 200 chars), `memory` (str, max 600 chars), `next_goal` (str, max 150 chars), and `action` (the 7-type union with `done` replacing `extract`)
- `app/browser.py` — implement Playwright: goto, click, type, press, scroll, screenshot, plus browser context management
- `app/executor.py` — rewrite as the Markov main loop with memory management: own `memory: str` (starts empty) and `recent_steps: list[dict]` (rolling window, capped at 3); extract evaluation/memory/next_goal/action from each LLM response; append `{step, action_type, action_target, status, error, next_goal}` to recent_steps each iteration; store evaluation and memory_snapshot in step trace records
- `app/main.py` — wire up new executor, remove planner import, add run_id generation

### Tests

**Unit tests:**

- `test_model.py` — DoneAction has correct fields, AgentOutput has evaluation/memory/next_goal/action fields, Action union includes all 7 types, old types are removed
- `test_executor.py` — Loop terminates after max_steps, loop returns list of steps, done action breaks loop, memory string updates carry forward between steps, recent_steps window caps at 3 entries
- `test_llm_schemas.py` — Schema includes AgentOutput wrapper with evaluation/memory/next_goal, action includes `done`, excludes `extract`

**Integration tests:**

- `test_api_interact.py` — POST /api/interact returns 200, response has `run_id` and `steps`, each step has `evaluation` and `memory_snapshot`
- `test_markov_e2e.py` — Mocked LLM returns a sequence of AgentOutputs, executor produces expected steps with memory evolving correctly across steps

---

## Slice 2: Smart DOM + Resilience

### What

Add smart DOM extraction so the LLM sees meaningful page state. Add loop detection and error handling so the agent doesn't spin forever or crash on failures.

### What Changes

**Modify:**

- `app/browser.py` — add `extract_page_state()` returning smart DOM: URL, title, interactive elements with text labels and ARIA roles, headings, visible text preview
- `app/executor.py` — add state fingerprinting for loop detection (hash of interactive elements + last action type + last action target), add `last_successful_action` tracking for error recovery, add `loop_detected` termination condition

**New concepts in executor:**

- State fingerprint: `hash(interactive_elements + last_action_type + last_action_target)`
- Loop detection: if same fingerprint appears 2 consecutive times → abort with `loop_detected`
- Error context: on failure, next LLM call receives `last_successful_action` alongside `last_action`
- Three termination conditions: LLM says `done`, max steps reached, loop detected

### Tests

**Unit tests:**

- `test_browser_state.py` — extract_page_state returns dict with url, title, interactive_elements, headings
- `test_loop_detection.py` — same fingerprint twice triggers loop_detected, different fingerprints don't trigger
- `test_error_context.py` — failed action includes last_successful_action in next LLM call context

**Integration tests:**

- `test_resilience_e2e.py` — agent recovers from a failed click by trying a different approach
- `test_loop_abort.py` — agent aborts when stuck in a loop

---

## Slice 3: Trace Storage

### What

Persist every run and its steps to SQLite so runs are inspectable after the fact. The API returns structured responses with run_id (generated by executor), steps, final_result, and screenshot paths.

### What Changes

**New:**

- `app/trace.py` — SQLite database management: init_db, insert_run, update_run_status, get_run, insert_step, get_steps
- `artifacts/janus.db` — SQLite database file (created automatically, configurable via `JANUS_DB_PATH` env var)

**Modify:**

- `app/executor.py` — generate run_id via uuid, call `insert_run` at start, `insert_step` after each step, `update_run_status` on completion/error. Returns `(run_id, steps, final_result)` tuple
- `app/main.py` — use run_id from executor return, stop generating it locally

**Schema:**

```
runs:
  run_id                TEXT PRIMARY KEY     — UUID generated by executor
  goal                  TEXT NOT NULL         — original user prompt
  status                TEXT NOT NULL         — running | completed | max_steps | error | loop_detected
  final_result          TEXT                  — JSON blob: {summary, url, title, screenshot_path}
  final_screenshot_path TEXT                  — path to terminal screenshot
  created_at            TEXT NOT NULL         — ISO-8601 timestamp

steps:
  id              INTEGER PRIMARY KEY AUTOINCREMENT
  run_id          TEXT NOT NULL REFERENCES runs(run_id)
  step_number     INTEGER NOT NULL           — 0-indexed step order
  action_type     TEXT NOT NULL              — goto | click | type | press | scroll | screenshot
  action_target   TEXT                       — URL, CSS selector, or key name
  status          TEXT NOT NULL              — success | failed
  error           TEXT                       — error message if failed
  latency_ms      REAL                       — execution time in milliseconds
  screenshot_path TEXT                       — path to step screenshot (if screenshot action)
  page_url        TEXT                       — URL after action executed
  page_title      TEXT                       — page title after action executed
  evaluation      TEXT                       — LLM's assessment of the previous action
  memory_snapshot TEXT                       — agent's scratchpad at this point
  next_goal       TEXT                       — LLM's planned next sub-goal
```

### Tests

**Unit tests:**

- `test_trace.py` — 14 tests covering init_db (file/dir creation, table columns, idempotent), insert_run/get_run/update_run_status, insert_step/get_steps (single, multiple ordered, nonexistent, error recording)

**Integration tests:**

- `TestTraceIntegration` (in `test_executor.py`) — complete run stores run+steps in DB, max_steps status stored, final_result stored on done, run_id returned from run()
- `test_api_interact.py` — POST /api/interact returns response matching expected schema (already passing)

---

## Slice 4: OTel Instrumentation

### What

Wrap the Markov loop with OpenTelemetry spans. Each run becomes a trace, each step becomes a span, each LLM call and browser action gets its own child span. A custom SQLiteTraceExporter populates the database from completed spans.

### What Changes

**New:**

- `app/telemetry.py` — OTel SDK setup: configure TracerProvider, MeterProvider, LogHandler
- `app/telemetry/exporters.py` — SQLiteTraceExporter that processes completed spans and writes to runs/steps tables
- `app/telemetry/cost.py` — model pricing table, cost computation function

**Modify:**

- `app/executor.py` — wrap each operation in OTel spans: `agent.run`, `agent.step.N`, `llm.decide_next_action`, `browser.execute`, `browser.extract_page_state`
- `app/llm/gemini.py` — add OTel span with token count attributes
- `app/browser.py` — add OTel spans for action execution and page state extraction
- `app/main.py` — add OTel FastAPI instrumentation
- `app/trace.py` — update schema to include OTel fields (trace_id, span_id, llm_input_tokens, llm_output_tokens, llm_cost_usd)
- `requirements.txt` — add opentelemetry-api, opentelemetry-sdk, opentelemetry-instrumentation-fastapi

**Span hierarchy (from observability.md §2):**

```text
Trace: agent.run (run_id)
├── Span: agent.step.0 (action: goto)
│   ├── Span: llm.decide_next_action (model, tokens, latency)
│   ├── Span: browser.execute (action, latency, success)
│   └── Span: browser.extract_page_state (url, title, element_count, latency)
├── Span: agent.step.1 (action: click)
│   └── ...
└── Span: agent.complete (status, result)
```

### Tests

**Unit tests:**

- `test_telemetry.py` — TracerProvider initializes, MeterProvider initializes, LogHandler correlates traces
- `test_exporters.py` — SQLiteTraceExporter processes agent.run span, processes agent.step.N span, handles missing attributes gracefully
- `test_cost.py` — cost computation matches expected formula, unknown model raises error

**Integration tests:**

- `test_telemetry_e2e.py` — complete run produces trace with correct span hierarchy, span attributes match expected values
- `test_trace_correlation.py` — logs from a run include the correct trace_id

---

## Slice 5: Token & Cost Tracking

### What

Count tokens from Gemini responses, compute cost per call, and record aggregate metrics. The runs table includes total_tokens and total_cost_usd.

### What Changes

**Modify:**

- `app/llm/gemini.py` — extract `usage_metadata` from Gemini response (prompt_token_count, candidates_token_count), set as span attributes
- `app/telemetry/cost.py` — implement cost computation: `(input_tokens * input_price + output_tokens * output_price) / 1000`
- `app/telemetry/exporters.py` — aggregate token counts and costs across steps, write totals to runs table
- `app/trace.py` — update runs schema to include total_tokens and total_cost_usd

**Metrics (from observability.md §3):**

- `agent.llm.latency` — histogram of LLM call latency
- `agent.llm.tokens` — histogram of tokens per call
- `agent.llm.cost` — histogram of cost per call in USD

### Tests

**Unit tests:**

- `test_cost.py` — gemini-2.0-flash pricing computes correctly, gemini-2.5-pro pricing computes correctly, unknown model raises error

**Integration tests:**

- `test_token_tracking_e2e.py` — complete run populates token counts in trace, total cost matches sum of step costs

---

## Slice 6: Docker + Production Topology

### What

Containerize the backend and add the observability stack: OTel Collector, Grafana, Tempo, Loki, Prometheus. Local dev runs the same topology as production.

### What Changes

**New:**

- `docker-compose.yml` — backend, frontend, otel-collector, grafana, tempo, loki, prometheus
- `otel-collector-config.yaml` — collector pipeline: receive OTLP, export to Tempo/Loki/Prometheus
- `prometheus.yml` — scrape config for metrics
- `grafana/provisioning/datasources.yaml` — auto-configure Tempo, Loki, Prometheus as datasources
- `grafana/provisioning/dashboards.yaml` — auto-provision dashboards
- `grafana/dashboards/janus-overview.json` — overview dashboard with run metrics

**Modify:**

- `requirements.txt` — add opentelemetry-exporter-otlp-proto-grpc
- `app/telemetry.py` — add OTLP exporter for production (alongside SQLite exporter)

### Tests

**Integration tests:**

- `test_docker_e2e.py` — docker compose up succeeds, all services are healthy, end-to-end flow produces traces in Grafana

---

## Dependencies

```text
Slice 1 (Core Loop)
  └─→ Slice 2 (Smart DOM + Resilience)
       └─→ Slice 3 (Trace Storage)
            └─→ Slice 4 (OTel Instrumentation)
                 └─→ Slice 5 (Token & Cost Tracking)
                      └─→ Slice 6 (Docker + Production)
```

Each slice depends on the previous one. Don't skip ahead.

---

## Scope Suggestions

### Critical (must ship)

- **Slice 1: Core Markov Loop** — Without this, there's no agent.
- **Slice 2: Smart DOM + Resilience** — Without this, the agent only works on toy examples.

### Important (should ship)

- **Slice 3: Trace Storage** — Without this, you can't debug or demo. But you could use in-memory storage temporarily.
- **Slice 4: OTel Instrumentation** — This is the differentiator. But you could defer the SQLiteTraceExporter and write directly to SQLite temporarily.

### Nice-to-have (defer if tight)

- **Slice 5: Token & Cost Tracking** — Important for production, but not for a demo.
- **Slice 6: Docker + Production** — Important for credibility, but you can demo without it.

### Combined slices (if time is tight)

- Combine Slice 3 + 4: Implement OTel instrumentation and SQLiteTraceExporter together. The trace storage becomes a byproduct of OTel, not a separate system.
- Combine Slice 4 + 5: Token counting is a natural extension of OTel instrumentation.

---

## Implementation Order

1. **Slice 1** — Get the agent working. End-to-end: `POST /api/interact` → browser executes → response returned.
2. **Slice 2** — Make it work on real websites. Smart DOM + loop detection + error recovery.
3. **Slice 3** — Make it inspectable. SQLite traces + proper API responses.
4. **Slice 4** — Make it observable. OTel spans + structured logging.
5. **Slice 5** — Make costs visible. Token counting + cost computation.
6. **Slice 6** — Make it deployable. Docker + Grafana.

After Slice 3, you have a demo-worthy system. After Slice 4, you have a production-style system. After Slice 6, you have a deployable system.

---

## Test Infrastructure

Before starting Slice 1, set up the test infrastructure:

**Create:**

- `tests/conftest.py` — shared fixtures (mock LLM, mock browser, test database)
- `tests/test_model.py` — model tests
- `tests/test_executor.py` — executor tests
- `tests/test_browser.py` — browser tests
- `tests/test_trace.py` — trace storage tests
- `tests/test_telemetry.py` — telemetry tests
- `tests/test_api.py` — API integration tests

**Add to requirements.txt:**

- pytest
- pytest-asyncio
- httpx (for TestClient)

**Test strategy:**

- Unit tests for each module (mocked dependencies)
- Integration tests for the executor loop (real LLM mocked, real browser)
- E2E tests for the API (full stack with mocked LLM)
- No real browser in CI — mock Playwright for speed and reliability

---

## Key Architecture Decisions (Reference)

From `docs/interact-api.md`:

1. **Adaptive Memory:** Each LLM call receives goal + memory (scratchpad, max 600 chars) + recent_steps[3] + page_state. Memory is LLM-controlled — the agent decides what to keep and what to drop after every step.
2. **AgentOutput:** Every LLM response has four fields: `evaluation` (did the last action work?), `memory` (updated scratchpad), `next_goal` (what to do next), `action` (the executable action). Evaluation and next_goal are ephemeral — they influence the memory update but are not passed forward as separate inputs. The distilled insight lives on in memory.
3. **Memory bounding:** Memory is capped at 600 chars by schema constraint (not just prompt instruction). The system prompt instructs: don't restate the goal verbatim, drop stale facts, never write credentials, keep it under 600 chars.
4. **Adaptive:** The LLM sees actual page state on every step and adjusts naturally.
5. **Token-efficient:** ~1-4K tokens per call. Adaptive memory adds ~15-20% over pure memoryless but prevents goal drift and retries, which cost far more in practice.
6. **Smart DOM:** URL + title + interactive elements + headings + visible text. Not full DOM.
7. **7 actions:** goto, click, type, press, scroll, screenshot, done.
8. **Loop detection:** Hash interactive elements + last action. Same combo 2x → abort. Memory helps with soft loops too — the LLM can write "tried clicking #btn twice, no response" and self-correct before fingerprint detection triggers.
9. **Three terminations:** LLM says done, max steps, loop detected.
10. **No auto-retry:** LLM adapts based on error context in evaluation. Blind retry doesn't help.
11. **Per-request browser:** Simple, clean, no concurrency issues.
12. **SQLite traces:** One database at `artifacts/janus.db` (configurable via `JANUS_DB_PATH`). Two tables: `runs` (run_id, goal, status, final_result, final_screenshot_path, created_at) and `steps` (id, run_id, step_number, action_type, action_target, status, error, latency_ms, screenshot_path, page_url, page_title, evaluation, memory_snapshot, next_goal). Each step record stores evaluation + memory_snapshot + next_goal for glass-box debugging.

From `docs/observability.md`:

1. **OTel as backbone:** Traces, metrics, logs all flow through OTel SDK.
2. **Span hierarchy:** agent.run → agent.step.N → llm/browser spans.
3. **SQLiteTraceExporter:** Populates runs/steps tables from completed spans.
4. **Trace correlation:** Logs include trace_id and span_id.
5. **Same topology:** Local dev and production run identical observability stack.
