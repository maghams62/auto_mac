# Telemetry & Logging Improvements (2025‑11‑28)

## Desktop/Electron

- Added a reusable `logPortDiagnostics()` helper that shells out to `lsof` (macOS) whenever port `8000` or `3000` is reported as “in use”.  
- The helper injects the process list into `logs/electron/*.log`, so we can immediately see which orphaned `python`/`next-server` instance is blocking startup.
- The frontend spawner now watches Next.js stdout for `Port 3000 is in use` and for “Local: http://localhost:<port>” lines:  
  - If Next binds any port other than 3000, Electron logs a warning explaining that the launcher will still target 3000 and suggests killing the conflicting process.  
  - When the expected port is claimed successfully we log the port number explicitly.

## Backend

- `api_server.py` uses `from __future__ import annotations`, eliminating the `ContextChangeRequest` NameError that previously crashed Uvicorn before it bound to port 8000.

## Frontend

- No code change was required, but the new telemetry makes it obvious when `/launcher` is being served from a fallback port rather than 3000, closing the loop between Next.js output and Electron’s diagnostics.

These changes tie the observed failures (port collisions, missing backend health) to actionable log lines without having to run `lsof` manually each time.

