# Option 2 – Cross-System Impact

## Overview
Option 2 answers the take-home question “Service A changed—what downstream docs or services are now wrong?” by combining a dependency map, an impact analyzer, and a DocIssue store. Git webhooks, Slack complaints, and the `impact_auto_ingest.py` cron all call `ImpactPipeline`, which maps file paths to components, walks cross-repo dependencies, and emits structured DocIssues. Those DocIssues drive `/impact/doc-issues`, the dashboard’s Impact Alerts pane, and (via Option 1) the Activity Graph’s dissatisfaction score.

## Quickstart (cross-system checkout demo)
1. `python scripts/seed_activity_graph.py --impact-limit 20` seeds the Activity Graph logs plus DocIssues (with `--allow-synthetic`) so the checkout storyline spans Git, Slack, and docs without extra setup.
2. `python scripts/cerebros.py status activity-graph` confirms each modality has fresh data (counts + timestamps) before you run slash commands or tests.
3. `pytest tests/test_cerebros_graph_reasoner.py -k cross_repo_drift` validates that the reasoner produces Git/Slack/Doc sources for the `core-api → billing-service → docs-portal` scenario.
4. `/cerebros summarize cross-system signals for billing checkout` now returns a payload whose `sources` array includes the upstream commit, the downstream Slack thread, and the stale docs page, proving the blast radius is captured end-to-end.

## Seeded cross-system scenario checkpoints
- `data/live/investigations.jsonl` now contains a synthetic payments-edge → billing-service → docs-portal incident whose summary reads “Payments edge schema change broke billing dependencies.” The record carries a populated `dependency_impact` tree and `graph_query.downstreamBlast` Cypher so the dashboard’s Cypher panel and dependency chips render instantly.
- Run `pytest tests/api/test_seed_incidents.py` to confirm at least one incident still satisfies the cross-system criteria (non-empty `dependency_impact.impacts`). This guards against accidentally dropping the blast-radius storyline during fixture edits.

## Dependency map & cross-repo modeling
`configs/dependency_map.yaml` encodes every component, the repo/code paths it owns, the docs tied to each component, and the explicit dependency edges between artifacts and components. A trimmed example:

```yaml
components:
  - id: "comp:payments"
    repo: "service-payments"
    artifacts:
      - id: "code:payments:service"
        path: "services/payments_service.py"
        depends_on:
          - "code:shared:http_client"
          - "code:auth:client"
    docs:
      - id: "doc:payments-guide"
        path: "docs/billing_onboarding.md"
        api_ids:
          - "api:payments:/charge"
          - "api:payments:/refund"
dependencies:
  - from_component: "comp:payments"
    to_component: "comp:auth"
    reason: "Payments service calls auth for token verification"
```

Why it matters:
- **Components/services.** Each component points to its owning service via `repo` and is linked back to service IDs through `DependencyGraphBuilder`. That lets the analyzer escalate from “file touched” → “component changed” → “service owners to notify.”
- **Docs.** Docs carry both repo paths and API references, so the analyzer can traverse from a changed component to every guide or tutorial that documents its APIs, even when those guides live in another repo (`shared-contracts`, `docs-site`, etc.).
- **Dependencies.** Explicit `from_component` and `from_artifact` edges capture runtime contracts (Auth → Payments) and documentation reuse (Docs → FastAPI). This is what enables cross-repo blast-radius reasoning when `repo_mode` is `polyrepo`.

## Impact pipeline flow
1. **Inputs.** GitHub webhooks hit `/impact/git-pr` or `/impact/git-change`. Slack complaints hit `/impact/slack-complaint`. Cron-based coverage uses `scripts/impact_auto_ingest.py`, which tailors per-repo since-cursors and calls `ImpactService.pipeline.process_git_event` for each matching commit/PR.
2. **Analyzer.** `ImpactAnalyzer` (`src/impact/impact_analyzer.py`) groups changed files by component, walks downstream dependency edges up to `impact.default_max_depth`, and collects impacted docs/services/APIs. Confidence scores and impact levels are derived from hop depth plus the evidence attached to each edge.
3. **Persistence.** `DocIssueService` (`src/impact/doc_issues.py`) writes/updates DocIssues in the JSON store configured by `activity_graph.doc_issues_path`. `ImpactGraphWriter` mirrors the same event into Neo4j or a JSONL log (`activity_graph.impact_events_path`).
4. **Outputs.** Every run returns an `ImpactReport` plus a list of DocIssues. Dashboards consume `/impact/doc-issues`, `/health/impact` exposes recent runs, and Activity Graph treats the DocIssues as an additional dissatisfaction feed. Optional notifications (`ImpactNotificationService`) can push Slack or PR comments whenever severity crosses the configured threshold.

Key files: `src/impact/pipeline.py`, `src/impact/impact_analyzer.py`, `src/impact/doc_issues.py`, `scripts/impact_auto_ingest.py`.

## Example scenarios & outputs

### Scenario 1 – FastAPI docs PR
1. `impact_auto_ingest.py` sees GitHub PR `fastapi#14421` touching tutorial files. Paths under `docs/en/docs/` resolve to `comp:docs` (see `dependency_map`).
2. `ImpactAnalyzer` marks `comp:docs` as the changed component and walks dependencies to docs that cite FastAPI tutorials or reuse that content.
3. `/impact/doc-issues?repo_id=fastapi` now returns:
```json
{
  "doc_issues": [
    {
      "id": "impact:doc:fastapi-tutorial:fastapi#PR-14421",
      "doc_id": "doc:fastapi-tutorial",
      "repo_id": "fastapi",
      "component_ids": ["comp:docs"],
      "severity": "high",
      "linked_change": "fastapi#PR-14421",
      "change_context": {
        "identifier": "fastapi#PR-14421",
        "title": "Docs: Update outdated Pydantic v1 example in tutorial to Pydantic v2",
        "url": "https://github.com/fastapi/fastapi/pull/14421",
        "pr_number": 14421
      }
    },
    {
      "id": "impact:doc:fastapi-release-notes:fastapi#PR-14421",
      "doc_id": "doc:fastapi-release-notes",
      "repo_id": "fastapi",
      "component_ids": ["comp:docs"],
      "severity": "high",
      "linked_change": "fastapi#PR-14421",
      "doc_url": "https://fastapi.tiangolo.com/release-notes/"
    }
  ]
}
```
The dashboard renders those cards immediately, and Activity Graph adds 60 open DocIssues to `comp:fastapi-core`, which is why that component dominates the dissatisfaction leaderboard.

### Scenario 2 – Slack complaint spanning multiple repos
1. A Slack thread (`slack:C123PAY:1700000000.00000`) complains about checkout failures. The complaint is normalized into `SlackComplaintContext` mentioning `comp:payments`.
2. `ImpactPipeline.process_slack_complaint` seeds the analyzer with that component and enriches it with recent commits under `service-payments`.
3. `/impact/doc-issues?component_id=comp:payments` surfaces both direct and transitive docs:
```json
{
  "doc_issues": [
    {
      "id": "impact:doc:payments-guide:slack:slack:C123PAY:1700000000.00000",
      "doc_id": "doc:payments-guide",
      "repo_id": "service-payments",
      "component_ids": ["comp:payments"],
      "severity": "high",
      "slack_context": {
        "thread_id": "slack:C123PAY:1700000000.00000",
        "channel": "C123PAY",
        "text": "Checkout failing"
      }
    },
    {
      "id": "impact:doc:mobile-guide:slack:slack:C123PAY:1700000000.00000",
      "doc_id": "doc:mobile-guide",
      "repo_id": "mobile-app",
      "component_ids": ["comp:mobile"],
      "severity": "medium"
    }
  ]
}
```
The same Slack run also produced DocIssues for `doc:payments-api` (service-payments) and shared docs under `shared-contracts`, proving that the dependency graph captured genuine cross-repo blast radius.

## Canonical multi-repo example: `core-api → billing-service → docs-portal`

The synthetic repos under `config/slash_git_targets.yaml` give us a neatly scoped story that touches three independent repos. In `configs/dependency_map.yaml` those repos show up as the `core.payments`, `billing.checkout`, and `docs.payments` components:

```yaml
components:
  - id: "core.payments"        # repo: core-api
    repo: "core-api"
    artifacts:
      - id: "code:core:contracts"
        path: "contracts/payment_v2.json"
  - id: "billing.checkout"     # repo: billing-service
    repo: "billing-service"
    artifacts:
      - id: "code:billing:client"
        path: "src/core_api_client.py"
  - id: "docs.payments"        # repo: docs-portal
    repo: "docs-portal"
    docs:
      - id: "doc:payments-api"
        path: "docs/payments_api.md"

dependencies:
  - from_component: "billing.checkout"
    to_component: "core.payments"
    reason: "Billing service calls the shared payment contracts"
  - from_component: "docs.payments"
    to_component: "billing.checkout"
    reason: "Docs portal documents billing flows"
```

### 1. Simulate a change in `core-api`

Trigger Option 2 manually with a synthetic git change. The request below mirrors a breaking schema change in the upstream contracts repo:

```bash
curl -X POST http://localhost:8000/impact/git-change \
  -H "Content-Type: application/json" \
  -d '{
        "repo": "acme/core-api",
        "title": "payments: require vat_code in contract v2",
        "description": "Update payment schema; billing-service and docs need to mention the new VAT field.",
        "files": [
          {"path": "contracts/payment_v2.json", "change_type": "modified"},
          {"path": "docs/payments.md", "change_type": "modified"}
        ]
      }'
```

### 2. Inspect the DocIssues emitted by ImpactPipeline

Because `billing.checkout` and `docs.payments` depend on `core.payments`, the analyzer fans out to both repos. Hitting `/impact/doc-issues?source=impact-report` after the request above returns (trimmed):

```json
{
  "doc_issues": [
    {
      "id": "impact:doc:billing-onboarding:acme/core-api#manual",
      "doc_id": "doc:billing-onboarding",
      "repo_id": "billing-service",
      "component_ids": ["billing.checkout", "core.payments"],
      "severity": "high",
      "doc_url": "https://github.com/acme/billing-service/blob/main/docs/billing_onboarding.md",
      "change_context": {
        "identifier": "acme/core-api#manual",
        "title": "payments: require vat_code in contract v2"
      }
    },
    {
      "id": "impact:doc:payments-api:acme/core-api#manual",
      "doc_id": "doc:payments-api",
      "repo_id": "docs-portal",
      "component_ids": ["docs.payments", "core.payments"],
      "severity": "medium",
      "doc_url": "https://github.com/acme/docs-portal/blob/main/docs/payments_api.md",
      "doc_update_hint": "Mention vat_code in the request schema"
    }
  ]
}
```

A single upstream change now has clear downstream evidence (service repo + docs repo) and preserves every URL Doc Issue cards need.

### 3. Why this matters

- **Cross-repo blast radius.** `ImpactAnalyzer` walks the dependency graph across repos (`impact.repo_mode=polyrepo`) so the billing-service team is alerted even though the commit landed in `core-api`.
- **Doc coverage.** Docs inherit the same dependency edges. Option 1 can surface dissatisfaction for `docs.payments` as soon as the DocIssue is created—no manual tagging required.
- **Reusability.** This example doubles as a demo script. The same `/impact/git-change` request flows all the way through `/impact/doc-issues`, `/activity-graph/top-dissatisfied`, and the dashboard without bespoke fixtures.

## Monorepo vs polyrepo notes
- `context_resolution.repo_mode` in `config.yaml` is currently `polyrepo`, so dependency edges can jump across repos and Impact Analyzer defaults `include_cross_repo=True`. In this mode, downstream docs/services in other repos show up automatically.
- Switching to `repo_mode: "monorepo"` (or passing `include_cross_repo=false` to the context-resolution APIs) limits traversal to the originating repo boundary. That is useful when each workspace only wants alerts inside its monorepo, or when teams phase Option 2 in gradually.
- Regardless of mode, `impact.default_max_depth`, `impact.include_docs`, and `impact.include_services` stay configurable, so you can dial back noisy recommendations while keeping the DocIssue store consistent for Option 1.

