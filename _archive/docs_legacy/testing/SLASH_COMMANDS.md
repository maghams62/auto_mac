# Slash Command End-to-End Test Plan

## Overview

Use this checklist whenever you update the Slack, GitHub, or Oqoqo slash commands. The goal is to verify that both the web UI (localhost:3000) and the Electron launcher execute identical flows against real services.

## Prerequisites

1. `.env` (or environment) contains:
   - `SLACK_TOKEN` (or legacy `SLACK_BOT_TOKEN`) and `SLACK_CHANNEL_ID`
   - `GITHUB_TOKEN` (and optional `GITHUB_WEBHOOK_SECRET`)
   - `OQOQO_API_KEY` (+ `OQOQO_BASE_URL`, `OQOQO_DATASET` if self-hosted)
2. `config.yaml` has the `slack`, `github`, and `activity.oqoqo` sections pointing to the correct workspace/repo.
3. Backend + frontend are running (either via `start_ui.sh` or Electron `npm run dev`).
4. A test Slack channel and PR number you can safely query (or a sandbox repo).

## Manual UI Scenarios

Perform each scenario twice: once in the web UI and once in the Electron launcher.

### 1. Slack Activity
1. **Launcher parity**: In the Raycast-style spotlight window, type `/slack ` and confirm the autocomplete list updates while you keep typing a multi-word query (e.g., `/slack explain billing service`). Press ⌘↵ or click “Expand view” to open the desktop window and re-run the same query—both UIs should render the same structured result.
2. Run `/slack list channels` – expect a channel table with IDs + member counts.
2. Run `/slack search #<channel> <keyword>` – confirm matches include permalink + author.
3. (Optional) Run `/slack fetch C0123456789 limit 10` if you have the channel ID handy.
4. Run `/slack summarize #<channel> last 24h` – confirm the assistant renders a structured summary card with Topics, Decisions, Tasks, Open Questions, and References sections (no missing headings, channel/time metadata chips visible). In the expanded desktop view, the spinner overlay should disappear once the Boot status switches to “Workspace ready”; if the backend is offline, the overlay shows the error message and “Back to Spotlight” button.
5. Run `/slack decisions about <feature> last week` – verify at least one decision item appears with participant + permalink, and the command palette hint chips (`Slack templates`) show up when issuing the command.
6. Run `/slack tasks #<channel> yesterday` – ensure tasks include assignee chips and “Jump to message” links and that `data/logs/slash/slack_graph.jsonl` receives a new entry for the run (graph emit flag on).

#### CLI smoke test (no UI)
When you only need backend verification, run the helper:

```bash
python scripts/verify_slack_command.py \
  --query "/slack whats the conversation in #incidents" \
  --expected-channel incidents
```

The script prints a checkbox-style report and exits non-zero if any requirement fails:
- **Task disambiguation** – shared planner resolved the hashtag into a Slack target.
- **Channel scope** – orchestrator metadata (and sources) stayed within the requested channel.
- **Summary generated** – response text surfaced for the UI bubble.
- **Slack deep link** – at least one permalink is present (powers the “Open Slack conversation” button).
- **Retrieval warnings** – script fails if Slack returned API errors (e.g., `not_allowed_token_type`) or needed network fallbacks, so we can fix tokens/scopes before considering the run healthy.

### 2. GitHub / Slash-Git
1. Run `/git repo info` – confirm summary mentions repo name, default branch, and URL.
2. Run `/git use develop` followed by `Which branch are you using?` – expect logical branch context to stick for the session.
3. Run `/git last 3 commits` – verify branch name is mentioned and commits show SHA, author, and message.
4. Run `/git commits since yesterday by <author>` – ensure filters are respected (returns 0 with a clear explanation if nothing matches).
5. Run `/git files changed in the last commit` – expect file list with status/add/delete counts.
6. Run `/git history src/<path>` – verify commit lineage references the file path explicitly.
7. Run `/git diff between main and develop` – expect ahead/behind counts and a list of changed files.
8. Run `/git tags` and `/git latest tag` – confirm tags point to SHAs with timestamps.
9. Run `/git PRs for develop` – expect PR number, title, state, base/head refs.
10. Run `/git last commit` – confirm the response references the default repo owner (e.g., `maghams62/core-api` unless `LIVE_GIT_ORG` overrides it) and that backend logs show GitHub requests pointing at the resolved owner, not literal `${…}` placeholders.

#### Slash Git Planner Checks
- The new planner + executor lives in `src/slash_git/` and relies on `config/slash_git_targets.yaml` for repo/component aliases. When validating, run at least two component-focused queries (e.g., core-api, billing-service, notifications-service) plus one repo-level query.
- Capture each scenario using `docs/testing/SLASH_GIT_REPORT_TEMPLATE.md`. That report forces you to log the parsed plan, retrieval evidence, summary quality, and whether the synthetic dataset surfaced correctly.
- If planning verdicts stay ✅/⚠️ across 4–6 scenarios, move on to synthetic data tweaks or cross-source QA. Any ❌ on planning means fix the resolver/aliases before touching fixtures.
- If you ever see `/repos/${LIVE_GIT_ORG:-maghams62}/…` in backend logs or 404s from GitHub, the catalog still has unresolved placeholders. The loader now raises immediately, so rerun `python -m pytest tests/test_slash_git_catalog.py` to catch the misconfiguration.

#### Generating fresh commits for slash-git
1. Ensure `config.yaml` exposes a dedicated test branch via `slash_git.test_branch`, `github.test_branch`, or an entry in `activity_ingest.git.repos` (otherwise the script falls back to `github.base_branch`).
2. From a clean working tree on that branch, run:
   ```bash
   python scripts/generate_git_story_commit.py --allow-switch
   ```
   Optional flags: `--branch` to override discovery, `--dry-run` to preview the entry, `--skip-push` to inspect locally first.
3. The script appends a telemetry-themed line to `tests/data/git_story.md`, commits with a `chore(story): …` message, and pushes to the remote branch (unless `--skip-push` is set).
4. Verify with `/git last commit` or `/git files changed in the last commit` that the new entry appears, keeping the storyline coherent for demos.

### `/git last commit` QA recipe
1. Ensure `LIVE_GIT_ORG` is unset (defaults to `maghams62`) or explicitly export it to the owner you need before starting `master_start.sh`.
2. Run `/git whats the last commit?` from the UI and note the summary – it should mention the resolved repo owner + branch.
3. Tail `logs/master-start/backend.log` and confirm the GitHub request path reads `https://api.github.com/repos/<owner>/<repo>/commits` with the expected owner.
4. Repeat with `LIVE_GIT_ORG=test-owner` to verify the command now points at `test-owner/<repo>` without falling back to the legacy GitAgent.
5. Record the backend log snippet plus the slash command response in your test notes so regressions are easy to spot.

### 3. Activity Intelligence (Cerebros)
1. Run `/cerebros What's the latest on <feature>?` – expect evidence, conflicts, gaps sourced from multiple modalities.
2. Run `/activity Summarize Slack + Git for <topic>` – confirm sources queried include both providers.

Capture screenshots or copy the response JSON if you need to attach proof to a PR.

## API Smoke Test Script

For quick regression tests (CI or terminal), use the helper script:

```bash
python scripts/run_slash_smoke_tests.py \
  --base-url http://localhost:8000 \
  --slack-channel C0123456789 \
  --pr-number 128 \
  --cerebros-question "Status of the onboarding flow"
```

The script sends the commands to `/api/chat` and prints a one-line summary for each. Any `⛔` entry indicates a failure that should be investigated in `logs/electron/*.log` or `api_server.log`.

### Phase 0 Command Success Criteria

Before shipping graph/visualization features, run these targeted checks (manually or via `pytest tests/commands/test_search_commands.py`):

1. **`/setup`**
   - Expect every enabled modality to show `last_indexed_at` + `needs_reindex=false`.
   - After editing `config.yaml` without re-indexing, rerun `/setup` and confirm the warning banner lists the stale modality (`needs_reindex=true` and telemetry logs a `reindex_needed` array).
2. **`/index`**
   - Run `/index slack files` (or `--index-targets "slack files"` via the smoke script) and verify both modalities emit success lines plus structured telemetry (`/index modality success` events).
   - Abort network access for one modality (e.g., unplug VPN) and rerun `/index <modality>` to ensure the timeout/error path surfaces and telemetry marks the failure.
3. **`/cerebros`**
   - Ask a “code” question (`/cerebros stack trace in auth.py`) and confirm only Git/Files run (planner log + response metadata).
   - Ask a generic question with no internal hits and confirm `/cerebros fallback engaged` telemetry plus a web result.

Document any failures in the PR description and attach the corresponding log lines. This makes it trivial for reviewers to replay the scenario.

## What to Record

- **Success path**: command, timestamp, and a short note about the output (e.g., “/git list open PRs → 4 results, repo=auto_mac”).
- **Failures**: include the command text, error message, and relevant log snippet.
- **Token issues**: if Slack/GitHub return authentication errors, double-check `.env` and note the fix applied.

Keeping these notes in PR descriptions makes it easy for reviewers to see the exact coverage you exercised.

