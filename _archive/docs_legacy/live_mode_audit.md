# Live vs Synthetic Audit

This document records where the Cerebros/Oqoqo stack still references the synthetic
dataset and what configuration toggles control each subsystem. It is intended to
be the source of truth for Step 1 of the live-data migration plan.

## Activity ingest & signals

| Area | Default | Config & files | Notes |
| --- | --- | --- | --- |
| Slack ingest | Live, but UI badge still says `synthetic_slack` | `config.yaml` → `slash_slack.workspace_url` (empty) and `debug_source_label` defaults to `${SLASH_SLACK_DEBUG_SOURCE_LABEL:-synthetic_slack}` | Set `workspace_url=https://<workspace>.slack.com` and `SLASH_SLACK_DEBUG_SOURCE_LABEL` to a live label to avoid synthetic branding. |
| Git ingest | Live when `SLASH_GIT_USE_LIVE_DATA=true`, synthetic otherwise | `config.yaml` → `slash_git.use_live_data` (env override) and `slash_git.synthetic_data.*` paths. `config/slash_git_targets.yaml` still declares `synthetic_root` for every repo. | Remove the `synthetic_root` references once real repos are wired so the synthetic loader is opt-in only. |
| Activity graph doc issues | Falls back to `data/synthetic_git/doc_issues.json` if `impact.data_mode=synthetic` | `src/activity_graph/service.py` lines 163‑183 | Keep `IMPACT_DATA_MODE=live` in all runtime environments so the graph only reads `data/live/doc_issues.json`. |
| Impact pipeline | Honors `impact.data_mode`; synthetic fixtures live under `data/synthetic_git/*` | `src/impact/pipeline.py` lines 62‑139; `config.yaml` `impact.data_mode` default `${IMPACT_DATA_MODE:-live}` | Never set `IMPACT_DATA_MODE=synthetic` outside automated tests. |

## Dashboard API & UI

| Area | Default | Config & files | Notes |
| --- | --- | --- | --- |
| `/api/activity` | Defaults to `"synthetic"` mode unless `OQOQO_MODE` env is `atlas` | `oqoqo-dashboard/src/app/api/activity/route.ts` lines 131‑189 | Set `NEXT_PUBLIC_OQOQO_MODE=atlas` (and server equivalent) so production never silently drops to synthetic when config is missing. |
| `/api/graph-*` | Provider fallback loads `syntheticGraphProvider` if the live provider errors | `oqoqo-dashboard/src/app/api/graph-metrics/route.ts` + `/graph-snapshot` | Keep fallback path but gate with `ALLOW_SYNTHETIC_FALLBACK` in prod so errors surface instead of hiding behind fixtures. |
| `/api/impact/doc-issues` | Accepts `mode=synthetic` query param and otherwise follows env mode | `oqoqo-dashboard/src/app/api/impact/doc-issues/route.ts` lines 50‑111 | Document that synthetic mode is strictly for tests and ensure env default is `atlas`. |
| Cerebros deep links | Historically pointed at `https://cerebros.oqoqo.dev/...` regardless of env | `oqoqo-dashboard/src/lib/cerebros.ts`, `project-card.tsx`, `ask-cerebros-button.tsx` | Set `NEXT_PUBLIC_CEREBROS_APP_BASE`/`CEREBROS_APP_BASE` to the live UI (e.g., `http://localhost:3002`) so “Open project” + “Ask Oqoqo / Cerebros” buttons generate valid links, and keep the slug config (`cerebrosSlug`) aligned with the server routes. |
| Storybook/tests | Force synthetic mode intentionally | `oqoqo-dashboard/playwright.config.ts`, `package.json` scripts, `docs/testing/*` | No change needed; these are dev-only flows. |

## Documentation

* `README.md`, `docs/option1_activity_graph.md`, and `docs/option2_cross_system_impact.md` still describe the synthetic “contract change” workflow. Update once live repos are wired so instructions describe running the ingest scripts instead of editing fixtures.
* `docs/live_ingest_setup.md` only lists env vars; extend it (Step 5) with a “Verification” section covering the curl checks from the plan.

Keep this file updated as subsystems migrate so future contributors can immediately see whether a given environment is running purely live data.

