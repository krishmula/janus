# Markov Agent + Observability Implementation Plan

**Goal:** Replace the two-phase planner/executor with a Markov Chain iterative agent loop, instrument it with OpenTelemetry, and store traces in SQLite.

**Architecture:** Each LLM call receives only goal + last action + current page state. No full plan, no execution history. The agent loop is memoryless and adaptive. Observability flows through OTel SDK — SQLite is populated by an OTel SpanExporter, not by direct writes in the executor.

**Tech Stack:** Python, FastAPI, Playwright, Pydantic, google-genai, OpenTelemetry SDK, SQLite, Docker Compose

---

## Slicing Strategy

Each slice is a **complete, demonstrable vertical feature**. You can stop after any slice and have a working system. Slices build on each other — don't skip ahead.

```
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

Replace the two-phase planner with a single-step LLM call. The agent loop becomes: `goal + last_action + page_state → LLM → single action → execute → repeat`.

### Why

This is the architectural foundation. Everything else (smart DOM, traces, OTel) wraps around this loop. Until this works, nothing else matters.

### What Changes

**Delete:**
- `app/planner.py` — no more upfront planning
- `app/llm/base.py` → remove `generate_plan()` method
- `app/llm/gemini.py` → remove `generate_plan()` method
- `app/llm/schemas.py` → remove `_PLAN_RESPONSE_SCHEMA`
- `app/llm/prompts.py` → remove `PLANNER_SYSTEM_PROMPT`

**Modify:**
- `app/model.py` — add `DoneAction`, remove unused action types (`select`, `back`, `hover`, `upload_file`, `confirm_human_checkpoint`), update `Action` union to 7 types only
- `app/llm/base.py` — simplify `decide_next_action()` signature to `(goal, last_action, page_state)`
- `app/llm/gemini.py` — implement new `decide_next_action()` with simplified signature
- `app/llm/prompts.py` — replace with single unified system prompt (from interact-api.md §9)
- `app/llm/schemas.py` — update `_ACTION_RESPONSE_SCHEMA`: replace `extract` with `done`
- `app/browser.py` — implement Playwright: goto, click, type, press, scroll, screenshot, plus browser context management
- `app/executor.py` — rewrite as the Markov main loop
- `app/main.py` — wire up new executor, remove planner import, add run_id generation

### Categorization

| Work | Category | Rationale |
|------|----------|-----------|
| Pydantic models (DoneAction, simplified Action) | **Agent-handleable** | Mechanical schema changes. You already know Pydantic. |
| JSON schema updates | **Agent-handleable** | Boilerplate dict definitions that mirror the Pydantic models. |
| Prompt text (system prompt from §9) | **Agent-handleable** | The prompt is specified in the spec. Copy-paste with minor formatting. |
| Markov loop architecture | **Must-learn** | This is the core insight. Understand why memoryless + adaptive beats planning. Understand the loop structure: `while step < max_steps`. |
| Browser lifecycle (per-request, context isolation) | **Must-learn** | Critical design decision. Understand why per-request browsers avoid concurrency issues, and why fresh contexts prevent state leakage. |
| LLM provider signature change | **In between** | The signature change is mechanical, but understanding *why* we removed `plan_step` and `history` teaches you about token efficiency. |
| Playwright action implementations (goto, click, type, etc.) | **In between** | The pattern is repetitive (locator → action → wait), but understanding Playwright's auto-waiting and timeout model is valuable. |
| API wiring (main.py) | **Agent-handleable** | Glue code connecting FastAPI to the executor. |

### Verification

- `POST /api/interact` with `{"prompt": "go to example.com"}` returns a response with steps
- The browser navigates to example.com
- The response includes at least one step with action type `goto`
- The response includes a `final_result` field

### Tests

**Unit tests:**
- `test_model.py` — DoneAction has correct fields, Action union includes all 7 types, old types are removed
- `test_executor.py` — Loop terminates after max_steps, loop returns list of steps, done action breaks loop
- `test_llm_schemas.py` — Action schema includes `done`, excludes `extract`

**Integration tests:**
- `test_api_interact.py` — POST /api/interact returns 200, response has `run_id` and `steps`
- `test_markov_e2e.py` — Mocked LLM returns a sequence of actions, executor produces expected steps

---

## Slice 2: Smart DOM + Resilience

### What

Add smart DOM extraction so the LLM sees meaningful page state. Add loop detection and error handling so the agent doesn't spin forever or crash on failures.

### Why

Without smart DOM, the LLM receives only URL + title — insufficient for real websites. Without loop detection, the agent can get stuck retrying the same failed action. Without error recovery, one failed action kills the entire run.

### What Changes

**Modify:**
- `app/browser.py` — add `extract_page_state()` returning smart DOM: URL, title, interactive elements with text labels and ARIA roles, headings, visible text preview
- `app/executor.py` — add state fingerprinting for loop detection (hash of interactive elements + last action type + last action target), add `last_successful_action` tracking for error recovery, add `loop_detected` termination condition

**New concepts in executor:**
- State fingerprint: `hash(interactive_elements + last_action_type + last_action_target)`
- Loop detection: if same fingerprint appears 2 consecutive times → abort with `loop_detected`
- Error context: on failure, next LLM call receives `last_successful_action` alongside `last_action`
- Three termination conditions: LLM says `done`, max steps reached, loop detected

### Categorization

| Work | Category | Rationale |
|------|----------|-----------|
| Smart DOM extraction concept | **Must-learn** | This is the key insight that makes Markov agents work on real pages. Understand what to include (interactive elements, ARIA roles) and what to exclude (full DOM, CSS classes). Understand why ~3-5K tokens is the sweet spot. |
| Playwright `evaluate()` for DOM extraction | **Must-learn** | You're running JS in the browser to extract structured data. Understand how `page.evaluate()` works, how to traverse the DOM, and how to filter for interactive elements. |
| State fingerprinting logic | **Must-learn** | Understand why we hash interactive elements + last action, not just URL. Understand why 2 consecutive identical fingerprints means "this action had no effect." |
| Error recovery pattern (last_successful_action) | **Must-learn** | This is the key to adaptive recovery. Understand why we only include it on failure, and how it gives the LLM enough context to recover without full history. |
| Interactive element selectors (CSS/ARIA) | **Agent-handleable** | The selectors for finding buttons, inputs, links, etc. are mechanical. An agent can write these. |
| Hashing implementation | **Agent-handleable** | Standard library usage. No learning value. |

### Verification

- `extract_page_state()` on example.com returns URL, title, and at least one interactive element
- Agent detects a loop when the same action is attempted twice with no page change
- Agent receives `last_successful_action` context when an action fails
- Agent terminates with `loop_detected` status after 2 consecutive identical fingerprints

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

Persist every run and its steps to SQLite. The API returns structured responses with run_id, steps, final_result, and screenshot paths.

### Why

Without trace storage, runs are ephemeral. You can't inspect what happened, debug failures, or demonstrate the agent's capabilities. Traces are the foundation for the dashboard.

### What Changes

**New:**
- `app/trace.py` — SQLite database management: create tables, insert runs/steps, query runs/steps
- `artifacts/janus.db` — SQLite database file (created automatically)

**Modify:**
- `app/executor.py` — after each step, store step data in SQLite; after run completes, store run data
- `app/main.py` — return full API response (run_id, steps, total_steps, final_result, final_screenshot_path)

**Schema (from interact-api.md §11):**
- `runs` table: run_id, goal, status, final_result, final_screenshot_path, final_page_state, created_at
- `steps` table: id, run_id, step_number, action_type, action_data, status, error, latency_ms, screenshot_path, page_state

### Categorization

| Work | Category | Rationale |
|------|----------|-----------|
| SQLite schema creation | **Agent-handleable** | DDL statements. Mechanical. |
| CRUD operations (insert run, insert step, query run) | **Agent-handleable** | Standard SQLite patterns. You know SQL. |
| API response design | **In between** | The response structure is specified in the spec, but understanding what fields matter for debugging (run_id, steps, screenshots) teaches you about agent observability. |
| Screenshot file path management | **Agent-handleable** | File I/O patterns. Mechanical. |
| Why trace storage matters for agent systems | **Must-learn** | Understand why agents need traces more than traditional software. Agents are non-deterministic — you can't reproduce a failure without a trace. |

### Verification

- Run completes and `artifacts/janus.db` contains the run and its steps
- Each step has action_type, status, latency_ms, and screenshot_path
- Run status is one of: completed, max_steps, loop_detected, failed

### Tests

**Unit tests:**
- `test_trace.py` — insert_run creates a row, insert_step creates a row, get_run returns correct data, get_steps returns correct list

**Integration tests:**
- `test_trace_e2e.py` — complete run stores all steps, run with failure stores error status, run with loop_detected stores correct status
- `test_api_response.py` — POST /api/interact returns response matching expected schema

---

## Slice 4: OTel Instrumentation

### What

Wrap the Markov loop with OpenTelemetry spans. Each run becomes a trace, each step becomes a span, each LLM call and browser action gets its own child span. A custom SQLiteTraceExporter populates the database from completed spans.

### Why

OTel is the industry standard for observability. It decouples telemetry generation from storage — the executor emits spans, and exporters handle storage. This means you can swap SQLite for Grafana Cloud without changing executor code.

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
```
Trace: agent.run (run_id)
├── Span: agent.step.0 (action: goto)
│   ├── Span: llm.decide_next_action (model, tokens, latency)
│   ├── Span: browser.execute (action, latency, success)
│   └── Span: browser.extract_page_state (url, title, element_count, latency)
├── Span: agent.step.1 (action: click)
│   └── ...
└── Span: agent.complete (status, result)
```

### Categorization

| Work | Category | Rationale |
|------|----------|-----------|
| OTel SDK setup (TracerProvider, MeterProvider) | **Must-learn** | Understand how OTel initializes, how providers work, and how exporters are registered. This is the foundation of the observability system. |
| Span hierarchy design | **Must-learn** | The span hierarchy (agent.run → agent.step.N → llm/browser) is a design decision. Understand why we nest spans this way and what attributes to put at each level. |
| SQLiteTraceExporter | **Must-learn** | This is the bridge between OTel and your storage. Understand how SpanExporter works, how to process completed spans, and how to map span attributes to database columns. |
| Structured logging with trace correlation | **Must-learn** | Understand how to correlate logs with traces using trace_id and span_id. This is what makes debugging possible. |
| OTel FastAPI instrumentation | **Agent-handleable** | One-line auto-instrumentation. Mechanical. |
| Span attribute setting | **Agent-handleable** | Repetitive `span.set_attribute()` calls. Mechanical. |
| Metric definitions (counters, histograms) | **In between** | The metric names are specified in the spec, but understanding when to use counter vs histogram, and what dimensions to include, teaches you about metrics design. |

### Verification

- Run completes and spans are exported to SQLite
- `trace_id` and `span_id` fields are populated in runs/steps tables
- Structured logs include trace_id and span_id
- LLM call spans include token counts

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

### Why

Without cost tracking, you can't manage LLM expenses. Token counting also helps you understand context efficiency — are you sending too many tokens per call?

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

### Categorization

| Work | Category | Rationale |
|------|----------|-----------|
| Gemini usage_metadata extraction | **In between** | The API call is mechanical, but understanding how Gemini reports tokens teaches you about LLM cost models. |
| Cost computation formula | **Agent-handleable** | Simple arithmetic. Mechanical. |
| Metric recording (histograms, counters) | **Must-learn** | Understand when to use histograms vs counters, what dimensions to include, and how metrics enable alerting. |
| Token counting for context efficiency | **Must-learn** | Understand why ~2-5K tokens per call is the target, and how to monitor drift. |

### Verification

- Run completes and runs table includes total_tokens and total_cost_usd
- Each step in steps table includes llm_input_tokens, llm_output_tokens, llm_cost_usd
- Cost computation is correct for known model pricing

### Tests

**Unit tests:**
- `test_cost.py` — gemini-2.0-flash pricing computes correctly, gemini-2.5-pro pricing computes correctly, unknown model raises error

**Integration tests:**
- `test_token_tracking_e2e.py` — complete run populates token counts in trace, total cost matches sum of step costs

---

## Slice 6: Docker + Production Topology

### What

Containerize the backend and add the observability stack: OTel Collector, Grafana, Tempo, Loki, Prometheus. Local dev runs the same topology as production.

### Why

Without containerization, you can't reproduce production issues locally. The observability stack makes traces, metrics, and logs visible in Grafana dashboards.

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

### Categorization

| Work | Category | Rationale |
|------|----------|-----------|
| docker-compose.yml | **Agent-handleable** | Boilerplate YAML. Mechanical. |
| OTel Collector config | **Must-learn** | Understand how the collector pipeline works: receivers → processors → exporters. This is the backbone of the observability system. |
| Grafana provisioning | **Agent-handleable** | Boilerplate YAML. Mechanical. |
| Grafana dashboard design | **In between** | The dashboard structure is specified, but understanding what to visualize and why teaches you about operational visibility. |
| Prometheus scrape config | **Agent-handleable** | Boilerplate YAML. Mechanical. |
| Why local dev should match production | **Must-learn** | Understand the "same topology" principle: if it works locally, it works in production. Only endpoints change. |

### Verification

- `docker compose up` starts all services
- Grafana is accessible at localhost:3001
- Traces appear in Tempo
- Logs appear in Loki
- Metrics appear in Prometheus

### Tests

**Integration tests:**
- `test_docker_e2e.py` — docker compose up succeeds, all services are healthy, end-to-end flow produces traces in Grafana

---

## Dependencies

```
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

1. **Memoryless:** Each LLM call receives only goal + last_action + page_state. No full plan, no execution history.
2. **Adaptive:** The LLM sees actual page state on every step and adjusts naturally.
3. **Token-efficient:** ~2-5K tokens per call instead of ~10-20K with full history.
4. **Smart DOM:** URL + title + interactive elements + headings + visible text. Not full DOM.
5. **7 actions:** goto, click, type, press, scroll, screenshot, done.
6. **Loop detection:** Hash interactive elements + last action. Same combo 2x → abort.
7. **Three terminations:** LLM says done, max steps, loop detected.
8. **No auto-retry:** LLM adapts based on error context. Blind retry doesn't help.
9. **Per-request browser:** Simple, clean, no concurrency issues.
10. **SQLite traces:** One database at `artifacts/janus.db`.

From `docs/observability.md`:

1. **OTel as backbone:** Traces, metrics, logs all flow through OTel SDK.
2. **Span hierarchy:** agent.run → agent.step.N → llm/browser spans.
3. **SQLiteTraceExporter:** Populates runs/steps tables from completed spans.
4. **Trace correlation:** Logs include trace_id and span_id.
5. **Same topology:** Local dev and production run identical observability stack.
