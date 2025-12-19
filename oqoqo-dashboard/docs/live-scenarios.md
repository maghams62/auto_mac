# Live Scenario Validation Playbook

This guide describes how to exercise the Atlas VAT and Nimbus notifications stories that keep our live DocIssue heuristics honest. Use it whenever you change ingest, mapper logic, or prepare a demo.

## Prerequisites

- `.env` contains valid GitHub + Slack tokens and the repo/channel mappings described in `docs/foundation-validation.md`.
- The dashboard is running locally (`npm run dev`). Live mode must be enabled (status pill should say “Live: OK” after the first refresh).
- You have permission to push lightweight commits to the configured repos and to post in the configured Slack channels.

> Run `npm run check:data` first to confirm required env vars are present and the synthetic dataset URLs are reachable. Add `-- --project project_atlas` or `project_nimbus` to scope the dataset checks.

> Tip: run `npm run validate:live` at any time to see how many live `DocIssue`s exist per project. Pass `-- --project project_atlas` or `project_nimbus` to focus on one scenario.

---

## Scenario A – Atlas VAT Drift

1. **Git activity**
   - Create a commit or PR in one of the Atlas repos (e.g., `atlas-core-api`) that touches VAT-related code or docs (`docs/api`, `payments` handlers, etc.).
   - Push to the branch configured in `.env` (usually `main` or `develop`).

2. **Slack signal**
   - In a monitored channel such as `#atlas-drifts` or `#billing-eng`, start or update a thread describing customers hitting VAT-related API/doc mismatches.
   - Include keywords like “docs wrong”, “VAT”, “payments”, etc. to help the heuristic match the relevant component.

3. **Verify ingest**
   - Wait up to 60 seconds (or trigger a manual refresh when Phase 5 lands) and confirm:
     - `/api/activity` returns HTTP 200 in the dev server logs.
     - The header pill shows `Live: OK • Updated <time>`.
     - `npm run validate:live -- --project project_atlas` lists at least one `live_issue`.

4. **UI checkpoints**
   - `/projects/project_atlas`: new issue appears in the issue list and top divergence alerts mention Git + Slack sources.
   - `/projects/project_atlas/issues/<issueId>`: timeline includes the commit + Slack thread, with coherent timestamps.
   - `/projects/project_atlas/components/<componentId>`: “Open doc drift issues” references the same issue and the component’s graph signals reflect elevated drift/dissatisfaction.

5. **Gate**
   - Do not proceed to the next phase until this entire flow reads correctly without touching schemas.

---

## Scenario B – Nimbus Notifications Drift

Follow the same pattern for Nimbus:

1. Push a change in one of the Nimbus repos referenced in `.env` (e.g., `nimbus-notifications`) that touches runbooks or notification schemas.
2. Start a Slack thread in `#nimbus-core`, `#nimbus-alerting`, or the configured channel complaining about outdated docs/runbooks.
3. Confirm ingest via the status pill and `npm run validate:live -- --project project_nimbus`.
4. Check that the relevant issue surfaces in:
   - `/projects/project_nimbus`
   - `/projects/project_nimbus/issues/<issueId>`
   - `/projects/project_nimbus/components/<componentId>`
5. Gate on clarity and stability just like the Atlas scenario.

---

## Validation Toolkit Summary

| Command | Purpose |
| --- | --- |
| `npm run dev` | Run the dashboard locally on port 3100. |
| `npm run validate:live` | Summarize live doc issues across all projects. |
| `npm run validate:live -- --project <project_id>` | Focus on a single project (e.g., `project_atlas`). |

Always re-run both scenarios after mapper or UI changes touching live issues. If anything looks off, stop and fix before moving to Phase 2.

