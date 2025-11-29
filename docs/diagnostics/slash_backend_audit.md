# Backend Audit – Slack / GitHub / Oqoqo Slash Commands (2025‑11‑28)

## 1. Current Capabilities

| Domain | Key Files | Notes |
|--------|-----------|-------|
| Slack | `src/agent/slack_agent.py`, `src/integrations/slack_client.py` | Tools exist for listing channels, fetching history, `search.messages`, and thread metadata. Requires `SLACK_BOT_TOKEN` (and optional `SlackAPIClient(bot_token=…)`). Errors are surfaced with structured payloads (`error_type`, `retry_possible`). |
| GitHub / Slash-Git | `src/agent/git_agent.py`, `src/agent/slash_git_assistant.py`, `src/services/github_pr_service.py`, `src/ui/slash_commands.py` | Git agent now exposes repo info, branch metadata, commit/file history, ref compare, tags, and PR listing tools. `SlashGitAssistant` (wired into `/git`) maintains logical branch context per session and formats graph-friendly summaries (Repo → Branch → Commit → File relationships). Requires `GITHUB_TOKEN`, `repo_owner`, `repo_name`, `base_branch`. |
| Oqoqo / Activity | `src/agent/oqoqo_agent.py`, `src/agent/multi_source_reasoner.py` | Wraps Slack + Git tools and adds `query_with_reasoning()` for evidence/conflict/gap detection. Requires `activity` and `oqoqo` config blocks (API key, base URL) plus Slack/Git data sources. |

Additional context:
- `SlashCommandParser.COMMAND_MAP` already routes `/slack`, `/git`, `/oq` to the corresponding agents. `/git` now delegates entirely to `SlashGitAssistant`, so branch context, repo info, and commit filters stay inside the git lane (no orchestrator round-trip).
- `AutomationAgent` loads these tools via `AgentRegistry` and exposes them through the standard WebSocket/chat pathway used by the UI.

## 2. Config & Secrets Status

- **Slack**: Only implicit via `os.environ["SLACK_BOT_TOKEN"]`. `config.yaml` has `activity_ingest.slack` metadata (channels, monitoring) but no top-level `slack.token`. `.env.example` also lacks Slack entries.  
  → Need to add `SLACK_BOT_TOKEN` (and optional signing secret) to `.env.example`, surface it in `config.yaml`, and teach `ConfigManager` to warn when missing.
- **GitHub**: `github_pr_service` reads from either env vars (`GITHUB_TOKEN`, `GITHUB_REPO_OWNER`, etc.) or `config["github"]`. The default config ships with FastAPI repo values, so documenting overrides is essential before wiring live tokens.
- **Oqoqo**: `config.yaml` already includes `activity`/`oqoqo` sections (API host, key) but the sample values are blank. Need to highlight them in setup docs and ensure `ConfigManager` plumbs them into `MultiSourceReasoner`.

## 3. API / Routing Hooks

- Slash commands piggyback on the `/ws/chat` channel; no extra REST endpoints are required. The FastAPI server already streams results (including custom payloads) back through `useWebSocket`.
- Deterministic slash requests (e.g., `/files list`) sometimes use HTTP fetchers, but the Slack/Git/Oq flows all go through the WebSocket + agent system, so no transport changes are needed.

## 4. Gaps Before Implementation

1. **Validation & Error UX**: Backend returns structured errors, but the UI doesn’t surface them (e.g., “Slack token missing” shows up only in logs). Need to translate these into palette warnings.  
2. **Token Plumbing**: Without adding token fields to `.env.example` + docs, setting up real Slack/Git access is undocumented and easy to misconfigure.  
3. **Webhook vs. Live API**: Git agent can fall back to webhook storage, but there’s no automated seeding of fake PRs. For “fake PR” scenarios we’ll need either a seeding script or instructions for using a sandbox repo with our PAT.  
4. **Testing Harness**: Existing `tests/test_slash_commands` do not cover Slack/Git/Oq flows. End-to-end steps (with real tokens) are missing from `docs/testing`.  
5. **UI Guidance**: Backend expects channel IDs (e.g., `C0123456789`) and numeric PRs; current UI has no helper text or pickers. Need placeholders/tooltips so both browser + Electron users know what to type.

With this audit, we can proceed to token wiring, UI integration, and execution logic confident that the backend agents are in place and only need configuration + UX support.

