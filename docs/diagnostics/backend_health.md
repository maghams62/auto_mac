# Backend Health Check (2025‑11‑28)

## Repro

```
cd /Users/siddharthsuresh/Downloads/auto_mac
venv/bin/python api_server.py
```

## Findings

1. **NameError during import**  
   - `async def post_context_resolution_changes(request: ContextChangeRequest):` executed before `ContextChangeRequest` was defined (class lived later in the file).  
   - Python evaluates annotations eagerly because `from __future__ import annotations` was missing, so the module crashed before Uvicorn spun up.

2. **Fix**  
   - Added `from __future__ import annotations` at the top of `api_server.py`.  
   - Backend now bootstraps successfully, initializes telemetry, background schedulers, Bluesky notifications, and GitHub watchers.

3. **Residual issues**  
   - If an older instance is still bound to port `8000`, the new process logs `[Errno 48] ... address already in use`. Run `lsof -ti:8000 | xargs kill -9` before restarting or rely on `scripts/start_ui.sh` which already does this.  
   - `urllib3` emits `NotOpenSSLWarning` because macOS ships LibreSSL—benign but noisy.  
   - OTLP trace exporter still targets `localhost:4317`; without an OpenTelemetry collector the retries continue (see `logs/api_server.log`), though they no longer prevent boot.

With the annotation gate removed, backend failures should now be limited to configuration (ports, telemetry endpoints) rather than Python import errors.

