# Looper

**A self-hosted AI company platform.** Create hierarchical companies of AI agents — each with a CEO, managers, and workers — powered by any model on OpenRouter. Agents browse the web, manage files, send email, run code, and call custom tools, all while keeping you in control through a human-in-the-loop approval system.

<a href="https://www.buymeacoffee.com/ChristopherCassidy" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="51" width="185">
</a>

---

## Windows Installer

The easiest way to get started. **No technical setup required.**

1. Download **[LooperInstaller.exe](installer/Output/LooperInstaller.exe)** from this repo
2. Run it — no administrator rights needed
3. The installer will automatically:
   - Install **Python 3.11** if not already present
   - Install **Git** if not already present
   - Install **Node.js** if not already present
   - Install **n8n** (automation engine) globally
   - Create a Python virtual environment and install all dependencies
   - Install the **Playwright Chromium** browser (~150 MB, for browser automation)
4. Choose whether to create a Desktop shortcut
5. Click **Launch Looper** on the final screen — or use the Start Menu / Desktop shortcut at any time

> **First install on a fresh machine** downloads ~200–250 MB total and takes a few minutes. Subsequent launches are instant.

Clicking the shortcut starts the Looper server silently in the background and opens **http://localhost:8731** in your browser.

---

## Linux Installer

A single-file bash script that installs everything and creates an app-menu entry and desktop shortcut. Primarily designed for **Linux Mint 22.x**, but also works on Ubuntu 22.04/24.04, Debian 12, Fedora 39/40, and Arch Linux.

**One-line install:**

```bash
curl -sSL https://raw.githubusercontent.com/Shango46/Looper/main/installer/install.sh | bash
```

Or download and inspect first:

```bash
curl -sSL https://raw.githubusercontent.com/Shango46/Looper/main/installer/install.sh -o install.sh
bash install.sh
```

The installer will automatically:

1. Detect your package manager (`apt` / `dnf` / `pacman`)
2. Install **Git** if not present
3. Clone the Looper repository to `~/.local/share/looper`
4. Install **Python 3.11** (via deadsnakes PPA on Mint/Ubuntu if needed)
5. Create a Python virtual environment and install all dependencies
6. Install **Node.js 20 LTS** (via NodeSource or nvm fallback)
7. Install **n8n** globally via npm
8. Install the **Playwright Chromium** browser engine (~150 MB)
9. Generate the application icon
10. Create a `looper-launch.sh` launcher and symlink it to `~/.local/bin/looper`
11. Create an XDG `.desktop` entry (app menu + desktop shortcut)
12. On Linux Mint / Cinnamon: mark the desktop shortcut as trusted so double-click works

After install, launch Looper by:
- Double-clicking the **Looper** icon on your Desktop
- Searching **"Looper"** in the app menu
- Running `looper` in any terminal (after `source ~/.bashrc`)

> **Re-running the installer** on an existing install pulls the latest code from GitHub, recreates the venv, and updates shortcuts.

---

## Features

### AI Companies & Agents

- Create up to **10 companies**, each with its own isolated workspace, agent hierarchy, API key, and budget
- Each company supports up to **50 agents** in an arbitrary hierarchy — CEO → managers → workers, any depth
- **Instruct the CEO** from the dashboard; delegation cascades down the org chart automatically
- Each agent has a name, job title, personality prompt, and model selection
- **Hire, fire, and edit** agents at any time; the org chart re-renders live
- **One-on-one agent chat** — have a direct conversation with any agent outside the task queue (useful for reviews, debugging, or exploratory conversations)
- **Pause and resume** any company to hold all task processing temporarily

### Live Activity Feed

- Watch your agents work in **real time** from the company's Live Activity page
- Every agent action is streamed live — instructions received, tool calls made, responses generated, delegations dispatched
- **Filter** by individual agent to focus on one part of the org chart
- **Pause/resume** the feed without leaving the page
- Click any entry to expand the full content

### Company File Browser

- Each company has a **sandboxed workspace folder** on disk that agents read and write during tasks
- The built-in file browser lets you **navigate, upload, download, create folders, and delete** files directly from the web UI — no file manager needed
- **Inline text editor** — click any text file (`.py`, `.md`, `.json`, `.yaml`, `.sh`, and 20+ other extensions) to edit it in the browser and save it back to disk
- Agents and you share the same folder; changes made by agents are immediately visible in the browser

### Email Integration (SMTP / IMAP)

- Give any company its own email identity — agents can **send and receive email** as part of tasks
- Configure display name, SMTP (outgoing), and IMAP (incoming) per company
- Credentials are **stored encrypted** on disk
- Built-in **Test SMTP** and **Test IMAP** buttons verify your settings before saving
- Expandable **provider setup guide** covers Gmail, Zoho Mail, Fastmail, and Outlook/Microsoft 365 with exact host and port settings

### n8n Automation Integration

- Connect each company to an **n8n automation engine** — either the self-hosted instance Looper manages automatically, or your own cloud/external n8n
- Build n8n workflows that trigger agent tasks via the inbound webhook, or have agents trigger n8n workflows as tool calls
- Manage workflows directly from the company's Automations page

### Knowledge Base (RAG)

- Upload documents to each company's knowledge base — agents can **search and retrieve** relevant content during tasks
- Supports plain text, markdown, PDF, and other document formats
- Retrieval is injected directly into the agent's context when relevant

### Inbound Webhooks

- Generate a **secret webhook URL** for any company
- External tools (n8n, Zapier, scripts, or any HTTP client) can POST to this URL to create a task for the CEO
- Simple JSON body: `{ "instruction": "...", "target_agent_id": 42 }` — target agent is optional (defaults to CEO)
- Useful for event-driven automation: "when X happens in your CRM, tell the CEO"

### Models (via OpenRouter)

- Access **1,000+ models** from Anthropic, OpenAI, Google, Meta, Mistral, and more — through a single OpenRouter API key
- Model catalog is cached locally and refreshable on demand from Settings
- Filter models by category: **Text, Vision, Video, Image Gen, Audio, Free**
- Per-model **pricing** is shown (input/output cost per million tokens)
- Tool-calling support is flagged per model — only tool-capable models can use file, shell, browser, and skill tools

### Task Execution & Tools

Agents work autonomously using a built-in tool suite:

| Tool | What it does |
|---|---|
| **Shell** | Run any command in the company's working directory |
| **File operations** | Read, write, create, delete files within the workspace |
| **Python** | Execute Python scripts directly |
| **Browser automation** | Full Playwright-based control of Chrome or bundled Chromium — navigate, click, fill forms, extract content |
| **Web search** | Search the live web via the Brave Search API (configured per company) |
| **Email** | Send and read email via SMTP/IMAP when configured |
| **Memory** | Write and recall persistent notes across tasks |
| **Delegation** | Spin up subtasks for subordinate agents and wait for results |
| **Skill tools** | Custom Python tools you define via the Skills system |
| **MCP tools** | Any tools exposed by registered MCP servers |

Configurable limits: up to **25 tool calls per task**, **10-minute timeout**, **3 concurrent tasks**.

### Approval System

Every action that could affect your machine or data outside the agent's sandbox is **paused for your approval**:

- Shell commands targeting paths outside the company folder
- File operations outside the company folder
- Risky tool calls flagged by the risk engine
- Skill grant requests from agents
- MCP tool calls

Approvals appear in the web UI's Approvals inbox and in the Android app. Approve or deny individually — tasks hold in place and continue immediately once you respond.

### Skills

Reusable capabilities you teach your agents:

- **Instructions-only** — markdown injected into the system prompt so the agent always "knows" something (policies, style guides, reference data)
- **Custom tool** — a small Python function that becomes a callable tool the agent can invoke mid-task
- **Private** (one agent) or **Skill Shop** (shareable globally across all companies)
- Agents can request skills from the Skill Shop; requests go to your Approvals inbox
- **Export** any skill to `.skill.json`; **import** it on any agent in any company
- A built-in skill library is pre-loaded on first run

### Agent Shop

- A library of **pre-built agent templates** — roles, personalities, and recommended models
- Covers researchers, writers, coders, analysts, project managers, and more
- Hiring from a template pre-fills name, title, personality, and model; you can edit before confirming

### MCP Server Integration

- Register any **Model Context Protocol (MCP)** server with a company
- Supports **stdio** (local command) and **streamable HTTP** transports
- Tools are discovered on connection and cached; refresh on demand
- MCP tools are available to all agents in the company alongside built-in tools
- Quick-add buttons for popular servers: Filesystem, GitHub, Memory

### Budget & Cost Tracking

- Set a **USD budget cap** per company — the company auto-pauses when reached
- Running spend displayed on the company dashboard
- Per-task cost tracked and stored in history

### Heartbeats

- Schedule **recurring tasks** for any agent in a company
- **Interval** mode: fires every N minutes/hours
- **Once** mode: fires at a specific date and time
- Great for daily briefings, periodic reports, monitoring tasks, or any timed automation

### Background Service

Install an OS-level background service so heartbeats keep firing even when the browser is closed:

- **Windows** — a per-user Scheduled Task that launches Looper headlessly at logon
- **Linux** — a `systemd --user` unit
- Install and uninstall from **Settings → Heartbeats Background Service** — no admin or sudo required

### Updates

- Looper checks **GitHub Releases** for newer versions
- "Check for Updates" in Settings shows the changelog and a one-click **Apply Update** button that runs `git pull` and restarts
- Zero-downtime updates — the server restarts automatically

### Android Remote App

A native Android app (**Looper Remote**) lets you manage everything from your phone:

- Requires **Tailscale** — connects to your Looper server over the Tailscale VPN
- Pair using an 8-character code generated in Company Settings → Remote Access
- Full company dashboard: org chart, status, spend, pause/resume, instruct CEO
- Browse tasks, approve/deny pending approvals with push notifications
- Agent detail, hire, edit, fire
- Full file browser: upload, download, open, delete
- Agent Shop, Skill Shop, MCP Servers, model browser
- Dark mode, auto-update check
- APK distributed as a GitHub Release asset

---

## Manual Installation (Developers)

```bash
# 1. Clone
git clone https://github.com/Shango46/Looper.git
cd Looper

# 2. Create a Python 3.11 virtual environment
py -3.11 -m venv .venv          # Windows
python3.11 -m venv .venv        # Linux / macOS

# 3. Activate
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / macOS

# 4. Install dependencies
pip install -r requirements.txt

# 5. First-time setup (installs Playwright's bundled Chromium, checks Chrome)
python setup/setup_environment.py

# 6. Start
python run.py
```

Then open **http://localhost:8731**.

> Python 3.11 specifically — 3.12+ has weaker wheel availability for some dependencies (tiktoken, playwright).

---

## First Run

1. Click **"New Company"** on the dashboard
2. Enter a company name, folder path, and your **OpenRouter API key** ([openrouter.ai](https://openrouter.ai) — free to sign up)
3. Name and configure your **CEO agent** (title, personality, model)
4. Click **"Instruct CEO"** to give it its first task
5. Watch the **Live Activity** feed as the CEO works and delegates
6. Risky actions pause in the **Approvals** inbox for you to review

Your OpenRouter key is stored encrypted — never in plaintext.

---

## Requirements

| Requirement | Notes |
|---|---|
| **Python 3.11** | 3.12+ has weaker wheel support for some deps |
| **Git** | Required for the update system |
| **Node.js + npm** | Required for n8n automation |
| **Google Chrome** | Recommended for browser automation; bundled Chromium is the fallback |
| **OpenRouter API key** | [openrouter.ai](https://openrouter.ai) — free tier available |
| **Tailscale** | Only needed for Android remote access |

The Windows and Linux installers handle all of these automatically.

---

## Project Structure

```
app/
├── agents/         # Agent runtime: task loop, tool dispatch, delegation, approvals
├── db/             # SQLAlchemy models, migrations, session
├── email_client.py # SMTP/IMAP email tooling for agents
├── mcp/            # MCP client and tool runtime
├── n8n/            # n8n process management and API client
├── openrouter/     # OpenRouter API client and model catalog
├── rag/            # RAG document store and retrieval
├── remote/         # Android remote access: auth, rate limiting, Tailscale
├── scheduler/      # Heartbeat scheduler
├── setup/          # First-run bootstrap and OS service installer
├── skills/         # Skill runtime and export/import
├── web/
│   ├── api/        # JSON REST API for the Android app (/api/v1/*)
│   ├── routes/     # Web UI routes (HTMX + Jinja2)
│   ├── static/     # CSS, Alpine.js, HTMX
│   └── templates/  # Jinja2 HTML templates
├── config.py       # Constants and tuneable limits
└── update.py       # GitHub release check, apply update, publish
installer/          # Windows installer (Inno Setup)
run.py              # Entry point (uvicorn on 0.0.0.0:8731)
start.bat           # Windows convenience launcher
requirements.txt
VERSION
agents.txt          # Agent template seed data
skills.txt          # Built-in skill seed data
```

---

## Configuration

Tuneable constants in `app/config.py`:

| Constant | Default | Description |
|---|---|---|
| `MAX_COMPANIES` | 10 | Maximum number of companies |
| `MAX_AGENTS_PER_COMPANY` | 50 | CEO + subordinates per company |
| `MAX_TOOL_ITERATIONS` | 25 | Tool calls per task before stopping |
| `TASK_WALL_CLOCK_TIMEOUT_SECONDS` | 600 | Hard timeout per task (10 min) |
| `WORKER_CONCURRENCY` | 3 | Concurrent tasks across all companies |
| `SHELL_OUTPUT_MAX_CHARS` | 8000 | Shell output truncation limit |
| `HEARTBEAT_POLL_INTERVAL_SECONDS` | 30 | How often the scheduler checks for due heartbeats |
| `MEMORY_RETENTION_PER_AGENT` | 1000 | Max memory entries kept per agent |

---

## License

[MIT](LICENSE)

---

<a href="https://www.buymeacoffee.com/ChristopherCassidy" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="51" width="185">
</a>
