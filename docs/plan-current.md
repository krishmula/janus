# Current Implementation Plan: LLMProvider + Hybrid Planner

> This document captures the active design decisions and implementation todos for wiring the LLMProvider abstraction and hybrid planner/executor loop into `/api/interact`.

---

## 1. Current State

### What exists
- `app/main.py`: FastAPI scaffold with `/api/interact` and `/api/extract` endpoints
- `app/planner.py`: Placeholder `plan()` returning `[{"type": "goto", "url": instruction}]`
- `app/executor.py`: Placeholder `run()` that loops through actions with zero page-state awareness
- `app/model.py`: Pydantic `Action` union (`GotoAction`, `ClickAction`, etc.) + request/response models
- `app/browser.py`: Empty scaffold
- `requirements.txt`: `fastapi`, `uvicorn`, `playwright`, `pydantic`, `python-dotenv`, `httpx`

### What's broken / incoherent
- `main.py` calls `plan(body.prompt)` → gets `list[dict]` → passes to `run(translated_prompt)` which expects a `str`, not `list[dict]`
- The executor has no observer, no LLM step-decision, no validation, no repair loop

---

## 2. Design Decisions

### 2.1 LLMProvider Interface

**Decision**: Two domain-specific methods rather than one generic `chat()` method.

```python
class LLMProvider(ABC):
    @abstractmethod
    async def generate_plan(
        self, instruction: str, max_steps: int = 10
    ) -> list[dict[str, Any]]:
        """Generate high-level action plan from natural language instruction."""

    @abstractmethod
    async def decide_next_action(
        self,
        goal: str,
        plan_step: dict[str, Any],
        page_state: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Given observed page state, return the concrete next action."""
```

**Rationale**:
- `generate_plan` can use higher temperature / more creative model settings
- `decide_next_action` should use low temperature (deterministic) since it operates on structured page state
- Different providers handle structured output differently; isolating the two call sites makes provider-specific tuning easy

### 2.2 Raw Dicts vs. Pydantic at the Provider Boundary

**Decision**: Return raw `dict` from both methods. Let the executor validate into Pydantic `Action` models.

**Rationale**:
- The executor is the deterministic chokepoint where all LLM output gets scrubbed
- The repair loop needs the raw dict to feed back into the LLM ("Invalid action X. Allowed actions: [...]. Try again.")
- Plan steps are intermediate representations (human-readable targets), not final validated actions
- Keeps the provider generic and decoupled from business-domain schemas

**Validation pipeline** (in executor):
```python
raw_action = await llm.decide_next_action(...)
validated = Action.model_validate(raw_action)      # Schema check
assert validated.type in ALLOWED_ACTIONS            # Vocab check
assert is_valid_url(validated.url)                  # Param check (if goto)
```

### 2.3 Structured Output Strategy

**Decision**: Use Gemini's JSON mode (`response_mime_type="application/json"`) with dynamically generated JSON Schema from Pydantic models.

**Rationale**:
- More reliable than freeform JSON parsing
- Maps cleanly to OpenAI/Anthropic structured output later
- Function calling is overkill here (not invoking external tools, generating an internal DSL)

### 2.4 SDK Choice for Gemini

**Decision**: Use `google-generativeai` Python SDK.

**Rationale**:
- Standard, well-documented Python SDK
- Good auth, retry, and structured output helpers
- Async support via `asyncio.to_thread()` is sufficient for MVP
- Raw `httpx` would require reimplementing auth, error handling, and JSON mode

**Dependency**: Add `google-generativeai>=0.7.0` to `requirements.txt`.

---

## 3. Target Architecture

### End-to-end flow for `/api/interact`

```text
POST /api/interact
  |
  v
main.py: interact(body)
  |
  v
Phase 1: Plan
  llm.generate_plan(instruction, max_steps)
  -> list[dict] (high-level action plan)
  |
  v
Phase 2: Execute (Hybrid Loop)
  for each plan_step:
    1. Observe: observer.capture_state()
       -> page_state (URL, title, smart DOM, screenshot)
    2. Decide: llm.decide_next_action(goal, plan_step, page_state, history)
       -> dict (concrete next action)
    3. Validate: Action.model_validate() + vocab + params
       -> repair loop if invalid (max 2 retries)
    4. Execute: browser.execute_action(validated)
       -> step_result (status, latency, screenshot, error)
    5. Record: append to history
       -> break if status == "failed" and unrecoverable
  |
  v
Return: JSONResponse({"steps": results})
```

### Core loop

```text
plan -> validate -> act -> observe -> decide -> recover or continue -> extract -> report
```

---

## 4. File Changes

### 4.1 New Files

| File | Purpose |
|------|---------|
| `app/llm.py` | `LLMProvider` ABC + `GeminiProvider` implementation |
| `app/observer.py` | Page state extraction (smart DOM, URL, title, screenshot) |

### 4.2 Modified Files

| File | Changes |
|------|---------|
| `app/planner.py` | Replace placeholder with `llm.generate_plan()` call |
| `app/executor.py` | Implement hybrid loop: observe → decide → validate → execute |
| `app/main.py` | Fix wiring: pass plan + goal to executor correctly |
| `app/browser.py` | Add Playwright execution primitives (goto, click, type, etc.) |
| `requirements.txt` | Add `google-generativeai>=0.7.0` |
| `.env.example` | Add `LLM_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_MODEL` |

---

## 5. Implementation Todos

### Phase 1: LLM Provider
- [ ] Create `app/llm.py` with `LLMProvider` ABC
- [ ] Implement `GeminiProvider` with `_generate_json()` helper
- [ ] Add `generate_plan()` with planner system prompt
- [ ] Add `decide_next_action()` with step executor system prompt
- [ ] Add JSON schema generation from Pydantic models
- [ ] Wire provider selection from `LLM_PROVIDER` env var

### Phase 2: Observer
- [ ] Create `app/observer.py` with `capture_state()`
- [ ] Implement minimal page state: URL, title, visible text
- [ ] Add smart DOM extraction (interactive elements, headings)
- [ ] Add screenshot capture per step

### Phase 3: Executor + Validation
- [ ] Rewrite `app/executor.py` with hybrid loop
- [ ] Add `Action.model_validate()` + vocab + param validation
- [ ] Implement repair loop (max 2 retries for invalid LLM output)
- [ ] Add error taxonomy: `selector_not_found`, `timeout`, `navigation_failed`, `unknown`
- [ ] Add step result recording (status, latency, screenshot, error)

### Phase 4: Browser Primitives
- [ ] Implement `browser.py` with Playwright actions:
  - `goto(url)`
  - `click(target)`
  - `type(target, text)`
  - `press(key)`
  - `scroll(direction, amount)`
  - `screenshot()`
- [ ] Add persistent browser context support
- [ ] Add timeout and error handling

### Phase 5: Integration
- [ ] Fix `app/main.py` wiring
- [ ] Add `InteractRequest.options` (max_steps, record_screenshots)
- [ ] Update response schema to include `run_id`, `status`, `final_output`, `reliability_score`
- [ ] Add structured logging per step

### Phase 6: Config + Deps
- [ ] Add `google-generativeai>=0.7.0` to `requirements.txt`
- [ ] Update `.env.example` with Gemini config
- [ ] Test end-to-end with a simple instruction (e.g., "Go to example.com")

---

## 6. Prompt Templates (Draft)

### Planner System Prompt
```
You are a browser automation planner. Given a user instruction, output a JSON object with an "actions" array.

Each action must use ONLY these types: goto, click, type, press, scroll, screenshot, extract.
Do not invent new action types.

Rules:
- Keep plans concise (max {max_steps} steps).
- Use human-readable descriptions for targets (e.g., "search input", "first result link").
- Include a screenshot action after significant state changes.
- End with extract if the goal implies data collection.

Output format:
{"actions": [{"type": "goto", "url": "..."}, ...]}
```

### Step Executor System Prompt
```
You are a browser automation executor. The user's goal is: {goal}.

The current planned step is: {plan_step}.

The current page state is:
- URL: {url}
- Title: {title}
- Interactive elements: {interactive_elements}
- Visible text preview: {visible_text}

Your task: output a single action object to execute now.
If the page state is unexpected, adapt using only allowed actions.
If you cannot proceed, output {"type": "screenshot"} to capture state for debugging.

Allowed actions: goto, click, type, press, scroll, screenshot, extract.
Output format: {"type": "...", ...}
```

### Repair Prompt (on validation failure)
```
The previous action was invalid: {error_message}

Invalid action: {invalid_action}

Allowed actions: {allowed_actions}
Please output a corrected action using only allowed types and valid parameters.
```

---

## 7. Open Questions

1. **Should `generate_plan` return the full plan or a plan preview?**
   - Decision: Full plan. The UI can show a preview later.

2. **Should the executor stop on first failure or attempt recovery?**
   - Decision: Attempt one auto-retry per step, one LLM-assisted recovery per run, then fail clearly.

3. **How much page state is too much for the step executor context?**
   - Decision: Start with `standard` observer mode (URL, title, interactive elements, headings, visible text preview). Defer `full` DOM tree to later.

4. **Should the LLM provider handle retry logic (network failures) or should the caller?**
   - Decision: Provider handles API-level retries (SDK default). Caller handles business-level retries (repair loop).

---

## 8. Success Criteria for This Plan

- [ ] `POST /api/interact` accepts a natural language instruction
- [ ] LLM generates a structured action plan
- [ ] Executor runs each step with page-state awareness
- [ ] Invalid LLM outputs are caught, repaired, and retried
- [ ] Each step produces a result with status, latency, and screenshot
- [ ] End-to-end demo: "Go to example.com and take a screenshot" works
