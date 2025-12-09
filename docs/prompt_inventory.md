# Prompt & Tooling Inventory Findings

## 1. `prompts/system.md`
- **Mismatch with live surface** – The mission still claims we orchestrate “macOS agents (File, Browser, Presentation, Email, Maps, WhatsApp, Reminders, etc.)” even though the shipped desktop experience is the Spotlight launcher + slash flows. The prompt spends ~150 lines on AppleScript delivery guardrails but never mentions `SlashSlack`, Doc Insights, or `/api/universal-search`, so LangGraph keeps planning Keynote/Pages work that the UI cannot launch.
- **Outdated delivery contracts** – The instructions hard-require `compose_email` for any “send/email” verb. Spotlight currently routes delivery through slash automation, not Mail.app, so agents frequently hallucinate email steps that the backend refuses to execute.
- **Tool bloat** – The system prompt references 60+ agents, including Notes/Reminders/Twitter/WhatsApp, while the active runtime primarily exposes Doc Insights, Slack summaries, Git ingest, and semantic search. This inflates context windows and makes “capability scan” noise.
- **Missing telemetry hooks** – Recent components (`plan telemetry`, `session_id`, `Doc Insights`) never appear in the core reasoning principles, so the model is unaware of the data available via slash providers.

**Proposed direction**
- Rewrite the mission around “Cerebros Launcher + Expanded View orchestrating LangGraph plans, slash automations, Doc Insights, and activity graph data”.
- Split delivery instructions: keep Mail.app guardrails behind an `email_enabled` feature flag, and add new guidance for slash feedback + task chips.
- Inject a scoped tool manifest (Doc Insights, SlashSlack, vector search) per session instead of enumerating every legacy AppleScript tool.

## 2. `prompts/tool_definitions.md`
- **Stale catalog** – The file lists 400+ Mac automation tools (Maps, Calendar AppleScript, WhatsApp UI automation, Keynote exporters). None of the slash providers (Slack, Git, Doc Insights, Activity Graph, `/api/universal-search`) are documented, so planners never call them explicitly.
- **Parameter drift** – Definitions refer to `compose_email.send`, `plan_trip_with_stops`, etc., but the LangGraph runtime no longer exposes those methods. We see plans that call `create_stock_report_and_email` even though the agent module is absent in `src/agent/`.
- **Missing failure notes** – There are no warning flags for flaky tools (`create_keynote`, screenshot automation). Observability docs (e.g., `docs/REPO_STATE_AUDIT.md`) identify failure zones, yet the prompt does not warn planners to prefer slash workflows.

**Proposed direction**
- Auto-generate the prompt from `AgentRegistry` but filter out disabled agents (AppleScript macros) unless the desktop runtime actually loads them.
- Add Doc Insights, Slash Slack, Activity ingestion, and RAG tool descriptions with concrete parameter examples.
- Annotate each tool with stability hints (“returns in ≤3 s”, “requires session_id”) to stop the planner from spamming slow AppleScript calls.

## 3. `prompts/task_decomposition.md`
- **JSON-only contract conflicts with multi-surface UI** – The planner insists on returning a full JSON object with `compose_email` steps even when Spotlight launches simple slash commands. This yields 6-step plans for “/slack summarize #incidents”, causing LangGraph to simulate nonexistent file exports and emails.
- **No awareness of slash providers** – Tool-selection rules spend hundreds of lines on email/report/presentation workflows but never mention `slash_slack`, `slash_git`, `/index`, or Doc Insights. As a result, planning often routes Slack summaries through “Writing Agent → create_detailed_report → create_keynote → compose_email”.
- **Outdated guardrails** – The document enforces `create_keynote` for any report attachment even though `docs/IMPLEMENTATION_STATUS.md` marks Keynote export as “experimental” and the UI has no affordance for attachments.

**Proposed direction**
- Introduce a “Slash / Telemetry path” section that maps `/slack`, `/setup`, `/files`, `/index`, and Doc Insights requests to their FastAPI/WebSocket endpoints instead of Keynote pipelines.
- Allow hybrid output: short plans for deterministic slash tasks (2 steps max) vs. JSON scaffolds for LangGraph deliberation.
- Move presentation/email templates into an optional appendix so they don’t dominate the context window for every task.

## 4. Agent Registry (`src/agent/agent_registry.py`)
- Still advertises Notes/Reminders/Twitter/WhatsApp/Maps agents while the runtime primarily calls Doc Insights, Slash Slack, vector search, and Micro Actions. Planners see the giant hierarchy doc and attempt to route through dormant agents.
- Doc Insights tools exist in the registry but lack prompt coverage; no description explains `resolve_component_id`, `get_component_activity`, etc., so they are never planned.

## 5. Redesign Goals (next iteration)
1. **Scope prompts per runtime** – Detect whether we’re running Spotlight/desktop only and inject a trimmed toolset (slash, Doc Insights, telemetry, vector search). Gate AppleScript-heavy agents behind a `mac_automation` flag.
2. **Surface slash commands & Doc Insights** – Add dedicated prompt sections for `/slack`, `/files`, `/index`, `/cerebros`, `/activity`, vector search, and telemetry so the planner selects the right tools.
3. **Context budget optimization** – Replace the monolithic tool catalog with links (`[see tool sheet]`) or dynamic few-shot examples focusing on RAG, Slack, and Doc Insights.
4. **Telemetry integration** – Teach the model about `plan_state`, `session_id`, and `LanGraph plan telemetry` so it explains step status updates to the UI.
5. **Safety rails per agent** – Document known failure modes (AppleScript, Keynote exports) and prefer slash or Doc Insights fallbacks unless `feature_flag_macos_agents=true`.

These findings roll into `docs/stability_audit.md` and the stabilization backlog.

