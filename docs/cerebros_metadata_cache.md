# Cerebros Metadata Cache

Cerebros fetches Slack and GitHub metadata on demand for slash-command UX and
autocomplete. The metadata services wrap the live APIs with lightweight,
TTL-bound caches so the UI feels responsive without drifting away from the real
source of truth.

## What We Cache

| Source | Payload | TTL (default) | Notes |
| ------ | ------- | ------------- | ----- |
| Slack  | Channel list (public + permitted private) | 600 seconds | Includes channel IDs, names, privacy flags, and member counts. |
| Slack  | User directory | 600 seconds | Captures IDs, handles, real names, and display names for mention autocomplete. |
| GitHub | Repo metadata | 900 seconds | Normalized `owner/repo`, descriptions, default branches, and topics for each configured repo. |
| GitHub | Branch listings | 300 seconds | Per-repo branch inventories (name, protection flag, default marker). |

The TTL values and size caps live under `metadata_cache` in `config.yaml` and
can be tuned per workspace or via env overrides. Each cache exposes hit/miss
stats for diagnostics endpoints.

### Recommended TTLs & Trade-offs

| Cache | Suggested Range | Notes |
| ----- | ---------------- | ----- |
| Slack channels/users | 5–10 minutes | Shorter TTLs keep private channel membership fresh but increase Slack API usage. |
| Git repos | 10–15 minutes | Repository metadata (default branch, description) rarely changes; prioritize rate-limit safety. |
| Git branches | 3–10 minutes | Feature branches churn more frequently; use the lower end during heavy release activity. |

Too-small TTLs risk Slack/GitHub throttling; too-large values mean autocomplete
may briefly show stale branch/channel lists. Pick the highest TTL that still
feels “live” for your team’s cadence.

## Invalidation

* **Automatic** – Entries expire after the configured TTL. The next lookup will
  transparently refetch from Slack/GitHub.
* **Manual** – Restarting the backend clears all in-memory caches. Individual
  services also provide `refresh_*` helpers that can be wired to admin endpoints
  if needed.

## Source of Truth

Slack and GitHub remain the authoritative data sources. The cache only softens
latency for autocomplete and planner contexts. Slash commands always send real
queries to Slack/GitHub for messages, commits, PRs, etc., so operators never
risk acting on stale metadata.

## Observability & Troubleshooting

* Set `metadata_cache.slack.log_metrics` or `metadata_cache.git.log_metrics` to
  `true` to emit `[METADATA] ... cache hits=...` log lines whenever caches are
  accessed. This is useful when validating hit rates or investigating token
  issues.
* Call the diagnostic helpers (e.g., `SlackMetadataService.describe()`,
  `GitMetadataService.describe()`) via your admin shell or debug endpoint to
  inspect cache sizes, TTLs, and fingerprints.
* If autocomplete returns outdated results, try `refresh_channels(force=True)`
  / `refresh_branches(force=True)` or simply restart the backend to clear the
  in-memory maps.
* For persistent failures (e.g., tokens revoked), enable metrics logging, watch
  for repeated `misses`, and verify the underlying Slack/Git credentials.


