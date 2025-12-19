# Traceability Tool Coverage

| Tool / Agent | Evidence hook | Status | Notes |
| --- | --- | --- | --- |
| `/slack` summaries (slash_slack_summary) | `sections.references + evidence[]` normalized via `_normalize_evidence_entries` | ✅ | Ensures every thread/permalink has canonical Slack IDs. |
| `/git` summaries (slash_git_summary) | `notable_prs` + `references` + doc fragments | ✅ | PRs/commits use canonical `git:{repo}:{id}` IDs. |
| Doc search (`documents.search`, `DocumentPreview`) | `files[]` array normalized to `doc:{repo}:{path}#L` | ✅ | Evidence chips created for doc fragments. |
| Impact analyzer / MultiSourceReasoner | `ImpactReport.evidence` fed through `EvidenceCollection` | ✅ | Each recommendation includes `evidence_ids` handed to DocIssueService. |
| Tickets / complaints (Slack complaint ingestion) | Slack + Git payloads normalized upstream | ✅ | Slack complaint context already includes canonical `slack:{channel}:{ts}` identifiers. |
| Multi-hop RAG helpers, bespoke LLM notes | No external tool usage → intentionally skipped | ⚠️ | Marked “conversation-only” so `_maybe_record_investigation` never persists them. |

## Coverage checklist

* Slash tool outputs are verified during CI via the new `tests/traceability/test_traceability_flow.py` golden path.
* `documents.search`, screenshot/doc preview, synthetic evidence jobs share the same `files[]` path (no custom plumbing required).
* Bespoke agents that never call external APIs (calendar, todo triage, small talk) are labeled “conversation-only” so the store doesn’t persist them.

## Backfill strategy

* **Decision:** no historical backfill. Traceability is guaranteed for all runs executed on/after **1 Dec 2025**.
* The JSONL store contains a `schema_version` so we can retro-migrate in the future if we ingest old DocIssues or run a one-off backfill job.
* Existing DocIssues remain untouched; new ones filed through the modal or impact pipeline automatically carry `origin_investigation_id` and `evidence_ids`.

