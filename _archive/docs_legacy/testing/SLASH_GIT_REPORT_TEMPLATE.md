# Slash Git Scenario Report Template

Use this template for every `/git` scenario before tweaking synthetic data or the cross-source flows. Capture the planning verdict, retrieval snapshot, answer quality, and whether the synthetic fixtures matched expectations.

```
**Scenario name:**
(e.g. Component activity – core-api)

**Command run:**
`/git what changed in core-api in the last 7 days?`

**1. Parsed Plan (GitQueryPlan)**
- mode: component_activity
- repo.name: oqoqo-dashboard
- component_id: core-api
- time_window.label: last 7 days
- pr_number / authors / topic: (if any)

👉 Verdict A (Planning):
- ✅ Pass – correct repo + component + time window
- ⚠️ Partial – repo ok, component missing/wrong
- ❌ Fail – mode or targets clearly wrong

**2. Retrieval Snapshot (High-level)**
- commit_count: X
- pr_count: Y
- Example commit titles:
  - `feat(core-api): add pagination to list endpoint`
- Example PRs:
  - `#42 – Add pagination to core API list endpoint`
- Do the touched file paths match the component’s expected paths?

👉 Verdict B (Retrieval):
- ✅ Pass – only relevant commits/PRs returned
- ⚠️ Partial – mixed in some unrelated stuff
- ❌ Fail – mostly wrong repo / wrong area

**3. Final Answer (Summary Quality)**
- 2–5 sentence summary:
  - Does it match the snapshot you saw?
  - Does it hallucinate things not in commits/PRs?
  - Does it mention breaking changes / risks if present?

👉 Verdict C (Answer):
- ✅ Pass – concise, accurate, grounded
- ⚠️ Partial – mostly correct but missing key points
- ❌ Fail – incorrect or obviously hallucinated

**4. Synthetic Data Check**
- Did the returned commits/PRs match the synthetic fixtures you expect?
- Or did it:
  - return nothing?
  - return only real/live data?
  - hit the wrong repo/branch?

👉 Verdict D (Synthetic Alignment):
- ✅ Pass – synthetic data is being used as intended
- ⚠️ Partial – some synthetic hits but missing others
- ❌ Fail – synthetic data not surfaced at all / inconsistent

**5. Notes & Next-Action Hint**
Short free-text:
- “Component resolver failed on `core API` (space vs dash). Need alias.”
- “Time window ignored; commits from months ago included.”
- “Synthetic PR #42 present but not mentioned in summary.”
```

