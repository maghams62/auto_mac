# Instant Startup + Expanded View Notes

This document gives coding LLMs (and new engineers) a quick mental model of the
launcher stack after the instant-startup improvements. It covers the cache,
telemetry hooks, and UI animation so future chats can reason about regressions
without spelunking through the entire repo.

## 1. Startup Cache (Python backend)

- **Entry points**
  - `src/cache/startup_cache.py` — `StartupCacheManager`
  - Wired into `api_server.py` right after the global `ConfigManager` loads.
- **What is cached?**
  - Pre-sliced prompt bundles for `AutomationAgent`.
  - Metadata (prompt keys, timestamps) for diagnostics.
- **Invalidation**
  - Fingerprints hash `config.yaml` plus the `prompts/` tree. Touching either
    file automatically invalidates the cache on the next boot.
- **Health**
  - `GET /api/storage/status` now returns `startup_cache` metadata so the
    Electron diagnostics overlay can display hit/miss information.

## 2. Startup Profiler & OTLP safeguards

- `src/utils/startup_profiler.py` provides a shared `StartupProfiler`.
- `api_server.py` marks key phases (`config_manager_ready`,
  `automation_agent_ready`, `fastapi_startup_complete`) and emits a timeline
  once FastAPI finishes its startup event.
- Noisy OTLP exporter failures are downgraded to a single warning via
  `_configure_otel_logging()` so launch logs stay readable even when a local OTLP
  collector is offline.

## 3. Electron timeline

- `desktop/src/main.ts` now records `markStartup()` entries for:
  - Electron readiness
  - Backend/frontend detection, spawn, and health checks
  - UI initialization (including failure summaries)
- `emitStartupSummary()` logs the entire timeline when the UI is ready or when
  diagnostics are shown. These entries make it trivial to answer “what took so
  long?” questions.

## 4. Expanded desktop animation

- `frontend/app/desktop/page.tsx` dynamically imports `ChatInterface` so the
  desktop window can render immediately.
- `frontend/components/DesktopExpandAnimation.tsx` shows a Raycast-style
  expansion overlay while the chat bundle hydrates. State changes are logged via
  `logger.info("[DESKTOP] Expand overlay state changed", …)`.

## 5. Test & verification checklist

```
# Python cache tests
pytest tests/unit/test_startup_cache.py

# Frontend lint + typecheck (optional but recommended when touching desktop UI)
cd frontend && npm run lint
```

Manual checks:
1. Launch Electron dev app — verify `[STARTUP]` timeline logs appear once the UI
   is ready.
2. Trigger the expanded window from Spotlight — overlay animation should play
   before chat history renders.
3. Hit `GET http://127.0.0.1:8000/api/storage/status` — response should include
   `startup_cache`.
4. If diagnostics show “Backend process exited with error,” tail
   `logs/electron/*.log` to see the new `[DIAGNOSTIC] Backend stderr tail`
   section. The launcher now aborts the 30s wait as soon as the backend dies, so
   import errors or dependency issues can be fixed immediately.

Armed with this doc, a new agent (or coding assistant) can reason about the
instant-startup pipeline without re-deriving the architecture from scratch.

