# Master Agent Integration Guide

This guide is the authoritative reference for any agent (human or automated) that needs to reason about, extend, or integrate with the Mac Automation Assistant codebase. Use it as the single entry point before diving into implementation details.

---

## 1. System Overview

- **Entry point:** `main.py`  
  Bootstraps configuration, session memory, agent registry, LangGraph automation agent, legacy workflow orchestrator, slash command handler, and the Rich-based terminal UI (`src/ui/chat.py`).

- **Core runtime components:**
  | Component | Location | Purpose |
  |-----------|----------|---------|
  | LangGraph Automation Agent | `src/agent/agent.py` | Plans & executes multi-step workflows using registered tools. |
  | Agent Registry | `src/agent/agent_registry.py` | Lazily instantiates specialist agents, maps tool names to the owning agent, and records usage. |
  | Specialist Agents | `src/agent/*.py` | Domain-focused mini-orchestrators (files, browser, presentations, email, maps, Twitter, Bluesky, etc.). Each exposes a list of LangChain tools. |
  | Tool Implementations | `src/automation/`, `src/integrations/` | Deterministic helpers that perform actual OS/API work (e.g., `folder_tools.py`, `bluesky_client.py`). |
  | UI Layer | `src/ui/chat.py`, `src/ui/slash_commands.py` | Handles user interaction, slash commands, and result rendering (including reply payloads). |
  | Session & Memory | `src/memory/` | Persists conversation context so agents can recall prior work. |

- **Prompt assets:** `prompts/` contains system, task decomposition, few-shot, and tool definition prompts consumed by the planning LLM. These files constrain behavior and must stay aligned with implementations.

- **Documentation:**  
  - `docs/architecture/AGENT_ARCHITECTURE.md` – LangGraph-specific architecture and state design.  
  - `docs/architecture/AGENT_HIERARCHY.md` – Catalog of agents and tools.  
  - `docs/features/SLASH_COMMANDS.md` – User-facing command palette.  
  - This guide – master context for coding tasks.

---

## 2. Agent & Tool Hierarchy

The registry exposes one or more agents, each registering tools (LangChain `@tool` functions). Specialists delegate to deterministic helpers so LLM output stays bounded.

| Agent | File | Domain | Key Tools |
|-------|------|--------|-----------|
| FileAgent | `src/agent/file_agent.py` | Document search/extraction | `search_documents`, `extract_section`, `take_screenshot`, `organize_files`, `create_zip_archive` |
| FolderAgent | `src/agent/folder_agent.py` | Folder listing & normalization | `folder_list`, `folder_plan_alpha`, `folder_apply`, `folder_organize_by_type` |
| BrowserAgent | `src/agent/browser_agent.py` | Web search with Playwright | `google_search`, `navigate_to_url`, `extract_page_content`, `take_web_screenshot`, `close_browser` |
| PresentationAgent | `src/agent/presentation_agent.py` | Keynote & Pages creation | `create_keynote`, `create_keynote_with_images`, `create_pages_doc` |
| EmailAgent | `src/agent/email_agent.py` | Mail.app automation | `compose_email` |
| WritingAgent | `src/agent/writing_agent.py` | LLM-assisted content generation | `synthesize_content`, `create_slide_deck_content`, `create_detailed_report`, `create_meeting_notes` |
| MapsAgent | `src/agent/maps_agent.py` | Apple Maps automation | `plan_trip_with_stops`, `open_maps_with_route` |
| TwitterAgent | `src/agent/twitter_agent.py` | Twitter/X summaries & posting | `summarize_list_activity`, `tweet_message` |
| BlueskyAgent | `src/agent/bluesky_agent.py` | Bluesky search, summaries, posting | `search_bluesky_posts`, `summarize_bluesky_posts`, `post_bluesky_update` |
| ReplyAgent | `src/agent/reply_tool.py` | UI-facing message wrapper | `reply_to_user` |
| (Additional agents) | `src/agent/` | Discord, Reddit, Notifications, Finance, etc. | See `docs/architecture/AGENT_HIERARCHY.md` |

**How agents interact:**
1. **Planning** (`src/agent/agent.py`): The LangGraph state machine produces a plan using the prompts under `prompts/`.
2. **Execution:** Each step invokes a tool; the registry routes to the owning agent and the agent calls its helper (`FolderTools`, `BlueskyAPIClient`, etc.).
3. **Verification:** Selected tools (e.g., screenshot capture) trigger `OutputVerifier` checks.
4. **Finalization:** The automation agent is required to call `reply_to_user` as the final step so the UI receives a structured payload.

---

## 3. Tool Usage & Parameter Passing

- **Canonical tool specs:** `prompts/tool_definitions.md` is generated from actual tool schemas. Read it before planning to avoid mismatched parameters.
- **Parameter source of truth:** Each tool defines a pydantic schema via `args_schema` (implicitly by decoration). Use the property keys exactly; missing or extra keys will be rejected.
- **Execution contract:**
  1. **Plan**: Always include a final `reply_to_user` call.
  2. **Dependencies**: Use `$stepN.field` references to feed outputs into later steps.
  3. **Type safety**: Strings vs lists vs bools must match the schema. For writing agent tools, pass strings (e.g., `.message` fields), not objects.
  4. **Error handling**: If a tool returns `{"error": True, ...}` stop or replan. Do not ignore errors silently.
  5. **Reply**: On success (or partial success), ensure a single `reply_to_user` payload is produced so human-readable output reaches the UI.

- **Common helper tips:**
  - Folder & file paths must stay within sandbox directories defined in `config.yaml` → `documents.folders`. Use `FolderTools.check_sandbox` to validate when in doubt.
  - External integrations (Twitter, Bluesky, Discord) read credentials from `.env` variables. Always check for the env var before calling the API; return a descriptive error if missing.
  - Use prompts under `prompts/` to align LLM expectations (e.g., summary format, single-tool rules).

---

## 4. Messaging & Reply Conventions

### Automation Workflows
- Final result **must** include a `reply_to_user` step whose payload looks like:
  ```json
  {
    "type": "reply",
    "message": "Primary user-facing headline",
    "details": "Markdown block with context or bullet list",
    "artifacts": ["paths or URLs to highlight"],
    "status": "success | partial_success | info | error",
    "error": false
  }
  ```
- `main.py` and `src/ui/chat.py` look for this structure to render a clean response. Without it, users see raw JSON.

### Slash Commands
- `src/ui/slash_commands.py` parses `/command task`. Each command is mapped to an agent.
- Many commands now call `reply_to_user` themselves (e.g., `/folder`, `/bluesky`). When adding new slash handlers, return a reply payload so the UI stays consistent.
- For mode-specific commands:
  - `/bluesky search …` → returns posts list panel.
  - `/bluesky summarize …` → Markdown summary + table.
  - `/bluesky post …` → results panel with link.

### Error Messaging
- Prefer explicit errors with actionable suggestions. Example from `folder_plan_alpha`:
  ```json
  {
    "error": true,
    "error_type": "SecurityError",
    "error_message": "Path outside allowed folders: …",
    "retry_possible": false
  }
  ```
- UI displays error panels automatically when `error` is truthy.

---

## 5. Document & Spec References

- **Architecture:** `docs/architecture/AGENT_ARCHITECTURE.md` (LangGraph flow, state shape), `docs/architecture/AGENT_HIERARCHY.md` (agent summaries), `docs/architecture/guides/` (experiment notes).
- **Features:** `docs/features/*.md` (slash commands, Maps improvements, UI updates).
- **Prompt Contract:** `prompts/system.md`, `prompts/task_decomposition.md`, `prompts/few_shot_examples.md`, `prompts/tool_definitions.md`.
- **Automation Helpers:** `src/automation/` (Mail, FolderTools, notifications, etc.).
- **Integrations:** `src/integrations/twitter_client.py`, `src/integrations/bluesky_client.py`, plus API wrappers for other services.
- **Tests:** `tests/` directory contains regression tests for agents and slash commands. Mimic test patterns when adding new capabilities.

---

## 6. Worked Examples (Copy These Patterns)

### Example A – Twitter List Summaries
Files: `src/agent/twitter_agent.py`, `src/integrations/twitter_client.py`
1. Tool `summarize_list_activity` loads config, fetches tweets via `TwitterAPIClient`, enriches data, and calls `ChatOpenAI` for a structured summary.
2. Tool returns a dictionary with summary Markdown and per-tweet metadata (URL, author, score).
3. Slash command `/x` uses `AgentRegistry.execute_tool("summarize_list_activity", …)` and renders Markdown plus a Rich table (`src/ui/chat.py:503`).
4. Tests under `tests/test_twitter_agent.py` stub API responses and assert the output format.

### Example B – Bluesky Integration
Files: `src/agent/bluesky_agent.py`, `src/integrations/bluesky_client.py`, `tests/test_bluesky_agent.py`
1. Client handles authentication and API calls (search, popular, create post).
2. Agent tools wrap the client, normalize data, optionally summarize with `ChatOpenAI`, and enforce a 300-character post limit.
3. Slash command `/bluesky` parses the task (search vs summarize vs post) and returns either a reply payload or mode-specific panel (`src/ui/slash_commands.py:520`).
4. UI recognizes the reply payload and renders consistent status messaging (`src/ui/chat.py:348`).
5. Tests cover each command path (`tests/test_bluesky_agent.py`, `tests/test_bluesky_command.py`).

### Example C – Folder Summaries via Reply Tool
Files: `src/agent/folder_agent.py`, `src/ui/slash_commands.py:947`, `tests/test_folder_slash_reply.py`
1. `folder_list` tool returns raw JSON describing files and folders.
2. Slash handler transforms the raw result into a `reply_to_user` payload containing counts, top file types, and sample items.
3. UI displays a polished message rather than raw JSON.
4. The regression test asserts that `/folder …` routes through the reply tool and that the message conforms to expectations.

Use these patterns when introducing new functionality: wrap deterministic helpers, generate structured results, and surface final messages via `reply_to_user`.

---

## 7. Implementation Checklist for New Features

1. **Understand Requirements**
   - Read relevant prompt files and existing docs.
   - Identify existing agents/tools you can reuse.

2. **Design**
   - Decide whether the feature fits an existing agent or requires a new one.
   - Sketch out tool inputs/outputs and helper functions.
   - Update `prompts/tool_definitions.md` (via tool catalog) if new tools are added.

3. **Build**
   - Implement deterministic helpers under `src/automation/` or `src/integrations/`.
   - Create or update agent tools (`src/agent/*.py`) to wrap helpers.
   - Register tools in `src/agent/agent_registry.py` and exports in `src/agent/__init__.py`.
   - Update configuration defaults (`config.yaml`) and validation (`src/config_validator.py`) as needed.

4. **Messaging**
   - Ensure workflows call `reply_to_user` in the final step.
   - For slash commands, either map directly to `reply_to_user` or join raw results with a reply before rendering.

5. **Documentation**
   - Add or update docs in `docs/` describing the new capability.
   - Reference this master guide where appropriate.

6. **Testing**
   - Add unit/regression tests under `tests/` that stub external dependencies.
   - Verify slash commands, tool outputs, and reply payloads.
   - Run `pytest` to confirm all suites pass.

7. **Validation**
   - Manually exercise slash commands or natural language prompts via `main.py`.
   - Confirm UI renders the reply correctly and artifacts are accessible.

By following this guide, new agents or features will integrate cleanly with the existing architecture, respect configuration and sandbox constraints, and provide consistent user-facing responses. Keep this document up to date whenever significant architectural changes land.

---

## 8. Vision-Assisted UI Fallback (NEW)

Some macOS apps surface unpredictable dialogs where scripted AppleScript flows stall. To keep the default path lightweight while still handling edge cases:

- **Feasibility checker** – Added to the LangGraph execution step. It tracks per-tool attempts, recent errors, and configured budgets. Only when the heuristic confidence exceeds `vision.min_confidence` (and retry thresholds) does it escalate.
- **Vision pipeline** – On escalation, the ScreenAgent captures a fresh screenshot; `analyze_ui_screenshot` (VisionAgent) prompts a multimodal LLM that returns structured JSON summarising the UI state and recommending next actions.
- **State tracking** – `AgentState` now carries `tool_attempts`, `recent_errors`, and `vision_usage` (per-task + per-session counts). Session memory persists `vision_session_count` so rate limits survive across runs.
- **Configuration** – All knobs live under `config.yaml → vision` (enable flag, confidence threshold, session/task quotas, eligible tool allowlist). Leave `enabled` false to disable the path entirely.
- **Cost control** – Logs record every escalation reason and confidence; cached insights can be layered on later by keying off screenshot/signature.

Result: deterministic AppleScript flows remain the default, while complex UI scenarios (WhatsApp notifications, Apple Maps permission prompts, etc.) can automatically escalate to a vision-powered analysis only when needed.
