# Agent Observability Design

**Date:** 2026-05-06
**Status:** Draft
**Author:** Janus Team
**Extends:** [InteractAPI Markov Agent Design](./superpowers/specs/2026-05-06-interactapi-markov-agent-design.md)

## Problem

The Markov agent spec defines trace storage (SQLite `runs`/`steps` tables) and per-step structured logging, but there's no broader observability design. Agent systems are inherently harder to debug than traditional software — the LLM makes non-deterministic decisions, browser state is fragile, and failures cascade in unexpected ways. We need observability that serves three audiences:

1. **Developers** — debugging why a run failed, tracing LLM decisions, replaying sessions
2. **End users** — seeing what the agent did on their behalf, step-by-step progress, screenshots
3. **Production operators** — aggregate metrics, success rates, cost tracking, alerting

## Design Decisions

### 1. OpenTelemetry as the Observability Backbone

All three signal types flow through the OpenTelemetry SDK:

- **Traces** — one trace per agent run, spans per step (LLM call, browser action, extraction)
- **Metrics** — run duration, step count, LLM latency, token usage, success rates
- **Logs** — structured JSON, correlated to traces via `trace_id` and `span_id`

**Rationale:** OTel is the industry standard. Single SDK, auto-instrumentation for FastAPI/Playwright, pluggable backends. The executor emits telemetry; storage and visualization are separate concerns.

**Key shift:** The Markov spec's SQLite trace storage becomes an **OTel SpanExporter** — the `runs`/`steps` tables are populated by processing completed spans, not by direct writes in the executor loop. This decouples storage from execution.

### 2. Trace Model

Each agent run produces one **trace** with this span hierarchy:

```
Trace: agent.run (run_id: abc123)
├── Span: agent.step.0 (action: goto, url: "...")
│   ├── Span: llm.decide_next_action (model: gemini-2.0-flash, tokens: 1234)
│   ├── Span: browser.execute (action: goto, latency_ms: 800)
│   └── Span: browser.extract_page_state (smart DOM extraction)
├── Span: agent.step.1 (action: click, target: "search button")
│   ├── Span: llm.decide_next_action (...)
│   ├── Span: browser.execute (...)
│   └── Span: browser.extract_page_state (...)
├── ...
└── Span: agent.complete (status: done, result: "Found pricing: $99/mo")
```

**Span attributes per level:**

| Span | Key Attributes |
|------|---------------|
| `agent.run` | `run_id`, `goal`, `status` (completed/max_steps/loop_detected/failed), `total_steps`, `total_latency_ms`, `total_tokens`, `total_cost_usd` |
| `agent.step.N` | `step_number`, `action_type`, `action_data` (JSON), `status` (success/failed), `error` |
| `llm.decide_next_action` | `model`, `input_tokens`, `output_tokens`, `latency_ms`, `temperature` |
| `browser.execute` | `action_type`, `target`, `latency_ms`, `success` |
| `browser.extract_page_state` | `url`, `title`, `element_count`, `latency_ms` |

### 3. Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `agent.run.duration` | Histogram | Total run time in seconds |
| `agent.run.steps` | Histogram | Number of steps per run |
| `agent.run.status` | Counter | Runs by terminal status |
| `agent.llm.latency` | Histogram | LLM call latency |
| `agent.llm.tokens` | Histogram | Tokens per LLM call (input + output) |
| `agent.llm.cost` | Histogram | Cost per LLM call in USD |
| `agent.browser.action_latency` | Histogram | Browser action latency |
| `agent.browser.action_errors` | Counter | Failed browser actions by error type |

### 4. Executor Integration

The executor's main loop becomes an **instrumented pipeline**. Instead of directly writing to SQLite, it wraps each operation in an OTel span.

```python
async def run(goal: str, run_id: str):
    tracer = trace.get_tracer("janus.agent")
    meter = metrics.get_meter("janus.agent")

    with tracer.start_as_current_span("agent.run", attributes={
        "run_id": run_id,
        "goal": goal,
    }) as run_span:
        step = 0
        while step < max_steps:
            with tracer.start_as_current_span(f"agent.step.{step}") as step_span:
                action = await llm.decide_next_action(goal, last_action, page_state)
                result = await browser.execute(action)
                page_state = await browser.extract_page_state()
                meter.create_counter("agent.run.steps").add(1)
                if action.type == "done":
                    break
                step += 1
```

**The SQLiteTraceExporter** receives completed spans and writes them to the `runs` and `steps` tables:

```python
class SQLiteTraceExporter(SpanExporter):
    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            if span.name == "agent.run":
                self._write_run(span)
            elif span.name.startswith("agent.step."):
                self._write_step(span)
        return SpanExportResult.SUCCESS
```

### 5. Token & Cost Tracking

**Token counting:** Gemini SDK returns `usage_metadata` with `prompt_token_count` and `candidates_token_count`. Set as span attributes: `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`.

**Cost computation:**
```python
MODEL_PRICING = {
    "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},  # per 1K tokens
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.005},
    "gpt-4o": {"input": 0.005, "output": 0.015},
}
```
Cost = `(input_tokens * input_price + output_tokens * output_price) / 1000`. Recorded as `janus.llm.cost_usd` on the span and `agent.llm.cost` metric.

### 6. Structured Logging with Trace Correlation

Every log line includes `trace_id` and `span_id`:

```python
class OTelLogHandler(logging.Handler):
    def emit(self, record):
        span = trace.get_current_span()
        ctx = span.get_span_context()
        record.trace_id = format(ctx.trace_id, '032x') if ctx.trace_id else ""
        record.span_id = format(ctx.span_id, '016x') if ctx.span_id else ""
```

**Log levels:** `DEBUG` (LLM prompts, full page state), `INFO` (step completion, run start/end), `WARNING` (loop detection approaching), `ERROR` (action failures, LLM errors).

### 7. Containerized Dev & Production Topology

**The principle: local dev and production run the same topology.**

```yaml
services:
  backend:
    build: .
    ports: ["8000:8000"]
    environment:
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
      OTEL_SERVICE_NAME: janus-backend
    depends_on: [otel-collector]

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [backend]

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    ports: ["4317:4317", "4318:4318"]
    volumes: ["./otel-collector-config.yaml:/etc/otelcol-contrib/config.yaml"]

  grafana:
    image: grafana/grafana:latest
    ports: ["3001:3000"]

  tempo:
    image: grafana/tempo:latest
    ports: ["3200:3200"]

  loki:
    image: grafana/loki:latest
    ports: ["3100:3100"]

  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes: ["./prometheus.yml:/etc/prometheus/prometheus.yml"]
```

**Production (Fly.io / Railway):** Same topology — backend + frontend as Fly.io apps, Grafana Cloud for observability (Tempo + Loki + Prometheus hosted). OTel Collector config is identical; only endpoints change.

**SQLite trace store** still exists as a local fallback and for API responses. The SQLiteTraceExporter runs in the backend alongside OTel export to the collector.

### 8. SQLite Trace Store Schema

```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,
    final_result TEXT,
    final_screenshot_path TEXT,
    final_page_state TEXT,
    trace_id TEXT,                 -- OTel trace ID
    total_tokens INTEGER,
    total_cost_usd REAL,
    total_latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    step_number INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    action_data TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    latency_ms INTEGER,
    screenshot_path TEXT,
    page_state TEXT,
    span_id TEXT,                   -- OTel span ID
    llm_input_tokens INTEGER,
    llm_output_tokens INTEGER,
    llm_cost_usd REAL
);

CREATE TABLE daily_metrics (
    date TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    PRIMARY KEY (date, metric_name)
);
```

### 9. Layered Implementation

| Layer | What | When |
|-------|------|------|
| **1: Structured Traces** | OTel SDK setup, instrument Markov loop, SQLiteTraceExporter, structured logging | Alongside Markov agent |
| **2: Token & Cost Tracking** | Token counting from Gemini, cost computation, aggregate metrics | After Layer 1 |
| **3: Metrics Export** | OTel metrics, Prometheus exporter | After Layer 1 |
| **4: Production Backend** | Grafana Cloud, daily_metrics aggregation, alerting, dashboards | When there's real traffic |

**Layers 1-2 are required for the Markov agent to ship.**

## File Changes

### Additions

| File | What |
|------|------|
| `app/telemetry.py` | OTel SDK setup |
| `app/telemetry/exporters.py` | SQLiteTraceExporter |
| `app/telemetry/cost.py` | Model pricing, cost computation |
| `docker-compose.yml` | Full containerized topology |
| `otel-collector-config.yaml` | Collector pipeline config |
| `prometheus.yml` | Prometheus scrape config |
| `grafana/provisioning/` | Grafana datasource/dashboard provisioning |

### Modifications

| File | What |
|------|------|
| `app/executor.py` | Instrument with OTel spans |
| `app/llm/gemini.py` | Instrument with OTel span, add token counting |
| `app/browser.py` | Instrument with OTel spans |
| `app/main.py` | Add OTel FastAPI instrumentation |
| `requirements.txt` | Add opentelemetry-* packages |

## Open Questions

1. **Grafana dashboards:** Provision default dashboards or leave for manual setup?
2. **Alerting:** What alerts are critical? (success rate < 80%, cost > $X/day, latency p99 > 30s)
3. **Trace retention:** How long to keep traces in Tempo?
