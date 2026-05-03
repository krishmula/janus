# Ariadne / Browser Agent Control Plane Roadmap

> Working title: **Ariadne** — a browser automation agent with execution tracing, replay, reliability scoring, and structured extraction.
>
> Core thesis: do not just build an agent that controls a browser. Build the **control plane** that makes browser agents observable, debuggable, measurable, and trustworthy.

---

## 0. North Star

The original challenge asks for an AI agent that automates browser workflows using an `interact API` and, at higher levels, an `extract API`, native-browser control, proxy/extension support, conversational context, scheduled tasks, and strong demos across real websites.

Your version should say:

> I modernized the browser automation challenge into a production-style agent system: natural language in, browser actions out, structured data extraction, step-level traces, screenshots, retries, replay, reliability metrics, and a demo that feels useful rather than toy-like.

### Final deliverable by May 20

A polished repo + Loom demo showing:

1. Natural language command accepted through an API/UI.
2. Agent creates an executable plan.
3. Browser executes the plan.
4. Agent handles errors/retries gracefully.
5. Agent extracts structured data.
6. Every run has an inspectable trace: steps, screenshots, latency, errors, retries, outputs.
7. A reliability/evals page summarizes how well the agent performs across tasks.

---

## 1. Product Positioning

### The project is not

- A generic browser-use clone.
- A thin wrapper around Playwright.
- A flashy demo with no introspection.
- A massive unfinished Level 3 attempt.

### The project is

- A **browser agent runtime**.
- A **traceable execution engine**.
- A **debuggable automation system**.
- A **small but credible control plane for browser agents**.

### Suggested tagline

> Ariadne: the thread through browser automation.

### Core narrative

Browsers are messy. Agents are non-deterministic. Ariadne makes browser automation inspectable: every decision, action, screenshot, retry, and extracted output is visible and replayable.

---

## 2. Scope Strategy

### Primary target

Build **excellent Level 1 + selective Level 2 flavor**.

Level 1 strength:

- Natural-language `interact API`.
- Website-agnostic action model.
- Browser automation through Playwright.
- Clear errors.
- Real demo involving login/search/navigation/interaction.

Selective Level 2 flavor:

- `extract API` returning structured JSON.
- Run trace dashboard.
- Screenshots per step.
- Session persistence.
- Partial support for native-like actions or OS-level fallback only if time permits.

### De-scope aggressively

Skip unless everything else is strong:

- Full cross-platform native browser control.
- Real CAPTCHA solving.
- Full proxy support.
- Full browser extension support.
- Periodic autonomous scheduling.
- Large multi-site benchmark suite.

### Why this scope wins

The challenge rewards demos, robustness, and handling real-world automation issues. Your twist adds infra-grade credibility through observability and reliability measurement.

---

## 3. Architecture Overview

```text
User / UI / API
      |
      v
Instruction Parser
      |
      v
Planner
      |
      v
Action Plan JSON
      |
      v
Executor
      |
      +--> Browser Controller / Playwright
      |
      +--> Observer / Page State / Screenshot / DOM snapshot
      |
      +--> Recovery Engine / Retry / Fallback
      |
      v
Extractor
      |
      v
Structured Output
      |
      v
Trace Store + Dashboard
```

### Core loop

```text
plan -> act -> observe -> evaluate -> recover or continue -> extract -> report
```

This loop is the conceptual heart of the project.

---

## 4. Recommended Tech Stack

### Backend

Recommended: **TypeScript + Node.js + Fastify/Express**

Why:

- Playwright has first-class TypeScript support.
- Good JSON schema validation with Zod.
- Easy deployment and UI integration.

Alternative: Python + FastAPI + Playwright

Use Python if you are much faster in Python and want easier data/eval scripting.

### Browser automation

- Playwright.
- Persistent browser contexts for login sessions.
- Trace/screenshot/video support.

### LLM integration

- Any model with structured JSON support.
- Use schema-constrained output where possible.
- Keep the executor deterministic.

### Database

Start with SQLite or Postgres.

Recommended simple path:

- SQLite for speed early.
- Postgres if deploying with a proper backend.

### UI

- Next.js or simple React/Vite.
- Minimal dashboard is enough.

### Validation

- Zod for TypeScript.
- Pydantic if Python.

### Observability

- Structured JSON logs.
- Trace table in DB.
- Optional OpenTelemetry export later.

---

## 5. System Modules

### 5.1 Instruction Parser

Responsibility:

- Convert a user command into a normalized task object.

Example input:

```json
{
  "instruction": "Search Hacker News for browser automation and open the first relevant result"
}
```

Example normalized task:

```json
{
  "goal": "Search Hacker News for browser automation and open the first relevant result",
  "constraints": {
    "max_steps": 8,
    "requires_login": false,
    "extract_output": true
  }
}
```

What to learn:

- Prompting for structured outputs.
- Schema validation.
- Rejecting ambiguous/unsafe commands.

Tradeoff to reason about:

- More flexible parser = more surprising behavior.
- Stricter parser = less magical but safer and easier to debug.

Recommended choice:

- Start strict. Expand later.

---

### 5.2 Planner

Responsibility:

- Convert a normalized task into an action plan.

Example action plan:

```json
[
  { "type": "goto", "url": "https://news.ycombinator.com" },
  { "type": "click", "target": "search input or Algolia link" },
  { "type": "type", "text": "browser automation" },
  { "type": "press", "key": "Enter" },
  { "type": "click", "target": "first relevant result" },
  { "type": "extract", "schema": "search_result" }
]
```

What to learn:

- Tool/action schemas.
- Planning boundaries.
- How to avoid letting the LLM directly execute arbitrary code.

Tradeoff:

- Big up-front plan vs step-by-step replanning.

Recommended choice:

- Begin with up-front plans for simplicity.
- Add step-by-step replanning only for recovery.

---

### 5.3 Action Model

Define a small action vocabulary.

MVP actions:

```text
goto(url)
click(target)
type(target, text)
press(key)
wait(condition)
extract(schema)
```

Later actions:

```text
scroll(direction)
select(target, value)
back()
hover(target)
upload_file(target, path)
confirm_human_checkpoint(reason)
```

What to learn:

- Why small action spaces are easier to test.
- Why unconstrained agents become flaky.

Tradeoff:

- More actions = more capability but more executor complexity.
- Fewer actions = reliable but less impressive.

Recommended choice:

- Start with 6 actions. Make them excellent.

---

### 5.4 Executor

Responsibility:

- Execute each action using Playwright.
- Track success/failure/latency.
- Capture evidence.

Each execution should produce:

```json
{
  "step_id": "...",
  "action": "click",
  "status": "success",
  "latency_ms": 842,
  "screenshot_path": "...",
  "error": null,
  "page_url_after": "..."
}
```

What to learn:

- Playwright locators.
- Auto-waiting.
- Timeouts.
- Persistent browser contexts.
- Screenshots.

Tradeoff:

- DOM selectors vs visual targeting.

Recommended choice:

- Use DOM/locator-first for MVP.
- Add visual fallback as a stretch.

---

### 5.5 Observer

Responsibility:

- Capture state after each action.

State includes:

- Current URL.
- Page title.
- Screenshot.
- Optional simplified DOM.
- Visible text summary.
- Network/page errors.

What to learn:

- How much state is useful vs too expensive.
- How to summarize page state for an LLM.

Tradeoff:

- Full DOM snapshots are rich but noisy and large.
- Text summaries are compact but lossy.

Recommended choice:

- Store screenshot + URL + title + selected visible text.
- Add DOM snapshot only when debugging extraction.

---

### 5.6 Recovery Engine

Responsibility:

- Classify errors.
- Retry or replan.

Error classes:

```text
selector_not_found
timeout
navigation_failed
blocked_or_captcha
login_required
unexpected_modal
extraction_schema_failed
unknown
```

Recovery examples:

- Timeout: wait and retry once.
- Selector not found: ask LLM for alternative target using page state.
- Modal detected: close modal if safe.
- CAPTCHA: stop, mark blocked, ask human.
- Extraction schema failed: retry extraction with stricter schema.

What to learn:

- Idempotency.
- Retry budgets.
- When not to retry.

Tradeoff:

- Aggressive retries improve success but hide real failures and waste time.
- Conservative retries expose issues but can make the demo brittle.

Recommended choice:

- One automatic retry per step.
- One LLM-assisted recovery per run.
- Then fail clearly.

---

### 5.7 Extract API

Responsibility:

- Convert page content into structured JSON.

Example request:

```json
{
  "run_id": "...",
  "schema": {
    "title": "string",
    "url": "string",
    "summary": "string"
  }
}
```

Example output:

```json
{
  "items": [
    {
      "title": "Example result",
      "url": "https://example.com",
      "summary": "Short description"
    }
  ]
}
```

What to learn:

- DOM extraction.
- Schema validation.
- LLM-assisted extraction vs deterministic extraction.

Tradeoff:

- Deterministic selectors are reliable but site-specific.
- LLM extraction is flexible but less predictable.

Recommended choice:

- Hybrid extraction:
  - deterministic DOM collection first,
  - LLM converts candidate text into schema,
  - Zod validates result.

---

### 5.8 Trace Store

Responsibility:

- Persist runs and steps.

Suggested DB tables:

```text
runs
- id
- instruction
- status
- started_at
- completed_at
- final_output_json
- reliability_score

steps
- id
- run_id
- index
- action_type
- action_payload_json
- status
- latency_ms
- error_type
- error_message
- screenshot_path
- url_before
- url_after
- created_at

artifacts
- id
- run_id
- step_id
- artifact_type
- path_or_blob
- metadata_json
```

What to learn:

- Modeling execution as events.
- Designing for later replay.

Tradeoff:

- Store everything = easy debugging but more storage complexity.
- Store too little = impossible to debug.

Recommended choice:

- Store metadata in DB.
- Store screenshots as files initially.

---

### 5.9 Dashboard

Responsibility:

- Make the agent inspectable.

Must-have UI pages:

1. New run page.
2. Run detail page.
3. Step timeline.
4. Final structured output.
5. Reliability summary.

Run detail page should show:

```text
Instruction
Status
Reliability score
Final JSON
Timeline
  Step 1: goto -> success -> screenshot
  Step 2: click -> failed -> retry -> success -> screenshot
  Step 3: extract -> success -> JSON
```

What to learn:

- Timeline UX.
- Making debugging legible.

Tradeoff:

- Pretty UI vs useful UI.

Recommended choice:

- Useful first. Pretty later.

---

## 6. Observability Concepts to Learn

### Logs

Logs answer:

> What happened?

Use structured logs:

```json
{
  "event": "step_completed",
  "run_id": "...",
  "step_index": 2,
  "action": "click",
  "status": "success",
  "latency_ms": 841
}
```

### Traces

Traces answer:

> How did one request flow through the system?

For Ariadne:

```text
run trace = user instruction + plan + every browser action + observations + output
```

### Metrics

Metrics answer:

> How is the system performing over time?

Track:

- Task success rate.
- Step success rate.
- Average run latency.
- Average retries per run.
- Extraction schema pass rate.
- Top error types.

### Artifacts

Artifacts answer:

> What evidence do we have?

Store:

- Screenshots.
- Optional Playwright trace zip.
- HTML snapshots for failed steps.
- Final JSON output.

---

## 7. Reliability Scoring

Create a simple score from 0 to 100.

Example:

```text
score = 100
- 20 if run failed
- 10 per failed step that recovered
- 5 per retry
- 15 if extraction schema failed once
- 20 if human intervention required
- 10 if runtime exceeds threshold
```

Display:

```text
Reliability: 84/100
- Completed successfully
- 1 retry
- 0 schema failures
- 1 slow navigation
```

Why this matters:

- It makes reliability visible.
- It shows you think like an infra/backend engineer.
- It creates a natural bridge to evals.

---

## 8. Evals Roadmap

### MVP evals

Create 5 deterministic tasks:

1. Search a public site and extract top results.
2. Navigate to a docs page and extract headings.
3. Open a product/listing page and extract item names/prices if public.
4. Handle a modal or cookie banner.
5. Navigate search results and open a specific item.

### Eval result schema

```json
{
  "task_id": "hn_search_001",
  "success": true,
  "steps_total": 6,
  "steps_failed": 1,
  "retries": 1,
  "latency_ms": 9123,
  "extraction_valid": true
}
```

### Metrics dashboard

Show:

```text
5/5 tasks completed
92% step success rate
1.2 avg retries/run
100% schema validation pass rate
```

Tradeoff:

- More tasks gives credibility but costs time.
- Better to have 5 reliable evals than 30 flaky ones.

---

## 9. Security, Safety, and Guardrails

You do not need to overbuild this, but you should show judgment.

### Guardrails to implement

- Do not enter passwords unless user explicitly provides/approves.
- Human approval before destructive actions.
- Block obviously unsafe commands.
- Detect CAPTCHA and stop instead of bypassing.
- Never hide failures.
- Log every action.

### Risky action examples

Require approval for:

- Submit forms.
- Purchase actions.
- Send messages/emails.
- Delete/update account data.
- Apply to jobs.

Human checkpoint response:

```json
{
  "status": "requires_approval",
  "reason": "Agent is about to submit a form",
  "proposed_action": {...}
}
```

---

## 10. Learning Roadmap

### A. Browser Automation

Get good at:

- Playwright basics.
- Locators vs selectors.
- Waiting correctly.
- Browser contexts.
- Session persistence.
- Screenshots/video/traces.
- Handling dynamic pages.
- Debugging failed selectors.

Key intuition:

> Browser automation is not hard because clicking is hard. It is hard because pages are asynchronous, stateful, inconsistent, and full of edge cases.

### B. Agent Systems

Get good at:

- Planning vs execution separation.
- Tool/action schemas.
- Structured outputs.
- Replanning on failure.
- Keeping the LLM away from dangerous execution details.
- Designing small action spaces.

Key intuition:

> The LLM should decide what to do. Deterministic code should decide exactly how to do it whenever possible.

### C. Extraction Systems

Get good at:

- DOM-to-JSON conversion.
- Schema validation.
- Partial data handling.
- LLM-assisted cleanup.
- Normalization.

Key intuition:

> Extraction is only useful when the output is predictable enough for another system to consume.

### D. Observability

Get good at:

- Structured logs.
- Traces.
- Metrics.
- Artifacts.
- Error taxonomies.
- Run dashboards.

Key intuition:

> If an agent fails and you cannot explain why, the system is not production-ready.

### E. Reliability Engineering

Get good at:

- Retry budgets.
- Idempotency.
- Failure classification.
- Graceful degradation.
- Timeouts.
- Recovery paths.

Key intuition:

> Good systems do not avoid failure. They make failure explicit, contained, and recoverable.

### F. Product/Demo Thinking

Get good at:

- Choosing deterministic demos.
- Showing value fast.
- Explaining architecture visually.
- Creating a compelling README.
- Recording a tight Loom.

Key intuition:

> The demo is part of the product. If they cannot understand why it is impressive in 90 seconds, you lose leverage.

---

## 11. Tradeoff Frameworks

### 11.1 Framework vs native browser control

| Option | Pros | Cons | Recommendation |
|---|---|---|---|
| Playwright | Fast, reliable, debuggable | Not true OS-level control | Use for MVP |
| Selenium | Mature ecosystem | Slower ergonomics | Skip unless needed |
| Puppeteer | Good Chrome support | Less cross-browser | Fine but Playwright better |
| OS-level clicks | Closer to challenge Level 2 | Hard, brittle, slow | Stretch only |

Decision:

- Use Playwright first.
- Mention native/OS-level control as future work or add tiny fallback if time permits.

### 11.2 Deterministic vs LLM-driven execution

| Option | Pros | Cons | Recommendation |
|---|---|---|---|
| Fully deterministic | Reliable | Less flexible | Use inside executor |
| Fully LLM-driven | Flexible | Unreliable and hard to debug | Avoid |
| Hybrid | Flexible + controlled | Requires clean boundaries | Best choice |

Decision:

- LLM plans.
- Code executes.
- LLM helps recover only when deterministic methods fail.

### 11.3 Generic agent vs domain-specific workflows

| Option | Pros | Cons | Recommendation |
|---|---|---|---|
| Generic | Impressive if works | Usually flaky | Avoid as main demo |
| Narrow workflow | Reliable, clear value | Less magical | Best for demo |
| Hybrid | Generic engine + curated demos | Requires discipline | Ideal |

Decision:

- Build generic primitives.
- Demo curated workflows.

### 11.4 More features vs more reliability

| Option | Hiring Signal | Risk |
|---|---|---|
| More features | Breadth | Unfinished/flaky |
| More reliability | Engineering maturity | Less flashy |
| Reliability + trace UI | Best balance | Manageable |

Decision:

- Prioritize reliability and traceability.

---

## 12. Day 1-5 Build Plan

## Day 1 — Foundation: Browser Control Loop

### Goal

Get a basic natural language -> browser action loop working.

### Learn

- Playwright launch/navigate/click/type/press.
- Basic structured LLM output.
- JSON schema validation basics.

### Build

1. Minimal `interact API`.
2. Hardcoded action executor.
3. Four actions:
   - `goto`
   - `click`
   - `type`
   - `press`
4. One working browser task:
   - “Search for OpenAI on Google” or a safer public search page.

### Outcome

By end of day:

```text
You can send an instruction and watch a browser execute 3-5 actions.
```

### Done when

- Browser launches.
- Action plan is generated or hardcoded.
- Actions execute sequentially.
- Basic success/failure response returned.

---

## Day 2 — State, Errors, and Step Logging

### Goal

Make it less brittle and start building the infra spine.

### Learn

- Playwright waits.
- Timeouts.
- Error handling.
- Retry basics.

### Build

1. Step execution wrapper.
2. State tracker:
   - current URL
   - page title
   - last action
   - step index
3. Structured logs per step.
4. One retry per failed action.
5. Error taxonomy v0:
   - timeout
   - selector_not_found
   - navigation_failed
   - unknown

### Outcome

By end of day:

```text
Every run produces a step-by-step execution log.
```

### Done when

- Failures do not crash the app.
- Step logs include status, latency, and error.
- Retried steps are visible.

---

## Day 3 — Extract API + Structured Output

### Goal

Turn browsing into useful structured data.

### Learn

- DOM extraction.
- Schema validation with Zod/Pydantic.
- LLM-assisted extraction patterns.

### Build

1. `extract API`.
2. Basic extraction schema.
3. Candidate text/DOM collection.
4. JSON validation.
5. One demo extraction task:
   - top search results,
   - article headings,
   - company names/descriptions,
   - or product/listing data from a public page.

### Outcome

By end of day:

```text
Agent can browse and return validated JSON.
```

### Done when

- Extract API returns JSON.
- Invalid JSON/schema failures are caught.
- Final output is saved with run logs.

---

## Day 4 — Observability Dashboard

### Goal

Make runs inspectable.

### Learn

- Trace concepts.
- Simple DB schema.
- Screenshot capture.

### Build

1. Run table/model.
2. Step table/model.
3. Screenshot per step.
4. Run detail page.
5. Timeline UI.

### Outcome

By end of day:

```text
You can open a run and see what happened step by step.
```

### Done when

- Run detail page shows instruction, status, final output.
- Each step shows action, status, latency, error, screenshot.
- You can debug a failed run from the UI.

---

## Day 5 — First Polished Demo

### Goal

Create a demo that feels like a product.

### Learn

- Demo design.
- Reliability scoring.
- How to narrate architecture.

### Build

1. Pick one deterministic workflow.
2. Add reliability score.
3. Add clean final output display.
4. Record first Loom draft.
5. Write README draft.

### Recommended workflow

```text
Given a topic, search a public website, open relevant results, extract structured information, and show the trace.
```

Example:

```text
“Search Hacker News for browser automation, open the top relevant result, and extract title, URL, and summary.”
```

### Outcome

By end of day:

```text
You have a working MVP with browser control, extraction, tracing, screenshots, and a demo path.
```

---

## 13. Day 6-10 Plan: Make It Robust

## Day 6 — Better Planning

Build:

- Planner prompt v2.
- Action schema validation.
- Max-step guardrail.
- Plan preview in UI.

Learn:

- Prompt iteration.
- How to constrain agents.

Outcome:

- Agent plans are more consistent and less weird.

---

## Day 7 — Recovery Engine v1

Build:

- Error classification.
- Recovery strategies by error type.
- LLM-assisted fallback for selector failures.
- Modal/cookie banner detection if useful.

Learn:

- Retry budgets.
- When to fail fast.

Outcome:

- The system recovers from at least one real failure mode.

---

## Day 8 — Session Persistence

Build:

- Persistent browser context.
- Optional saved login/session state.
- Clear session reset button.

Learn:

- Browser profiles.
- Auth/session management.

Outcome:

- Demo can handle sites that require login without redoing auth every run.

---

## Day 9 — Evals v1

Build:

- 5 test tasks.
- Eval runner.
- Eval results table.
- Success/failure metrics.

Learn:

- Agent evaluation basics.
- Measuring reliability.

Outcome:

- You can show performance across multiple tasks, not just one cherry-picked demo.

---

## Day 10 — Demo Workflow 2

Build:

- A second polished workflow on another website.
- Better final output formatting.
- README architecture section.

Learn:

- Generalization vs demo curation.

Outcome:

- You can credibly claim the agent is not website-specific.

---

## 14. Day 11-15 Plan: Production Polish

## Day 11 — Dashboard Polish

Build:

- Better timeline visualization.
- Screenshot thumbnails.
- Error badges.
- Retry indicators.

Outcome:

- The dashboard becomes the memorable differentiator.

---

## Day 12 — Extraction Quality

Build:

- Better schema definitions.
- Partial extraction handling.
- Extraction confidence.
- Schema failure display.

Outcome:

- Structured outputs look reliable and intentional.

---

## Day 13 — Human-in-the-Loop Checkpoints

Build:

- Approval step type.
- UI approval/reject control.
- Risky action detection.

Outcome:

- System shows mature guardrail thinking.

---

## Day 14 — Optional Stretch: Playwright Trace / Video

Build:

- Save Playwright trace zip or video for each run.
- Link from run detail page.

Outcome:

- Debuggability becomes extremely strong.

---

## Day 15 — Optional Stretch: OpenTelemetry-ish Export

Build:

- Export run/step spans to JSON in OTel-like shape.
- Or add real OpenTelemetry if easy.

Outcome:

- Strong infra/observability connection.

Do not let this derail the core project.

---

## 15. Day 16-20 Plan: Finalization and Hiring Package

## Day 16 — Hardening

Tasks:

- Fix flaky demo paths.
- Tighten error messages.
- Add timeouts everywhere.
- Remove dead code.
- Add seed/demo tasks.

Outcome:

- Demo works repeatedly.

---

## Day 17 — README + Architecture Docs

README sections:

1. What is Ariadne?
2. Why browser agents need observability.
3. Architecture diagram.
4. Features.
5. Demo workflows.
6. API docs.
7. Run trace screenshots.
8. Tradeoffs.
9. Future work.

Outcome:

- Repo tells a compelling story before anyone runs it.

---

## Day 18 — Loom Script and Recording

Loom structure:

1. 20 sec: explain problem.
2. 30 sec: show architecture.
3. 90 sec: run workflow.
4. 60 sec: inspect trace/replay.
5. 30 sec: show evals/reliability.
6. 20 sec: explain tradeoffs/future work.

Outcome:

- A tight 3-5 minute demo.

---

## Day 19 — Final Polish

Tasks:

- Landing page polish.
- Better screenshots.
- Add sample `.env.example`.
- Add setup instructions.
- Add known limitations.

Outcome:

- Reviewer can understand and run the project.

---

## Day 20 — Outreach Package

Prepare:

- GitHub repo.
- Loom link.
- Short writeup.
- Demo URL if hosted.
- Email/LinkedIn message.

Suggested positioning:

> I focused on the browser automation challenge and extended it with production-grade observability: every browser-agent run has step traces, screenshots, retries, structured extraction, and reliability scoring. I wanted to show not just that I can build an agent, but that I can build the infrastructure needed to operate one.

---

## 16. Repository Structure

Recommended TypeScript layout:

```text
ariadne/
  apps/
    web/
      src/
        app/
        components/
        pages/
    api/
      src/
        server.ts
        routes/
          interact.ts
          extract.ts
          runs.ts
  packages/
    agent/
      src/
        planner.ts
        action-schema.ts
        executor.ts
        recovery.ts
        observer.ts
        extractor.ts
    db/
      src/
        schema.ts
        client.ts
    shared/
      src/
        types.ts
        zod-schemas.ts
  artifacts/
    screenshots/
    traces/
  evals/
    tasks.json
    run-evals.ts
  README.md
  .env.example
```

Simpler single-app layout if moving fast:

```text
ariadne/
  src/
    server/
      routes/
      agent/
      db/
    web/
      components/
      pages/
  artifacts/
  evals/
  README.md
```

Choose simplicity if you feel setup friction.

---

## 17. API Design

### POST /interact

Request:

```json
{
  "instruction": "Search Hacker News for browser automation and extract the top 3 results",
  "options": {
    "max_steps": 10,
    "record_screenshots": true
  }
}
```

Response:

```json
{
  "run_id": "run_123",
  "status": "completed",
  "final_output": {...},
  "reliability_score": 91
}
```

### POST /extract

Request:

```json
{
  "run_id": "run_123",
  "schema_name": "search_results"
}
```

Response:

```json
{
  "status": "success",
  "data": [...]
}
```

### GET /runs/:id

Returns full run trace.

### GET /runs

Returns recent runs.

### POST /evals/run

Runs eval suite.

---

## 18. Demo Workflow Ideas

Pick 2-3 only.

### Workflow A: Public search + extraction

Instruction:

```text
Search Hacker News for browser automation, open the top relevant result, and extract title, URL, and summary.
```

Why good:

- Public.
- No login.
- Easy to reproduce.

### Workflow B: Docs navigation

Instruction:

```text
Go to the Playwright docs, search for tracing, open the relevant page, and extract the key headings.
```

Why good:

- Relevant to the project.
- Shows navigation and extraction.

### Workflow C: Logged-in flow

Instruction:

```text
Open a logged-in site, search for a term, open a result, and extract visible metadata.
```

Why good:

- Matches challenge’s login suggestion.
- Shows session persistence.

Use a safe account/test site if possible.

---

## 19. What to Avoid

Avoid:

- Trying to support every website.
- Letting the LLM write selectors with no validation.
- Hiding failures.
- Building too much native OS control too early.
- Spending days on UI polish before the core loop works.
- Creating a demo dependent on fragile auth or CAPTCHA.
- Claiming production-readiness beyond what you can show.

---

## 20. Interview Talking Points

Be ready to explain:

### Why Playwright first?

Because the fastest path to a reliable baseline is a browser automation framework. Native OS-level control is interesting but slower and more brittle; I prioritized a working, observable agent runtime first.

### Why observability?

Browser agents fail in opaque ways. A trace dashboard makes failures debuggable and makes reliability measurable.

### Why hybrid LLM/deterministic design?

LLMs are good at interpreting intent and recovering from ambiguity. Deterministic code is better for execution, validation, and safety.

### What was hardest?

Likely answers:

- Choosing the right action abstraction.
- Handling flaky page states.
- Designing useful traces without storing too much noise.
- Balancing generality against demo reliability.

### What would you build next?

- Native browser/OS-level control.
- More evals.
- Better visual grounding.
- Proxy/extension support.
- Scheduled workflows.
- Multi-browser support.
- OpenTelemetry integration.

---

## 21. Success Criteria

### Minimum success

- Interact API works.
- Browser executes commands.
- Extract API returns structured JSON.
- Run trace dashboard exists.
- Loom demo is clear.

### Strong success

- Two workflows work reliably.
- Errors/retries are visible.
- Screenshots per step.
- Reliability score.
- Eval suite with 5 tasks.

### Exceptional success

- Replay/trace artifacts.
- Human checkpoint.
- Session persistence.
- OTel-style trace export.
- README clearly explains tradeoffs.

---

## 22. Daily Operating Rules

1. Always end the day with a working demo path.
2. Never spend more than half a day blocked on a non-core feature.
3. Prefer visible progress over hidden refactors.
4. Write down every tradeoff as you make it.
5. Record mini demos frequently.
6. Keep the action space small.
7. Make failures visible.
8. Polish only after the core loop works.

---

## 23. Final Mental Model

A normal browser agent is:

```text
Prompt -> Browser -> Maybe result
```

Ariadne should be:

```text
Prompt
  -> Plan
  -> Execute
  -> Observe
  -> Recover
  -> Extract
  -> Trace
  -> Measure
  -> Explain
```

That is the difference between a hack and an engineering system.

---

## 24. Immediate Next Actions

1. Create repo.
2. Choose stack.
3. Implement Playwright hello-world.
4. Define action schema.
5. Create `/interact` endpoint.
6. Execute one fixed plan.
7. Add step logs.
8. Add screenshots.
9. Add extraction.
10. Build trace UI.

Start with the smallest possible loop. Then make it visible, reliable, and memorable.
