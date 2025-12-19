# Neo4j Graph Provider

This document captures the dashboard-side contract for Phase 7, where the live graph view consumes Neo4j snapshots instead of the in-process synthetic builder.

## 1. Configuration

Set the following in `.env.local` (or your deployment secret manager):

- `GRAPH_PROVIDER=neo4j`
- `NEO4J_URI=bolt://<host>:<port>` (or `neo4j+s://` for Aura)
- `NEO4J_USER=<username>`
- `NEO4J_PASSWORD=<password>`

For local development without Neo4j, omit the variables and the dashboard will remain in `synthetic` mode.

## 2. Schema

The dashboard expects the following labels/relationships (all IDs must match `Project`, `ComponentNode`, and `DocIssue` IDs in the export schema):

| Label      | Properties (minimum)                             |
| ---------- | ------------------------------------------------ |
| `Component`| `id`, `name`, `ownerTeam`, `serviceType`, drift/activity bundles |
| `Issue`    | `id`, `title`, `severity`, `componentId`         |
| `Signal`   | `id`, `source` (`ticket`/`support`/`slack`), `summary`, `timestamp`, `link` |

| Relationship | Direction | Notes |
| ------------ | --------- | ----- |
| `DEPENDS_ON` | `Component` → `Component` | `surface`, `description` |
| `ALERTS`     | `Issue` → `Component` | severity is stored on the issue node |
| `SIGNAL_FOR` | `Signal` → `Component` | indicates contextual chatter linked to the component |

Minimal Cypher to inspect a project graph:

```cypher
MATCH (p:Project {id: $projectId})-[:HAS_COMPONENT]->(c:Component)
OPTIONAL MATCH (c)-[r:DEPENDS_ON]->(target:Component)
RETURN c, collect(r) as dependencies, collect(target) as targets
```

## 3. Dashboard snapshot contract

`GET /api/graph-snapshot?projectId=<id>` will:

1. Call the provider returned by `getGraphProvider()` (`neo4j` when `GRAPH_PROVIDER=neo4j`).
2. Map the Neo4j result into the existing `GraphSnapshot` shape (component/issue/signal nodes + dependency/issue/signal edges).
3. Return:

```jsonc
{
  "snapshot": { "nodes": [...], "edges": [...] },
  "provider": "neo4j",
  "counts": { "nodes": 120, "edges": 230, "components": 14, "issues": 5 },
  "updatedAt": "2025-12-01T21:14:03.123Z",
  "fallback": false
}
```

If Neo4j errors, the route downgrades to the synthetic provider and sets `fallback: true`.

## 4. Troubleshooting

| Symptom | Fix |
| --- | --- |
| API returns `provider: "synthetic"` even though `GRAPH_PROVIDER=neo4j` | Ensure all `NEO4J_*` env vars are set. Missing credentials cause the provider to throw before running any query. |
| UI badge shows `Neo4j live (fallback)` | Neo4j timed out or returned an error. Check server logs for `[graph-snapshot] primary provider failed`; the request already fell back to synthetic data. |
| Nodes missing in Neo4j view | The dashboard caps rendering at 150 nodes. When `counts.nodes > 150`, only the first 150 nodes are visualized, and a note appears on the banner. Narrow the filters or reduce the query scope in Neo4j. |
| IDs mismatch | Verify the Phase 6 export job is writing identical component/issue IDs into Neo4j. Drift issues must reference `componentId` to allow the `ALERTS` relationship. |

## 5. Query snippets

Latest issues for a project:

```cypher
MATCH (i:Issue)-[:ALERTS]->(c:Component {projectId: $projectId})
RETURN i, c
ORDER BY i.detectedAt DESC
LIMIT 25
```

Signals for a component:

```cypher
MATCH (s:Signal)-[:SIGNAL_FOR]->(c:Component {id: $componentId})
RETURN s
ORDER BY s.timestamp DESC
LIMIT 10
```

