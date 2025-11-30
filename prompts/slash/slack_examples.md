# `/slack` Few-Shot Examples

Use these condensed examples to understand how tool outputs should be turned
into structured summaries. Each example shows (1) the tool data you receive
and (2) the JSON you must emit.

---

## Example 1 – Channel recap with doc-drift alerts

**Tool data**

```json
{
  "context": {
    "mode": "channel_recap",
    "channel_label": "#docs",
    "time_window_label": "in the last 1 day"
  },
  "messages": [
    {
      "ts": "1732611000.000300",
      "text": "Docs alert: docs/payments_api.md still shows POST /v1/payments/create without vat_code...",
      "user_name": "eve",
      "permalink": "https://.../p1732611000",
      "service_ids": ["docs-portal", "core-api-service"],
      "component_ids": ["docs.payments", "core.payments"],
      "related_apis": ["/v1/payments/create"],
      "labels": ["doc_drift"]
    },
    {
      "ts": "1732611120.000301",
      "text": "Please document the rule... reference core-api PR 2041",
      "user_name": "alice",
      "permalink": "https://.../p1732611120",
      "labels": ["doc_drift", "api_change"],
      "related_apis": ["/v1/payments/create"]
    }
  ]
}
```

**Expected JSON**

```json
{
  "summary": "#docs focused on doc drift for /v1/payments/create and aligning docs with PR 2041.",
  "sections": {
    "topics": [
      {
        "title": "Doc drift: vat_code missing from payments docs",
        "insight": "Docs and onboarding guides still lack vat_code examples; eve and alice queued fixes.",
        "evidence_id": "evt-1"
      }
    ],
    "decisions": [
      {
        "text": "Document vat_code requirement referencing core-api PR 2041.",
        "participants": ["alice"],
        "timestamp": "1732611120.000301",
        "permalink": "https://.../p1732611120",
        "services": ["core-api-service"],
        "components": ["core.payments"],
        "apis": ["/v1/payments/create"]
      }
    ],
    "tasks": [
      {
        "description": "Eve to push docs-portal update plus billing-guide PRs.",
        "assignees": ["eve"],
        "timestamp": "1732611000.000300",
        "permalink": "https://.../p1732611000"
      }
    ],
    "references": [
      {
        "title": "core-api PR 2041",
        "url": "https://github.com/acme/core-api/pull/2041",
        "kind": "github",
        "timestamp": "1732611120.000301"
      }
    ]
  },
  "entities": [
    {
      "name": "docs/payments_api.md",
      "type": "doc",
      "services": ["docs-portal"],
      "components": ["docs.payments"],
      "apis": ["/v1/payments/create"],
      "labels": ["doc_drift"],
      "evidence_ids": ["evt-1"]
    }
  ],
  "doc_drift": [
    {
      "doc": "docs/payments_api.md",
      "issue": "Examples omit vat_code required for EU payments",
      "services": ["docs-portal", "core-api-service"],
      "components": ["docs.payments", "core.payments"],
      "apis": ["/v1/payments/create"],
      "labels": ["doc_drift"],
      "permalink": "https://.../p1732611000"
    }
  ],
  "evidence": [
    {
      "id": "evt-1",
      "channel": "#docs",
      "ts": "1732611000.000300",
      "permalink": "https://.../p1732611000",
      "text": "Docs alert: docs/payments_api.md still shows POST /v1/payments/create...",
      "services": ["docs-portal", "core-api-service"],
      "components": ["docs.payments", "core.payments"],
      "apis": ["/v1/payments/create"],
      "labels": ["doc_drift"]
    }
  ]
}
```

## Example 2 – Decision extraction in #billing-dev

**Tool data**

```json
{
  "context": {
    "mode": "decision",
    "channel_label": "#billing-dev",
    "time_window_label": "in the last 7 days"
  },
  "messages": [
    {
      "ts": "1732603200.000200",
      "text": "We decided to adopt option B for billing_service going forward.",
      "user_name": "alice",
      "permalink": "https://.../p1732603200",
      "service_ids": ["billing-service"],
      "component_ids": ["billing.checkout"],
      "labels": ["architecture"]
    },
    {
      "ts": "1732603560.000204",
      "text": "I'll add vat_code to the core-api client. Hotfix branch `bob/vat-code` is in review.",
      "user_name": "bob",
      "permalink": "https://.../p1732603560",
      "service_ids": ["core-api-service"],
      "component_ids": ["core.payments"],
      "labels": ["bugfix"]
    }
  ]
}
```

**Expected JSON (abbreviated)**

```json
{
  "summary": "#billing-dev finalized option B for billing_service and queued a vat_code hotfix.",
  "sections": {
    "decisions": [
      {
        "text": "Adopt option B for billing_service.",
        "participants": ["alice"],
        "timestamp": "1732603200.000200",
        "permalink": "https://.../p1732603200",
        "services": ["billing-service"],
        "components": ["billing.checkout"]
      }
    ],
    "tasks": [
      {
        "description": "Ship hotfix branch `bob/vat-code` adding vat_code to core-api client.",
        "assignees": ["bob"],
        "timestamp": "1732603560.000204",
        "permalink": "https://.../p1732603560"
      }
    ]
  },
  "entities": [
    {
      "name": "billing_service",
      "type": "service",
      "services": ["billing-service"],
      "components": ["billing.checkout"],
      "labels": ["architecture"],
      "evidence_ids": []
    }
  ],
  "evidence": [
    {
      "id": "evt-2",
      "channel": "#billing-dev",
      "ts": "1732603200.000200",
      "permalink": "https://.../p1732603200",
      "text": "We decided to adopt option B for billing_service...",
      "services": ["billing-service"],
      "components": ["billing.checkout"],
      "labels": ["architecture"]
    }
  ]
}
```

These examples are illustrative—mirror the structure, cite only the
information that came from tools, and adapt the summary + sections to match
the user’s actual `/slack` request.

