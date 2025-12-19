# Git + Slack Integration Setup Guide

This guide will walk you through setting up the enhanced Git and Slack integrations for Cerebros.

## Prerequisites

- Python environment with all dependencies installed
- Access to your Slack workspace (admin privileges to create apps)
- Access to your GitHub repository (admin privileges to configure webhooks)
- ngrok or similar tool for local webhook testing (optional but recommended)

---

## Part 1: Slack Integration Setup

### Step 1: Create a Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"** → **"From scratch"**
3. Enter app name: `Cerebros` (or your preferred name)
4. Select your workspace
5. Click **"Create App"**

### Step 2: Configure OAuth & Permissions

1. In your app settings, go to **"OAuth & Permissions"** in the left sidebar
2. Scroll down to **"Scopes"** → **"Bot Token Scopes"**
3. Add the following scopes:
   - `channels:history` - View messages in public channels
   - `channels:read` - View basic channel info
   - `search:read` - Search workspace messages and files
   - `users:read` - View user information

### Step 3: Install App to Workspace

1. Scroll to the top of the OAuth & Permissions page
2. Click **"Install to Workspace"**
3. Review permissions and click **"Allow"**
4. Copy the **"Bot User OAuth Token"** (starts with `xoxb-`)
   - This is your `SLACK_TOKEN` (legacy name: `SLACK_BOT_TOKEN`)

### Step 4: Get Channel IDs

You need the channel ID for any channels you want to search or monitor:

1. Open Slack in your browser
2. Navigate to the desired channel
3. Look at the URL: `https://app.slack.com/client/T12345678/C0123456789`
4. The part starting with `C` is your channel ID (e.g., `C0123456789`)
5. Copy this as your `SLACK_CHANNEL_ID`

**Optional:** To get multiple channel IDs for monitored channels:
- Repeat this for each channel you want to monitor
- Add them to `config.yaml` under `slack.monitored_channels`

### Step 5: Update Environment Variables

Add to your `.env` file:

```bash
SLACK_TOKEN=xoxb-1234567890123-1234567890123-abcdefghijklmnopqrstuvwx
SLACK_CHANNEL_ID=C0123456789
```

### Step 6: Update Config (Optional)

Edit `config.yaml` to add monitored channels:

```yaml
slack:
  bot_token: "${SLACK_TOKEN}"
  default_channel_id: "${SLACK_CHANNEL_ID}"

  monitored_channels:
    - "C0123456789"  # #general
    - "C9876543210"  # #engineering
    - "C1111111111"  # #product
```

---

## Part 2: GitHub Integration Setup

### Step 1: Create a Personal Access Token

1. Go to [https://github.com/settings/tokens](https://github.com/settings/tokens)
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Enter a note: `Cerebros Git Integration`
4. Set expiration as needed (recommend: 90 days or No expiration for testing)
5. Select scopes:
   - ✅ `repo` (full control of private repositories)
   - OR for public repos only: `public_repo`, `read:org`, `read:user`
6. Click **"Generate token"**
7. **Copy the token immediately** (you won't be able to see it again)
   - This is your `GITHUB_TOKEN`

### Step 2: Generate Webhook Secret

Generate a strong random string for webhook signature verification:

**Using Terminal:**
```bash
openssl rand -hex 32
```

**Or Python:**
```python
import secrets
print(secrets.token_hex(32))
```

Save this as your `GITHUB_WEBHOOK_SECRET`

### Step 3: Update Environment Variables

Add to your `.env` file:

```bash
GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz1234567890
GITHUB_WEBHOOK_SECRET=your_generated_secret_here
```

> **Heads up:** Older internal notes referenced a GitHub App (`GITHUB_APP_ID`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_PRIVATE_KEY`, `GITHUB_INSTALLATION_ID`). Cerebros’ slash-git tooling no longer consumes those values—only a classic PAT (`GITHUB_TOKEN`) plus the optional webhook secret are required. Remove any unused GitHub App secrets from `.env` to avoid leaking credentials that the stack will never read.

If you work with the synthetic Git dataset helper, keep the following alongside your PAT:

```bash
SYNTHETIC_GIT_BRANCH=synthetic-git-dataset         # optional override
SYNTHETIC_GIT_BASE_BRANCH=main
SYNTHETIC_GIT_REMOTE=https://<token>@github.com/<owner>/<repo>.git
SYNTHETIC_GIT_REPO_OWNER=<owner>
SYNTHETIC_GIT_REPO_NAME=<repo>
```

These flags are **only** used by `scripts/synthetic_git_dataset.py`; they have no effect on slash-git commands. If you do not push synthetic fixtures, you can delete them.

### Step 4: Configure GitHub Webhook (Local Testing with ngrok)

For local development, you'll need ngrok to expose your local server:

#### 4a. Install and Start ngrok

```bash
# Install ngrok (if not already installed)
brew install ngrok

# Start ngrok on port 8000 (or your API server port)
ngrok http 8000
```

You'll see output like:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:8000
```

Copy the `https://` URL (e.g., `https://abc123.ngrok.io`)

#### 4b. Configure GitHub Webhook

1. Go to your repository: `https://github.com/{owner}/{repo}/settings/hooks`
2. Click **"Add webhook"**
3. Configure:
   - **Payload URL:** `https://abc123.ngrok.io/webhooks/github`
   - **Content type:** `application/json`
   - **Secret:** Paste your `GITHUB_WEBHOOK_SECRET`
   - **SSL verification:** Enable SSL verification
   - **Which events would you like to trigger this webhook?**
     - Select **"Let me select individual events"**
     - Check ✅ **Pull requests**
     - Uncheck everything else
   - **Active:** ✅ Checked
4. Click **"Add webhook"**

#### 4c. Verify Webhook

1. GitHub will send a test ping
2. Check ngrok terminal to see if the request was received
3. In GitHub webhook settings, you should see a green checkmark ✅

### Step 5: Configure GitHub Webhook (Production)

For production, replace the ngrok URL with your actual domain:

1. Update webhook URL to: `https://your-domain.com/webhooks/github`
2. Ensure your server has a valid SSL certificate
3. Restart the webhook to trigger a new ping

---

## Part 3: Cerebros Activity Reasoning (Optional, powers `/cerebros`)

### Step 1: Request API Access

1. If your team already runs Oqoqo, ask the admin for an API key, base URL, and dataset/workspace name.
2. If you self-host, deploy the service and generate an API key there (see the Oqoqo docs).

### Step 2: Update Environment Variables

```bash
OQOQO_API_KEY=oq_live_xxxxxxxxxxxxx
OQOQO_BASE_URL=https://api.oqoqo.ai   # Override if self-hosted
OQOQO_DATASET=production              # Workspace slug
```

### Step 3: Update `config.yaml`

```yaml
activity:
  oqoqo:
    api_key: "${OQOQO_API_KEY}"
    base_url: "${OQOQO_BASE_URL:-https://api.oqoqo.ai}"
    dataset: "${OQOQO_DATASET:-production}"
```

With those values in place, `/cerebros` (and the multi-source reasoning engine) can correlate Slack discussions with GitHub PRs using live data.

---

## Part 4: Testing the Integration

### Test Slack Search

1. Start your Cerebros server:
   ```bash
   python api_server.py
   ```

2. Open the Cerebros UI and try:
   ```
   /slack List channels
   /slack Search for discussions about authentication
   /slack Did we talk about the API changes?
   ```

3. Verify:
   - Channels are listed correctly
   - Search returns relevant messages
   - Messages include author, timestamp, and permalink

### Test Slash-Git (Remote GitHub)

1. Ensure you have at least one active branch, commit history, and tag in your repo.
2. In Cerebros UI, try:
   ```
   /git repo info
   /git use develop
   /git which branch are you using?
   /git last 3 commits
   /git commits since yesterday by alice
   /git files changed in the last commit
   /git history src/api_server.py
   /git diff between main and develop
   /git tags
   /git PRs for develop
   ```

3. Verify:
   - Summaries explicitly mention repo/branch/commit/file entities so graph ingestion can wire Repo → Branch → Commit → File edges.
   - Branch context sticks after `/git use <branch>` and is surfaced when you ask which branch is active.
   - Commit listings include SHA, author, timestamp, and short messages; file listings include status + additions/deletions.
   - Ref comparisons report ahead/behind counts and list changed files.
   - Tag and PR commands show tag→commit and branch→PR relationships.

### Test GitHub Webhook Notifications

1. Open a new PR in your repository
2. Check Cerebros UI for notification: "New PR opened: #X - [title]"
3. Update the PR with new commits (push to PR branch)
4. Check for notification: "PR #X updated with new commits: [title]"
5. Close and reopen the PR
6. Check for notifications for each action

---

## Troubleshooting

### Slack Issues

**Error: "Slack credentials not configured"**
- Check that `SLACK_TOKEN` is set in `.env` (or provide the legacy `SLACK_BOT_TOKEN`)
- Verify the token starts with `xoxb-`

**Error: "missing_scope" or "not_allowed"**
- Go to Slack App → OAuth & Permissions
- Ensure all required scopes are added
- Reinstall the app to workspace

**Search returns empty results**
- Verify the bot has been invited to channels: `/invite @Cerebros` in Slack
- For private channels, the bot must be a member
- Try the fallback by searching with a specific channel ID

### GitHub Issues

**Error: "Invalid signature"**
- Verify `GITHUB_WEBHOOK_SECRET` matches what's in GitHub webhook settings
- Ensure the secret is the same in both `.env` and GitHub

**Error: "Authentication failed"**
- Check that `GITHUB_TOKEN` is valid and not expired
- Verify token has correct scopes (repo access)
- Generate a new token if needed

**Webhook not receiving events**
- Check ngrok is running and URL is correct
- Verify webhook is Active in GitHub settings
- Check GitHub webhook "Recent Deliveries" for error logs
- Ensure your API server is running and accessible

**Rate limiting**
- GitHub API: 5000 requests/hour for authenticated users
- Monitor via response headers: `X-RateLimit-Remaining`
- Tools automatically fall back to webhook cache if API rate limited

### Brain Explorer renders an empty graph

When the Brain Explorer page cannot load `/api/brain/universe`, the canvas now shows a **Graph Request Status** panel. Use it to copy the exact `curl` command the UI is firing and follow this checklist:

1. **Backend health:** run `curl http://localhost:8000/health` (or the health URL shown in the panel). Fix the backend before debugging the UI.
2. **Network tab:** reload `http://localhost:3000/brain/universe` with DevTools → Network open. You should see `GET /api/brain/universe?...`. If it never appears, `NEXT_PUBLIC_API_URL` is pointing to the wrong place or the browser blocked the request (VPN/proxy/extension).
3. **Server logs:** watch `logs/master-start/backend.log` (or your FastAPI console). Every successful page load logs an entry like `GET /api/brain/universe ... 200`. No log entry means the request never reached the backend.
4. **Hard refresh:** once the API responds, Shift+Reload the page so React replays the fetch. The status panel will clear as soon as data lands.

### Brain Explorer layout + focus controls

- The graph now renders as a fixed Neo4j-style canvas (no physics). Nodes are placed deterministically by modality, so screenshots line up with what the backend returns.
- Clicking a modality chip filters down to that source and auto-zooms to it. Click the chip again to return to “All”.
- Use the **Reset view** button if you’ve panned/zoomed around and want to recenter everything.
- Timeline controls appear only when the backend includes timestamp metadata; otherwise the replay button and slider stay hidden to avoid confusion.

---

## Configuration Reference

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SLACK_TOKEN` | Slack bot OAuth token | `xoxb-123...` |
| `SLACK_CHANNEL_ID` | Default Slack channel ID | `C0123456789` |
| `GITHUB_TOKEN` | GitHub personal access token | `ghp_abc...` |
| `GITHUB_WEBHOOK_SECRET` | Webhook signature secret | Random hex string |
| `OQOQO_API_KEY` | Oqoqo activity reasoning API key | `oq_live_xxx` |
| `OQOQO_BASE_URL` | Oqoqo API base (optional) | `https://api.oqoqo.ai` |
| `OQOQO_DATASET` | Oqoqo dataset/workspace slug | `production` |

### Config.yaml Settings

#### Slack Configuration
```yaml
slack:
  bot_token: "${SLACK_TOKEN}"
  default_channel_id: "${SLACK_CHANNEL_ID}"
  monitored_channels:
    - "C0123456789"  # Channel IDs to search
  search:
    default_limit: 20
    max_limit: 100
```

#### GitHub Configuration
```yaml
github:
  token: "${GITHUB_TOKEN}"
  repo_owner: "your-org"
  repo_name: "your-repo"
  base_branch: "main"
  webhook:
    enabled: true
    filter_by_branch: true
  notification_actions:
    - opened
    - ready_for_review
    - closed
    - synchronize
    - reopened
```

#### Vector + Graph Backends
```yaml
vectordb:
  backend: "${VECTOR_BACKEND:-local}"   # local JSON or "qdrant"
  url: "${QDRANT_URL:-http://localhost:6333}"
  api_key: "${QDRANT_API_KEY:-}"
  collection: "oqoqo_context"

graph:
  enabled: ${NEO4J_ENABLED:-false}
  uri: "${NEO4J_URI:-bolt://localhost:7687}"
  username: "${NEO4J_USERNAME:-neo4j}"
  password: "${NEO4J_PASSWORD:-pass}"
```

Set `VECTOR_BACKEND=qdrant` when you want slash commands to hit a live Qdrant cluster instead of the local JSON snapshots. Likewise, export `NEO4J_ENABLED=true` (plus the URI/user/pass trio) before running `scripts/ingest_synthetic_graph.py` so the doc-drift reasoner can pull neighborhoods from Neo4j. If either backend is disabled or missing credentials, Cerebros automatically falls back to the local fixtures—just make sure you’ve run:

```bash
python scripts/build_vector_index.py --domain all
python scripts/ingest_synthetic_graph.py
```

whenever you refresh the synthetic datasets.

### Verify live backends

Once `.env` contains your Qdrant + Neo4j credentials, you can sanity-check the full stack before launching Cerebros:

```bash
# 1) Ping Qdrant + Neo4j using the same config the app uses.
python scripts/check_backends.py

# 2) Rebuild the vector indexes (writes to Qdrant when VECTOR_BACKEND=qdrant).
python scripts/build_vector_index.py --domain all

# 3) Re-ingest the synthetic graph (writes to Neo4j when NEO4J_ENABLED=true).
python scripts/ingest_synthetic_graph.py
```

The `check_backends.py` script exits with a non-zero status if an enabled backend is unreachable. The indexer/ingester commands now log which backend/collection they touch, so you can confirm the data really landed in Qdrant/Neo4j. After all three commands succeed, start the Cerebros API and run `/slack` or `/git` in the UI to exercise the live pipelines.

### Graph-only demo mode (no live GitHub reads)

The documentation prioritization demo ships in a "graph-only" profile so `/git`, `/slash_cerebros`, and the dashboard never hit the GitHub API on read paths. To keep the graph warm:

1. **Require graph mode in config**  
   ```yaml
   slash_git:
     data_mode: "graph"
     graph_mode:
       enabled: true
       require: true
       max_results: 80
   ```

2. **Populate Neo4j/Qdrant via ingest** (runs outside the UI request path):
   ```bash
   # Pull the latest Git/Slack/doc activity into Neo4j + Qdrant
   python scripts/run_activity_ingestion.py --sources git slack doc_issues
   ```

3. **Keep `SLASH_GIT_USE_LIVE_DATA` unset (or false)** so fallback code never calls GitHub, and set `SLASH_GIT_DATA_MODE=graph` if you need to override config at runtime.

4. **Avoid GitAgent fallbacks** – in graph-only mode the Slash Git assistant blocks `list_recent_prs`, `list_repository_branches`, etc. Run ingest again if you need fresher data instead of querying GitHub directly.

If you temporarily need live GitHub reads (e.g., for branch drift checks), set `SLASH_GIT_DATA_MODE=live` or flip `slash_git.graph_mode.require=false` and restart the API. Remember to turn it back on before demos.

#### Oqoqo / Activity Configuration
```yaml
activity:
  oqoqo:
    api_key: "${OQOQO_API_KEY}"
    base_url: "${OQOQO_BASE_URL:-https://api.oqoqo.ai}"
    dataset: "${OQOQO_DATASET:-production}"
```

---

## Next Steps

Once everything is working:

1. **Customize monitored channels** in `config.yaml`
2. **Set up production webhooks** with your actual domain
3. **Configure notification preferences** for different PR actions
4. **Explore natural language queries**:
   - "Search Slack for discussions about the payments bug"
   - "Show me PRs that modified the auth service"
   - "What did the team say about the deployment?"

---

## Support

If you encounter issues:

1. Check the API server logs for error messages
2. Verify all environment variables are set correctly
3. Test Slack/GitHub APIs independently using curl
4. Check GitHub webhook delivery logs for failures
5. Ensure ngrok is running if testing locally

For more help, refer to:
- [Slack API Documentation](https://api.slack.com/docs)
- [GitHub Webhooks Documentation](https://docs.github.com/en/webhooks)
- [Cerebros Documentation](README.md)
