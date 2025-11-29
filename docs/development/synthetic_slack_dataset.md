# Synthetic Slack Dataset Workflow

This script mirrors the Git dataset flow but populates Slack conversations that
reference the same vat_code incident storyline. Use it whenever you need to
refresh `slack_events.json` for demos or ingestion tests.

## Environment variables

Set these in `.env` (all have sane defaults if omitted):

```
SLACK_WORKSPACE=acme
SLACK_DATA_DIR=data/synthetic_slack
SLACK_EVENTS_FILE=slack_events.json
SLACK_DEFAULT_TIMEZONE=UTC
SLACK_BASE_TIME=2025-11-26T09:00:00
SLACK_CHANNEL_MAP={"#incidents":"C123INCIDENTS","#billing-dev":"C123BILLING","#docs":"C123DOCS","#support":"C123SUPPORT","#core-api":"C123COREAPI","#notifications":"C123NOTIFY"}
SLACK_CONFIG_PATH=/Users/you/auto_mac/config.yaml
# Standard Slack creds used elsewhere in the app
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_CHANNEL_ID=C0123456789
```

You can also override `SLACK_DATA_DIR` / `SLACK_EVENTS_FILE` separately or pass
explicit CLI flags when running the script.

If you already keep channel metadata in `config.yaml` under `activity_ingest.slack.channels`,
the script will ingest those `name`/`id` pairs automatically. `SLACK_CHANNEL_MAP`
(or `--channel-map`) can override specific entries without touching the config file.

## Generate the dataset

```
python scripts/synthetic_slack_dataset.py --force --pretty
```

What this does:

1. Loads `.env`, resolves workspace + timezone, and creates the output path
   (defaults to `data/synthetic_slack/slack_events.json`).
2. Builds five Slack threads (`#incidents`, `#billing-dev`, `#docs`,
   `#support`, and a noise thread in `#core-api`) plus their thread summaries.
3. Emits a JSON array with both `slack_message` and `slack_thread_summary`
   records, already annotated with `service_ids`, `component_ids`,
   `related_apis`, and `labels`.

Use `--output` to point somewhere else, `--base-time` to shift the timestamps,
`--timezone` if you want a zone other than UTC, and `--channel-map` to inject
channel IDs inline (e.g., `'--channel-map "#incidents=C0A1,#billing-dev=C0B2"'`).
Re-run with `--force` when you intentionally want to overwrite the existing file.

