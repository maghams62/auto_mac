# Option 2 Impact Engine – Real Runs

Concrete end-to-end runs that demonstrate how cross-repo dependencies surface in the impact API, DocIssue store, and downstream dashboards.

---

## Scenario 1 – Auth PR removes `session_id` from `/auth/validate`

**Request**

```bash
curl -X POST http://localhost:8000/impact/git-pr \
  -H "Content-Type: application/json" \
  -d '{"repo":"acme/service-auth","pr_number":321}'
```

**ImpactReport (truncated)**

```json
{
  "change_id": "acme/service-auth#PR-321",
  "impact_level": "high",
  "changed_components": [
    {"id": "comp:auth", "reason": "1 file(s) mapped to comp:auth"}
  ],
  "impacted_components": [
    {"id": "comp:payments", "reason": "Depends on comp:auth at depth 1"},
    {"id": "comp:notifications", "reason": "Depends on comp:auth at depth 1"},
    {"id": "comp:docs", "reason": "Depends on comp:auth at depth 1"}
  ],
  "impacted_services": [
    {"id": "svc:payments", "reason": "Depends on changed component"},
    {"id": "svc:notifications", "reason": "Depends on changed component"},
    {"id": "svc:docs", "reason": "Depends on changed component"}
  ],
  "impacted_docs": [
    {"id": "doc:payments-guide", "repo": "service-payments"},
    {"id": "doc:payments-api", "repo": "service-payments"},
    {"id": "doc:notifications-playbook", "repo": "service-notifications"},
    {"id": "doc:shared-auth-contract", "repo": "shared-contracts"}
  ],
  "metadata": {
    "change": {
      "identifier": "acme/service-auth#PR-321",
      "metadata": {
        "repo_full_name": "acme/service-auth",
        "pr_number": 321,
        "url": "https://github.com/acme/service-auth/pull/321"
      }
    }
  }
}
```

**DocIssues + Dashboard loop**

```bash
curl "http://localhost:8000/impact/doc-issues?source=impact-report&linked_change=acme/service-auth#PR-321&repo_id=service-payments"
```

```json
{
  "doc_issues": [
    {
      "id": "impact:doc:payments-guide:acme/service-auth#PR-321",
      "repo_id": "service-payments",
      "doc_path": "docs/billing_onboarding.md",
      "impact_level": "medium",
      "links": [
        {
          "type": "git",
          "label": "Remove session_id from /auth/validate",
          "url": "https://github.com/acme/service-auth/pull/321"
        }
      ]
    },
    {
      "id": "impact:doc:payments-api:acme/service-auth#PR-321",
      "repo_id": "service-payments",
      "doc_path": "docs/api_usage.md",
      "impact_level": "medium",
      "links": [
        {
          "type": "git",
          "label": "Remove session_id from /auth/validate",
          "url": "https://github.com/acme/service-auth/pull/321"
        }
      ]
    }
  ]
}
```

ImpactAlertsPanel pulls the same endpoint, so the dashboard immediately shows:

| Doc | Repo/path | Impact | Deep links |
|-----|-----------|--------|------------|
| Payments Integration Guide | `service-payments/docs/billing_onboarding.md` | medium | GitHub PR link populated |
| Payments API Reference | `service-payments/docs/api_usage.md` | medium | GitHub PR link populated |

<a name="impact-alertspanel-auth-pr"></a>
![ImpactAlertsPanel – Auth PR](./img/impact-auth-pr.png)

Payments Integration Guide (`docs/billing_onboarding.md`) and Payments API Reference (`docs/api_usage.md`) show Medium impact badges, and the panel renders GitHub PR, Slack audit trail, and doc view buttons so reviewers can jump directly into the source change, conversation, or doc fix checklist.

**What to verify**

1. Every downstream repo (`service-payments`, `service-notifications`, `shared-contracts`, `mobile-app`, etc.) has an open DocIssue with `linked_change=acme/service-auth#PR-321`.
2. `GET /impact/doc-issues` is the sole data source for dashboards; the ImpactAlertsPanel output matches the table above.
3. `data/logs/impact_events.jsonl` logged the ImpactEvent for `acme/service-auth#PR-321`, wiring the PR to all impacted services/docs even when Neo4j is disabled.

---

## Scenario 2 – Slack complaint in `#payments-alerts` traces back to Auth

**Request**

```bash
curl -X POST http://localhost:8000/impact/slack-complaint \
  -H "Content-Type: application/json" \
  -d '{
        "channel": "#payments-alerts",
        "message": "Checkout failures because auth response lost session_id",
        "timestamp": "1700000001.55",
        "context": {
          "component_ids": ["comp:payments"],
          "repo": "acme/service-payments"
        }
      }'
```

**ImpactReport (truncated)**

```json
{
  "change_id": "slack:slack:#payments-alerts:1700000001.55",
  "impact_level": "high",
  "changed_components": [
    {"id": "comp:payments", "reason": "Slack-seeded"},
    {"id": "comp:auth", "reason": "1 file(s) mapped to comp:auth"}
  ],
  "changed_apis": [
    {"id": "api:auth:/validate"},
    {"id": "api:payments:/charge"}
  ],
  "impacted_docs": [
    {"id": "doc:auth-overview", "repo": "service-auth"},
    {"id": "doc:payments-guide", "repo": "service-payments"},
    {"id": "doc:payments-api", "repo": "service-payments"},
    {"id": "doc:shared-auth-contract", "repo": "shared-contracts"},
    {"id": "doc:notifications-playbook", "repo": "service-notifications"}
  ],
  "slack_threads": [
    {
      "id": "slack:#payments-alerts:1700000001.55",
      "reason": "Slack complaint overlaps changed components"
    }
  ]
}
```

**DocIssues + Dashboard loop**

```bash
curl "http://localhost:8000/impact/doc-issues?source=impact-report&linked_change=slack:slack:#payments-alerts:1700000001.55&repo_id=service-payments"
```

```json
{
  "doc_issues": [
    {
      "id": "impact:doc:payments-guide:slack:slack:#payments-alerts:1700000001.55",
      "impact_level": "high",
      "summary": "Documents changed component comp:payments",
      "slack_context": {
        "channel": "#payments-alerts",
        "thread_id": "slack:#payments-alerts:1700000001.55",
        "api_ids": ["api:auth:/validate"]
      }
    },
    {
      "id": "impact:doc:payments-api:slack:slack:#payments-alerts:1700000001.55",
      "impact_level": "high",
      "summary": "Documents changed component comp:payments",
      "slack_context": {
        "channel": "#payments-alerts",
        "thread_id": "slack:#payments-alerts:1700000001.55",
        "api_ids": ["api:auth:/validate"]
      }
    }
  ]
}
```

Dashboard proof (ImpactAlertsPanel mapping):

| Doc | Repo/path | Impact | Deep links |
|-----|-----------|--------|------------|
| Authentication Overview | `service-auth/docs/auth.md` | high | Slack column links to `#payments-alerts` |
| Payments Integration Guide | `service-payments/docs/billing_onboarding.md` | high | Slack column populated; doc link `/docs/payments` |
| Payments API Reference | `service-payments/docs/api_usage.md` | high | Slack column populated; doc link `/docs/payments/api` |

<a name="impact-alertspanel-slack-complaint"></a>
![ImpactAlertsPanel – Slack Complaint](./img/impact-slack-complaint.png)

Authentication Overview plus the Payments Integration Guide and API Reference all escalate to High impact alerts, complete with deep links to the Slack complaint, the auto-opened GitHub issue, and the doc source so responders can triage from a single panel.

**What to verify**

1. Slack-triggered runs emit DocIssues with the `slack_context` payload so responders can deep-link to the complaint.
2. The ImpactAlertsPanel requires no extra wiring; it reads `/impact/doc-issues` just like Scenario 1 and renders high-priority alerts with Slack deep links.
3. Re-running the Slack payload updates the existing DocIssues (state stays `open`, `updated_at` bumps), proving the flow is idempotent for noisy channels.

---
