# API Smoke & Provider Matrix Tests

These checks keep the Cerebros integrations honest without opening the UI.

## 1. Provider matrix test suite

Runs through combinations of `GRAPH_PROVIDER`, `CONTEXT_PROVIDER`, and `ISSUE_PROVIDER`, ensuring each endpoint continues to return valid payloads. Silent fallbacks are no longer allowed—any HTML/non-JSON upstream response now fails fast so we notice missing envs immediately.

```bash
npm run test -- src/tests/api/backend.test.ts
```

What to expect:

- All tests pass in ~1s.
- Upstream HTML or 5xx responses now surface as 502s (see `Live-mode safeguards` tests for regression coverage).
- The cross-API test still verifies `componentId`s match across `/api/activity`, `/api/graph-snapshot`, and `/api/issues`.

## 2. Quick smoke script

Calls the five public APIs for a single project and prints key stats.

```bash
# defaults to base=http://localhost:3100 & project=project_atlas
npm run smoke:api

# override project/base
npm run smoke:api -- --project project_nimbus --base http://localhost:3100
```

It will:

1. Hit `/api/activity` and confirm the project is present.
2. Fetch `/api/graph-snapshot`, `/api/issues`, `/api/context`.
3. Warn if any DocIssues reference component IDs that don’t exist in the activity/graph payloads.
4. Validate `/api/impact/doc-issues` twice—once in the currently requested mode and once with `mode=synthetic`—and fail if the response is missing `doc_issues`, `mode`, or `fallback`.
   - Treat any HTML response or missing keys as a hard failure (this is how we catch JSON parse regressions).
   - When synthetic mode is forced the script expects `mode=synthetic`; otherwise it requires `mode=atlas`.

Exit code is non-zero only when invariants fail (e.g., mismatched component IDs or HTTP errors).

## 3. Live-mode validator

`npm run validate:live` calls `/api/activity` and `/api/doc-issues` to ensure:

- `mode === "atlas"` when the Cerebros backend is reachable.
- DocIssues contain GitHub links for the configured org (no more `github.com/oqoqo/...` placeholders).

This script exits non-zero if either endpoint falls back to synthetic data without an explicit `mode=synthetic`.

## 4. When to run

- Before wiring new providers (Neo4j, Qdrant, Cerebros) or changing env configuration.
- After touching `/api/activity`, `/api/doc-issues`, `/api/issues`, or `/api/context`.
- Ahead of a demo: run `npm run validate:live`, `npm run smoke:api`, then do the lightweight UI sweep in `docs/testing/dashboard-clarity.md`.

