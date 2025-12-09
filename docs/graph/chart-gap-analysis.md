# Graph Dashboard Metrics Coverage

## Current UI ↔ Backend Mapping

- **KPI Row** – Consumes `docDriftIndex`, `docDriftChange`, `openDocIssues`, `criticalDocIssues`, `redZoneComponents`, plus provider metadata from the snapshot response.
- **Risk Quadrant Scatter** – Uses `metrics.riskQuadrant` (`changeVelocity`, `driftScore`, `blastRadius` per component).
- **Top Risks Bar Chart** – Uses `metrics.topRisks` along with `riskScore`, `supportPressure`, and `blastRadius`.
- **Signal Mix Pie** – Uses `metrics.sourceMix` aggregated by `git`, `slack`, `tickets`, and `support`.
- **Issue Cadence Area Chart** – Uses `metrics.issueTimeline` buckets built in `_query_issue_timeline`.
- **Component Detail Drawer** – Reads `snapshot.components[*]` payload fields (`driftScore`, `activityScore`, `changeVelocity`, `issues`, `signals`, `dominantSignal`, etc.).

## Observed Gaps

1. **Doc Freshness KPIs** – The frontend renders doc coverage states but lacks doc freshness deltas per component. `GraphDashboardService` already returns `docFreshnessDays`; aggregating averages/percentiles would unlock “Docs overdue (>7 days)” KPIs.
2. **Dependency Volatility** – Visuals emphasize change velocity but do not expose dependency hotspots (e.g., components with high incoming edges *and* high drift). The backend already computes `blastRadius`; exposing a `dependencyVolatility` array (sorted by `blastRadius × driftScore`) would enable a small table or stacked bar.
3. **SLA / Ticket Pressure** – The UI hints at SLA compliance in copy, yet there is no explicit metric for “components breaching SLA.” `GraphDashboardService._build_metrics_payload` sets `sla.overdue` and `sla.onTrack`; surfacing those in KPI row (or a donut) would close the gap.
4. **Support Queue Trend** – No chart shows support pressure over time. Persisting the `support_weight` signal per day (similar to `issueTimeline`) would enable a dual-axis “Support pressure vs Doc issues” chart.

## Recommended Backend Additions

- Extend `_build_metrics_payload` to emit:
  - `docFreshness`: `{ avgDays, overdueComponents, healthyComponents }`
  - `dependencyVolatility`: top 5 `{ componentId, componentName, volatilityScore }` using `changeVelocity * blastRadius`
  - `slaTrend`: simple timeline derived from `issueTimeline` buckets (opened vs resolved) to reuse on the frontend.
- Update `LiveGraphSnapshot` / `GraphMetrics` types (and Vitest contract tests) once new fields land so the dashboard can bind new KPIs/charts without fallback providers breaking.

These additions keep the UI aligned with FastAPI outputs while giving designers room to add the “doc freshness gap,” “dependency volatility,” and SLA widgets called out in the execution plan.

