# AppleScript / Mac MCP Implementation Tasks (For Claude)

This document turns the AppleScript MCP integration plan into **concrete coding tasks** for you (Claude) to implement in this repo.

Focus on:
- Stability and error-handling of existing Mac automation
- Implementing missing high-value Mac capabilities from the MCP plan
- Improving generality/config‑driven behavior

**Out of scope for now:** adding/modifying tests or test data. You may run tests to sanity‑check, but **do not add new test files** unless explicitly requested elsewhere.

When in doubt, **preserve the existing architecture and patterns**—multi‑agent orchestration, automation modules in `src/automation/`, agents in `src/agent/`, and tool wiring via `AgentRegistry` and `slash_commands`.

---

## 0. General Implementation Guidelines

Please follow these throughout:

- Keep changes focused on the tasks below; avoid drive‑by refactors.
- Reuse existing helpers/utilities when possible (especially for AppleScript).
- Maintain existing error contract:
  - On success: `{"success": True, ...}` (or an equivalent success shape already used by that agent)
  - On failure: `{"error": True, "error_type": "...", "error_message": "...", "retry_possible": bool}`
- Prefer small, composable helpers inside automation modules over large monolithic functions.
- Do **not** introduce new external dependencies unless strictly necessary.

File paths in this document are **relative to repo root**.

---

## 1. Standardize AppleScript Execution & Error Handling

### 1.1 Use shared AppleScript helpers everywhere

There is already a shared AppleScript utility module:
- `src/utils/applescript_utils.py`

**Goal:** All AppleScript execution should go through this utility (or be refactored to do so) instead of ad‑hoc `subprocess.run(["osascript", ...])` calls.

**Tasks:**
- Inspect `src/utils/applescript_utils.py` and identify:
  - The public helper(s) for running AppleScript (`run_applescript`, etc.).
  - How errors and timeouts are reported (`format_applescript_error`, etc.).
- For the following modules, replace direct `subprocess.run(... "osascript" ...)` usage with calls to the shared helper:
  - `src/automation/calendar_automation.py`
  - `src/agent/imessage_agent.py` (function `_send_imessage_applescript`)
  - `src/automation/discord_controller.py`
  - Any other obvious AppleScript automation modules that still use raw `subprocess.run`, such as:
    - `src/automation/reminders_automation.py`
    - `src/automation/maps_automation.py`
    - `src/automation/notes_automation.py`
    - `src/automation/stocks_app_automation.py`
    - `src/automation/weather_automation.py`
    - etc., if they exist and still bypass the shared helper.

**Acceptance criteria:**
- Each of the above modules calls into `applescript_utils` instead of spawning `osascript` directly.
- Timeouts and stderr/stdout handling are consistent with `applescript_utils` behavior.
- Logging remains at least as informative as before (do not remove useful logs).

---

### 1.2 Fix Calendar event creation error handling

File:
- `src/automation/calendar_automation.py`

Focus on:
- `create_event(...)`
- `_build_create_event_applescript(...)`
- `_run_applescript(...)` (if not already delegated to `applescript_utils`)

**Tasks:**
- Remove any incorrect assumptions about `stderr` types. For example, if `result.stderr` is already a string, do **not** call `.decode(...)` on it.
- Ensure `create_event(...)` always returns a **consistent dict**:
  - On success:
    ```python
    {
        "success": True,
        "event": {
            "title": ...,
            "start_time": ...,
            "end_time": ...,
            "location": ...,
            "notes": ...,
            "attendees": [...],
            "calendar_name": ...,
        },
    }
    ```
  - On failure:
    ```python
    {
        "success": False,
        "error": True,
        "error_type": "CalendarCreationError",
        "error_message": "<clear human‑readable message>",
        "event_attempted": {
            "title": ...,
            "start_time": ...,
            "end_time": ...,
        },
    }
    ```
- Use `applescript_utils.format_applescript_error(...)` (or equivalent) to derive `error_message` when AppleScript fails.

**Acceptance criteria:**
- No `.decode(...)` misuse on `stderr`/`stdout`.
- `create_event(...)` never raises a secondary exception when AppleScript fails; it returns a structured error dict instead.
- Callers (e.g., `src/agent/calendar_agent.py`) can rely on the `success`/`error` keys without having to guess the shape.

---

### 1.3 Enforce a consistent AppleScript pattern

For **all AppleScript snippets we build dynamically**, we want a standard pattern:

```applescript
try
    -- main logic
    return "Success"
on error errMsg
    return "Error: " & errMsg
end try
```

**Tasks:**
- Update `_build_create_event_applescript(...)` in `src/automation/calendar_automation.py` so that:
  - The generated script is fully wrapped in a `try / on error / end try` block.
  - You still use `tell application "Calendar"` etc. inside that `try`.
- Scan other AppleScript‑building helpers (especially in `src/automation/*_automation.py` and agents like `src/agent/imessage_agent.py`) and:
  - Add or confirm they already have this `try ... on error ... end try` structure.

**Acceptance criteria:**
- All **new or refactored** AppleScript you touch follows the pattern above.
- The Python side never has to parse AppleScript stack traces directly from stderr; instead, it sees `"Error: ..."` style messages on stdout.

---

### 1.4 Centralize AppleScript string escaping

We currently have similar escaping logic in multiple files (e.g., `_escape_applescript_string` and ad‑hoc replacements).

**Tasks:**
- Identify the canonical escape helper (if one exists) in:
  - `src/utils/applescript_utils.py`
  - Or, if it does **not** exist yet, create a single `escape_applescript_string(...)` helper there.
- Update the following modules to use the shared helper instead of local, duplicated logic:
  - `src/agent/imessage_agent.py`
  - `src/automation/calendar_automation.py`
  - `src/agent/notifications_agent.py`
  - Any other file with manual AppleScript escaping (quotes, backslashes, newlines).

**Acceptance criteria:**
- There is **one** canonical escape function used by all AppleScript‑building code you touch.
- The escape behavior is at least as safe as the current implementations (handles backslashes, quotes, newlines).

---

### 1.5 Optional: Configurable timeouts and activation behavior

If it is straightforward and minimally invasive:

**Tasks (optional / nice‑to‑have):**
- Introduce optional config values (via existing config machinery) for:
  - Default AppleScript timeout.
  - Whether certain apps should be auto‑activated (e.g., Calendar, Discord, Maps).
- Thread these values into `applescript_utils.run_applescript(...)` and the key automation classes (Calendar, Discord, etc.).

If this becomes too invasive, **skip it** for now. The critical pieces are 1.1–1.4.

---

## 2. Implement Shortcuts Agent + Automation

We want to bring in a macOS Shortcuts integration (from the MCP plan) that:
- Runs named Shortcuts via `Shortcuts Events`.
- Lists available Shortcuts.
- Exposes this via a dedicated agent and tools.

### 2.1 Shortcuts automation module

Add a new file:
- `src/automation/shortcuts_automation.py`

**Design:**
- Create a class `ShortcutsAutomation` similar in spirit to `CalendarAutomation`:
  - `def __init__(self, config: Optional[Dict[str, Any]] = None): ...`
  - `def run_shortcut(self, name: str, input_text: Optional[str] = None) -> Dict[str, Any]:`
  - `def list_shortcuts(self) -> Dict[str, Any]:`
- Use AppleScript via `Shortcuts Events`:
  - Wrap each script in `try / on error / end try`.
  - Execute via `applescript_utils.run_applescript(...)`.
  - Escape all user‑supplied strings.

**Expected return shape examples:**
- `run_shortcut` success:
  ```python
  {"success": True, "shortcut_name": name, "output": "<string or structured info if available>"}
  ```
- `run_shortcut` failure:
  ```python
  {
      "success": False,
      "error": True,
      "error_type": "ShortcutExecutionError",
      "error_message": "...",
      "shortcut_name": name,
  }
  ```
- `list_shortcuts` success:
  ```python
  {"success": True, "shortcuts": [{"name": "...", "folder": "..."}]}
  ```

---

### 2.2 Shortcuts agent (LangChain tools)

Add a new file:
- `src/agent/shortcuts_agent.py`

**Design:**
- Import `tool` from `langchain_core.tools`.
- Use a helper to construct a `ShortcutsAutomation` instance (similar to how other agents load automation/config).
- Define tools:
  - `@tool def run_shortcut(name: str, input_text: Optional[str] = None) -> Dict[str, Any]:`
  - `@tool def list_shortcuts() -> Dict[str, Any]:`
- Implement a `ShortcutsAgent` class mirroring the pattern used in `CalendarAgent` and `NotificationsAgent`:
  - `__init__(self, config: Dict[str, Any])`
  - `get_tools(self) -> List`
  - `get_hierarchy(self) -> str` (small hierarchy doc string is enough)
  - `execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]`

**Acceptance criteria:**
- The two tools can be invoked via `.invoke(...)` and call into `ShortcutsAutomation`.
- Error handling matches the general pattern described in section 0.

---

### 2.3 Registry and exports

Wire the new agent into the existing registry.

**Files & tasks:**

1. `src/agent/agent_registry.py`
   - Import:  
     ```python
     from .shortcuts_agent import ShortcutsAgent, SHORTCUTS_AGENT_TOOLS, SHORTCUTS_AGENT_HIERARCHY
     ```
   - Add `"shortcuts": ShortcutsAgent` to `self._agent_classes` in `AgentRegistry.__init__`.
   - Add `SHORTCUTS_AGENT_TOOLS` into:
     - `ALL_AGENT_TOOLS` tuple.
     - `tool_lists["shortcuts"]` mapping so `tool_to_agent` gets populated.

2. `src/agent/__init__.py`
   - Import and add `ShortcutsAgent` and `SHORTCUTS_AGENT_TOOLS` to `__all__` similar to other agents.

**Acceptance criteria:**
- `AgentRegistry.get_agent("shortcuts")` lazy‑loads the agent successfully.
- Shortcuts tools appear in `ALL_AGENT_TOOLS` and can be resolved by name.

---

### 2.4 Slash commands + tool catalog (routing)

**Files:**
- `src/ui/slash_commands.py`
- `src/orchestrator/tools_catalog.py`

**Tasks:**
- In `slash_commands.py`:
  - Add entries to `COMMAND_MAP` so `/shortcut` (and possibly aliases like `/shortcuts`) route to the `shortcuts` agent.
  - Add `/shortcut` to `COMMAND_TOOLTIPS`, `AGENT_DESCRIPTIONS`, and `EXAMPLES`.
  - Implement a private helper (e.g., `_route_shortcut_command`) that:
    - Parses simple natural language variations such as:
      - `"run 'Resize Images'"`
      - `"list all shortcuts"`
    - Maps them to either `run_shortcut` or `list_shortcuts` with appropriate params.
- In `tools_catalog.py`:
  - Add Shortcuts tools to the catalog with clear descriptions:
    - When to use `run_shortcut`.
    - When to use `list_shortcuts`.

**Acceptance criteria:**
- `/shortcut ...` commands are parsed and routed to the correct Shortcuts tool.
- The tool catalog includes Shortcuts entries with correct names and descriptions.

---

## 3. Implement System Control Agent

We want a small set of system controls:
- Volume
- Dark mode
- (Optionally) basic Do Not Disturb or brightness controls

### 3.1 System control automation module

Add:
- `src/automation/system_control_automation.py`

**Design:**
- `class SystemControlAutomation:`
  - `def __init__(self, config: Optional[Dict[str, Any]] = None): ...`
  - `def set_volume(self, level: int) -> Dict[str, Any]:`
  - `def toggle_dark_mode(self) -> Dict[str, Any]:`
  - Optionally: `def set_do_not_disturb(self, enabled: bool) -> Dict[str, Any]:`
- Use AppleScript with the standard try/on‑error pattern and `applescript_utils.run_applescript(...)`.
- Validate inputs in Python (e.g., clamp volume between 0–100).

**Acceptance criteria:**
- `set_volume` and `toggle_dark_mode` return structured success/error dicts.
- AppleScript is robust and uses the shared escape / execution helpers.

---

### 3.2 System control agent

Add:
- `src/agent/system_control_agent.py`

**Design:**
- Two core tools:
  - `@tool def set_volume(level: int) -> Dict[str, Any]:`
  - `@tool def toggle_dark_mode() -> Dict[str, Any]:`
- Optionally expose DND as a tool if you implement it.
- Implement `SystemControlAgent` with the same pattern as other agents (see `NotificationsAgent` / `CalendarAgent`).

**Acceptance criteria:**
- Tools call into `SystemControlAutomation` and respect the common error contract.

---

### 3.3 Registry, exports, and slash commands

**Files & tasks:**

1. `src/agent/agent_registry.py`
   - Import:
     ```python
     from .system_control_agent import SystemControlAgent, SYSTEM_CONTROL_AGENT_TOOLS, SYSTEM_CONTROL_AGENT_HIERARCHY
     ```
   - Add `"system_control": SystemControlAgent` to `_agent_classes`.
   - Add `SYSTEM_CONTROL_AGENT_TOOLS` to `ALL_AGENT_TOOLS` and `tool_lists`.

2. `src/agent/__init__.py`
   - Export `SystemControlAgent` and `SYSTEM_CONTROL_AGENT_TOOLS`.

3. `src/ui/slash_commands.py`
   - Add `/system` (and optionally `/sys`) to `COMMAND_MAP` → `"system_control"`.
   - Add command tooltip, agent description, and examples, e.g.:
     - `/system volume 40`
     - `/system toggle dark mode`
   - Implement a simple `_route_system_command(...)` that parses the above into the appropriate tool and params.

4. `src/orchestrator/tools_catalog.py`
   - Add catalog entries describing the system control tools.

**Acceptance criteria:**
- `/system ...` commands route correctly to system control tools.
- System control tools appear in the global tool catalog.

---

## 4. Clipboard Tools (Text + File Paths)

We want a reusable clipboard abstraction that:
- Reads/writes plain text via the clipboard.
- Reads file paths from the clipboard (e.g., when user copies files in Finder).
- Can be reused by agents that rely on clipboard (Discord, etc.).

### 4.1 Clipboard utilities module

Add:
- `src/automation/clipboard_tools.py`

**Design:**
- Implement:
  - `def read_clipboard(mode: str = "text") -> Dict[str, Any]:`
    - For `"text"`:
      - Use `pbpaste` (or an AppleScript helper) with timeouts and errors handled gracefully.
    - For `"files"`:
      - Use AppleScript to interpret clipboard contents as file URLs / aliases and return POSIX paths.
  - `def write_clipboard_text(text: str) -> Dict[str, Any]:`
  - Optionally:
    - `def read_file_paths_from_clipboard() -> Dict[str, Any]:` as a convenience wrapper for `mode="files"`.
- Follow the same error contract and logging practices as other automation modules.

**Acceptance criteria:**
- `read_clipboard("text")` returns `{"success": True, "content": "<string>"}` on success.
- `read_clipboard("files")` returns `{"success": True, "file_paths": [<POSIX paths>]}` on success.
- On failure, functions return structured error dicts as specified in section 0.

---

### 4.2 Refactor Discord clipboard usage to use clipboard_tools

File:
- `src/automation/discord_controller.py`

Focus on:
- Methods `_read_clipboard` and `_write_clipboard`.

**Tasks:**
- Replace internal implementations of `_read_clipboard` and `_write_clipboard` so they delegate to `clipboard_tools`:
  - `_read_clipboard` → `read_clipboard("text")`
  - `_write_clipboard` → `write_clipboard_text(...)`
- Keep the public behavior of `DiscordController` the same (i.e., `send_message`, etc. still work the same way conceptually).

**Acceptance criteria:**
- `DiscordController` no longer talks to `pbcopy`/`pbpaste` directly.
- Errors during clipboard operations are logged but do not crash the controller; they propagate as structured error dicts when relevant.

---

### 4.3 Optional: Expose clipboard as tools

If it fits cleanly (without over‑engineering):

**Option A:** Create a dedicated `ClipboardAgent` in `src/agent/clipboard_agent.py`.
**Option B:** Add clipboard tools to `MicroActionsAgent` if that pattern is already used for small utilities.

Possible tools:
- `clipboard_read_text`
- `clipboard_read_files`

If this becomes too large in scope, it is acceptable to **only** implement the automation module and Discord refactor for now.

---

## 5. Generalisability & Config‑Driven Behavior

### 5.1 Centralize Mac defaults in config accessors

Files to reference:
- `src/config_manager.py`
- `src/config_validator.py`
- Existing config usage in:
  - `src/agent/imessage_agent.py`
  - `src/automation/calendar_automation.py`
  - `src/agent/maps_agent.py`
  - `src/agent/notes_agent.py`
  - `src/agent/reminders_agent.py`

**Tasks:**
- Confirm that Mac‑specific defaults are provided via config/accessors rather than hardcoded strings. Examples:
  - Default iMessage recipient (already handled via config in `imessage_agent`, just ensure consistency).
  - Default calendar name (if any).
  - Default Notes folder for saving meeting briefs.
  - Default reminders list.
  - Default Maps provider (already partially wired via `config.yaml`).
- Where you find obvious hardcoded values that should be config‑driven (and there is already a relevant config accessor), replace the hardcoded value with the accessor call.

**Acceptance criteria:**
- Mac behaviors that are user‑specific (e.g., which calendar, which default recipient) are read from config/accessors instead of inline literals wherever feasible, without breaking existing flows.

---

### 5.2 Normalize automation vs agent pattern

**Goal:** Ensure a clean separation:
- `src/automation/*_automation.py` → pure OS/AppleScript logic.
- `src/agent/*_agent.py` → LangChain tools + agent orchestration.

**Tasks:**
- When implementing new functionality (Shortcuts, SystemControl, Clipboard), stick to this pattern.
- If you find any **obvious** direct AppleScript embedded in agents that really belongs in automation modules, and it is a **small change** to move it, refactor it out. (If it’s large or risky, leave it for a future pass.)

**Acceptance criteria:**
- New code follows the existing architecture (automation modules + agents).

---

### 5.3 Keep error contracts consistent

As you touch Mac‑related tools (Calendar, iMessage, Discord, Maps, Reminders, Notes, Shortcuts, SystemControl, Clipboard):

**Tasks:**
- Make sure they all:
  - Return `{"success": True, ...}` on success **or** follow the existing, clearly documented success shape for that agent.
  - Return `{"error": True, "error_type": "...", "error_message": "...", "retry_possible": bool}` on failure.
- Align naming of `error_type` and `error_message` with the semantics of the failure (e.g., `CalendarReadError`, `ShortcutExecutionError`, `SystemControlError`, etc.).

**Acceptance criteria:**
- Callers (AgentRegistry, orchestrator, other agents) can treat tool results uniformly instead of special‑casing each agent.

---

### 5.4 Make new tools discoverable by the orchestrator

Files:
- `src/orchestrator/tools_catalog.py`
- `src/orchestrator/main_orchestrator.py` (and related planner code)

**Tasks:**
- Ensure all newly added tools (Shortcuts, SystemControl, any clipboard tools you expose as LangChain tools) are:
  - Present in the tools catalog with good descriptions and usage notes.
  - Available for natural‑language routing (i.e., the planner can see and choose them when appropriate).

You do **not** need to deeply change planner logic—just make sure the new tools are properly described and registered so the existing planner can use them.

---

## 6. Notifications Agent Integration (Optional Enhancement)

File:
- `src/agent/notifications_agent.py`
- Existing docs in `docs/changelog/AGENT_FIXES_AND_NOTIFICATIONS.md`

The Notifications agent is already implemented and wired. A small optional enhancement is to leverage it for long‑running Mac workflows.

**Optional task (only if time/space allows):**
- In a few high‑value flows (e.g., long file operations, large stock presentation generation, heavy searches):
  - When the user explicitly asks to “notify me when you’re done”, have the orchestrator (or the relevant agent) call `send_notification` at the end.

Do **not** implement complex new orchestration behavior here; this is a UX improvement and can be skipped if it complicates things.

---

## 7. Testing Scope (Important)

Per the current request:

- Do **not** add new test files (e.g., `tests/test_shortcuts_agent.py`, etc.) in this pass.
- You **may**:
  - Run existing tests locally to sanity‑check changes.
  - Make small, necessary adjustments to existing tests **only** if they are directly broken by your changes and the fix is obvious and safe.

The primary focus of this implementation pass is **code and wiring**, not test coverage.

