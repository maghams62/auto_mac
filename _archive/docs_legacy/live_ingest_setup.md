# Live ingest setup

This check-list moves the dashboard + Cerebros bridge off the synthetic fixtures. Keep
it handy when setting up a new environment or debugging “why did the API fall back?”.

## 1. Environment variables

Set these in `.env` (dashboard) and `DONT_PUSH_env_stuff.md` (backend). Defaults fall
back to the canonical demo repos, but real deployments should override them. After
filling the values, run `python scripts/diagnose_slack_ingest.py` to make sure the
Slack token can hit `conversations.history` and the bot sits in the monitored channel.

| variable | purpose |
| --- | --- |
| `CEREBROS_API_BASE`, `NEXT_PUBLIC_CEREBROS_API_BASE` | FastAPI backend base URL (e.g., `https://cerebros.yourcompany.com`). |
| `NEXT_PUBLIC_CEREBROS_APP_BASE` | Optional link target for “Open in Cerebros” buttons. |
| `LIVE_GIT_ORG` | GitHub org/owner that hosts `core-api`, `billing-service`, `docs-portal` (defaults to `maghams62`). |
| `CORE_API_REPO`, `CORE_API_BRANCH` | Override repo slug/branch if the upstream service uses a different name. |
| `BILLING_SERVICE_REPO`, `BILLING_SERVICE_BRANCH` | Same for the downstream repo. |
| `DOCS_PORTAL_REPO`, `DOCS_PORTAL_BRANCH` | Same for the docs portal repo. |
| `DOCS_BASE_URL` / `NEXT_PUBLIC_DOCS_BASE` | Base URL for docs deep-links. |
| `SLACK_WORKSPACE`, `SLACK_CHANNELS`, `SLACK_BOT_TOKEN`, `SLACK_TOKEN` | Slack ingest + permalink generation (validated via `scripts/diagnose_slack_ingest.py`). |
| `NEXT_PUBLIC_OQOQO_MODE` | Set to `atlas` for live mode, `synthetic` only when demos explicitly require it. |

> Synthetic fixtures are no longer auto-loaded in production. Pass `?mode=synthetic` or
> set `NEXT_PUBLIC_OQOQO_MODE=synthetic` if you really want the mock data.

## 2. Seed real Git activity

1. Push real commits/PRs to the three repos. The canonical storyline assumes:
   - `core-api`: contract changes under `contracts/payment_v2.json`
   - `billing-service`: downstream integrations touching `src/checkout.py`
   - `docs-portal`: docs in `docs/payments_api.md` and friends
2. Run the ingest jobs (requires valid GitHub + Slack credentials). Before kicking them off, you can run `python scripts/diagnose_git_ingest.py` to make sure each repo/branch resolves for the PAT in `GIT_TOKEN`/`GITHUB_TOKEN`.

```bash
cd /path/to/auto_mac
python scripts/refresh_live_ingest.py
```

> `refresh_live_ingest.py` re-runs `run_activity_ingestion.py` for Slack+Git and then
> executes `scripts/impact_auto_ingest.py --limit 20`. Pass `--skip-slack`, `--skip-git`,
> or `--skip-impact` if you only want to refresh a single source.

Both scripts log the repo/channel they are touching. If you see `Resource not found`
errors, double-check `GIT_ORG` and repository names.

## 3. Verification

With the FastAPI server running (`uvicorn api_server:app --reload`):

```bash
curl "$CEREBROS_API_BASE/impact/doc-issues?source=impact-report" | jq '.mode,.doc_issues[0].links'
curl "$CEREBROS_API_BASE/activity-graph/top-dissatisfied?limit=5" | jq '.provider,.results[0].component_id'
curl "$CEREBROS_API_BASE/activity/snapshot?limit=5" | jq '.mode,.git[0].url'
```

Expected results:

- `mode` should be `atlas` (or another live variant), never `synthetic`.
- Git/Slack/doc links should be fully qualified URLs (GitHub, Slack, docs site).
- `fallback` flags should be `false`. If a route returns `503`, fix the upstream
  service instead of flipping to synthetic.

## 4. Dashboard smoke

1. Visit `/projects/project_atlas/activity` and confirm the provider badge reads
   “Cerebros ActivityService • live”.
2. Click “Doc”, “Slack”, “Git” chips and ensure they open real systems.
3. Trigger the Ask-Cerebros button and confirm it calls `/api/cerebros/ask-graph`
   (Network tab) and returns a link built from `NEXT_PUBLIC_CEREBROS_APP_BASE`.

If any of the API routes fall back to synthetic while `NEXT_PUBLIC_OQOQO_MODE=atlas`,
capture the server log—they now return `5xx` instead of silently swapping in fixtures.
