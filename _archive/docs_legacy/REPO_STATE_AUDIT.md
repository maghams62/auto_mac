# Repository Drift & Tracking Audit

Date: 2025-11-30

## 1. Current Git Status Snapshot

- `git status -sb` shows **>1,300 files** changed relative to `main`, with almost all historical docs/tests marked as deleted. The current `stable` branch therefore reflects a heavily reduced surface (docs, tests, scripts trimmed down) and we should treat that as the new baseline.
- Key tracked directories with modifications: `desktop/`, `frontend/`, `src/`, `api_server.py`, `docs/LLM_CODEBASE_GUIDE.md`, `docs/DOCUMENTATION_INDEX.md`, `tests/test_slash_slack_orchestrator.py`.
- Mass deletions cover legacy assets in `docs/**`, `tests/**`, `scripts/testing/**`, archived prompt summaries, etc. This appears intentional (cleanup of redundant reports); do **not** resurrect them without discussion.

## 2. Newly Added / Untracked Buckets

These directories/files are untracked (`git status` `??`). We need to decide whether to add or ignore them:

| Path | Notes / Recommendation |
| --- | --- |
| `frontend/config/ui.ts` | **Track.** Shared spotlight design tokens; already imported by components. Stage the `frontend/config/` directory. |
| `docs/spotlight_ux_findings.md` | **Track.** Captures UX audit; needed for future agents. |
| `config/canonical_ids.yaml` | **Track.** Canonical ID mapping referenced by new vector tooling. |
| `src/vector/**`, `scripts/build_vector_index.py`, `scripts/ingest_synthetic_graph.py`, `scripts/replay_slack_dataset.py`, `tests/vector/**` | **Track.** These form the new vector indexing subsystem; nothing suggests they are generated assets. Stage as part of feature work. |
| `oqoqo-dashboard/src/app/api/`, `oqoqo-dashboard/src/components/common/`, `oqoqo-dashboard/src/components/live/`, `oqoqo-dashboard/vitest.config.ts` | **Track.** First-party dashboard code. Coordinate with dashboard owners before staging to avoid conflicts. |
| `prompts/slash/**`, `src/orchestrator/slash_slack/llm_formatter.py`, `src/demo/**`, `src/synthetic/**` | **Track.** Contain slash/memory prompt assets used by deterministic router; do not ignore. |
| `scripts/demo_llm_vector_graph.py`, `scripts/build_vector_index.py` | **Track** (developer tooling). |

> Action: create a dedicated staging commit for the code buckets above once we finish the current UX fixes, so future agents don’t keep seeing them as untracked.

## 3. Generated State That Should Stay Ignored

We already ignore `qdrant_storage/`, `data/trajectories/`, and `.cursor/`, but the latest runs produced additional generated folders:

| Path | Action |
| --- | --- |
| `data/logs/slash/` | Add to `.gitignore` (log dumps from slash replay). |
| `data/vector_index/` | Add to `.gitignore` (FAISS / sentence-transformer cache). |
| `slack_events.json` | Add to `.gitignore` (raw replay export; synthetic fixtures already live under `data/synthetic_slack/`). |

I will update `.gitignore` accordingly; this keeps `git status` clean without deleting useful telemetry.

## 4. Summary / Next Steps

1. **Stage real code buckets** (`frontend/config`, vector modules, prompt assets) once current fixes land. Until then, keep them untracked but documented here so parallel agents know they exist.
2. **Keep generated artifacts out of Git** by extending `.gitignore` for `data/logs/slash/`, `data/vector_index/`, and `slack_events.json`.
3. **Preserve the lean docs/tests footprint** introduced on `stable`—the deletions are intentional; do not re-add legacy reports unless explicitly asked.
4. Re-run `git status` after the ignore updates to confirm only intentional source changes remain; share this doc with other agents so everyone has the same baseline.


