# Slack Replay Automation

Use `scripts/replay_slack_dataset.py` to push the synthetic conversations in
`slack_events.json` into a real Slack workspace for demos or regression tests.

## Prerequisites

- Create or reuse a Slack app with a bot token.
- Grant at least the following OAuth scopes and reinstall the app:  
  `channels:read`, `channels:manage`, `groups:read`, `chat:write`.
- Invite the bot to any existing channels you plan to reuse. The script can
  create missing public channels automatically.
- Set `SLACK_BOT_TOKEN` in your `.env`.

## Dry Run

Validate how the replay would look without contacting Slack:

```bash
python scripts/replay_slack_dataset.py --dry-run
```

## Live Replay

```bash
python scripts/replay_slack_dataset.py \
  --dataset slack_events.json \
  --post-summaries
```

Key behaviors:

- Messages are grouped by channel + thread order using the ISO timestamps.
- Each Slack post is prefixed with the persona (e.g., `[Alice] ...`) and
  includes the original metadata (timestamp, services, APIs, labels).
- Root messages start new threads; replies reuse the thread timestamp returned
  by Slack.
- `--post-summaries` optionally adds each `slack_thread_summary` entry as a
  recap reply tagged `(thread summary)`.
- `--token` can override the environment variable when needed.

## Safety Notes

- Slack does not allow impersonating other users via a single bot token; all
  posts will appear from the bot account with persona text inline.
- Timestamps cannot be overridden, so the ISO timestamp is embedded in the
  message body for auditing.
- The script retries on `rate_limited` errors and supports a dry-run mode to
  verify channel creation ahead of time.

