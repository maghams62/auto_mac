# Slash Git Manual Report – Option 1

## Scenario: Component activity – core-api
**Command run:**
```
/git what changed in core-api in the last 7 days?
```

**1. Parsed Plan (GitQueryPlan)**
- mode: `component_activity`
- repo_id: `core-api`
- component_id: `core.payments`
- time_window.label: `last 7 days (component)`
- filters: none

👉 **Verdict A (Planning):** ✅ Pass – resolver locked onto `core-api` + `core.payments` with the correct default window.

**2. Retrieval Snapshot (High-level)**
- commit_count: 3
- pr_count: 1
- Example commits:
  - `feat!: require vat_code for EU`
  - `docs: refresh onboarding`
- Example PR:
  - `#2041 – Add required vat_code to /v1/payments/create`
- Files align with `src/payments.py`, `openapi/payments.yaml`, etc.

👉 **Verdict B (Retrieval):** ✅ Pass – only payments-related commits/PRs surfaced.

**3. Final Answer (Summary Quality)**
- Summary matched the VAT enforcement storyline.
- Noted the breaking-change PR and called out downstream impacts/docs follow-up.
- No hallucinated repos or files.

👉 **Verdict C (Answer):** ✅ Pass – concise + grounded.

**4. Synthetic Data Check**
- All commits/PRs match `data/synthetic_git/core-api`.
- Breaking change PR #2041 surfaced as expected.

👉 **Verdict D (Synthetic Alignment):** ✅ Pass.

**5. Notes & Next-Action Hint**
- None – baseline scenario behaves as intended.

---

## Scenario: Repo activity – docs-portal
**Command run:**
```
/git what changed in docs-portal this week?
```

**1. Parsed Plan (GitQueryPlan)**
- mode: `repo_activity`
- repo_id: `docs-portal`
- component_id: `None`
- time_window.label: `last 7 days`

👉 **Verdict A:** ✅ Pass – correct repo + default window applied.

**2. Retrieval Snapshot**
- commit_count: 2
- pr_count: 0
- Example commits:
  - `docs: partial VAT update`
  - `docs: backlog notification template updates`
- Files live under `docs/payments_api.md`, `docs/changelog.md`.

👉 **Verdict B:** ✅ Pass – commits restricted to docs portal paths.

**3. Final Answer**
- Summary emphasized doc refresh for VAT/template_version.
- Suggested syncing docs with recent API changes.
- Grounded entirely in snapshot evidence.

👉 **Verdict C:** ✅ Pass.

**4. Synthetic Data Check**
- Matches `data/synthetic_git/docs-portal`.
- No live GitHub noise.

👉 **Verdict D:** ✅ Pass.

**5. Notes**
- Consider surfacing linked DocIssues once activity graph queries are wired.

