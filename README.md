# Looper

A self-hosted web application for running hierarchical companies of AI agents. Each company has a CEO agent that can delegate to a full org chart of subordinates, all powered by any model available through OpenRouter. Agents can browse the web, write and execute code, manage files, and call custom tools — with a human-in-the-loop approval system that keeps every risky action under your control.

---

## Features

### AI Companies & Agents

- Create up to **10 companies**, each with its own isolated workspace, agent hierarchy, and budget
- Each company supports up to **50 agents** organized in an arbitrary hierarchy (CEO → managers → workers, any depth)
- **Instruct the CEO** directly from the dashboard and watch the delegation cascade down the org chart in real time
- Each agent has its own name, job title, personality prompt, and model selection
- **Hire and fire** agents at any time; the org chart re-renders automatically
- **Edit** any agent's name, title, personality, or model without firing and replacing them
- **One-on-one chat** with any individual agent, independent of the task queue — useful for reviews, debugging, or exploratory conversations

### Models

- Powered by **OpenRouter** — access 1,000+ models from providers including Anthropic, OpenAI, Google, Meta, Mistral, and more
- Model catalog is cached locally and refreshable on demand from the Settings page
- Filter models by category: **Text, Vision, Video, Image Gen, Audio, Free**
- Per-model pricing is shown (input/output cost per million tokens) so you know what each agent costs to run
- Tool-calling support is indicated per model — only tool-capable models can use file, shell, browser, and skill tools

### Task Execution & Tools

Agents work autonomously on tasks using a built-in tool suite:

- **Shell** — run any command in a sandboxed working directory
- **File operations** — read, write, create, and delete files within the company's workspace
- **Python** — execute Python scripts directly
- **Browser automation** — full Playwright-based browser control using real Chrome (or the bundled Chromium fallback); agents can navigate, click, fill forms, and extract content
- **Memory** — agents can write and recall their own persistent notes across tasks
- **Skill tools** — any custom Python tools granted via the Skills system (see below)
- **MCP tools** — tools exposed by any registered MCP server (see below)
- Up to **25 tool calls per task**, **10-minute wall clock timeout**, **3 concurrent tasks** across all companies

### Approval System

Every action that could affect your machine or data outside the agent's sandbox is **paused for your approval** before it runs:

- Shell commands that access paths outside the company folder
- File operations outside the company folder
- Custom skill tool calls
- MCP tool calls
- Skill grant requests made by agents

Approvals appear in a dedicated inbox in the web UI and in the Android app (with push notification). Approve or deny each one individually. Tasks that are waiting on approval are held in a paused state and continue immediately once you respond.

### Skills

Skills are reusable capabilities you teach your agents:

- **Instructions-only** — plain text/markdown injected into the agent's system prompt, so it always "knows" something (style guides, policies, reference data)
- **Custom tool** — a small Python function that becomes a callable tool the agent can invoke mid-task, with arguments you define
- Skills can be **Private** (one agent only) or **Skill Shop** (shareable across all agents and companies)
- Agents can **request** skills from the Skill Shop on their own initiative; the request goes to your Approvals inbox
- **Export** any skill to a `.skill.json` file; **import** it on any agent in any company
- A built-in skill library is pre-loaded on first run (see `agents.txt` and `skills.txt`)

See [SKILLS_GUIDE.md](SKILLS_GUIDE.md) for a complete walkthrough with worked examples.

### Agent Shop

- A library of **pre-built agent templates** (roles, personalities, and recommended models) that you can hire directly into any company
- Templates cover a wide range of roles — researchers, writers, coders, analysts, and more
- Hiring from a template pre-fills the agent's name, title, personality, and model selection; you can edit before confirming

### MCP Server Integration

- Connect any **Model Context Protocol (MCP)** server to a company
- Supports both **stdio** (local process) and **SSE** (remote HTTP) transports
- Tools are discovered on connection and cached; refresh on demand
- MCP tools are available to all agents in the company alongside built-in tools
- All MCP tool calls go through the approval system

### File Browser

- Each company has its own **sandboxed working folder** on disk
- The built-in file browser lets you navigate, upload, download, rename, and delete files directly from the web UI
- Agents read and write files within this folder during tasks; you can inspect or modify them at any time

### Budget & Cost Tracking

- Set a **USD budget cap** per company; the company auto-pauses when it is reached
- Running spend is shown on the company dashboard (total USD spent since creation)
- Per-task cost is tracked and stored in the task history

### Heartbeats

- Schedule **recurring tasks** for any company — the CEO receives the configured instruction on a timer
- Two modes: **Interval** (every N minutes) or **Once** (a one-shot future trigger)
- The heartbeat scheduler runs in-process; the optional background service (below) keeps it running even when the browser is closed

### Background Service

- Install an OS-level background service so heartbeats keep firing even when you are not actively using Looper:
  - **Windows** — a Scheduled Task that launches Looper headlessly at logon
  - **Linux** — a `systemd --user` unit
- Install and uninstall from Settings — no admin/sudo required

### Updates

- Looper checks **GitHub Releases** (this repo) for newer versions
- "Check for Updates" in Settings shows the changelog and a one-click "Apply Update" button that runs `git pull` and restarts the server
- The publisher machine can push new releases directly from Settings (commits, tags, and creates a GitHub Release, optionally attaching the Android APK)

### Android Remote App

A native Android app (**Looper Remote**) lets you manage your companies from your phone:

- Requires **Tailscale** — the app connects to your Looper server over the Tailscale VPN
- Pair the app with a company using an 8-character code generated in Settings → Remote Access
- Full company dashboard: org chart, status, spend, pause/resume, instruct CEO
- Browse and manage tasks, approve or deny pending approvals (with notifications)
- Agent detail, edit, hire direct reports from Agent Shop templates
- Model browser with category filters and pricing
- Full file browser: upload, download, open, rename, delete
- Agent Shop, Skill Shop, MCP Servers
- Dark mode, auto-update check
- APK distributed as a GitHub Release asset; install directly from the release page

---

## Requirements

- **Python 3.11** (specifically — 3.12+ has weaker wheel availability for some dependencies)
- **Git** (required for the update system)
- **Google Chrome** (recommended for browser automation; Playwright's bundled Chromium is the fallback)
- A free **OpenRouter account** and API key — [openrouter.ai](https://openrouter.ai)
- **Tailscale** (only required if using the Android remote app)

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/Shango46/Looper.git
cd Looper

# 2. Create a virtual environment with Python 3.11
py -3.11 -m venv .venv          # Windows
python3.11 -m venv .venv        # Linux / macOS

# 3. Activate it
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / macOS

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run first-time setup (installs Playwright's bundled Chromium, checks Chrome)
python setup/setup_environment.py

# 6. Start Looper
python run.py                   # Linux / macOS
start.bat                       # Windows (double-click or run from terminal)
```

Then open **http://localhost:8731** in your browser.

Your OpenRouter API key is entered per-company when you create one — Looper never stores it in plaintext; it is encrypted at rest using a machine-specific Fernet key.

---

## First Run

1. Click **"New Company"** on the dashboard
2. Enter a company name and your OpenRouter API key
3. Your CEO agent is created automatically — give it a name, title, personality, and model
4. Click into the company and use **"Instruct CEO"** to give it its first task
5. Watch tasks appear in the **Activity** tab as the CEO works (and delegates if needed)
6. Any risky actions will pause in the **Approvals** inbox for you to review

---

## Project Structure

```
app/
├── agents/         # Agent runtime: task loop, tool dispatch, delegation, approvals
├── db/             # SQLAlchemy models, migrations, session management
├── mcp/            # MCP client and runtime for external tool servers
├── openrouter/     # OpenRouter API client and model catalog refresh
├── remote/         # Android remote access: auth, rate limiting, Tailscale detection
├── scheduler/      # Heartbeat scheduler
├── setup/          # First-run environment bootstrap and OS service installer
├── skills/         # Skill runtime and export/import
├── web/
│   ├── api/        # JSON REST API for the Android app (/api/v1/*)
│   ├── routes/     # Web UI routes (HTMX + Jinja2)
│   ├── static/     # CSS, Alpine.js, HTMX
│   └── templates/  # Jinja2 HTML templates
├── config.py       # Constants and paths
└── update.py       # GitHub release check, apply update, publish release
run.py              # Entry point (uvicorn on 0.0.0.0:8731)
start.bat           # Windows convenience launcher
requirements.txt
VERSION
agents.txt          # Agent template seed data
skills.txt          # Built-in skill seed data
```

---

## Configuration

All tuneable constants are in `app/config.py`:

| Constant | Default | Description |
|---|---|---|
| `MAX_COMPANIES` | 10 | Maximum number of companies |
| `MAX_AGENTS_PER_COMPANY` | 50 | CEO + subordinates per company |
| `MAX_TOOL_ITERATIONS` | 25 | Tool calls per task before stopping |
| `TASK_WALL_CLOCK_TIMEOUT_SECONDS` | 600 | Hard timeout per task (10 min) |
| `WORKER_CONCURRENCY` | 3 | Concurrent tasks across all companies |
| `SHELL_OUTPUT_MAX_CHARS` | 8000 | Shell output truncation limit |
| `HEARTBEAT_POLL_INTERVAL_SECONDS` | 30 | How often the scheduler checks for due heartbeats |
| `MEMORY_RETENTION_PER_AGENT` | 1000 | Max memory entries per agent |

---

## License

[MIT](LICENSE)
