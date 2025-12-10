# Cerebros Divergence Audit (Dec 7, 2025)

## Sample scenarios pulled from synthetic investigations

- **Option 1 – Core API rollout activity.** The seeded incident highlights Git + Slack chatter around `comp:core-api` and a doc gap in `payments_api.md`.
```1760:1844:data/live/investigations.jsonl
    "question": "Why is core-api so active without complaints?",
    ...
    "evidence": [
      {"source": "git", "title": "Core API rollout cadence"},
      {"source": "slack", "title": "#core-api-releases coordination"},
      {"source": "doc", "title": "Payments API guide"}
    ],
```
- **Option 1 – VAT rollout doc prioritization.** Investigates `docs.payments` and lists specific doc issues/priorities (Payments API, Billing Flows, Notification Playbook, Pricing Page).
```2457:2587:data/live/investigations.jsonl
    "question": "Which docs need to be updated first after the VAT rollout?",
    ...
    "doc_priorities": ["Payments API", "Billing Flows", ...]
```
- **Option 2 – Payments edge schema fallout.** Tracks component chain (`comp:payments-edge → comp:billing-service → comp:docs-portal`) plus dependency impact + Cypher payload.
```2139:2250:data/live/investigations.jsonl
    "summary": "Payments edge schema change broke billing dependencies",
    ...
    "dependency_impact": {"affectedComponents": ["comp:payments-edge", "comp:billing-service", "comp:docs-portal"]}
```
- **Option 2 – Notifications template_version drift.** Should explain which downstream docs/services break when the field changes.
```1600:1694:data/live/investigations.jsonl
    "question": "Service notifications changed template_version. Which downstream services/docs are impacted?"
```

## Baseline `/cerebros` outputs (before fixes)
Runs captured under `data/reports/cerebros_runs/*.json`.

### 1. `Why is core-api so active without complaints?`
- **Observed summary:** repeats VAT doc issues, ignores Slack/Git activity except PR #2041, and claims “no dissatisfaction data” despite seeded Slack thread.
- **Evidence set:** only Git PR + doc issues; no Slack even though investigation store has it.
- **Structured payload:** `dependency_impact` generic; `source_divergence` only covers PR vs doc issue. No doc priorities, root cause stuck at placeholder “SUMMARY”.
- **Issues:**
  - Activity Graph / doc insights never resolved (no `doc_insights`, no doc priorities), so Option 1 narrative skipped.
  - Search stack ignoring seeded Slack/Git evidence and falling back to doc issues.
  - Summary template over-indexes on generic instructions (“Git source outweighs doc issues”) and never cites blast-radius counts from Activity Graph.

### 2. `Which docs need to be updated first after the VAT rollout?`
- **Observed summary:** slightly better ordering of docs but still lumps unrelated medium-severity pages, doesn’t cite blast radius counts or doc priorities, and `information_gaps` claims priority unknown despite data existing.
- **Issues:**
  - `option` misclassified as `cross_system_context` even though this is Option 1 doc prioritization.
  - Same missing doc insights → no structured drift list; `root_cause_explanation` stuck at “SUMMARY”.
  - Summary lacks per-modality rationale (no Slack vs Git vs Doc comparison) and doesn’t reference Activity Graph scoring.

### 3. `What broke after the payments edge schema change?`
- **Expected:** Should describe ledger schema rename, identify impacted downstream services/docs, and expose the Cypher query from the seeded incident.
- **Observed:** Recycled VAT rollout answer referencing PR #2041; no mention of payments-edge, billing-service, or docs portal; `graph_query.context_impacts.row_count=0`.
- **Issues:**
  - Component hint `comp:payments-edge` not resolved anywhere in dependency map, so doc insights/context impacts never load.
  - Evidence retrieval again limited to VAT doc issues, so summary cannot speak to cross-system blast radius.

### 4. `Service notifications changed template_version. Which downstream services/docs are impacted?`
- **Observed:** Summary admits “evidence does not provide sufficient information” and still cites VAT doc issues + PR #2041.
- **Issues:**
  - Query planner never surfaces Notification Playbook drift even though doc issue exists; no Slack/Git references.
  - Dependency impact degenerates to a single doc entry, missing downstream services.

## Key gaps identified
1. **Doc insights + Activity Graph fetch failures:** Calls to `get_component_activity`/`list_doc_issues` silently fail, leaving `doc_insights` empty. Structured reasoning falls back to placeholder text, and Option 1 narrative never runs.
2. **Evidence imbalance:** Multi-source retrieval hits only doc issues + a single PR (likely because GitHub rate limit errors short-circuit Git/Slack retrievers). We need a local fallback (traceability store) to inject the seeded Slack/Git/Doc evidence.
3. **Prompt contract drift:** The `/cerebros` LLM summary repeats template boilerplate even when evidence is thin, and it doesn’t reference blast radius, Activity Graph scores, or dependency walks.
4. **Context context/cross-system metadata missing:** `graph_query.context_impacts` returns empty for payments-edge and notifications, so cross-system answers cannot cite downstream components/docs.

These findings will guide the fixes: add a traceability-backed fallback to enrich evidence + doc insights, harden structured payload generation (Option 1 + Option 2 narratives), and tighten the summary template to require per-modality alignment plus explicit divergence reporting.
