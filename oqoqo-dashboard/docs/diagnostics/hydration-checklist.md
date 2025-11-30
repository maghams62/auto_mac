# Hydration Stability Checklist

Last updated: 2025-03-17

## Quick triage

1. **Disable DOM-mutating extensions** (notably ones that inject `bis_*` attributes). The dashboard now strips these during bootstrap, but verifying extensions helps reproduce user reports.
2. **Verify root layout** is rendered with `suppressHydrationWarning` and the `strip-extension-attrs` script is delivered before interactive JS.
3. **Confirm console logs**:
   - `[ux:hydration.clean]` indicates no suspicious attributes.
   - `[ux:hydration.extension-attrs]` indicates attributes were scrubbed; no user action required if hydration completes.

## Manual test flow

1. `npm run build && npm run start`.
2. Load `/projects` and `/projects/project_atlas/graph` in a clean profile.
3. Ensure the dev console shows *no* "A tree hydrated..." warnings.
4. Toggle navigation links and manual refresh; check `[ux:*]` logs for mode + actions.

## Regression guidance

- New client components must avoid `Date.now()` or other non-deterministic values during render.
- If a component depends on client-only APIs, wrap the dynamic parts in `useEffect` or gate behind `typeof window !== "undefined"`.
- Record discoveries in this file so future contributors know which surfaces were historically brittle.


