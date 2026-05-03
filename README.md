# Janus

**An API for browser agents.** Natural language in, browser actions out, structured data back.

Named for the Roman god of doorways and transitions — Janus sits between a user's intent and the browser, translating one into the other and back.

---

## What it is

Janus is a control plane for browser automation agents. It exposes two primary APIs:

- **`POST /api/interact`** — Say what you want done in natural language. Janus translates it into a plan, executes it via Playwright, and returns a trace of what happened.
- **`GET /api/extract`** — Given a run, extract structured data from the browser's final page state.

Every execution produces a trace: each step logs its action, latency, status, errors, and screenshots. The goal is not just an agent that works — but one you can inspect, debug, and trust.

---

## Current state

Early but building. The action vocabulary is defined, the API stubs exist, and the core loop is taking shape.

```
plan → act → observe → recover → extract → trace
```

See [`docs/roadmap.md`](docs/roadmap.md) for the full build plan and [`docs/understanding.md`](docs/understanding.md) for ongoing design thinking.

---

## Action vocabulary

| Action | Description |
|---|---|
| `goto` | Navigate to a URL |
| `click` | Click an element |
| `type` | Type text into an element |
| `press` | Press a key |
| `scroll` | Scroll the page |
| `select` | Select an option |
| `back` | Navigate back |
| `hover` | Hover over an element |
| `screenshot` | Capture the page |
| `upload_file` | Upload a file |
| `confirm_human_checkpoint` | Pause for human approval |

---

## Stack

- **Python** + **FastAPI** — API layer
- **Playwright** — Browser automation
- **Pydantic** — Action schemas and validation
- **SQLite** — Trace storage (starting)

---

## Getting started

```bash
pip install -r requirements.txt
playwright install
cp .env.example .env  # add your API keys
uvicorn app.main:app --reload
```

---

## Project structure

```
app/
  main.py        — FastAPI server, /interact, /extract endpoints
  model.py       — Action type definitions and Pydantic schemas
  browser.py     — Playwright controller (in progress)
  runner.py      — Execution engine (in progress)
artifacts/
  screenshots/   — Step-level screenshots per run
  traces/        — Playwright trace zips
docs/
  roadmap.md     — Full build plan and architecture deep-dive
  understanding.md — Design notes and open questions
```

---

## Name

Janus is the Roman god of beginnings, transitions, and doorways. Fitting for a system that stands at the threshold between human intent and browser automation.
