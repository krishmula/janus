🧠 Crustdata Build Challenge: AI Agent for Browser Automation

⸻

🎯 Goal

Build an AI agent to automate browser workflows on your machine’s native browser.
(Think: OpenAI’s Operator, but running on your own browser.)

⸻

📚 Core Concepts (Grammar)

1. Interact API

An API that:

- Accepts natural language commands
- Translates them into browser automation actions
- Uses frameworks like:
  - Playwright
  - Puppeteer
  - Selenium

⸻

2. Extract API

An API that:

- Retrieves and parses structured data
- Works on web pages loaded in the browser

⸻

🚀 Milestones

⸻

🟢 Level 1 — Basic Browser Control

✅ Minimum Requirements

- Implement an Interact API:
  - Accepts natural language commands
  - Controls browser actions
- Handle common errors with clear messages
- Must be website-agnostic
- Demonstrate a workflow such as:
  - Logging into a website
  - Searching with user-defined keywords
  - Navigating results
  - Interacting with a selected item

⸻

📦 Submission

- Private GitHub repo
- Email to: buildchallenge@crustdata.co
- Include Loom recording of working demo

⚠️ Only submissions with a recording will be evaluated

⸻

🎁 Reward

- Technical interview with Crustdata team
- Evaluation based on:
  - Your implementation
  - Interview performance

⸻

🟡 Level 2 — Advanced Browser Integration

✅ Requirements

Everything in Level 1 plus:

🔧 Native Browser Control

- Control real browsers (Chrome/Firefox)
- Use OS-level APIs (NOT browser automation APIs)
  - Think: mouse clicks, keyboard input

📊 Extract API

- Extract structured data from pages

🔄 End-to-End Flow

Demonstrate:

1. Login
2. Search
3. Navigate
4. Extract structured data

⚙️ Additional Features

- Proxy support
- Browser extension integration

⸻

📦 Submission

- Complete Level 1 first
- Submit repo + Loom recording

⸻

🎁 Reward

- 💰 $3,000 total

⸻

🔴 Level 3 — Contextual Intelligence & Advanced Workflows

✅ Requirements

Everything in Level 1 & 2 plus:

🌐 Cross-Platform Support

- Works on:
  - Windows
  - macOS
  - Linux

⏱️ Autonomous Execution

- Agent can:
  - Run periodically
  - Perform predefined tasks

💬 Conversational Interface

- Maintains context across multiple commands

⸻

📦 Submission

- Complete Levels 1 & 2
- Submit repo + Loom recording

⸻

🎁 Reward

- 💰 $15,000 total
- 💼 Full-time offer (after 15-min CEO call)

⸻

💡 General Rules & Tips

🎥 Demo Matters A LOT

- Record Loom demos across multiple websites
- Show complex workflows

⸻

⭐ Bonus Points For Handling:

- CAPTCHA detection
- Session management (logins)
- Dynamic page content
- Loading states
- Unexpected page behavior

⸻

⚠️ Important Constraints

- Build from scratch
- Do NOT extend existing tools directly
- You can take inspiration from:

🔗 Reference Projects

- https://github.com/lavague-ai/LaVague
- https://github.com/Skyvern-AI/skyvern
- https://github.com/steel-dev/steel-browser
- https://github.com/browserbase/stagehand
- https://github.com/browser-use/browser-use

⸻

🧩 Mental Model (to build intuition)

Think of your agent as a loop:

User Command (Natural Language)
↓
Interpretation (Interact API)
↓
Action Plan
↓
Browser Execution
↓
Observation (DOM / UI / State)
↓
Extraction (Extract API)
↓
Structured Output

⸻

🧠 Intuition: What They REALLY Want

This isn’t just about automation.

They’re testing if you can:

- Build agent systems
- Handle real-world messiness of browsers
- Think in terms of:
  - reliability
  - abstraction
  - system design

⸻

🔥 If You Want to Stand Out

Focus on:

- ✅ Reliability > flashy features
- ✅ Clean demos > complex ideas
- ✅ Clear architecture > hacks

⸻

If you want, I can also:

- Turn this into a Notion doc
- Help you design the architecture
- Or break down how to actually build Level 1 step-by-step
