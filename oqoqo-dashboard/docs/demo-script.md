# Demo Script – Atlas VAT & Nimbus Notifications

This walkthrough shows how to demo the dashboard using the synthetic Atlas VAT and Nimbus Notification scenarios.

## Prep

1. Start the dashboard: `npm run dev`
2. (Optional) trigger a manual refresh from the project overview once the UI loads.
3. Run the validation helper if you want CLI evidence beforehand:
   - `npm run validate:live -- --project project_atlas`
   - `npm run validate:live -- --project project_nimbus`

### Latest validation snapshot

```
$ npm run validate:live -- --project project_atlas
Live issues: 3 (all medium) for Core, Billing, Portal

$ npm run validate:live -- --project project_nimbus
Live issues: 1 (medium) for Notifications
```

## Demo Flow (Atlas)

1. **Project overview**
   - Show the live drift hero: counts, impacted components, signal totals, severity chips.
   - Fire the manual refresh button to highlight the “snapshot updated” state.
   - Point out the ingest inspector: git/slack/ticket/support counts + warnings when ingest fails.

2. **Live drift inbox (`/projects/:id/issues`)**
   - Use the filters to narrow by severity and component; flip on “Live issues only.”
   - Highlight the per-issue external links (Git/Slack/Tickets) and open an issue page.

3. **Issue detail → component detail**
   - In the issue sheet/page show the signals section and source cards with “Open source” links.
   - Jump to the affected component: note live issue cards, activity metrics, source event links.

4. **Graph view**
   - Switch to `/projects/:id/graph`.
   - Use the component vs issue toggle, severity filters, and explain the legend.
   - Select a node, show the right-hand CTA buttons (Focus, Inspect, Repo link) and related issues.

## Demo Flow (Nimbus variation)

1. Switch to the Nimbus project via the sidebar switcher.
2. Repeat the overview → inbox → issue detail path, focusing on the single notifications issue.
3. In the graph view, toggle to the “Doc issues” filter to show how the issue list changes.

## Notes & Tips

- When live data isn’t available, the UI now calls out “synthetic dataset mode” and explains empty states.
- New live issues trigger a small toast near the manual refresh controls and a temporary highlight on the hero list.
- Graph nodes and issue rows now expose repo and source-system links so you can deep-link into GitHub/Slack during Q&A.

