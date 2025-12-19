# Cerebros Settings Surface

Cerebros now separates infrastructure configuration (`config.yaml` / env vars) from operator-facing settings stored in `data/settings.json` and editable from the dashboard (`/settings`).

## What lives where?

| Concern | Location | Notes |
| --- | --- | --- |
| Secrets, service URLs, repo wiring defaults | `config.yaml`, env vars | Checked into source control (without secrets) and loaded via `ConfigManager`. |
| Source-of-truth priorities, git branch overrides, automation modes | `data/settings.json` | Loaded via `SettingsManager`; editable through `/api/settings` and the dashboard. |
| Runtime wiring metadata (projects, repos, Slack channels) | Dashboard "Sources & Configuration" page | Read-only snapshot sourced from config + live data. |

## Settings API

- `GET /api/settings` → `{ defaults, overrides, effective }`
- `PATCH /api/settings` → accepts partial overrides; merges into `data/settings.json` with schema validation.

Example payload to override the monitored branch for atlas:

```json
{
  "gitMonitor": {
    "projects": {
      "atlas": [{ "repoId": "oqoqo/atlas", "branch": "develop" }]
    }
  }
}
```

## Dashboard settings page

The dashboard now includes a "System settings" entry in the global nav. The new page lets you:

1. Reorder source-of-truth policies per domain (code vs docs vs API specs) and toggle hint sources such as Slack or tickets.
2. Override default git branches per project/repo without editing YAML.
3. Choose automation behavior (off, suggest only, PR, PR + auto-merge) per domain.
4. Review wired data sources (repos + branches) in a read-only panel for transparency.

Changes are persisted via `/api/settings` and applied live—no restarts required. The raw JSON overrides remain in `data/settings.json` for auditability.
