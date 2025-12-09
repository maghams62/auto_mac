## Live Dashboard Runbook

This checklist keeps the dashboard honest about _live_ data by separating the happy-path acceptance flow from the synthetic regression path.

### 1. Prep the backends

1. Start FastAPI (defaults to `http://localhost:8000`) and Next.js (`npm run dev -- -p 3100`).
2. Run the ingest jobs:
   - `python3 scripts/impact_auto_ingest.py --repos <owner/repo>` to ensure DocIssues exist.
   - `python3 scripts/run_activity_ingestion.py --sources slack git` so ActivityGraph sees Slack/Git.
3. Seed/refresh the Neo4j graph if needed: `python3 scripts/seed_graph.py --fixtures --swagger`.

#### Required env

- `CEREBROS_API_BASE` and `NEXT_PUBLIC_CEREBROS_API_BASE` must point at the live FastAPI host (default `http://localhost:8000`).
- `LIVE_GIT_ORG` / `NEXT_PUBLIC_LIVE_GIT_ORG` define the GitHub org that deep links use (defaults to `maghams62`). Override individual slugs with `ATLAS_CORE_REPO_SLUG`, `ATLAS_BILLING_REPO_SLUG`, etc., if the repo names changed.
- Keep `ALLOW_SYNTHETIC_FALLBACK` unset (or `false`). Set it to `true` only when you intentionally want `/api/activity` or `/api/doc-issues` to fall back to fixtures.

### 2. Live acceptance checks

1. `curl http://localhost:8000/activity/snapshot` – expect non-empty git+slack arrays and a `generatedAt` timestamp from the last ingest.
2. `curl http://localhost:8000/api/graph/snapshot?projectId=project_atlas` – expect `provider:"neo4j"` and the component count you seeded.
3. `curl http://localhost:8000/api/graph/metrics?projectId=project_atlas` – verify all four KPIs have numeric values.
4. `curl http://localhost:8000/impact/doc-issues?project_id=project_atlas` – confirm every issue lists the same `component_ids` that appear in the graph snapshot.
5. `npm run smoke:api` (defaults to project_atlas). This fails if any endpoint falls back to synthetic data or if DocIssues reference component IDs that the graph/activity snapshot doesn’t know about.
6. `npm run validate:live` – confirms `/api/activity` and `/api/doc-issues` both return `mode=atlas` and that GitHub links point at the configured org.

### 3. Synthetic regression path

CI and local unit tests shouldn’t need Neo4j/Qdrant/Slack. Use the new synthetic flag instead of relying on env hacks:

```bash
npm run smoke:api:synthetic            # equivalent to node scripts/smoke-api.mjs --synthetic
# or on demand:
node scripts/smoke-api.mjs --mode synthetic --project project_nimbus
```

The script adds `?mode=synthetic` to every API call so the Next.js routes skip Cerebros/Neo4j and return fixture data. The contract tests (`vitest`) also cover this path via `mode=synthetic` to guarantee it keeps working.

### 4. Operational notes

- **DocIssues vs Graph:** The default Atlas fixtures now use canonical Neo4j IDs (`comp:atlas-core`, etc.), so the smoke test’s component-alignment check is meaningful even when you fall back to mock data.
- **Env toggles:** Use `OQOQO_MODE=synthetic` (server) or `NEXT_PUBLIC_OQOQO_MODE=synthetic` (client) when you want the entire UI to stay in fixture mode, but prefer the per-request `mode=synthetic` flag for scripts/tests.
- **Live guardrail:** Leave `ALLOW_SYNTHETIC_FALLBACK` unset in production so the dashboard never pretends synthetic data is live. The only exceptions are manual demos where you explicitly export `ALLOW_SYNTHETIC_FALLBACK=true`.
- **Debug mode:** `/projects/<id>/configuration#setup-debug` still surfaces ingest counters, so you can confirm the “live-first” status cards match the raw numbers before each demo.

Following this runbook ensures “live” truly means live, while keeping the synthetic workflow reliable for CI.

