## Dashboard Testing Playbook

Use this checklist to verify the Activity/Drift experience before demos or deployments.

### 1. Start the backend + dashboard

```bash
# terminal 1 – FastAPI + Neo4j bridge
cd /Users/siddharthsuresh/Downloads/auto_mac
source venv/bin/activate
python api_server.py

# terminal 2 – Next.js dashboard with sane defaults
cd /Users/siddharthsuresh/Downloads/auto_mac/oqoqo-dashboard
./oq_start.sh --hostname 127.0.0.1 --port 3100
```

`oq_start.sh` now auto-exports `CEREBROS_API_BASE` and `NEXT_PUBLIC_CEREBROS_API_BASE` when they are missing, so the dashboard immediately points at `http://127.0.0.1:8000`.

### 2. Exercise the API surface

Run the dual-mode smoke test (live + synthetic) against the dev server:

```bash
npm run smoke:api -- --project project_atlas --base http://127.0.0.1:3100 --both
```

- Uses live (`mode=atlas`) first, then synthetic (`mode=synthetic`).
- Set `SMOKE_BASE_URL`, `SMOKE_PROJECT_ID`, or pass `--mode synthetic` to scope manually.

For a quick regression sweep:

```bash
npm run test:full   # lint + typecheck + vitest + smoke:api
```

Ensure the dashboard (port 3100) is running before invoking `test:full`, since `smoke:api` hits the live endpoints.

### 3. UI smoke via Playwright

Playwright wraps `npm run dev` automatically and runs against `http://127.0.0.1:3100`:

```bash
npm run smoke:pages
```

The new `playwright/activity.spec.ts` script verifies:

- System map nodes & legend
- Component summary + doc issues w/ real Slack/Git links
- Replay timeline slider + tooltip updates
- Synthetic/live toggle visibility

Override the base URL with `PLAYWRIGHT_BASE_URL` if needed.

### 4. Manual UX sweep

1. Visit `/projects/project_atlas/activity`.
2. Use the mode toggle (top-right) to flip between “Live data” (`mode=atlas`) and “Synthetic dataset”.
3. Click nodes on the system map—doc issues and the replay timeline should update instantly.
4. Drag the timeline scrubber; the summary pill above the chart should reflect the selected day.
5. Expand a doc issue and follow the Git/Slack deep links; they now only render when the URLs are valid `https://` targets.
6. Press “Ask Cerebros” on a component or issue—the button exposes loading/error states and links back to Cerebros when the backend responds.

### 5. Nimbus spot-check

Repeat steps 2–4 for `project_nimbus`. Use the smoke script:

```bash
npm run smoke:api -- --project project_nimbus --base http://127.0.0.1:3100 --both
```

If any endpoint falls back to synthetic unexpectedly, double-check:

- FastAPI logs (`api_server.py`) for Neo4j timeouts.
- `.env.local` for `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.
- That `scripts/ingest_synthetic_graph.py` completed recently (populates Neo4j quickly).

### 6. Common fixes

| Symptom | Likely fix |
| --- | --- |
| `/api/graph-snapshot` 5xx or fallback | Ensure FastAPI is running and `NEO4J_*` env vars are exported. |
| Dashboard still “screensaver” | Toggle to Synthetic to ensure data, then back to Live once backend recovers. |
| Ask Cerebros errors immediately | Verify `CEREBROS_API_BASE` is reachable (the API route now surfaces upstream error text). |

Capture console output (`npm run smoke:api`) plus screenshots from Playwright before sign-off.


