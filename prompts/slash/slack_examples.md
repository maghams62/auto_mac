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

---

## Example 3 – Incident recap with graph highlights

**Tool data**

```json
{
  "context": {
    "mode": "channel_recap",
    "channel_label": "#incidents",
    "time_window_label": "in the last 4 hours"
  },
  "graph_highlights": {
    "services": ["checkout-service", "core-api-service"],
    "components": ["billing.checkout", "core.payments"],
    "apis": ["/v1/payments/create"],
    "labels": ["incident", "pager"],
    "top_participants": [
      {"user": "siddharth.suresh", "messages": 4},
      {"user": "eleni", "messages": 3}
    ]
  },
  "messages": [
    {
      "ts": "1732665600.000010",
      "user_name": "siddharth.suresh",
      "text": "Pager triggered: EU checkout returns 500s after vat_code rollout. Tracking as INC-428.",
      "permalink": "https://.../p1732665600",
      "service_ids": ["core-api-service"],
      "component_ids": ["core.payments"],
      "related_apis": ["/v1/payments/create"],
      "labels": ["incident", "sev2"]
    },
    {
      "ts": "1732665755.000040",
      "user_name": "eleni",
      "text": "Graph edges show billing.checkout owns most failing calls; handing over to checkout on-call.",
      "permalink": "https://.../p1732665755",
      "service_ids": ["checkout-service"],
      "component_ids": ["billing.checkout"],
      "labels": ["handoff"]
    },
    {
      "ts": "1732666020.000077",
      "user_name": "marco",
      "text": "Fix: revert to commit 4e0651 on core-api/main. Need follow-up task to re-add vat_code safely.",
      "permalink": "https://.../p1732666020",
      "service_ids": ["core-api-service"],
      "component_ids": ["core.payments"],
      "labels": ["rollback", "followup"]
    }
  ]
}
```

**Expected JSON**

```json
{
  "summary": "#incidents (last 4h) coordinated the INC-428 checkout outage: pager fired on /v1/payments/create, checkout picked up mitigation, and core-api rolled back while logging follow-ups.",
  "sections": {
    "topics": [
      {
        "title": "Impact",
        "insight": "EU checkout hit sustained 500s once vat_code enforcement shipped; alerts tied to core.payments.",
        "evidence_id": "evt-incident-1"
      },
      {
        "title": "Handoff",
        "insight": "Graph context shows billing.checkout owns most failing edges, so checkout on-call owns coordination.",
        "evidence_id": "evt-incident-2"
      }
    ],
    "decisions": [
      {
        "text": "Rollback to commit 4e0651 on core-api/main until safer vat_code patch is ready.",
        "participants": ["marco", "siddharth.suresh"],
        "timestamp": "1732666020.000077",
        "permalink": "https://.../p1732666020",
        "services": ["core-api-service"],
        "components": ["core.payments"]
      }
    ],
    "tasks": [
      {
        "description": "Checkout team to craft forward-fix that keeps vat_code while preventing 500s.",
        "assignees": ["checkout on-call"],
        "timestamp": "1732665755.000040",
        "permalink": "https://.../p1732665755"
      },
      {
        "description": "Core-api to reintroduce vat_code behind a feature flag post-rollback.",
        "assignees": ["marco"],
        "timestamp": "1732666020.000077",
        "permalink": "https://.../p1732666020"
      }
    ],
    "references": [
      {
        "title": "INC-428",
        "url": "https://pager/INC-428",
        "kind": "other",
        "timestamp": "1732665600.000010"
      }
    ]
  },
  "entities": [
    {
      "name": "/v1/payments/create",
      "type": "api",
      "services": ["core-api-service", "checkout-service"],
      "components": ["core.payments", "billing.checkout"],
      "labels": ["incident"],
      "evidence_ids": ["evt-incident-1", "evt-incident-2"]
    }
  ],
  "evidence": [
    {
      "id": "evt-incident-1",
      "channel": "#incidents",
      "ts": "1732665600.000010",
      "permalink": "https://.../p1732665600",
      "text": "Pager triggered: EU checkout returns 500s after vat_code rollout...",
      "services": ["core-api-service"],
      "components": ["core.payments"],
      "apis": ["/v1/payments/create"],
      "labels": ["incident", "sev2"]
    },
    {
      "id": "evt-incident-2",
      "channel": "#incidents",
      "ts": "1732665755.000040",
      "permalink": "https://.../p1732665755",
      "text": "Graph edges show billing.checkout owns most failing calls...",
      "services": ["checkout-service"],
      "components": ["billing.checkout"],
      "labels": ["handoff"]
    }
  ]
}
```

---

## Example 4 – Thread recap tying Slack + doc follow-ups

**Tool data**

```json
{
  "context": {
    "mode": "thread_recap",
    "channel_label": "#docs",
    "time_window_label": "in the last 24 hours",
    "thread_ts": "1732670000.000111"
  },
  "graph_highlights": {
    "services": ["docs-portal", "notifications-service"],
    "components": ["docs.notifications", "notifications.dispatch"],
    "labels": ["doc_drift"],
    "apis": ["/v1/notifications/send"],
    "top_participants": [
      {"user": "eve", "messages": 3},
      {"user": "dave", "messages": 2}
    ]
  },
  "messages": [
    {
      "ts": "1732670000.000111",
      "user_name": "eve",
      "text": "Doc drift alert: notification_playbook.md still lacks template_version guidance even though git PR #142 shipped.",
      "permalink": "https://.../p1732670000",
      "service_ids": ["docs-portal"],
      "component_ids": ["docs.notifications"],
      "labels": ["doc_drift"]
    },
    {
      "ts": "1732670120.000118",
      "user_name": "dave",
      "text": "PR #142 is merged; please mirror the template_version contract today.",
      "permalink": "https://.../p1732670120",
      "service_ids": ["notifications-service"],
      "component_ids": ["notifications.dispatch"],
      "labels": ["api_contract"]
    },
    {
      "ts": "1732670400.000150",
      "user_name": "eve",
      "text": "I'll update notification_playbook.md + changelog; ETA 5pm.",
      "permalink": "https://.../p1732670400",
      "service_ids": ["docs-portal"],
      "component_ids": ["docs.notifications"],
      "labels": ["followup"]
    }
  ]
}
```

**Expected JSON (abbreviated)**

```json
{
  "summary": "Thread 1732670000 in #docs resolved a doc-drift alert: eve agreed to refresh notification_playbook.md so it matches PR #142 on /v1/notifications/send before 5 pm.",
  "sections": {
    "topics": [
      {
        "title": "Doc drift",
        "insight": "Graph ties this drift to notifications.dispatch + docs.notifications; docs must describe template_version immediately.",
        "evidence_id": "evt-doc-1"
      }
    ],
    "tasks": [
      {
        "description": "Update notification_playbook.md and changelog with template_version steps.",
        "assignees": ["eve"],
        "due": "today 17:00",
        "timestamp": "1732670400.000150",
        "permalink": "https://.../p1732670400"
      }
    ],
    "references": [
      {
        "title": "PR #142 Require template_version",
        "url": "https://github.com/acme/notifications-service/pull/142",
        "kind": "github",
        "timestamp": "1732670120.000118"
      }
    ]
  },
  "doc_drift": [
    {
      "doc": "docs/notification_playbook.md",
      "issue": "Missing template_version instructions even though notifications-service now requires it.",
      "services": ["docs-portal", "notifications-service"],
      "components": ["docs.notifications", "notifications.dispatch"],
      "apis": ["/v1/notifications/send"],
      "permalink": "https://.../p1732670000"
    }
  ]
}
```

These additional scenarios show how `graph_highlights` anchors the recap tone:
mention the active channel/timeframe, state the incident or drift outcome,
summarize handoffs, and finish with explicit owners + deadlines.

