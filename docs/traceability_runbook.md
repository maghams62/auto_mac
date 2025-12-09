# Traceability Runbook

## Feature flag

| Toggle | Location | Default | Notes |
| --- | --- | --- | --- |
| `traceability.enabled` | `config.yaml` | `true` | Set to `false` to keep Cerebros chat online while disabling investigation persistence. |
| `TRACEABILITY_ENABLED` | env var | `true` | Runtime override (e.g., `TRACEABILITY_ENABLED=false uvicorn api_server:app`). Takes precedence over config. |

When either flag is `false`, `/traceability/*` endpoints return empty payloads and Cerebros hides the “Create doc issue” CTA.

## JSONL store management

* Location: `traceability.investigations_path` (default `data/live/investigations.jsonl`).
* `TraceabilityStore` enforces:
  * `max_entries`
  * `retention_days`
  * `max_file_bytes` (default 5 MB)
  * tenant scoping via `tenant_id`
* To inspect the latest investigations:

  ```bash
  python - <<'PY'
  import json, pathlib
  path = pathlib.Path("data/live/investigations.jsonl")
  records = json.loads(path.read_text())
  print(len(records), "records")
  print(records[-1])
  PY
  ```

* To reset the store, stop the API server, move the file, and restart:

  ```bash
  mv data/live/investigations.jsonl data/live/investigations.jsonl.bak.$(date +%s)
  ```

## Health monitoring

`GET /health` now includes:

```json
{
  "traceability": {
    "enabled": true,
    "feature_enabled": true,
    "path": "data/live/investigations.jsonl",
    "max_entries": 1000,
    "retention_days": 30,
    "max_file_bytes": 5242880,
    "schema_version": 1,
    "last_write_at": "...",
    "last_error": null
  }
}
```

If `last_error` is non-null, the store is not accepting writes—inspect disk space or permissions.

## Operational playbook

1. **Enable/disable quickly** – set `TRACEABILITY_ENABLED=false` and restart Uvicorn (or use supervisor command) to pause persistence without redeploying.
2. **Inspect live data** – hit `GET /traceability/investigations?component_id=core.api&limit=10` to audit what was recorded.
3. **File DocIssues manually** – use `POST /traceability/doc-issues` with the investigation/evidence IDs returned by the WebSocket payload.
4. **Export for audits** – `GET /traceability/investigations/export?format=csv&project_id=atlas` produces a CSV snapshot. JSON export is the default when `format=json`.
5. **Cleanup** – rotate the JSON file periodically if `max_file_bytes` warnings appear; the store logs `[TRACEABILITY] Failed to append investigation` when it cannot write.

## Environment defaults

| Environment | `retention_days` | `max_entries` | `max_file_bytes` |
| --- | --- | --- | --- |
| Dev | 7 | 100 | 2 MB |
| Staging | 14 | 500 | 5 MB |
| Prod | 30 | 1000 | 10 MB |

Override the defaults in `config.yaml > traceability` per environment. For privacy-sensitive test beds, set `traceability.enabled=false` and rely on `TRACEABILITY_ENABLED` to temporarily re-enable when debugging.

