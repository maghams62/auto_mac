# Canonical ID Contract (Synthetic Data)

This document freezes the identifiers that tie Slack events, Git artifacts, docs,
vector embeddings, and the Neo4j graph together. Every ingestion, indexer, and
slash command must treat these as immutable keys until we intentionally rev the
contract.

The single source of truth for these lists lives in
`config/canonical_ids.yaml`. Update that file (and bump the version section
below) if we ever add or rename IDs.

| Domain        | Canonical IDs |
| ------------- | ------------- |
| `service_ids` | `core-api-service`, `billing-service`, `notifications-service`, `docs-portal` |
| `component_ids` | `core.payments`, `core.webhooks`, `billing.checkout`, `notifications.dispatch`, `docs.payments`, `docs.notifications` |
| `apis`        | `/v1/payments/create`, `/v1/notifications/send` |
| `doc paths`   | `docs/payments_api.md`, `docs/billing_flows.md`, `docs/notification_playbook.md`, `docs/api_usage.md`, `docs/billing_onboarding.md`, `docs/changelog.md` |

## Usage Notes

- **Synthetic Slack** (`data/synthetic_slack/slack_events.json`): every
  `service_ids`, `component_ids`, and `related_apis` entry must be a member of
  the lists above. Slack ingest should fail fast if it encounters anything else.
- **Synthetic Git** (`data/synthetic_git/git_events.json`, `git_prs.json`):
  `service_ids`, `component_ids`, and `changed_apis` must match the contract so
  graph edges can be created deterministically.
- **Docs corpus** (`data/synthetic_git/**/docs/**/*.md`): use the doc paths
  verbatim when chunk metadata is stored in the vector DB or Neo4j.
- **Future pipelines** (vector indexers, Neo4j ingester, slash orchestrators)
  should load `config/canonical_ids.yaml` rather than duplicating literals.

## Versioning

- `v1` (2025-11-29): Initial contract captured after VAT + notification storyline
  refresh.

