## Traceability Gap Analysis (Dec 1 2025)

Decisions that just landed:
- Investigations are persisted only when a run executed at least one external tool and produced evidence.
- Canonical evidence IDs live in `config/canonical_ids.yaml`; helpers exist under `src/agent/evidence.py`.
- Neo4j trace graph ships in v1.5 (post-MVP); MVP relies on JSONL + dashboard linking.

Outstanding work implied by those decisions:

### 1. Investigation persistence & storage
- [ ] Implement a `TraceabilityStore` (JSONL path under `data/live/investigations.jsonl`, later Neo4j).
- [ ] Update `api_server.websocket_chat` → capture plan/execution metadata, detect tool usage, and append an Investigation record (id, session, question, answer, component targets, timestamps).
- [ ] Expose `investigationId` + evidence metadata in WS responses so the frontend can render CTAs.

### 2. Evidence normalization pipeline
- [ ] Ensure every tool result (slash Git/Slack/Doc search/impact) emits canonical `evidence_id` + permalink + component/service tags.
- [ ] Teach `MultiSourceReasoner` / `EvidenceCollection` to surface those IDs back to the orchestrator.
- [ ] Map Evidence -> UI-friendly cards (Slack threads, PRs, doc fragments) so MessageBubble can render “Evidence” lists.

### 3. DocIssue + dashboard linking
- [ ] Extend `DocIssueService` payloads with `origin_investigation_id` & `evidence_ids`.
- [ ] Update `/impact/doc-issues` → surface new fields; update dashboard types + cards.
- [ ] Add “View in Cerebros” deep link on issue detail (uses `investigationId`) and “Create DocIssue” button in chat (calls new API).

### 4. UI wiring
- [ ] Extend `useWebSocket.Message` to support `investigationId`, `evidence[]`, CTA metadata.
- [ ] Update `MessageBubble` to render evidence list + buttons (“Open dashboard”, “File doc issue”).
- [ ] Add modal/form to collect doc issue metadata before POSTing to Cerebros API.

### 5. Follow-up (v1.5)
- [ ] Neo4j ingestion job for Investigations/Evidence + graph edges (Investigation ▸ Evidence ▸ DocIssue ▸ Component).
- [ ] Dashboard graph panel linking to investigations when nodes are selected.

## Execution Roadmap (v1)

1. **Backend plumbing (Investigations & store)**
   - Add `TraceabilityStore` (e.g., `src/traceability/store.py`) + config entry pointing to `data/live/investigations.jsonl`.
   - Teach `api_server.websocket_chat` to capture tool usage metadata, persist Investigations, and include `investigationId` + evidence in final messages.
   - Expose read APIs (`GET /traceability/investigations`, `GET /traceability/investigations/{id}`) for dashboard links and audits.

2. **Evidence propagation**
   - Ensure slash Git/Slack executors, doc search, impact flows attach canonical `evidence_id`, `url`, component/service tags in their payloads.
   - Update `MultiSourceReasoner` and other planners to forward evidence arrays into `result_dict` so the websocket path can reuse them without re-querying.

3. **DocIssue & dashboard integration**
   - Extend `DocIssueService` schema + FastAPI serializers to store `origin_investigation_id` and `evidence_ids`.
   - Update `oqoqo-dashboard` API proxy + components to consume the new fields, render evidence badges, and add a “View in Cerebros” CTA (linking via investigation ID).
   - Provide a `POST /traceability/doc-issues` endpoint so Cerebros can file issues directly from an investigation + evidence selection.

4. **Frontend UX**
   - Update `frontend/lib/useWebSocket.ts` message model to include `investigationId`, `evidence[]`, and CTA metadata.
   - Add an `EvidenceList` component in `MessageBubble` with per-source icons + deep links.
   - Implement “Create DocIssue” modal (captures severity/title/owner, posts to backend) and “Open in dashboard graph” button that jumps to the correct component/doc issue.

5. **Testing & rollout**
   - Unit tests: `TraceabilityStore`, evidence helpers, updated DocIssue service.
   - End-to-end script: run `/cerebros` query, verify investigation persisted, evidence renders in UI, doc issue button works, dashboard shows backlink.

