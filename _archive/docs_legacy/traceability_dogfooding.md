# Traceability Dogfooding Workflow

Goal: validate the end-to-end experience for “ask → evidence → doc issue → dashboard → revisit” before broad rollout.

## Participants

* PM / Engineer (driver)
* Observer (captures friction)

## Script

1. **Ask Cerebros**
   * Use `/slack` or `/git` against a real component.
   * Confirm the assistant response shows “Why this answer?”, evidence chips, and “Create doc issue”.
2. **Review evidence**
   * Expand “Why this answer?” and verify the tool runs and evidence links match expectations.
   * Click a Slack/Git evidence link to ensure canonical permalinks work.
3. **File a DocIssue**
   * Launch “Create doc issue”, ensure evidence + component IDs are pre-selected.
   * Submit; verify toast + DocIssue persists (hit `/projects/<id>/issues` or `GET /impact/doc-issues`).
4. **Inspect dashboard**
   * Open `/projects/<id>/investigations` and confirm the run appears with filters.
   * Navigate to the affected component and confirm “Recent investigations” lists the new run.
5. **Graph trace**
   * From the component detail panel, open “Show trace” and confirm the investigation → evidence → DocIssue overlay renders.
6. **Revisit run**
   * Use “Open run” or Cerebros chat search to jump back to the original investigation.

## Feedback capture

Use a shared doc or Notion page to record:

* Where CTAs were unclear.
* Evidence/tool mismatches.
* Dashboard gaps (missing filters, confusing copy).
* Performance pain (slow API, SSE disconnects).

Prioritize fixes before GA.

