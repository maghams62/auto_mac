# Slash Summary Validation Plan

This note tracks how we exercise the updated `/slack` and `/git` summarizers
now that they incorporate metadata-driven graph context and incident tone.

## 1. Automated Coverage

| Area | Test | What it asserts |
| ---- | ---- | ---------------- |
| `/slack` formatter | `tests/orchestrator/test_slash_slack_llm_formatter.py` | `graph_highlights` captures services, components, APIs, participants, and topic samples derived from the prompt payload. |
| `/git` assistant | `tests/agent/test_slash_git_graph_context.py` | Pipeline graph context aggregates incident labels, file touch counts, and activity stats before hitting the LLM formatter. |

Run all relevant suites after changes:

```bash
pytest tests/orchestrator/test_slash_slack_llm_formatter.py tests/agent/test_slash_git_graph_context.py
```

CI already executes the full test suite, but the above focused command lets us
spot regressions in the new reasoning helpers quickly.

## 2. Manual Validation

1. **Slash Slack incident recap**
   - Start the Cerebros UI and run `/slack what happened in #incidents last 4h`.
   - Expect the summary headline to mention the channel + timeframe + outcome,
     cite the top participants from the metadata highlights, and produce action
     items that reference the implicated services/components.
   - Confirm the response references real Slack snippets/links (no `UNKNOWN`).

2. **Doc drift / graph blending**
   - Run `/slack summarize thread <link>` for a doc-drift thread.
   - Ensure the summary invokes `graph_highlights` by naming the impacted API,
     doc, and owner, and that the `doc_drift` array includes the canonical doc.

3. **Slash Git incident follow-up**
   - Issue `/git what changed in billing-service last 2 days`.
   - Verify the summary opening line reflects the activity counts from the
     graph context, and that the sections explicitly mention the labels
     (`incident`, `docs_followup`) returned by the planner.

4. **Cross-check fallback text**
   - Temporarily filter to an empty time window (e.g., `/git core-api last 1h`)
     and ensure the empty result summary still cites the timeframe + branch.

Document any unexpected tone or missing citations so we can extend the few-shot
library further.

