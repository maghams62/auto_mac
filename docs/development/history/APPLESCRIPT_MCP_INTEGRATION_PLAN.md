# AppleScript MCP Integration Plan

## Executive Summary

After analyzing both codebases, I recommend a **selective integration** strategy that:
1. **Keeps your superior agentic architecture** (orchestrator, multi-agent system, LLM-driven planning)
2. **Adopts MCP's better AppleScript implementations** for missing features
3. **Preserves your existing code** where it's more robust
4. **Adds 4 new agents** with carefully selected capabilities

---

## Comparison Matrix: Your Code vs MCP

| Feature | Your Implementation | MCP Implementation | Winner | Reasoning |
|---------|-------------------|-------------------|--------|-----------|
| **Email** | Robust, multi-attach, tested | Not present | **YOURS** | Production-ready with attachment support |
| **iMessage** | Works but service-specific | Simpler Messages.app | **HYBRID** | Combine your structure with their simpler script |
| **Calendar** | ❌ Missing | Basic, date bugs | **MCP (with fixes)** | Add this capability, fix date handling |
| **Reminders** | ❌ Missing | Basic operations | **MCP** | Add this capability |
| **Clipboard** | pbcopy/pbpaste (simple) | Type-aware, file paths | **MCP** | Better file path handling |
| **Shortcuts** | ❌ Missing | Clean with error handling | **MCP** | Add this capability |
| **System Control** | ❌ Missing | Volume, dark mode | **MCP** | Add this capability |
| **Notifications** | ❌ Missing | Not in MCP either | **NEW** | Implement from scratch |
| **File Operations** | Excellent (LLM + security) | Basic Finder | **YOURS** | Your implementation is superior |
| **Screen Capture** | Multi-strategy, robust | Not present | **YOURS** | Excellent implementation |
| **Discord** | Comprehensive (A grade) | Not present | **YOURS** | Most sophisticated module |
| **Maps** | Good URL scheme approach | Not present | **YOURS** | Keep existing |
| **Browser** | Playwright-based | Not present | **YOURS** | Modern, cross-platform |
| **Report Gen** | RTF/HTML/PDF pipeline | Not present | **YOURS** | Keep existing |

---

## Integration Decisions

### ✅ ADOPT from MCP (New Capabilities)

#### 1. Calendar Integration
**Status:** Your code is missing this entirely

**MCP Code Quality:** C+ (has date handling bugs)

**Strategy:** Use MCP's structure but **fix the date bugs**

**Implementation:**
```python
# src/agent/calendar_agent.py
@tool
def create_calendar_event(
    title: str,
    start_datetime: str,  # ISO format: 2025-01-15T14:30:00
    end_datetime: str,
    calendar_name: str = "Calendar",
    notes: Optional[str] = None,
    location: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create calendar event using proper datetime parsing (fix MCP bugs).
    """
```

**Fixes to Apply:**
- Use Python datetime parsing instead of string slicing
- Format dates properly for AppleScript
- Add error handling (try-catch blocks)
- Validate calendar exists
- Return structured success/failure

---

#### 2. Shortcuts Integration
**Status:** Your code is missing this

**MCP Code Quality:** B+ (good error handling)

**Strategy:** **Adopt directly** with minor enhancements

**Implementation:**
```python
# src/agent/shortcuts_agent.py
@tool
def run_shortcut(
    name: str,
    input_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run macOS Shortcut using Shortcuts Events.

    Direct adoption from MCP with better error messages.
    """
    applescript = f'''
    try
        tell application "Shortcuts Events"
            {"set result to run shortcut \\"" + name + "\\" with input \\"" + input_text + "\\"" if input_text else "run shortcut \\"" + name + "\\""}
        end tell
        return "Success"
    on error errMsg
        return "Error: " & errMsg
    end try
    '''
```

---

#### 3. System Control
**Status:** Your code is missing this

**MCP Code Quality:** B (functional but limited)

**Strategy:** **Adopt and extend** with additional controls

**Implementation:**
```python
# src/agent/system_control_agent.py

@tool
def set_volume(level: int) -> Dict[str, Any]:
    """Set system volume (0-100). Direct adoption from MCP."""

@tool
def toggle_dark_mode() -> Dict[str, Any]:
    """Toggle dark mode. Direct adoption from MCP."""

@tool  # NEW - not in MCP
def set_do_not_disturb(enabled: bool) -> Dict[str, Any]:
    """Enable/disable Do Not Disturb. Add this ourselves."""
    applescript = '''
    tell application "System Events"
        tell process "Control Center"
            -- Implementation needed
        end tell
    end tell
    '''
```

---

#### 4. Enhanced Clipboard
**Status:** Your code uses pbcopy/pbpaste (simpler)

**MCP Code Quality:** B+ (better file path handling)

**Strategy:** **Hybrid** - keep pbcopy/pbpaste for text, add MCP's file path detection

**Implementation:**
```python
# src/automation/clipboard_tools.py

def read_clipboard(mode: str = "text") -> Dict[str, Any]:
    """
    Read clipboard.

    Args:
        mode: "text" (default) or "files"
    """
    if mode == "text":
        # Use existing pbpaste (simpler, more reliable)
        result = subprocess.run(["pbpaste"], capture_output=True, text=True)
        return {"content": result.stdout}

    elif mode == "files":
        # Use MCP's file path detection
        applescript = '''
        try
            set clipContent to the clipboard as text
            if clipContent starts with "file://" then
                set filePaths to {}
                -- Convert file URLs to POSIX paths
                -- (Use MCP's implementation)
            end if
        end try
        '''
```

---

### ✅ KEEP Your Code (Superior Implementation)

#### 1. Email (mail_composer.py) - Grade: B+
**Reason:** Your code has:
- Multiple attachment support
- Better error handling
- Production testing
- Signature support

**MCP Status:** Not present

**Action:** **Keep as-is**, no changes needed

---

#### 2. File Operations (file_agent.py, folder_tools.py) - Grade: A-
**Reason:** Your code has:
- LLM-driven categorization (intelligent)
- Sandbox security (path validation)
- Dry-run support
- Atomic operations

**MCP Has:** Basic Finder operations only

**Action:** **Keep as-is**, this is a differentiator

---

#### 3. Screen Capture (screen_capture.py) - Grade: A-
**Reason:** Your code has:
- Multiple fallback strategies
- Window-specific capture
- Quartz/CGWindowID support
- Auto-sizing

**MCP Status:** Not present

**Action:** **Keep as-is**, excellent implementation

---

#### 4. Discord (discord_controller.py) - Grade: A
**Reason:** Your code is the **most sophisticated automation module**:
- Login automation
- Message reading (accessibility scraping)
- Delivery confirmation
- MFA support

**MCP Status:** Not present

**Action:** **Keep as-is**, this is production-grade

---

#### 5. Browser (web_browser.py) - Grade: A
**Reason:** Your Playwright implementation is:
- Modern and cross-platform
- Industry-standard
- Async/await support
- Content extraction

**MCP Status:** Not present

**Action:** **Keep as-is**

---

#### 6. Report Generation (report_generator.py) - Grade: B+
**Reason:** Your code has:
- RTF and HTML formats
- PDF conversion pipeline
- Base64 image embedding
- Just fixed with reportlab

**MCP Status:** Not present

**Action:** **Keep as-is**

---

### ⚠️ IMPROVE Your Code (Learn from MCP)

#### 1. iMessage (imessage_agent.py)
**Current Grade:** B (works but service-specific)

**Problem:** Hardcoded `service "E:icloud.com"` may not work for all users

**MCP Approach:** Simpler script without service specification

**Action:** **Simplify your script**
```python
# OLD (your current code)
tell application "Messages"
    send myMessage to buddy myBuddy of service "E:icloud.com"
end tell

# NEW (adopt MCP's simpler approach)
tell application "Messages"
    send "..." to participant "..."  # No service needed
end tell
```

---

#### 2. Add Error Handling to Keynote/Pages
**Current Grade:** B/C+ (basic implementations)

**MCP Pattern:** All scripts have try-catch blocks

**Action:** Wrap all AppleScript with try-catch
```applescript
try
    tell application "Keynote"
        -- your code
    end tell
    return "Success"
on error errMsg
    return "Error: " & errMsg
end try
```

---

## Implementation Plan

### Phase 1: Add Missing Core Features (Week 1)
Priority: High-value capabilities you're missing

1. **Create calendar_agent.py**
   - Tools: `create_event`, `list_events`, `delete_event`
   - Fix MCP's date bugs
   - Add to AgentRegistry
   - Register tools with orchestrator

2. **Create shortcuts_agent.py**
   - Tools: `run_shortcut`, `list_shortcuts`
   - Direct adoption from MCP
   - Add to AgentRegistry

3. **Create system_control_agent.py**
   - Tools: `set_volume`, `toggle_dark_mode`, `set_brightness`, `set_do_not_disturb`
   - Adopt MCP + add new tools
   - Add to AgentRegistry

4. **Enhance clipboard_tools.py**
   - Add file path detection from MCP
   - Keep pbcopy/pbpaste for text

**Estimated Time:** 8-12 hours
**Files Created:** 3 new agents (~800 lines total)
**Breaking Changes:** 0

---

### Phase 2: Quality Improvements (Week 2)
Priority: Harden existing code

1. **Add error handling to Keynote**
   - Wrap AppleScript with try-catch
   - Return structured errors

2. **Simplify iMessage**
   - Remove service hardcoding
   - Test with various account types

3. **Add Notifications**
   - Create notifications_agent.py (not in MCP)
   - Use NSUserNotification or AppleScript

**Estimated Time:** 4-6 hours
**Files Modified:** 2 existing agents
**Files Created:** 1 new agent

---

### Phase 3: Testing & Documentation (Week 3)
Priority: Ensure reliability

1. **Create test suite**
   - tests/test_calendar_agent.py
   - tests/test_shortcuts_agent.py
   - tests/test_system_control_agent.py

2. **Update documentation**
   - docs/agents/CALENDAR_AGENT.md
   - docs/agents/SHORTCUTS_AGENT.md
   - docs/agents/SYSTEM_CONTROL_AGENT.md

3. **Add slash commands**
   - /calendar - Calendar operations
   - /shortcut - Run shortcuts
   - /system - System controls

**Estimated Time:** 6-8 hours

---

## Architecture Integration

Your agentic architecture **remains unchanged**:

```
User Request
    ↓
MainOrchestrator (LLM planning)
    ↓
Planner (task decomposition)
    ↓
AgentRegistry (tool selection)
    ↓
Specialized Agents:
├── FileAgent (existing)
├── EmailAgent (existing)
├── BrowserAgent (existing)
├── DiscordAgent (existing)
├── CalendarAgent (NEW from MCP)
├── ShortcutsAgent (NEW from MCP)
├── SystemControlAgent (NEW from MCP)
└── NotificationsAgent (NEW custom)
    ↓
Tools execute AppleScript
    ↓
Results return to Orchestrator
    ↓
LLM synthesizes response
```

**Key Principles:**
- ✅ LLM-driven planning preserved
- ✅ Multi-agent pattern preserved
- ✅ Tool registration pattern preserved
- ✅ Slash command system preserved
- ✅ Session memory preserved

**What Changes:**
- ➕ 4 new agents added
- ➕ ~12 new tools added
- 🔧 2 existing agents improved
- 📚 Documentation updated

---

## Code Quality Standards

When integrating MCP code, apply **your quality standards**:

### Required Improvements:

1. **Error Handling**
   ```python
   try:
       result = subprocess.run(["osascript", "-e", script],
                              capture_output=True, text=True, timeout=15)
       if result.returncode != 0:
           return {"error": True, "error_message": result.stderr}
   except subprocess.TimeoutExpired:
       return {"error": True, "error_message": "AppleScript timeout"}
   ```

2. **Input Validation**
   ```python
   if not title or not start_datetime:
       return {"error": True, "error_message": "Missing required fields"}
   ```

3. **Structured Returns**
   ```python
   return {
       "success": True,
       "event_id": "...",
       "message": "Event created successfully"
   }
   ```

4. **Logging**
   ```python
   logger.info(f"[CALENDAR AGENT] Creating event: {title}")
   ```

5. **Tool Decoration**
   ```python
   @tool
   def create_calendar_event(...) -> Dict[str, Any]:
       """Comprehensive docstring with examples."""
   ```

---

## File Structure

```
src/
├── agent/
│   ├── calendar_agent.py          # NEW - from MCP (improved)
│   ├── shortcuts_agent.py         # NEW - from MCP (direct)
│   ├── system_control_agent.py    # NEW - from MCP (extended)
│   ├── notifications_agent.py     # NEW - custom implementation
│   ├── imessage_agent.py          # MODIFIED - simplified
│   ├── keynote_composer.py        # MODIFIED - better errors
│   └── agent_registry.py          # MODIFIED - register new agents
├── automation/
│   ├── clipboard_tools.py         # NEW - hybrid approach
│   ├── mail_composer.py           # KEEP - no changes
│   ├── screen_capture.py          # KEEP - no changes
│   ├── discord_controller.py      # KEEP - no changes
│   └── web_browser.py             # KEEP - no changes
├── ui/
│   └── slash_commands.py          # MODIFIED - add /calendar, /shortcut, /system
└── orchestrator/
    └── main_orchestrator.py       # NO CHANGES - architecture preserved

tests/
├── test_calendar_agent.py         # NEW
├── test_shortcuts_agent.py        # NEW
├── test_system_control_agent.py   # NEW
└── test_notifications_agent.py    # NEW

docs/
├── agents/
│   ├── CALENDAR_AGENT.md          # NEW
│   ├── SHORTCUTS_AGENT.md         # NEW
│   └── SYSTEM_CONTROL_AGENT.md    # NEW
└── APPLESCRIPT_MCP_INTEGRATION.md # This file
```

---

## Risk Assessment

### Low Risk (Safe to Proceed)
- ✅ Adding new agents (no impact on existing code)
- ✅ Registering new tools (backwards compatible)
- ✅ Creating new slash commands (optional usage)

### Medium Risk (Test Thoroughly)
- ⚠️ Simplifying iMessage script (test with multiple account types)
- ⚠️ Calendar date handling (validate datetime parsing)

### High Risk (Avoided)
- ❌ Replacing your file operations (keep your superior implementation)
- ❌ Changing orchestrator architecture (preserve existing)
- ❌ Modifying Discord/Browser (production-grade, don't touch)

---

## Success Metrics

After integration, you'll have:

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total Agents | 11 | 15 | +36% |
| Total Tools | 45 | 57 | +27% |
| Mac App Coverage | 8 apps | 11 apps | +38% |
| Missing Core Features | 4 | 0 | Complete |
| Average Code Quality | B+ | A- | Improved |

---

## Recommendation

**Proceed with selective integration:**

1. ✅ **Adopt** Calendar, Shortcuts, System Control agents from MCP
2. ✅ **Enhance** Clipboard with file path detection
3. ✅ **Keep** all your existing agents (they're better)
4. ✅ **Preserve** your agentic architecture entirely
5. ✅ **Add** Notifications agent (custom, not in MCP)
6. ✅ **Improve** iMessage and Keynote with MCP patterns

This gives you the **best of both worlds**:
- Your superior architecture and existing automation
- MCP's missing capabilities (Calendar, Shortcuts, System)
- Enhanced overall Mac automation coverage

**Estimated Total Effort:** 20-30 hours over 3 weeks
**Risk Level:** Low
**Breaking Changes:** 0
**Value Add:** High

---

## Next Steps

**Decision needed from you:**

1. Should I proceed with Phase 1 (Calendar, Shortcuts, System agents)?
2. Any specific priorities in which agent to implement first?
3. Do you want me to create all 4 new agents, or start with just 1-2?

Let me know and I'll start building!
