# Cross-System Context & Impact Engine (Option 2)

This document explains how the cross-system impact service is wired, how to call
it over HTTP/webhooks, and how to interpret the returned `ImpactReport`.

---

## 1. System Overview

1. **Dependency ingestion** – `DependencyGraphBuilder` loads every file listed in
   `context_resolution.dependency_files` and normalizes Components, Services,
   APIs, Docs, Repositories, and CodeArtifacts. The builder is idempotent and can
   either keep the data in memory or upsert it into Neo4j through
   `GraphIngestor`.
2. **Impact analysis** – `ImpactAnalyzer` maps Git file changes (or seeded
   component IDs) to Components/APIs, traverses downstream dependencies up to
   `impact.default_max_depth`, and outputs structured blast-radius summaries.
3. **Evidence generation** – `EvidenceGraphFormatter` converts the structured
   report into deterministic reasoning bullets (optionally polished by an LLM
   if `context_resolution.impact.evidence.llm_enabled` is true).
4. **Pipelines** – `ImpactPipeline` wires it together for Git webhooks
   (`process_git_event`) and Slack complaints (`process_slack_complaint`),
   persisting signals back into the graph and surfacing recommendations.
5. **Persistence** – Every `ImpactReport` upserts DocIssues (stored at
   `activity_graph.doc_issues_path`) via `DocIssueService` and emits
   `ImpactEvent` nodes via `ImpactGraphWriter`. When Neo4j is disabled the writer
   falls back to appending JSONL entries under
   `activity_graph.impact_events_path`.

### 1.1 Toy Org Structure

| Service | What it owns | Why it matters |
|---------|--------------|----------------|
| `service-auth` | `comp:auth`, `/auth/login`, `/auth/validate` | Upstream source of truth for auth tokens and schemas. |
| `service-payments` | `comp:payments`, docs under `docs/payments` | Calls Auth, embeds `/auth/validate` excerpts, exposes payouts APIs. |
| `service-notifications` | `comp:notifications`, runbooks in `docs/notifications` | Uses Auth tokens to send receipts and relies on `/auth/validate`. |
| `shared-contracts` | `comp:docs`, canonical OpenAPI + guides | Publishes shared contracts reused by both downstream services. |

This toy org models just enough cross-repo coupling to demonstrate Option 2 end-to-end without colliding with the Step 3 work that is persisting DocIssues + ImpactEvents.

### 1.2 Investigation cadence

Traceability hinges on storing the “question → tools → evidence → answer” loop without drowning in low-signal chats. We persist an Investigation only when:

1. The run executed at least one external tool (slash Git/Slack, doc search, impact analyzer, auto-ingest, multi-source reasoner, etc.), guaranteeing we have structured evidence to cite.
2. Evidence outputs were returned to the user (reply payload, slash summary, or completion card). Pure acknowledgements or small-talk replies skip persistence.

The automation agent already knows if any tool ran during a step. The WebSocket layer can therefore check `step_results` for tool executions before appending to the shared investigation log. This keeps the store focused on actionable, traceable answers while letting conversational follow-ups flow freely.

---

## 2. Cross-Repo Topology

The dependency map models a small org with explicit cross-repo links:

| Repo | Components | Notes |
|------|------------|-------|
| `service-auth` | `comp:auth`, APIs `/auth/login`, `/auth/validate` | Source of truth for tokens. |
| `service-payments` | `comp:payments` | Calls Auth and ships docs that embed `/auth/validate`. |
| `service-notifications` | `comp:notifications` | Validates tokens before sending receipts. |
| `shared-contracts` | `comp:docs` | Publishes the canonical contract docs (auth schema, billing flows). |

### Upstream → downstream mapping

- `SERVICE_CALLS_API` edges capture runtime calls (e.g., payments invoking `/auth/validate`) so the graph knows which upstream API a downstream service depends on.
- `COMPONENT_USES_COMPONENT` edges describe service-to-service relationships, enabling transitive reasoning, e.g., auth → payments → shared-contracts.
- `DOC_DOCUMENTS_API` edges map individual doc files to the APIs they reference, letting the analyzer jump from code change → doc debt.

Docs declare their owning repo/path and `api_ids`, so `DOC_DOCUMENTS_API` edges connect `service-payments` and `service-notifications` docs to the upstream auth APIs. Component dependencies capture service-to-service calls, letting ImpactReports trace “Service A changed → Services B/C docs out of date.”

---

## 3. Public API Surface

All endpoints live on the FastAPI server (`api_server.py`).

### Flow A – Git PR → `/impact/git-pr`

1. GitHub webhook (or CLI) hits `/impact/git-pr` with `{repo, pr_number}`.
2. `ImpactService` uses `GitIntegration` to fetch the PR metadata + diff.
3. `ImpactPipeline.process_git_event` calls `ImpactAnalyzer`, which walks dependency edges up to `impact.default_max_depth`.
4. The returned `ImpactReport` describes changed vs. impacted entities, confidence, evidence, and recommendations. Dashboards + notifications just render this payload.
5. After every run the pipeline writes DocIssues to `activity_graph.doc_issues_path` and exposes them through `GET /impact/doc-issues`, which is exactly what the ImpactAlertsPanel consumes (e.g., `/impact/doc-issues?source=impact-report&repo_id=service-payments` for the Auth PR demo).

### Flow B – Slack complaint → `/impact/slack-complaint`

1. A Slack message is normalized into `SlackComplaintInput` (channel, text, seeds).
2. `ImpactService` infers component/api IDs from the complaint text and optionally hydrates recent commits.
3. `ImpactPipeline.process_slack_complaint` reuses the same analyzer path, augmenting the `ImpactReport` with Slack thread metadata + “respond in-channel” recommendations.
4. The report feeds DocIssues, dashboards, and (optionally) notification stubs so responders see the same evidence used for Git events.
5. Slack runs store the thread metadata (`channel`, `thread_id`, `api_ids`) inside each DocIssue, so `/impact/doc-issues` immediately gives dashboards a clickable Slack deep link next to every impacted doc/service.

### Dashboard View

`ImpactAlertsPanel` simply calls `/impact/doc-issues`, so every DocIssue emitted by an `ImpactReport` renders as an alert with severity, timestamps, and the actionable links QA reviewers need. Each card bundles three deep links: the source GitHub PR (or auto-opened issue), the originating Slack thread, and the impacted documentation path, keeping the investigation inside a single UI. See the real-run snapshots for the [Auth PR dashboard](docs/testing/reports/CROSS_SYSTEM_OPTION2_REAL_RUNS.md#impact-alertspanel-auth-pr) and the [Slack complaint dashboard](docs/testing/reports/CROSS_SYSTEM_OPTION2_REAL_RUNS.md#impact-alertspanel-slack-complaint) to show how the pipeline output maps 1:1 onto the panel.

### `POST /impact/git-pr`

```
{
  "repo": "acme/service-auth",
  "pr_number": 123
}
```

- Resolves the PR via `GitHubPRService`, builds a `GitChangePayload`, and
  returns the full `ImpactReport` JSON.
- Fails with `400` (bad request) for missing fields and `502` for GitHub API
  failures.

### `POST /impact/git-change`

```
{
  "repo": "acme/service-auth",
  "commits": ["9f3c2a1", "72d1b80"]
}
```

or provide `files` directly:

```
{
  "repo": "service-auth",
  "files": [
    {"path": "src/auth.py", "change_type": "modified"}
  ],
  "title": "Manual change",
  "description": "docs update"
}
```

- Aggregates the supplied commits/files, runs the analyzer, and returns the
  `ImpactReport`.

### `POST /impact/slack-complaint`

```
{
  "channel": "#payments-alerts",
  "message": "Checkout failures because auth response lost session_id",
  "timestamp": "1700000000.0101",
  "context": {
    "component_ids": ["comp:payments"],
    "repo": "acme/service-payments",
    "commit_shas": ["7ac22d1"]
  }
}
```

- Heuristically maps complaint text to components/APIs, optionally fetches
  recent commits, and returns an `ImpactReport` suitable for a Slack reply or
  ticket.

### `GET /impact/doc-issues`

```
GET /impact/doc-issues?component_id=comp:auth&source=impact-report
```

- Lists the persisted DocIssues generated by impact analysis (the same payload
  stored at `activity_graph.doc_issues_path`).
- Optional filters: `source`, `component_id`, `service_id`, and `repo_id`,
  enabling dashboards to focus on a specific service or dependency chain.

---

## 4. Webhook & Automation Hooks

`src/impact/webhooks.py` exposes `ImpactWebhookHandlers`, which translate
incoming webhooks into analyzer calls.

- **GitHub pull_request/push** – `handle_github_event` parses payloads, kicks off
  `/impact/git-pr` or `/impact/git-change`, and logs when a report is produced.
- **Slack complaint events** – `handle_slack_complaint` accepts pre-parsed Slack
  analyzer output (channel/text/context) and returns an `ImpactReport` dict.

`/webhooks/github` now calls both the legacy PR notifier and the impact handler,
so every PR push automatically triggers analysis.

---

## 5. Slack Complaint Flow

1. Normalize complaint attributes into `SlackComplaintInput`.
2. Use dependency metadata & aliases to infer component/API IDs when the message
   references “payments”, `/v1/payments/refund`, etc.
3. Optionally fetch recent commits (if `repo` and `commit_shas` are provided or
   if the component metadata includes an owner/repo pair).
4. Seed the analyzer with the inferred component IDs so that even empty file
   lists yield deterministic reports.

End users can provide additional hints in `context.api_ids`, `context.repo`, or
`context.commit_shas` to improve accuracy.

---

## 6. ImpactReport Schema

`ImpactReport` is stable, documented, and returned by every API:

- `change_id`, `change_title`, `change_summary`
- `impact_level` – `"low" | "medium" | "high"` (derived from highest-confidence
  entity)
- `changed_components`, `changed_apis`, `impacted_components`,
  `impacted_services`, `impacted_docs`, `impacted_apis`, `slack_threads`
- `recommendations` – each entry has `description`, `reason`, and `confidence`
- `evidence` – list of deterministic statements
- `evidence_summary` + `evidence_mode` – short text for Slack/PR comments

`changed_*` fields describe the blast epicenter (files/components you touched) while `impacted_*` lists downstream services/docs uncovered via graph traversal. Evidence entries cite exactly which edge(s) fired so you can understand why a doc showed up.

### Canonical Example

```
{
  "change_id": "acme/core-api#PR-123",
  "change_title": "Tighten auth token issuer",
  "impact_level": "high",
  "changed_components": [
    {
      "id": "comp:auth",
      "type": "component",
      "confidence": 0.95,
      "impact_level": "high",
      "reason": "2 file(s) mapped to comp:auth"
    }
  ],
  "changed_apis": [
    {
      "id": "api:auth:/login",
      "type": "api",
      "confidence": 0.9,
      "impact_level": "high",
      "reason": "API owned by changed component"
    }
  ],
  "impacted_components": [
    {
      "id": "comp:payments",
      "type": "component",
      "confidence": 0.7,
      "impact_level": "medium",
      "reason": "Depends on comp:auth at depth 1"
    }
  ],
  "impacted_docs": [
    {
      "id": "doc:payments-guide",
      "type": "doc",
      "confidence": 0.75,
      "impact_level": "medium",
      "reason": "Documents impacted dependency comp:payments"
    }
  ],
  "recommendations": [
    {
      "description": "Review and refresh doc:payments-guide",
      "reason": "Documents impacted dependency comp:payments",
      "confidence": 0.75
    }
  ],
  "evidence_summary": "comp:auth changed (2 file(s) mapped to comp:auth) comp:payments impacted via dependency depth 1 Additional context: Documentation doc:payments-guide references impacted component comp:payments",
  "evidence_mode": "deterministic"
}
```

---

## 7. Example Scenario & Workflows

> **Auth removes `session_id` → billing + notifications docs need updates**

1. PR #321 in `service-auth` updates `/auth/validate`. The dependency graph maps
   that path to `comp:auth`.
2. `comp:payments`, `comp:notifications`, and `comp:docs` all depend on the same
   API, so their docs (`doc:payments-api`, `doc:notifications-playbook`,
   `doc:shared-auth-contract`) appear with medium/high confidence.
3. Services `svc:payments` and `svc:notifications` receive impact entries so
   on-call teams know to regression test.
4. The Slack flow reuses the same analyzer, so a complaint in
   `#payments-alerts` pointing at `comp:payments` links back to the upstream
   auth change.
5. As soon as the ImpactReport is produced, DocIssues are upserted (state
   `open`, severity derived from `impact_level`) and an `ImpactEvent` node is
   written to Neo4j with edges to the docs/services/slack thread.

### Running the Pipelines Manually

Populate the graph:

```
python3 -m src.graph.dependency_graph
```

Git change:

```python
from src.graph.dependency_graph import DependencyGraphBuilder
from src.impact import ImpactAnalyzer, GitChangePayload, GitFileChange

graph = DependencyGraphBuilder(config).build(write_to_graph=False)
analyzer = ImpactAnalyzer(graph)
payload = GitChangePayload(
    identifier="PR-123",
    title="Tighten auth token issuer",
    repo="service-auth",
    files=[GitFileChange(path="clients/auth_client.py")]
)
report = analyzer.analyze_git_change(payload)
```

Slack complaint:

```python
from src.impact import ImpactPipeline, SlackComplaintContext

pipeline = ImpactPipeline()
slack_ctx = SlackComplaintContext(
    thread_id="slack:C123:1700000000.0001",
    channel="#payments-alerts",
    component_ids=["comp:payments"],
    text="Checkout still failing because auth response lost session_id"
)
report = pipeline.process_slack_complaint(slack_ctx)
```

### Doc issues & graph artifacts

`ImpactPipeline` calls two sinks after every report:

1. `DocIssueService` → appends to `activity_graph.doc_issues_path`, so Activity Graph
   and the dashboard immediately show new drift issues sourced from impact analysis.
2. `ImpactGraphWriter` → calls `GraphIngestor.upsert_impact_event` when Neo4j is
   enabled or logs JSONL entries to `activity_graph.impact_events_path` otherwise.
   Either way, Option 1 (activity graph) and Option 2 (impact service) now share
   the same evidence stream.

### Optional Notifications

Teams that want a human-in-the-loop ping can turn on the optional notification layer:

- `ImpactPipeline` gathers the DocIssues returned by `DocIssueService.create_from_impact`
  and hands them to `ImpactNotificationService`.
- The service computes the highest `impact_level` across the batch and exits unless it
  meets `context_resolution.impact.notifications.min_impact_level`.
- When enabled, it sends:
  - a Slack message to `context_resolution.impact.notifications.slack_channel`
    summarizing the impact level, impacted services/components/docs, and deep links
    (PR, Slack thread, doc URLs) when present.
  - an optional PR comment (when a PR number is known) with a one‑sentence summary
    pointing reviewers back to the DocIssues dashboard.

Notifications are disabled by default and fully controlled via config:

```yaml
context_resolution:
  impact:
    notifications:
      enabled: false          # opt-in per environment
      slack_channel: "#docs-impact"
      min_impact_level: "high"
```

If `enabled` remains `false`, the pipeline continues to persist DocIssues/ImpactEvents
silently—no network calls or side-effects occur. Ops teams can safely opt in later
once they have a real Slack webhook or GitHub App wiring.

---

## 8. Why Option 2 solves cross-repo doc drift

- **Single reasoning engine** – Git, commit, and Slack inputs all converge on `ImpactAnalyzer`, so DocIssues, dashboards, and notifications stay in sync.
- **Graph-native blast radius** – Traversing `SERVICE_CALLS_API`, `COMPONENT_USES_COMPONENT`, and `DOC_DOCUMENTS_API` edges yields deterministic recommendations with human-readable reasons.
- **LLM-optional** – Deterministic evidence is the default; enabling the LLM formatter only polishes wording.
- **Polyrepo aware** – Each repo owns its metadata, but ingestion merges everything into one graph, so teams can add services incrementally without central coordination.

---

## 9. Monorepo vs. polyrepo tradeoffs

| Aspect | Monorepo | Polyrepo (current demo) |
|--------|----------|-------------------------|
| Ingestion | One checkout, easier globbing | Need per-repo metadata + canonical IDs |
| Ownership | CODEOWNERS/paths can imply ownership | Must record repo/component mappings explicitly |
| CI & deploys | Unified pipelines but heavier | Lightweight per team but harder to coordinate |
| Drift detection | Grep-able but noisy | Requires automation (Option 2) to align teams |

Option 2 leans polyrepo-first, yet works for monorepos as long as you provide `dependency_files` for each domain. The graph normalizes everything, so downstream tooling does not care how repos are structured.

---

## 10. Transitive dependencies & depth controls

- `impact.default_max_depth` governs how many hops the analyzer walks (auth → payments → docs).
- Depth 1 keeps alerts tightly scoped to direct consumers; depth 2–3 exposes doc portals or partner teams that sit behind another service.
- Evidence strings always encode the depth (“Depends on comp:auth at depth 1”), making it easy to explain why a doc appeared.

---

## 11. Evidence Modes

- **Deterministic (default)** – `EvidenceGraphFormatter` builds structured bullet
  points and a short summary without external calls.
- **LLM-enhanced** – enable `context_resolution.impact.evidence.llm_enabled`
  and provide `llm_client`; the formatter prompts the LLM to rewrite the bullet
  list into 2‑4 human sentences. Failures automatically fall back to the
  deterministic summary, and responses include `evidence_mode = "llm"` so
  downstream systems know which path ran.

---

## 12. Real-World Dry Runs

See `docs/testing/reports/CROSS_SYSTEM_OPTION2_REAL_RUNS.md` for two annotated
scenarios (PR-driven change and Slack complaint). Each example lists:

- Input payload (PR or Slack)
- Returned ImpactReport JSON
- Commentary on accuracy, false positives, and doc/service follow-ups

Use this doc as the “portfolio proof” when demoing Option 2.

---

## 13. Scalability Notes

- **Caching** – `DependencyGraphBuilder` keeps a normalized in-memory graph so
  analyzers can run without round-trips to Neo4j. Share a singleton builder in
  long-lived workers.
- **Extensibility** – new repositories can provide incremental YAML in separate
  files; the builder merges them in order.
- **Safety rails** – impact depth and recommendation limits are configurable via
  `context_resolution.impact.*` to keep response payloads bounded.

---

## 14. Future Extensions

### Other nice-to-haves

- **LLM reasoning** – hook richer reasoners into
  `EvidenceGraphFormatter` (config already wires in model + toggle).
- **Embeddings** – add doc/endpoint embeddings to correlate free-form Slack
  text with APIs even when component IDs are missing.
- **Per-org graphs** – make `dependency_files` multi-tenant by pointing to
  customer-specific configs and storing repo ownership metadata per org.

