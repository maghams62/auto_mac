# Log Snapshot — 2025‑11‑28

## Electron (`logs/electron/cerebros-2025-11-28T18-03-57-309Z.log`)

- Launcher initializes cleanly: detects dev mode, confirms `venv` + `api_server.py`, and notes both backend/frontend already running.
- `waitForServer` succeeds immediately (`~/health` in 2 ms, `localhost:3000` in ~15 ms).
- Self-test confirms the visibility state machine (lock/unlock + blur grace) and hotkey toggling.
- No `STARTUP FAILED` or diagnostic-window triggers in the latest run.

## Frontend (`logs/frontend.log`)

- Single session of `npm run dev` with Next.js 14.2.0.
- Server boots in ~1.3 s; no compilation errors or warnings recorded.
- Suggests port `3000` is free and the dev server is able to serve `/launcher`.

## Backend (`logs/api_server.log`)

Key signals from the tail section:

1. **OTLP telemetry exporter failures**  
   - Repeated `StatusCode.UNAVAILABLE` errors when exporting traces to `localhost:4317`.  
   - Indicates no collector listening; spans are retried indefinitely, adding log noise and potential latency.

2. **File thumbnail 404**  
   - `GET /api/files/thumbnail?...` returns 404 for `tests/data/test_docs/mountain_landscape.jpg`, suggesting either the sample asset moved or indexing is pointing at test paths.

3. **Heavy polling**  
   - `GET /api/spotify/status` floods the log (multiple requests per second). Functionally OK (200 responses) but makes error hunting harder; consider reducing poll cadence or logging level.

4. **Clean shutdown**  
   - Recent run exited gracefully (scheduler + Bluesky notification service stop messages), so no lingering traceback currently.

## Takeaways

- Electron orchestration is functioning; failures are unlikely to stem from window creation.
- Frontend dev server is healthy; if the UI is blank, it is likely due to renderer-code regressions rather than server startup.
- The backend OTLP exporter misconfiguration is the only critical error pattern and should be muted or pointed at a live collector to avoid log spam and startup slowdowns.

