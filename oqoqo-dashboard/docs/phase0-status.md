# Phase 0 – Atlas/Nimbus Data Check (2025-11-30)

Command: `npm run check:data`

## Environment variables

| Variable      | Present | Notes |
| ------------- | ------- | ----- |
| `GITHUB_TOKEN` | ✅ | Loaded from the root `.env`. |
| `GITHUB_ORG`   | ⚠️ | Missing – add your GitHub org slug so live ingest can map repo URLs. |
| `SLACK_TOKEN`  | ⚠️ | Missing – add a Slack bot/user token with read access to the monitored channels. |

> Update `.env` at the workspace root to include the missing variables before running the live scenarios.

## Synthetic dataset URLs

All URLs in `scripts/data-sources.json` responded with HTTP 404. The `maghams62/oqoqo_test` repository may be private, renamed, or missing those JSON files. Push or restore the synthetic files (git/slack/tickets/support) or update `data-sources.json` to point to working locations before proceeding to Phase 1.

