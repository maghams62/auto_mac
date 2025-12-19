# UX IA Plan – Drift Dashboard

## Objectives
1. **Single source of truth** – every major question (status, triage, component health, operator state) has one canonical surface.
2. **Predictable navigation** – left rail groups routes by intent (Status → Systems → Ops) and discourages one-off pages.
3. **Cerebros readiness** – deep links, exports, and graph contracts stay stable so the reasoning agent can treat the dashboard as the visual front-end.

## Proposed structure

| Section | Routes | Description | Key interactions |
| --- | --- | --- | --- |
| **Status & triage** | `/projects/:id`, `/projects/:id/issues` | Combined hero + inbox view. Overview highlights live metrics, inbox handles triage via shared filters. | Manual refresh, filter chips, deep link CTA |
| **Systems & graph** | `/projects/:id/components`, `/components/:componentId`, `/graph`, `/impact` | Component explorer, detail sheets, dependency graph. Graph pulls from provider-agnostic endpoint (Neo4j-ready). | Component selection, graph filters, Ask Cerebros buttons |
| **Operator & config** | `/projects/:id/configuration`, `/projects/:id/activity` | Export, dataset refs, diagnostics, Cerebros Activity feed. Live ingest inspector anchored here instead of overview. | Export JSON, slash command copy, dataset probes |
| **Workspace** | `/projects` | Project switcher & creation flow, lightweight summary cards only. | Create project, jump links |

## Implementation checklist

1. **Route audit** – ensure sidebar order matches the table above and remove any stale nav entries.
2. **Shared filter store** – already in place; enforce usage on hero + inbox + component detail to avoid divergent UX.
3. **Operator CTA** – overview now links to diagnostics instead of embedding counts.
4. **Telemetry** – log nav clicks, manual refresh results, and graph interactions (see `src/lib/logging.ts`) so we know which surfaces get real usage.
5. **Docs** – keep this plan + inventory in `docs/ux/` and update when routes change; reference in onboarding docs for future agents.

## Next steps

- Mock a combined “status + triage” layout for `/projects/:id` so demos flow hero → inbox → issue detail without jumping around.
- Evaluate whether `/activity` (Cerebros feed) belongs alongside configuration or inside “systems” group once ActivityService is GA.
- Share the IA plan with the Cerebros agent so exports, DocIssues, and graph feeds map to the same conceptual sections.


