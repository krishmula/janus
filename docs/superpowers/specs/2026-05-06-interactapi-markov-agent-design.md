# InteractAPI: Markov Agent Design

**Date:** 2026-05-06
**Status:** Draft
**Author:** Janus Team

## Problem

The current InteractAPI uses a two-phase planner/executor architecture: an upfront `generate_plan()` call produces a full action list, then each action is executed sequentially. This is over-engineered for a browser automation agent — the LLM doesn't need a full plan, and passing execution history on every call bloats context windows.

## Proposed Architecture

Replace the two-phase planner with a Markov Chain-like iterative loop. Each step:

```
goal + last_action + page_state → LLM → single action
execute action → result + page_state
repeat until done or abort
```

### Key Properties

- **Memoryless:** Each LLM call receives only the goal, the last action, and the current page state. No full plan, no execution history.
- **Adaptive:** The LLM sees the actual page state on every step and adjusts naturally. No mismatch between planned state and real state.
- **Token-efficient:** ~2-5K tokens per call instead of ~10-20K with full history.

## Design Decisions

### 1. Page State: Smart DOM

The page state passed to the LLM on each step contains:
- URL
- Page title
- Interactive elements with text labels and ARIA roles (clickable, typeable, selectable)
- Visible headings and text content

Not included: full DOM tree, CSS class names, `<div>` wrappers, non-visible elements.

**Rationale:** The LLM needs enough context to decide what to do next. URL + title alone is insufficient. Full DOM is too expensive (~10-20K tokens). Smart DOM (~3-5K) is the right balance.

### 2. Action Context Structure

**On success:**
```python
{
    "goal": "find pricing for X",
    "last_action": {"type": "click", "target": "search button", "status": "success"},
    "page_state": { ... smart DOM ... }
}
```

**On failure:**
```python
{
    "goal": "find pricing for X",
    "last_action": {"type": "click", "target": "search button", "status": "failed", "error": "not found"},
    "last_successful_action": {"type": "type", "target": "search box", "text": "X", "status": "success"},
    "page_state": { ... smart DOM ... }
}
```

The `last_successful_action` field is only included when the current action failed. This provides the LLM with enough context to recover without passing full history.

### 3. Action Vocabulary

The LLM can emit exactly seven action types:

| Action | Description |
|--------|-------------|
| `goto` | Navigate to a URL |
| `click` | Click an element (target: human-readable descriptor) |
| `type` | Type text into an element |
| `press` | Press a key |
| `scroll` | Scroll the page (direction: up/down, amount: pixels) |
| `screenshot` | Capture current page state for debugging |
| `done` | Signal that the goal is achieved (include result summary) |

**Removed from existing vocab:** `select`, `back`, `hover`, `upload_file`, `confirm_human_checkpoint`, `extract`.
- These can be added back when there's evidence they're needed.
- `extract` is handled by a separate API (ExtractAPI) that runs after InteractAPI completes.

### 4. Loop Detection

Hash the combination of interactive elements + last action. If the same combo appears 2 consecutive times, abort with `loop_detected` error.

```python
state_fingerprint = hash(interactive_elements + last_action_type + last_action_target)
```

**Rationale:** If the page state and the attempted action haven't changed after execution, the action had no effect. Retrying won't help. Abort.

### 5. Termination

Three termination conditions:

| Condition | Trigger | Result |
|-----------|---------|--------|
| LLM says "done" | `{"type": "done", "result": "..."}` | Success — trace includes result + final screenshot |
| Max steps | Budget exhausted (default: 10) | Forced exit — trace includes `max_steps_reached` |
| Loop detected | Same state+action 2 consecutive times | Abort — trace includes `loop_detected` |

**On `done`:** The system auto-captures a final screenshot and final page state. This provides evidence for verification.

### 6. Error Handling

When an action fails (element not found, timeout, etc.), the error is returned as part of the action result:
```python
{"status": "failed", "error": "element not found: search button", ...}
```

The next LLM call receives the failed action (in `last_action`) and the last successful action (in `last_successful_action`), along with the current page state. The LLM can then adapt its approach naturally.

No auto-retry. If the element isn't found, retrying immediately won't help. The LLM is smarter than a blind retry.

### 7. LLM Output Validation

Schema validation only:
- Action type is in the allowed vocabulary
- Required fields are present (e.g., `url` for `goto`, `target` for `click`)

No semantic validation (e.g., URL format). No auto-repair. If the LLM outputs garbage, the action will fail in the browser, and the error gets passed back to the LLM in the next loop iteration.

### 8. Browser Lifecycle

**Now:** Per-request browser. Open at the start of `/api/interact`, close after `done`. Simple, clean, no concurrency issues. Cost: ~1-2s startup per request.

**Future:** Browser pool. Pre-launch N browsers, assign to requests, return to pool. This is a performance optimization, not an architecture change.

Key pattern: Even with a shared browser, each run gets a fresh browser **context** (incognito-like session). Runs don't leak cookies, storage, or state.

### 9. System Prompt

```
You are a browser automation agent. You achieve goals by executing one
browser action at a time.

ALLOWED ACTIONS: goto, click, type, press, scroll, screenshot, done

DECISION RULES:
- Your first action MUST be goto if no page is loaded.
- Use human-readable targets (e.g. "search input", "first result link").
- If the page shows an error or unexpected state, adapt. Do not repeat
  the same failed action.
- Use "done" when the goal is achieved. Include a brief result summary.
- Use "screenshot" when stuck or to capture state for debugging.

FAILURE HANDLING:
- If an action failed, look at the error and current page state.
- Try a different approach. Do not retry the exact same action.
- If you cannot proceed after 2 attempts, use "screenshot" and then
  "done" with a summary of what went wrong.

OUTPUT: A single JSON action object: {"type": "...", ...}
```

### 10. API Response

**`POST /api/interact`** returns:
```json
{
    "run_id": "abc123",
    "goal": "find pricing for X",
    "steps": [
        {"step": 0, "action": {"type": "goto", "url": "..."}, "status": "success", "latency_ms": 1200},
        ...
    ],
    "total_steps": 6,
    "final_result": "Found pricing: $99/mo",
    "final_screenshot": "artifacts/runs/abc123/screenshots/final.png"
}
```

**`POST /api/extract`** takes `run_id` + `schema_name`, looks up the stored trace and final page state, and runs extraction. Separate concern from interact.

### 11. Trace Storage

**Now:** SQLite. One database at `artifacts/janus.db`.

Schema:
```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,          -- completed, max_steps, loop_detected, failed
    final_result TEXT,
    final_screenshot_path TEXT,
    final_page_state TEXT,         -- JSON blob
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    step_number INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    action_data TEXT NOT NULL,      -- JSON blob
    status TEXT NOT NULL,           -- success, failed, completed (for done)
    error TEXT,
    latency_ms INTEGER,
    screenshot_path TEXT,
    page_state TEXT                 -- JSON blob (Smart DOM after this step)
);
```

**Future:** Upgrade to Postgres when multi-instance or high concurrency is needed.

### 12. First Step (Step 0)

The first LLM call receives:
- `goal`: the user's natural language instruction
- `last_action`: null (no previous action)
- `page_state`: {} (no page loaded)

The system prompt handles this: "Your first action MUST be goto if no page is loaded." The LLM must infer a starting URL from the goal.

## File Changes

### Deletions

| File | What |
|------|------|
| `app/planner.py` | Entire file — no more upfront planning |
| `app/llm/base.py` | `generate_plan()` method |
| `app/llm/gemini.py` | `generate_plan()` method |
| `app/llm/schemas.py` | `_PLAN_RESPONSE_SCHEMA` |
| `app/llm/prompts.py` | `PLANNER_SYSTEM_PROMPT` |

### Modifications

| File | What |
|------|------|
| `app/model.py` | Add `DoneAction`, update `Action` union |
| `app/llm/base.py` | Simplify `decide_next_action()` signature (goal, last_action, page_state) |
| `app/llm/gemini.py` | Implement new `decide_next_action()` |
| `app/llm/prompts.py` | Replace with single unified system prompt |
| `app/llm/schemas.py` | Update `_ACTION_RESPONSE_SCHEMA`: replace `extract` with `done` in the action type enum |
| `app/browser.py` | Implement with Smart DOM extraction built in (currently empty) |
| `app/executor.py` | Rewrite as the Markov main loop |
| `app/main.py` | Wire up new executor, remove planner import |

### Additions

| File | What |
|------|------|
| `app/trace.py` | Trace storage (SQLite) |
