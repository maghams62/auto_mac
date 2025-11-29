# Slash Command Infrastructure (Inventory – 2025‑11‑28)

## 1. Entry Point (Web + Electron)

- Both the **Electron launcher** and **web UI (localhost:3000)** use the same `frontend/components/CommandPalette.tsx`.  
- The palette keeps two modes: search (files) vs. `command_input` (slash command arguments).  
- User input flows through `useCommandRouter()` for deterministic shortcuts (e.g., Spotify, `/clear`). Any remaining text—including `/slack …`, `/github …`, `/oq …`—is sent to the backend via the WebSocket at `ws://<api>/ws/chat`.  
- Electron’s preload bridge (`frontend/lib/electron.ts` + `desktop/src/main.ts`) only handles window chrome; no slash-specific logic lives there, so once commands reach the renderer, the experience is identical on desktop and browser.

## 2. Backend Parser & Routing

- `src/ui/slash_commands.py` defines the authoritative `COMMAND_MAP`, tooltips, and examples.  
  - `/slack`, `/git`/`/pr`, `/oq` `/oqoqo` are **already mapped** to the `slack`, `git`, and `oq` agents respectively.  
  - Parser functions (`_extract_time_window`, `_extract_count`, etc.) normalize channel names, PR numbers, and quoted text before invoking agents.
- After parsing, commands are dispatched through `AutomationAgent` (see `src/agent/agent.py`) or to specialized helpers (e.g., Slack agent, Git agent).  
- Responses are sent back over the WebSocket as standard assistant messages; specialized payloads (files, summaries) piggyback through the same channel the Electron/web UI already consume.

## 3. Agent Capabilities (Current State)

- **Slack**: `src/agent/slack_agent.py` + `src/services/slack_client.py` provide channel listing, message fetch, and summarization hooks. Requires a `SLACK_BOT_TOKEN` in config/env.  
- **GitHub PRs**: `src/services/github_pr_service.py` handles PR polling/comparison; `src/agent/git_agent.py` exposes summarization helpers. Needs `GITHUB_TOKEN`.  
- **Oqoqo / Activity**: `src/agent/oqoqo_agent.py` plus `src/agent/activity_agent.py` combine Git + Slack telemetry into cross-source reports. Accepts `/oq`, `/activity`, etc.

## 4. API Surface

- **FastAPI** entry points live in `api_server.py`. Slash commands do not use bespoke REST endpoints; instead, they ride the `/ws/chat` WebSocket + `/api/conversation/*` history endpoints.  
- Deterministic slash invocations can also go through `/api/commands/execute` (see existing frontend fetches) when the UI uses HTTP for specific features (files list, etc.).

## 5. Config & Secrets

- `.env.example` and `config.yaml` already expose OpenAI keys, Mongo, etc., but **do not yet document Slack/GitHub/Oqoqo tokens explicitly**. The agents read from `config_manager.get_config()` keys:
  - `slack.bot_token`, `slack.signing_secret`
  - `github.token`, `github.webhook_secret`
  - `activity.oqoqo.api_key` (plus optional base URL)
- `config_manager.update_components()` (line ~274) hot-swaps the agent references when config changes, so adding new secrets only requires extending the YAML + validation rules.

## 6. Known Gaps Before Feature Work

1. **UI palette** lists `/slack`, `/git`, `/oq`, but there is no UX scaffold (placeholders, prompts, validation) guiding users to enter channel IDs or PR URLs; we need to add that for both launcher and browser modes.  
2. **Tokens** are not surfaced in `.env.example` or docs, so configuring real Slack/GitHub/Oqoqo credentials currently requires digging through code.  
3. **Slash executions** rely on existing agents, but we still need to confirm end-to-end flows (e.g., Slack history fetch + summarization) once tokens are wired.  
4. **Testing docs** do not mention these commands. A new `docs/testing/SLASH_COMMANDS.md` (or an extension of the existing file) is needed for regression coverage.

With this inventory captured, we can proceed to auditing backend coverage, wiring tokens, and exposing the commands in both UIs as outlined in the plan.

