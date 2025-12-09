# Cerebro OS

> AI-powered document search and email automation for macOS

A Mac-native automation tool that uses GPT-4o to interpret natural language instructions and automate tasks on your machine. Similar in spirit to [Air.app](https://tryair.app), Cerebro OS helps you find documents, extract specific sections, and compose emails—all through natural language.

## Features

- **🌐 Two User Interfaces**: Modern ChatGPT-style web UI or classic terminal interface
- **💬 Natural Language Interface**: Just describe what you want in plain English
- **🔍 Semantic Document Search**: Uses OpenAI embeddings + FAISS for fast, intelligent document retrieval
- **🎯 Smart Section Extraction**: GPT-4o understands requests like "just the summary" or "page 10"
- **📧 Native Mail Integration**: Composes and sends emails directly in macOS Mail.app using AppleScript
- **📊 Keynote Presentations**: Automatically creates slide decks from document content
- **📝 Pages Documents**: Generates formatted documents with sections and headings
- **📄 Multiple File Formats**: Supports PDF, DOCX, and TXT files
- **🏗️ Modular Architecture**: Clean separation of concerns (LLM planner, search, extraction, mail composer)

## Architecture

```
┌─────────────────┐
│   User Input    │
│  (Natural Lang) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GPT-4o Planner │  ← Intent parsing & action planning
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Semantic Search │  ← OpenAI embeddings + FAISS
│  (Document DB)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│Section Extractor│  ← PDF/DOCX parsing
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Email Composer  │  ← GPT-4o + AppleScript
│  (Mail.app)     │
└─────────────────┘
```

## Installation

### Prerequisites

- macOS (tested on 10.15+)
- Python 3.8+
- OpenAI API key
- macOS Mail.app configured

### Setup

1. **Clone or download this repository**:
```bash
cd /path/to/mac_auto
```

2. **Create a virtual environment**:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Set up your OpenAI API key**:
```bash
# Create .env file
cp .env.example .env

# Edit .env and add your API key
# OPENAI_API_KEY=sk-...
```

Or export directly:
```bash
export OPENAI_API_KEY='sk-your-key-here'
```

5. **Configure document folders**:

Edit `config.yaml` to specify which folders to index:
```yaml
documents:
  folders:
    - "~/Documents"
    - "~/Downloads"
    - "/path/to/your/documents"
```

6. **Index your documents**:
```bash
python main.py
# Then type: /index
```

## Development Quickstart (Backend + Frontend + Desktop)

The current stack is split across a Python FastAPI backend (`api_server.py`), a Next.js frontend (`frontend/`), and an optional Electron shell (`desktop/`). Define your repo root once (`export REPO_ROOT=/path/to/auto_mac`) and reuse it in the commands below for a clean local run.

### 1. Prep the shared environment (one-time per machine)

```bash
cd "$REPO_ROOT"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env    # fill in OpenAI/Slack/GitHub/Spotify keys

cd frontend && npm install && cd ..
cd desktop && npm install && cd ..
```

- Keep secrets in `.env`; `config.yaml` pulls them via `${VAR_NAME}`.
- The frontend honors `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_API_PORT` if you need to point at a remote backend.

### 2. Start the FastAPI backend

```bash
cd "$REPO_ROOT"
source venv/bin/activate
python api_server.py
```

- Default port: `8000`. Verify health with `curl http://localhost:8000/health` or open `http://localhost:8000/docs`.
- Logs stream to stdout; the launcher also mirrors them into `api_server.log`.

### 3. Start the Next.js frontend

```bash
cd "$REPO_ROOT/frontend"
npm run dev   # serves http://localhost:3000
```

- The dev server proxies API calls to `http://localhost:8000` automatically via `frontend/lib/apiConfig.ts`.
- If you prefer a production-style build: `npm run build && npm run start`.

> **Running the dashboard + master stack together**
>
- **Stacks & ports:** `bash master_start.sh` now runs the Cerebros chat/brain UI on `http://localhost:3300` (backend stays on 8000). The Oqoqo dashboard lives in `oqoqo-dashboard/` and, via `./oq_start.sh`, runs on `http://localhost:3100` by default. Override ports with `MASTER_PORT=<port>` (or `FRONTEND_PORT=<port>`) for master and `PORT=<port>` for the dashboard if you need alternatives.
- **Port forwarding tips:** tunnel `3100` when you need dashboard access (`ssh -L 3100:localhost:3100 …`) and `3300` for the Cerebros UI. Backend diagnostics still flow through `8000`, so forward that port if you plan to curl FastAPI directly.
- **One-liner recap:**
  ```bash
  MASTER_PORT=3300 bash master_start.sh          # backend 8000 + Cerebros UI 3300
  (cd oqoqo-dashboard && ./oq_start.sh)          # dashboard on 3100
  ```

### 4. (Optional) Launch the Electron desktop shell

```bash
cd "$REPO_ROOT/desktop"
npm run dev
```

- Electron expects both the backend (8000) and Next.js dev server (3000) to be alive before it starts.
- The packaged build serves the static export written by `frontend/out`.

### 5. One-command clean start (optional helper)

```bash
cd "$REPO_ROOT"
./start_ui.sh
```

The script kills stray servers, clears caches (`__pycache__`, `.next`), verifies the venv + Node modules, then launches `python api_server.py` and `npm run dev`, tailing logs to `api_server.log` and `frontend.log`. Press `Ctrl+C` to stop both.

### 6. Stopping & restarting

- Use `Ctrl+C` in each terminal to stop the backend, frontend, or Electron shell.
- If ports 3000/8000 get wedged, run `./start_ui.sh` or manually `lsof -ti :3000 :8000 | xargs kill -9`.

## Multi-repo impact demo (Option 2 → Option 1)

Once the backend is running (either via `master_start.sh` or the steps above), you can exercise the canonical cross-repo story end-to-end. All commands below assume `CEREBROS_API_BASE=http://localhost:8000`.

1. **Trigger a synthetic change in `core-api`:**
   ```bash
   curl -X POST "$CEREBROS_API_BASE/impact/git-change" \
     -H "Content-Type: application/json" \
     -d '{
           "repo": "acme/core-api",
           "title": "payments: require vat_code in contract v2",
           "description": "Upstream contract changed; billing-service + docs must mention vat_code.",
           "files": [
             {"path": "contracts/payment_v2.json", "change_type": "modified"},
             {"path": "docs/payments.md", "change_type": "modified"}
           ]
         }'
   ```
2. **Inspect the DocIssues produced by ImpactPipeline:**
   ```bash
   curl "$CEREBROS_API_BASE/impact/doc-issues?source=impact-report" | jq '.doc_issues[:2]'
   ```
   You should see entries whose `component_ids` include both `billing.checkout` (billing-service) and `docs.payments` (docs-portal), proving that a single upstream change fanned out to two downstream repos.
3. **Check Activity Graph’s dissatisfaction leaderboard:**
   ```bash
   curl "$CEREBROS_API_BASE/activity-graph/top-dissatisfied?limit=5"
   ```
   The response lists `core.payments`, `billing.checkout`, and `docs.payments` with non-zero `dissatisfaction_score`.
4. **Grab the snapshot cards used by the dashboard:**
   ```bash
   curl "$CEREBROS_API_BASE/activity/snapshot?limit=5"
   ```
5. **Optional UI verification:** Open the dashboard (Next.js front-end at `http://localhost:3000`) and watch the Impact Alerts + Activity Graph tiles update in real time. They consume the same APIs you just called, so no extra wiring is required.

This mini run book is the quickest way to prove that Option 2 (Impact → DocIssues) and Option 1 (Activity Graph) stay in sync for cross-repo changes.

## Unified quota demo seeder

The `scripts/seed_quota_demo.py` helper locks in the new “free tier drops from 1 000 → 300 calls” storyline. It can operate entirely against the synthetic fixtures or touch real repos/Slack depending on the mode you choose.

```bash
# Update fixtures + ingest them (safe to run repeatedly)
python scripts/seed_quota_demo.py --mode synthetic

# Push demo branches/commits and replay the Slack thread using your tokens
python scripts/seed_quota_demo.py --mode live
```

Add `--dry-run` to either command to see what would change without mutating anything.

### What happens under the hood

1. **Seed Git** – creates `core-api` + `billing-service` commits that enforce 300-call quotas while leaving `web-dashboard`/`docs-portal` stale at 1 000.
2. **Seed Slack** – appends (or posts live) a support thread where CSMs/PMs complain about the mismatch, tagging all four repos.
3. **Seed DocIssues** – writes JSON entries tying the drift to `src/pages/Pricing.tsx` and `docs/pricing/free_tier.md` plus a meta issue for `core-api`.
4. **Run ingestion** – reuses the existing Slack/Git/DocIssue ingestors. Synthetic mode calls the fixture APIs; live mode hits Slack/GitHub.
5. **Verification** – calls `get_component_activity`, `list_doc_issues`, and `get_context_impacts`. Any FAIL explains what’s missing (graph offline, doc issues absent, etc.) and the script exits 1 so you never walk into a demo half-seeded.

The `quota_demo` block in `config.yaml` centralizes all IDs:

- Repo metadata + demo branches (`quota_demo.git.repos`), including path hints used to rewrite quota constants.
- Slack channel + participant IDs (`quota_demo.slack`) so fixture text matches the Option 1 classifiers.
- Doc issue templates (`quota_demo.doc_issues.templates`) which the script renders with both “1 000” and “300” baked into the summaries.
- Verification targets (`quota_demo.verification`) telling the script which component IDs must light up.

Synthetic mode rewrites:

- `data/synthetic_git/git_events.json`
- `data/synthetic_slack/slack_events.json`
- `data/synthetic_git/quota_doc_issues.json`

and also mirrors the doc issues into `data/live/doc_issues.json` so Activity Graph’s DocIssue reader sees the new dissatisfaction signals immediately.

You should see output similar to:

```
PASS – Fixtures: Synthetic fixtures updated
PASS – Ingestion: Synthetic ingest complete (slack=5)
PASS – Activity Graph: comp:web-dashboard activity=…
PASS – Doc Issues: comp:docs-portal doc issues: 2
PASS – Context Resolution: Dependents=['comp:docs-portal', 'comp:web-dashboard']
Quota demo seeding complete.
```

Treat this PASS/FAIL report as the go/no-go gate before partner demos or regression runs. If any line fails, the script already logged the missing dependency so you can fix it before the audience notices.

### Live-data checklist

- 📋 Follow [`docs/live_ingest_setup.md`](docs/live_ingest_setup.md) to switch every ingest path (Slack, Git, docs, Cerebros) to live data. Synthetic fixtures now load **only** when `mode=synthetic`.
- 🧩 Set the `LIVE_GIT_ORG` env var (or rely on its default `maghams62`) so `activity_ingest.git.repos` and slash-git targets resolve to the live GitHub repos you control (`core-api`, `billing-service`, `docs-portal`).

## Slash command live check

Use `scripts/check_slash_live.py` to exercise the canonical `/slack` and `/git` flows against a running Cerebros instance:

```bash
python scripts/check_slash_live.py --base-url http://localhost:8000
# run just the git scenarios
python scripts/check_slash_live.py --only git_billing_summary,git_doc_drift
```

The script replays the scenarios listed in `docs/slash_flow_health.md`, prints a short PASS/FAIL line for each command, and exits non-zero if any response is empty or missing the expected keywords. Keep your production `SLACK_TOKEN` (or legacy `SLACK_BOT_TOKEN`) / `GITHUB_TOKEN` configured so the live backend can resolve real messages and commits.
- 🕵️ Review [`docs/live_mode_audit.md`](docs/live_mode_audit.md) when debugging—each subsystem’s live vs synthetic switch is documented there with the corresponding config flag.
- ✅ Verification curl commands (`/impact/doc-issues`, `/activity-graph/top-dissatisfied`, `/activity/snapshot`) must return `mode=atlas` and real GitHub/Slack/doc URLs before demos go out.

## Usage

Cerebro OS provides **two interfaces**: a modern web UI and a classic terminal UI. Choose whichever fits your workflow!

---

### 🌐 Option 1: Web UI (Recommended)

**Launch the Web Interface:**

```bash
python app.py
```

Then open your browser and navigate to:

```
http://localhost:7860
```

**Features:**
- 💬 ChatGPT-style chat interface
- 📊 Live system statistics (indexed documents, chunks)
- 📝 Example queries you can click
- 🎨 Clean, modern UI with message history

**Example Usage:**
Just type naturally in the chat box:
- "Find the document about AI agents and email it to spamstuff062@gmail.com"
- "Send me a screenshot of page 3 from the Night We Met document"
- "Find the Tesla document and send just the summary"
- "Create a Keynote presentation from the Q3 earnings report"
- "Make a slide deck based on the AI research paper"
- "Create a Pages document summarizing the Tesla Autopilot document"

**To Stop:**
Press `Ctrl+C` in the terminal where the app is running, or:
```bash
pkill -f "python app.py"
```

---

### 💻 Option 2: Terminal UI

**Launch the Terminal Interface:**

```bash
python main.py
```

**Features:**
- 🖥️ Classic command-line interface
- ⚡ Fast and lightweight
- 🔧 Advanced commands available

**Example Requests:**

```
"Send me the doc about Tesla Autopilot — just the summary section."

"Find the Q3 earnings report and email page 5 to john@example.com"

"Get me the machine learning paper, introduction section"

"Find the contract with Acme Corp and send me section 3"
```

**Terminal Commands:**

- `/index` - Reindex all documents in configured folders
- `/setup` - Inspect universal search modalities and status
- `/cerebros` - Run universal semantic search across all modalities
- `/test` - Test system components (Mail.app, OpenAI API, FAISS index)
- `/help` - Show help message
- `/quit` - Exit the application

---

### 🔄 Quick Start Workflow

1. **First time setup** - Index your documents:
   ```bash
   python main.py
   # Type: /index
   ```

2. **Launch the web UI:**
   ```bash
   python app.py
   ```

3. **Open browser** to http://localhost:7860

4. **Start chatting!** Type your requests naturally

---

## How It Works

### 1. Intent Parsing (GPT-4o)

When you type a request like:
```
"Send me the Tesla Autopilot doc — just the summary"
```

GPT-4o parses this into structured parameters:
```json
{
  "intent": "find_and_email_document",
  "parameters": {
    "search_query": "Tesla Autopilot",
    "document_section": "summary",
    "email_action": {
      "subject": "Tesla Autopilot Summary",
      "body_instructions": "Include the summary section"
    }
  }
}
```

### 2. Semantic Search (FAISS)

- Documents are chunked (by page or size)
- Each chunk is embedded using OpenAI's `text-embedding-3-small`
- FAISS index enables fast cosine similarity search
- Results are ranked by relevance

### 3. Section Extraction

GPT-4o plans how to extract the requested section:
- **Page ranges**: "page 10" → extract page 10
- **Keywords**: "summary" → find pages with "summary"
- **Full document**: Default fallback

### 4. Email Composition

- GPT-4o composes a professional email with the extracted content
- AppleScript opens a draft in Mail.app
- Attaches the source document
- User reviews and sends manually (for safety)

## Configuration

### `config.yaml`

```yaml
# OpenAI API
openai:
  model: "gpt-4o"
  embedding_model: "text-embedding-3-small"

# Document folders to index
documents:
  folders:
    - "~/Documents"
    - "~/Downloads"
  supported_types:
    - ".pdf"
    - ".docx"
    - ".txt"

# Search settings
search:
  top_k: 5
  similarity_threshold: 0.7

# Email settings
email:
  signature: "\n\n---\nSent via Cerebro OS"
```

## Documentation

### How It Fits Together
- [Option 2 – Cross-System Impact](docs/option2_cross_system_impact.md) emits DocIssues by analyzing Git/Slack changes with the dependency map, so cross-repo documentation drift is captured as machine-readable alerts (`/impact/doc-issues`, `/health/impact`).
- [Option 1 – Activity Graph](docs/option1_activity_graph.md) consumes those DocIssues alongside live Slack + Git JSONL logs to prioritize the noisiest components via `/activity-graph/*`, `/activity/snapshot`, and `/activity/quadrant`.
- The dashboard and Cerebros Graph UI build on the same APIs (e.g., `/impact/doc-issues`, `/activity/snapshot`, `/api/cerebros/ask-graph`), so humans and agents see consistent evidence when triaging doc work.

**📚 Central Documentation Index**: See [docs/DOCUMENTATION_INDEX.md](docs/DOCUMENTATION_INDEX.md) for a complete mapping of all documentation files.

### Quick Links
- **Getting Started**: [docs/quickstart/START_HERE.md](docs/quickstart/START_HERE.md) or [docs/quickstart/QUICK_START.md](docs/quickstart/QUICK_START.md)
- **Architecture**: [docs/architecture/OVERVIEW.md](docs/architecture/OVERVIEW.md)
- **Agent Guide**: [docs/MASTER_AGENT_GUIDE.md](docs/MASTER_AGENT_GUIDE.md) - **For developers and AI agents**
- **Features**: [docs/features/SLASH_COMMANDS.md](docs/features/SLASH_COMMANDS.md)
- **Testing**: [docs/testing/COMPREHENSIVE_TEST_REPORT.md](docs/testing/COMPREHENSIVE_TEST_REPORT.md)

### Documentation Structure
- **Architecture**: `docs/architecture/` - System design and architecture
- **Agents**: `docs/agents/` - Agent-specific documentation
- **Features**: `docs/features/` - Feature guides and summaries
- **Testing**: `docs/testing/` - Test documentation and results
- **Development**: `docs/development/` - Development guides
- **Changelog**: `docs/changelog/` - Fix summaries and changelog
- **Quick Start**: `docs/quickstart/` - Getting started guides

## Project Structure

```
cerebro/
├── main.py                 # Terminal UI entry point
├── app.py                  # Web UI entry point (Gradio)
├── config.yaml            # Configuration file
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
│
├── docs/                  # Documentation (see DOCUMENTATION_INDEX.md)
│   ├── DOCUMENTATION_INDEX.md  # Central documentation repository
│   ├── architecture/     # System architecture docs
│   ├── agents/           # Agent documentation
│   ├── features/         # Feature guides
│   ├── testing/          # Test documentation
│   ├── development/      # Development guides
│   ├── changelog/        # Fix summaries
│   └── quickstart/       # Getting started guides
│
├── src/
│   ├── llm/              # LLM integration (GPT-4o)
│   │   ├── planner.py    # Intent parser & action planner
│   │   └── prompts.py    # Prompt templates
│   │
│   ├── documents/        # Document processing
│   │   ├── indexer.py    # FAISS indexing with embeddings
│   │   ├── parser.py     # PDF/DOCX/TXT parsing
│   │   └── search.py     # Semantic search engine
│   │
│   ├── automation/       # macOS automation
│   │   └── mail_composer.py  # AppleScript Mail integration
│   │
│   ├── ui/              # User interface
│   │   └── chat.py      # Terminal chat UI
│   │
│   ├── workflow.py      # Workflow orchestrator
│   └── utils.py         # Config & logging utilities
│
└── data/
    ├── embeddings/      # FAISS index files
    │   ├── faiss.index
    │   └── metadata.pkl
    └── app.log          # Application logs
```

## Modules

### LLM Planner (`src/llm/planner.py`)

Handles all GPT-4o interactions:
- `parse_intent()` - Convert natural language to structured actions
- `plan_section_extraction()` - Determine how to extract sections
- `compose_email()` - Generate email content
- `refine_search_query()` - Optimize search queries

### Document Indexer (`src/documents/indexer.py`)

Manages document indexing with FAISS:
- Crawls configured folders for documents
- Extracts text from PDF/DOCX/TXT
- Chunks large documents
- Generates embeddings via OpenAI
- Stores in FAISS index for fast retrieval

### Semantic Search (`src/documents/search.py`)

Performs similarity search:
- Embeds user query
- Searches FAISS index
- Ranks results by cosine similarity
- Groups chunks by document

### Mail Composer (`src/automation/mail_composer.py`)

Native macOS Mail.app integration:
- Uses AppleScript for Mail.app control
- Composes email with subject, body, recipient
- Attaches source document
- Opens draft for user review

### Workflow Orchestrator (`src/workflow.py`)

Coordinates the complete workflow:
1. Parse intent (LLM)
2. Search documents (FAISS)
3. Plan extraction (LLM)
4. Extract section (Parser)
5. Compose email (LLM)
6. Open in Mail.app (AppleScript)

## Troubleshooting

### "No documents indexed"

Run `/index` command to index your documents:
```bash
python main.py
# Type: /index
```

### "OpenAI API key not set"

```bash
export OPENAI_API_KEY='your-key-here'
```

### "Mail.app integration failed"

- Ensure Mail.app is installed and configured
- Run `/test` to check Mail.app accessibility
- macOS may prompt for automation permissions

### "Document not found"

- Check configured folders in `config.yaml`
- Verify file format is supported (PDF, DOCX, TXT)
- Run `/index` to refresh the index

## Advanced Usage

### Custom Document Folders

Edit `config.yaml`:
```yaml
documents:
  folders:
    - "/Users/you/Work/Contracts"
    - "/Users/you/Research/Papers"
```

### Adjusting Search Sensitivity

Lower threshold = more results (less strict):
```yaml
search:
  similarity_threshold: 0.6  # Default: 0.7
```

### Programmatic Usage

```python
from src.workflow import WorkflowOrchestrator
from src.utils import load_config

config = load_config()
orchestrator = WorkflowOrchestrator(config)

result = orchestrator.execute(
    "Find the Tesla doc and send the summary"
)

print(result)
```

## Roadmap

- [x] **Web UI (Gradio)** - ✅ Complete!
- [x] **Keynote Presentations** - ✅ Complete!
- [x] **Pages Documents** - ✅ Complete!
- [x] **Auto-send Emails** - ✅ Complete!
- [ ] Support for more file formats (Markdown, HTML, Excel)
- [ ] Custom keyboard shortcut trigger
- [ ] Multi-document workflows
- [ ] Slack/Teams integration
- [ ] Voice input support
- [ ] Calendar integration
- [ ] Native macOS app (SwiftUI)

## Security Notes

- **API Keys**: Never commit `.env` file or expose API keys
- **Email Safety**: Emails are drafted but not auto-sent (requires manual review)
- **Document Privacy**: All processing happens locally; only embeddings are sent to OpenAI
- **Permissions**: macOS may prompt for Automation permissions for Mail.app

## Contributing

Contributions welcome! Areas of interest:
- Additional file format support
- GUI improvements
- More automation integrations
- Performance optimizations

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Inspired by [Air.app](https://tryair.app)
- Built with OpenAI GPT-4o and embeddings
- Uses FAISS for vector similarity search
- macOS automation via AppleScript

## Support

For issues or questions:
1. Check the Troubleshooting section
2. Review logs in `data/app.log`
3. Open an issue on GitHub

---

Built with ❤️ for macOS productivity
