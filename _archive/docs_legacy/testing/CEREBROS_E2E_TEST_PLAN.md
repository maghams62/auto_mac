# Cerebros End-to-End Testing Checklist

> Paste this prompt into Codex (or any QA automation agent) when you want a brutal `/cerebros` verification run. The agent **must not** mark the task complete until **every** scenario below passes.

---

## 0. General requirements

For **every** scenario, the QA agent must:

1. **Run end-to-end** where possible: set up synthetic data → ingest → query → UI (when applicable).
2. **Assert concrete values**, not just HTTP 200s.
3. **Log actual outputs** into fixtures/snapshots, including:
   - `cerebros_answer.answer`
   - `cerebros_answer.option`
   - `cerebros_answer.components`
   - `cerebros_answer.sources[]`
4. Fail loudly if:
   - No nodes are written to Neo4j when they should be.
   - No embeddings are written/retrieved from Qdrant when they should be.
   - Evidence chips or backlinks are missing in the UI.

Helper code, fixtures, Playwright/browser tests, and screenshots are allowed. Do **not** weaken any assertions.

---

## 1. Backend – Option 1 prioritization & weights

### Scenario 1A – Simple weighted prioritization
**Goal:** Prove `activity_signals.weights` affects ordering.

Steps:
1. Load a config with explicit weights:
   ```yaml
   activity_signals:
     weights:
       git: 3
       slack: 2
       issues: 1
       support: 4
   ```
2. Create two synthetic doc issues (same component):
   - Doc A: git activity 10, slack 1, support 0.
   - Doc B: git 1, slack 1, support 5.
3. Pass both through `src/activity_graph/prioritization.py`.

Assertions:
- `PriorityScore(DocB) > PriorityScore(DocA)` because support weight dominates.
- The helper returns a sorted list with Doc B first.
- Log/print both scores for debugging.

### Scenario 1B – `/api/graph/query` Option 1 response
**Goal:** `/api/graph/query` emits the prioritized shape.

Steps:
1. Seed synthetic component `core-api` + multiple doc issues with varied signals.
2. Call `/api/graph/query`:
   ```json
   {
     "query": "Which docs should we update first for the core API?",
     "component": "core-api"
   }
   ```

Assertions:
- Response includes `cerebros_answer`.
- `cerebros_answer.option == "activity_graph"`.
- Components contain `core-api`.
- Sources list includes the highest-priority doc issue (type `doc`).
- Answer text mentions *why* that doc matters (activity/pain/gap cues).
- Log the full `cerebros_answer`.

---

## 2. Backend – Option 2 cross-system context

### Scenario 2A – Cross-repo dependency impact
**Goal:** Validate Option 2 tagging + downstream mapping.

Steps:
1. Seed toy dependency graph: Service A → B → C.
2. Map docs: `doc_a.md` documents Service A, `doc_b.md` documents B.
3. Seed Git change: breaking API PR on Service A.
4. Query `/api/graph/query`:
   ```json
   {
     "query": "Service A changed its API. Which downstream services and docs are impacted?",
     "component": "service-a"
   }
   ```

Assertions:
- `cerebros_answer.option == "cross_system_context"`.
- Components include downstream services (B, C).
- Sources contain:
  - `type: "git"` entry for Service A change.
  - `type: "doc"` entry for downstream docs.
- Answer text calls out impacted services/docs.
- Log full response.

---

## 3. Backend – Multi-modality + config gating

### Scenario 3A – Slack + Git enabled
**Goal:** When both modalities are on, both backlinks appear.

Steps:
1. Config:
   ```yaml
   modalities:
     slack: true
     git: true
     docs: true
     issues: true
   ```
2. Seed:
   - One Slack message about `core-api` with known permalink.
   - One Git PR for `core-api` with known URL.
   - One doc issue.
3. Query `/api/graph/query` (Option 1 style).

Assertions:
- `cerebros_answer.sources` contains:
  - `type: "slack"` entry with the seeded permalink.
  - `type: "git"` entry with the seeded URL.

### Scenario 3B – Slack disabled
**Goal:** Slack sources disappear when disabled.

Steps:
1. Config:
   ```yaml
   modalities:
     slack: false
     git: true
     docs: true
     issues: true
   ```
2. Reuse Scenario 3A data + query.

Assertions:
- No `type: "slack"` entries.
- Git/doc sources remain.

---

## 4. Ingestion → graph → retrieval path

### Scenario 4A – New Slack message flows to `/cerebros`
**Goal:** Validate ingestion → Neo4j/Qdrant → retrieval.

Steps:
1. Point Slack ingestor to stub workspace that returns a unique message, e.g., `"DEMO_CORE_API_ROLLOUT_80_PERCENT"`.
2. Run:
   ```bash
   python scripts/run_activity_ingestion.py --sources slack
   ```
3. Post-ingest:
   - Query Neo4j to confirm a `slack` node with the unique text exists.
   - Query Qdrant (or `search.modalities.slack`) and confirm the chunk is retrievable.
4. Ask `/api/graph/query` or `/cerebros`:
   ```
   "what is the current core API rollout status?"
   ```

Assertions:
- `cerebros_answer.sources` includes a `type: "slack"` entry referencing the ingested message.
- Answer text mentions the 80% detail.

---

## 5. Frontend – UI & animation tests (Playwright)

Use Playwright against a dev server seeded with deterministic data. Save screenshots for each scenario.

### Scenario 5A – Task disambiguation animation
1. Open the chat UI.
2. Submit `/cerebros which docs should we update first for core-api?`

Assertions:
- `data-testid="task-disambiguation-cerebros"` appears immediately after submit.
- A loading string like “Analyzing across Slack, Git, and docs…” is visible.
- After answer arrives, the disambiguation element disappears and a Cerebros bubble renders.

### Scenario 5B – Option badges
1. Run two queries:
   - Option1: `/cerebros which docs should we update first for core-api?`
   - Option2: `/cerebros service A changed its API; which downstream docs are impacted?`

Assertions:
- Option1 answer shows a badge like `data-testid="badge-activity-graph"`.
- Option2 answer shows `data-testid="badge-cross_system_context"`.
- Capture screenshots for both.

### Scenario 5C – Evidence chips & backlinks
1. Ensure Slack & Git enabled (Scenario 3A dataset).
2. Query `/cerebros what’s going on with the core API rollout docs?`

Assertions:
- Under the Cerebros bubble:
  - “Sources from Slack” section with at least one chip linking to Slack permalink.
  - “Sources from Git” section with at least one chip linking to PR/commit URL.
- Validate `href` attributes and grab screenshots.

### Scenario 5D – Doc priority list
1. Seed ≥3 doc issues with different scores.
2. Run an Option1 query.

Assertions:
- `data-testid="doc-priority-list"` is visible.
- Items are sorted descending by score, with severity badges and “Open Doc” links.

---

## 6. Reporting back

After implementing tests:

1. Run:
   ```bash
   pytest tests/test_activity_prioritization.py tests/test_cerebros_graph_reasoner.py
   pytest tests/test_cerebros_end_to_end.py      # or equivalent integration suite
   npx playwright test
   ```
2. Ensure:
   - All tests pass.
   - Screenshots exist for UI scenarios.
3. Update docs (e.g., `docs/cerebros_flow_map.md`) with:
   - Test file list.
   - Commands to run.
   - Coverage summary per scenario.

Only mark the QA effort complete when:
- Each backend scenario has at least one failing-to-passing test.
- Playwright suite covers animation, badges, evidence chips, and doc priorities.
- Logs and screenshots are captured for auditing.

