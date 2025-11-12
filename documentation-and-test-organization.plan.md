## Prompt Library Enrichment & Validation Plan

### Goals
- Deepen per-agent few-shot coverage so planners reliably select the right tools, parameters, and delivery steps.
- Improve task disambiguation (e.g., report vs. slideshow, summarize vs. compress).
- Capture failure patterns so the planner can proactively refuse unsupported requests.
- Align documentation and tests with the richer prompt hierarchy.

### Tasks
1. **Expand Agent Example Sets**
   - Add 3–5 new examples for each high-traffic agent (file, folder, email, presentation, stock).
   - Cover short/long inputs, optional parameters, attachments, and delivery verbs.
   - Register the new markdown snippets in `prompts/examples/index.json`.

2. **Delivery & Attachment Patterns**
   - Create cross-domain examples illustrating `[work step(s)] → compose_email (with $stepN attachments/body) → reply_to_user`.
   - Include positive and corrective (bad→good) cases so the planner learns the contract without code hacks.

3. **Task Disambiguation Mini-Catalog**
   - Add a shared “disambiguation” category showing how to decide between similar intents (e.g., summarize vs. zip, report vs. slideshow).
   - Include reasoning snippets so the LLM knows when to clarify vs. choose a branch.

4. **Report Flow Parity**
   - Write a stock-report example that mirrors the slide deck flow but uses the Pages-based PDF tool.
   - Show the full chain: fetch data → synthesize sections → create Pages PDF → compose_email with attachment → reply_to_user.

5. **Rejection & Safety Examples**
   - Add explicit “impossible / refuse” few-shots covering missing capabilities, sandbox violations, and unsupported file types.
   - Ensure the planner learns to return structured errors instead of attempting unsafe actions.

6. **Documentation & Testing**
   - Update docs (prompt README, agent guides) with the new categories and usage guidelines.
   - Add regression tests or fixtures that assert the planner references the enriched examples (e.g., snapshot planned steps for representative requests).

### Deliverables
- New markdown examples under `prompts/examples/**`.
- Updated `prompts/examples/index.json`.
- Documentation updates (prompt README, relevant agent docs).
- Tests verifying plan correctness for key flows (slides, reports, disambiguations).
