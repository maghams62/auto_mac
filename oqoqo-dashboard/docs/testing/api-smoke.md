# API Smoke & Provider Matrix Tests

These checks keep the Cerebros integrations honest without opening the UI.

## 1. Provider matrix test suite

Runs through combinations of `GRAPH_PROVIDER`, `CONTEXT_PROVIDER`, and `ISSUE_PROVIDER`, ensuring each endpoint continues to return valid payloads (falling back to synthetic data when the upstream service isn’t configured).

```bash
npm run test -- src/tests/api/backend.test.ts
```

What to expect:

- All tests pass in ~1s.
- When `neo4j`, `qdrant`, or `cerebros` envs are missing you’ll see console warnings, but the responses still succeed (`fallback: true`). This is intentional.
- The cross-API test verifies `componentId`s match across `/api/activity`, `/api/graph-snapshot`, and `/api/issues`.

## 2. Quick smoke script

Calls the five public APIs for a single project and prints key stats.

```bash
# defaults to base=http://localhost:3000 & project=project_atlas
npm run smoke:api

# override project/base
npm run smoke:api -- --project project_nimbus --base http://localhost:3100
```

It will:

1. Hit `/api/activity` and confirm the project is present.
2. Fetch `/api/graph-snapshot`, `/api/issues`, `/api/context`.
3. Warn if any DocIssues reference component IDs that don’t exist in the activity/graph payloads.

Exit code is non-zero only when invariants fail (e.g., mismatched component IDs or HTTP errors).

## 3. When to run

- Before wiring new providers (Neo4j, Qdrant, Cerebros) or changing env configuration.
- After touching `/api/activity`, `/api/graph-snapshot`, `/api/issues`, or `/api/context`.
- Ahead of a demo: run `npm run smoke:api`, then do the lightweight UI sweep in `docs/testing/dashboard-clarity.md`.

