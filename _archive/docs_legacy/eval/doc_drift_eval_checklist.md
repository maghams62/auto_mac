# Doc Drift Evaluation Checklist

This lightweight checklist helps verify the `DocDriftReasoner` prompt template and
its integrations (/slack + /git) in ~10 minutes.

---

## 1. Environment setup

1. Ensure the synthetic backends are healthy:
   ```bash
   python scripts/check_backends.py
   python scripts/build_vector_index.py --domain all
   python scripts/ingest_synthetic_graph.py
   ```
2. Start Cerebros (backend + UI) so `/slack` and `/git` slash agents can route to
   the doc-drift reasoner.

If any command fails, fix ingestion before validating prompt behavior.

---

## 2. Scripted questions

Run the following queries via the CLI or slash interfaces. For each query, confirm
that the answer:

- Identifies the correct API / service / doc.
- Explains what changed in code vs. symptoms vs. doc gaps.
- Cites Slack/Git/Doc evidence and admits uncertainty when data is thin.

| ID | Query | Expected high-level behavior |
| -- | ----- | ---------------------------- |
| Q1 | `/slack what's going on with payments?` | Focus on `/v1/payments/create`, describe VAT requirement change, cite Slack incidents + git commit 2041 + doc gaps. |
| Q2 | `/git summarize drift around payments` | Same storyline but Git-forward: highlight PR 2041, mention affected docs + services. |
| Q3 | `/slack what's going on with notifications?` | Target `/v1/notifications/send`, explain `template_version` enforcement, cite Slack alerts + PR 142 + doc backlog. |
| Q4 | `/git summarize drift around notifications` | Git-centric recount of template_version drift with impacted docs. |
| Q5 | `/slack what's going on with the billing service docs?` | Generalize wording: still surfaces VAT drift, ties billing-service symptoms to stale docs. |
| Q6 | `/slack what's going on with /v1/totally_made_up_endpoint?` | Admit low evidence, suggest rebuilding indexes rather than hallucinating. |

Tips:

- Q1/Q3 should mention Slack complaint IDs, doc sections, and code changes.
- Q2/Q4 should highlight Git commits / PRs plus doc updates that must follow.
- Q5 validates paraphrased phrasing still maps to `/v1/payments/create`.
- Q6 ensures the model states “no evidence” instead of inventing entities.

---

## 3. Manual checklist

Record outcomes for each query below. Expected evidence column should include the
sources the reasoner actually cited (Slack/Git/Docs).

| ID | Query | Evidence used? (Slack/Git/Docs) | Drift story correct? | Docs mentioned? | Honesty about gaps? | Notes |
| -- | ----- | ------------------------------- | -------------------- | --------------- | ------------------- | ----- |
| Q1 | /slack what's going on with payments? | | ✅ / ⚠ / ❌ | ✅ / ⚠ / ❌ | ✅ / ⚠ / ❌ | |
| Q2 | /git summarize drift around payments | | ✅ / ⚠ / ❌ | ✅ / ⚠ / ❌ | ✅ / ⚠ / ❌ | |
| Q3 | /slack what's going on with notifications? | | ✅ / ⚠ / ❌ | ✅ / ⚠ / ❌ | ✅ / ⚠ / ❌ | |
| Q4 | /git summarize drift around notifications | | ✅ / ⚠ / ❌ | ✅ / ⚠ / ❌ | ✅ / ⚠ / ❌ | |
| Q5 | /slack what's going on with the billing service docs? | | ✅ / ⚠ / ❌ | ✅ / ⚠ / ❌ | ✅ / ⚠ / ❌ | |
| Q6 | /slack what's going on with /v1/totally_made_up_endpoint? | | ✅ / ⚠ / ❌ | ✅ / ⚠ / ❌ | ✅ / ⚠ / ❌ | |

Use the Notes column to capture unexpected behavior, e.g., missing citations or
hallucinated services. Update the prompt or retrieval pipelines if any row is ❌.

