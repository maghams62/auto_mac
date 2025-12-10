# Vector Operations Playbook

This guide covers everything needed to keep the Qdrant-backed vector layer healthy,
including configuration, health checks, and recovery tooling.

## Environment Variables

Set the following secrets in `.env` (or export them in CI):

| Variable | Purpose | Notes |
| --- | --- | --- |
| `QDRANT_URL` | Base URL for the Qdrant instance | Defaults to `http://localhost:6333` for local dev |
| `QDRANT_API_KEY` | API key for hosted clusters | Optional for localhost deployments |
| `QDRANT_COLLECTION` | Primary collection name | Defaults to `oqoqo_context` |
| `VECTORDB_URL` / `VECTORDB_API_KEY` / `VECTORDB_COLLECTION` | Legacy fallbacks | Still honored so older env files keep working |

> Tip: `.env.sample` in the repo already contains these keys so new environments can copy it directly.

## Health Checks

1. **Targeted check**
   ```bash
   python scripts/verify_vectordb.py --skip-mutation   # read-only ping
   python scripts/verify_vectordb.py                   # full create/delete verification
   ```
   Sample output (local Qdrant):

   ```text
   [OK] Connected to Qdrant at http://localhost:6333 (36.1 ms).
        Collections visible: 1
   [OK] Created temporary collection 'oqoqo_context_verify_64dda496'.
   [OK] Deleted temporary collection 'oqoqo_context_verify_64dda496'.
   ```

2. **Preflight bundle**
   ```bash
   python scripts/run_checks.py --vectordb
   ```
   `--all` runs every available check (vector checks run by default when no flags are passed).

The scripts load `config.yaml`, so updating the vectordb block is the single source of truth.

### CI / Preflight Integration

- Add a pipeline step such as:
  ```bash
  export QDRANT_URL=$QDRANT_URL
  export QDRANT_API_KEY=$QDRANT_API_KEY
  python scripts/run_checks.py --vectordb
  ```
- Fail the job if the script exits non-zero; that indicates connectivity or permission issues.
- In GitHub Actions, declare the secrets under environment variables and run the command inside the same job to block deploys when Qdrant is unreachable.
- Use `--list` to verify available checks before wiring multiple steps into CI.

## Backfilling Chat History

Use the Mongo DAO plus the new backfill CLI to replay historical chats into Qdrant.

```bash
# Dry-run, prints progress without writing to Qdrant
python scripts/backfill_chats_to_vectordb.py \
  --dry-run \
  --batch-size 200 \
  --resume-file data/vector_backfill.cursor

# Resume from a specific timestamp (ISO format) and target a single session
python scripts/backfill_chats_to_vectordb.py \
  --resume-after 2025-11-01T00:00:00+00:00 \
  --session-id session_123 \
  --resume-file data/vector_backfill.cursor
```

Tips:
- Enable the mongo block in `config.yaml` and ensure `motor` can reach the cluster.
- Provide `QDRANT_*` env vars before running so the CLI can authenticate.
- The script stops on the first failed batch to avoid silent gaps; rerun with `--resume-after`
  using the last successful `created_at` timestamp printed in the logs (or point the new
  `--resume-file` flag at a location that automatically tracks the latest cursor).
- Each batch logs throughput (docs/second) so you can estimate total runtime when replaying
  large histories.

## API Monitoring

- `GET /api/vector/health` – validates the vectordb config, pings `/collections`, and emits
  latency plus collection counts (useful for dashboards and uptime checks).
- `GET /api/storage/status` – existing endpoint covering Mongo/chat cache health for Agent 1.

## Smoke / Integration Tests

Once Qdrant credentials are available, run:

```bash
export QDRANT_URL="https://YOUR-CLUSTER.qdrant.tech"
export QDRANT_API_KEY="..."
pytest tests/vector/test_qdrant_client.py -k integration
```

Unit-only coverage (no live Qdrant) still runs via:

```bash
pytest tests/vector/test_qdrant_client.py -k "not integration"
```

The unit portion of `tests/vector/test_qdrant_client.py` runs without a live cluster,
while the `-k integration` subset performs real inserts/searches and respects the
same env vars outlined above.

