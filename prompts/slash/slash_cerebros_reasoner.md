# Slash Cerebros Reasoner Prompt Contract

This asset documents the prompt rules used by the multi-source Cerebros reasoner that powers the `/cerebros` slash flow and downstream incident creation.

## 1. Goals
- Fuse Git, Slack, doc, issue, and graph insights into a single incident-ready narrative.
- Call out divergences between sources (e.g., Slack complaints vs. docs vs. Git) and explain why they disagree.
- Surface the metrics the UI exposes: blast radius, activity score, dissatisfaction score, dependency impact, doc priorities, and structured remediation guidance.
- Provide machine-readable fields (`root_cause_explanation`, `impact_summary`, `resolution_plan`, `activity_signals`, `dissatisfaction_signals`, `dependency_impact`, `source_divergence`, `information_gaps`) so the dashboard and incidents API can render consistent panels.

## 2. Input payload (summarized)
Every prompt includes:
- `QUERY` – verbatim user ask.
- `EVIDENCE` – normalized entries grouped by source with metadata (component IDs, repos, timestamps, etc.).
- Optional sections:
  - `CONFLICTS DETECTED` – pre-parsed contradictions returned by the conflict detector.
  - `INFORMATION GAPS` – explicit missing-data observations.
  - `SOURCE WEIGHTS` – priority order (Git > Docs > Doc issues > Activity graph > Issues > Slack) with scalar weights.
  - `EVIDENCE SUMMARY` – per-source counts to ground severity/blast radius math.

## 3. Required response format
The LLM must emit the headings below verbatim so the UI card can render multi-section text without extra parsing:

```
SUMMARY:
- Two tightly written sentences that answer the query, cite the hot component/doc/service, and reference recency.

SOURCE ALIGNMENT:
- <source>: detail + cite the evidence source_name/entity_id. Include Git/Slack/Docs/Issues when present.

DIVERGENCES:
- <source1> vs <source2>: <reason>. If there are no conflicts, output "- None detected."

IMPACT:
- Blast radius: quantify components/docs/services touched (use graph counts when available).
- Severity: justify using SOURCE WEIGHTS and evidence volume.
- Dissatisfaction: cite Slack complaints, doc severity, or dissatisfaction signals.

NEXT ACTIONS:
1. Owner · Action ordered from highest-weight modality to lowest. Reference specific evidence.
```

## 4. Structured reasoning fields
The summarizer must populate or preserve the following keys so they can be copied into `incident_candidate` snapshots:

| Field | Description |
| --- | --- |
| `root_cause_explanation` | Single sentence root cause derived from the highest-weight evidence. |
| `impact_summary` | Plain-language blast-radius statement (components + docs + services). |
| `resolution_plan` | Ordered list of next steps (max 5) referencing responsible owners. |
| `activity_signals` | Counts of Git events, Slack conversations/complaints, doc issues. |
| `dissatisfaction_signals` | Critical doc issues, complaint counts, ticket counts. |
| `dependency_impact` | Graph slice describing upstream component and dependent docs/services/APIs. |
| `source_divergence` | `{ summary, count, items[] }` derived from the conflict detector. Each item lists `source1`, `source2`, and `description`. |
| `information_gaps` | Array of `{ description, type }` describing missing evidence that blocks a confident answer. |

These keys feed both the Cerebros UI (structured reasoning card) and the incidents dashboard (signals, divergence, and gap panels). Values must be grounded in the evidence or graph payload—no invented scores or owners.

## 5. Blast radius & severity logic
- Use the evidence counts plus dependency metadata to quantify blast radius (`n components`, `m docs`, `k downstream services`).
- Severity messaging must honor the weight hint (e.g., Git weight 1.0 outranks Slack 0.7). If a lower-weight modality contradicts a higher-weight one, call it out in `DIVERGENCES` and explain which source should be trusted.
- Dissatisfaction comments must reference actual complaints, doc issue severity, or calculated dissatisfaction signals.

## 6. Incident alignment checklist
Before completing the response, ensure:
- Every action cites a real owner or team name present in the evidence or graph metadata.
- Slack messages are labeled with channel/thread context; Git evidence references repo + PR/commit.
- Doc links are rewired through `rewrite_github_url` (handled upstream) and mentioned when recommending doc updates.
- Divergence summary highlights the exact modalities that disagree so the UI can justify new incidents during demos.
- Information gaps clearly state what additional node/edge or signal is required (e.g., "Need downstream billing checkout doc to confirm API change").

Following this contract keeps `/cerebros` answers aligned with the dashboard panels and ensures demo data exposes the weighted blast radius, severity, and dissatisfaction story without manual edits.
