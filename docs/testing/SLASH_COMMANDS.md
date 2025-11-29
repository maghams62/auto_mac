# Slash Command End-to-End Test Plan

## Overview

Use this checklist whenever you update the Slack, GitHub, or Oqoqo slash commands. The goal is to verify that both the web UI (localhost:3000) and the Electron launcher execute identical flows against real services.

## Prerequisites

1. `.env` (or environment) contains:
   - `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID`
   - `GITHUB_TOKEN` (and optional `GITHUB_WEBHOOK_SECRET`)
   - `OQOQO_API_KEY` (+ `OQOQO_BASE_URL`, `OQOQO_DATASET` if self-hosted)
2. `config.yaml` has the `slack`, `github`, and `activity.oqoqo` sections pointing to the correct workspace/repo.
3. Backend + frontend are running (either via `start_ui.sh` or Electron `npm run dev`).
4. A test Slack channel and PR number you can safely query (or a sandbox repo).

## Manual UI Scenarios

Perform each scenario twice: once in the web UI and once in the Electron launcher.

### 1. Slack Activity
1. Run `/slack list channels` – expect a channel table with IDs + member counts.
2. Run `/slack search #<channel> <keyword>` – confirm matches include permalink + author.
3. (Optional) Run `/slack fetch C0123456789 limit 10` if you have the channel ID handy.
4. Run `/slack summarize #<channel> last 24h` – confirm the assistant renders a structured summary card with Topics, Decisions, Tasks, Open Questions, and References sections (no missing headings, channel/time metadata chips visible).
5. Run `/slack decisions about <feature> last week` – verify at least one decision item appears with participant + permalink, and the command palette hint chips (`Slack templates`) show up when issuing the command.
6. Run `/slack tasks #<channel> yesterday` – ensure tasks include assignee chips and “Jump to message” links and that `data/logs/slash/slack_graph.jsonl` receives a new entry for the run (graph emit flag on).

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

#### Generating fresh commits for slash-git
1. Ensure `config.yaml` exposes a dedicated test branch via `slash_git.test_branch`, `github.test_branch`, or an entry in `activity_ingest.git.repos` (otherwise the script falls back to `github.base_branch`).
2. From a clean working tree on that branch, run:
   ```bash
   python scripts/generate_git_story_commit.py --allow-switch
   ```
   Optional flags: `--branch` to override discovery, `--dry-run` to preview the entry, `--skip-push` to inspect locally first.
3. The script appends a telemetry-themed line to `tests/data/git_story.md`, commits with a `chore(story): …` message, and pushes to the remote branch (unless `--skip-push` is set).
4. Verify with `/git last commit` or `/git files changed in the last commit` that the new entry appears, keeping the storyline coherent for demos.

### 3. Activity Intelligence (Oqoqo)
1. Run `/oq What's the latest on <feature>?` – expect evidence, conflicts, gaps.
2. Run `/activity Summarize Slack + Git for <topic>` – confirm sources queried include both providers.

Capture screenshots or copy the response JSON if you need to attach proof to a PR.

## API Smoke Test Script

For quick regression tests (CI or terminal), use the helper script:

```bash
python scripts/run_slash_smoke_tests.py \
  --base-url http://localhost:8000 \
  --slack-channel C0123456789 \
  --pr-number 128 \
  --oq-question "Status of the onboarding flow"
```

The script sends the commands to `/api/chat` and prints a one-line summary for each. Any `⛔` entry indicates a failure that should be investigated in `logs/electron/*.log` or `api_server.log`.

## What to Record

- **Success path**: command, timestamp, and a short note about the output (e.g., “/git list open PRs → 4 results, repo=auto_mac”).
- **Failures**: include the command text, error message, and relevant log snippet.
- **Token issues**: if Slack/GitHub return authentication errors, double-check `.env` and note the fix applied.

Keeping these notes in PR descriptions makes it easy for reviewers to see the exact coverage you exercised.

