# Brain Graph Explorer

The Brain Explorer surfaces Neo4j evidence (services, components, endpoints, docs, Git events, Slack threads, DocIssues, etc.) in both the global Brain Universe view and the DocIssue detail page. This file documents the API contract, temporal controls, and test strategy so future contributors can extend the experience without guesswork.

## API contract (`/api/brain/universe`)

### Request parameters
| Parameter | Type | Notes |
| --- | --- | --- |
| `mode` | `"universe"` \| `"issue"` | Universe fetches a global slice; issue mode builds an ego network around `rootId`. |
| `rootId` | string | Required when `mode="issue"`. Typically a DocIssue, Component, or Investigation id. |
| `depth` | number (1-4) | Ego-network depth for issue mode (default 2). |
| `limit` | number (25-1200) | Max nodes to return; defaults to 400 for universe mode. |
| `modalities` | string[] | Optional set of modalities (e.g., `["git","slack"]`). Empty/null returns all. |
| `snapshotAt` | ISO8601 string | Optional “show everything with created_at ≤ snapshotAt”. |
| `from` / `to` | ISO8601 string | Optional time range filter (`created_at` ∈ [from, to]). Only one of `snapshotAt` or (`from`,`to`) should be supplied. |
| `projectId` | string | Future use for project-scoped graphs. |

### Response shape
```jsonc
{
  "generatedAt": "2025-01-01T00:00:00Z",
  "nodes": [{ "id": "component:1", "label": "Component", "title": "Billing", "modality": "component", "createdAt": "...", "props": {...} }],
  "edges": [{ "id": "edge:1", "source": "component:1", "target": "doc:2", "type": "DESCRIBES_COMPONENT", "createdAt": "..." }],
  "filters": { "mode": "universe", "limit": 600, "snapshotAt": null },
  "meta": {
    "nodeLabelCounts": { "Component": 20, "Doc": 15 },
    "relTypeCounts": { "DESCRIBES_COMPONENT": 15 },
    "propertyKeys": ["id","title","created_at", "..."],
    "modalityCounts": { "component": 20, "doc": 15 },
    "missingTimestampLabels": ["Service"],
    "minTimestamp": "2024-12-01T12:00:00Z",
    "maxTimestamp": "2025-01-01T00:00:00Z"
  }
}
```

`created_at` (and optionally `updated_at`) should already exist on Neo4j nodes/edges via ingestion. The backend normalizes timestamps, so the UI can rely on `createdAt`/`updatedAt` fields for rendering.

## Frontend components
- **GraphExplorer** (shared module) handles fetching, highlighting new nodes, and coordinating selection state.
- **GraphFilterBar** renders modality toggles, the time slider, and the replay control. Time controls hide automatically if `meta.minTimestamp`/`maxTimestamp` are missing.
- **GraphCanvas** is a deterministic 2D canvas (no force sim) with dark Neo4j-style styling and neighbor highlighting.
- **DatabaseInfoPanel** mirrors the Neo4j “Database Information” sidebar using `meta.nodeLabelCounts` etc.
- **NodeDetailsPanel** shows the selected node’s properties plus deep links (Slack/GitHub/Docs).
- **Neo4j-style page:** visit `/brain/neo4j` in the frontend to see the Neo4j Browser-inspired layout (left labels/relationships, centered canvas, right overview + node details) backed by `/api/brain/universe`.
- **Performance tweaks:** the Neo4j page defaults to a 100-node snapshot so the request returns in under ~5 s even on heavily populated graphs.

## Performance & caching
- `GraphDashboardService` now caches recent `/api/brain/universe` payloads for `GRAPH_SNAPSHOT_CACHE_TTL` seconds (default 30s). Repeat requests with the same filters are served from memory in ~100 ms so UI reloads feel instant.
- For speedy smoke tests, set `NEXT_PUBLIC_API_URL=http://localhost:8000` (or whichever port runs FastAPI) and visit `/brain/neo4j`. Combine with the cache for near-instant reloads.

## Temporal controls & replay
- **Snapshot slider:** default is “live” (current timestamp). Moving the slider sets `snapshotAt` and refetches the graph.
- **Replay:** clicking “Replay growth” steps from `meta.minTimestamp` → `meta.maxTimestamp` in ~16 increments, highlighting newly appeared nodes/edges.
- **Issue mode:** time controls are optional—DocIssue mini graphs disable them to reduce clutter. They can be re-enabled for investigations that benefit from replay.
- **Missing timestamps:** If a label lacks timestamp metadata, it’s listed in `meta.missingTimestampLabels` and remains visible regardless of slider position.

## Manual verification checklist
1. **Universe view:** `npm run dev` in `frontend`, open `http://localhost:3000/brain/universe`. Confirm filters, time slider, replay animation, and DatabaseInfoPanel counts match the current Neo4j data. For the Neo4j-styled shell, also open `http://localhost:3000/brain/neo4j` (defaults to limit=100 for speed) and verify label/relationship counts and overview pills match backend counts once `/api/brain/universe` returns 200.
2. **Issue mini graph:** In `oqoqo-dashboard`, run `npm run dev -p 3100`, open an issue detail page, and ensure GraphExplorer renders with correct neighbors, node details, and optional time controls.

## Testing (avoid loops)
- **Backend:** `cd /Users/siddharthsuresh/Downloads/auto_mac && source venv/bin/activate && pytest tests/api/test_brain_universe.py`
- **Frontend:** run the BrainUniverseView suite once with `npx vitest run BrainUniverseView`. This exits automatically. If you prefer `npm run test -- BrainUniverseView`, press `q` after the results to leave watch mode.
- **Dashboard:** optional smoke via `npm run lint && npm run typecheck` or the existing Playwright suite.

These steps prevent infinite watch loops and keep the graph experience consistent across both the Brain Universe and DocIssue views.

