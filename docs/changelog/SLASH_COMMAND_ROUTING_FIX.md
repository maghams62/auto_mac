# Slash Command Routing Architecture Fix

## Overview

This update fixes the slash command system to properly integrate with the new agentic architecture, resolves issues with natural language queries containing paths being hijacked as commands, and ensures demo data constraints are honored.

## Problems Solved

### 1. Parser Treats Any `/token` as a Command
**Issue:** The parser treated any text starting with `/` as a slash command, causing natural queries like "organize files in /Users/john/Documents" to fail with "unknown command: /Users" errors.

**Solution:**
- Parser now only recognizes tokens in `COMMAND_MAP`
- Unknown tokens (e.g., `/Users/...`) return `None` instead of errors, allowing them to fall through to the orchestrator
- Added `//` escaping mechanism for paths that need to start with `/`

**Code:** [src/ui/slash_commands.py:265-377](src/ui/slash_commands.py#L265-L377)

### 2. Command Map Points at Legacy Agent Names
**Issue:** `COMMAND_MAP` still used legacy agent names, and the handler then made a fresh LLM call to choose tools, bypassing the new agentic plans and often picking mismatched tools.

**Solution:**
- Added deterministic routing functions:
  - `_route_files_command()`: Routes `/files` commands directly to appropriate tools (search_documents, organize_files, create_zip_archive, etc.)
  - `_route_folder_command()`: Routes `/folder` commands to folder tools (folder_list, folder_organize_by_type, folder_normalize_names)
- Eliminated redundant LLM calls for file/folder operations
- Direct tool execution via `registry.execute_tool()` instead of going through agent LLM routing

**Code:** [src/ui/slash_commands.py:1408-1489](src/ui/slash_commands.py#L1408-L1489)

### 3. No Demo Data Anchoring
**Issue:** `/files` and `/folder` commands didn't anchor to the demo data (`tests/data/test_docs`), causing them to crawl real user directories instead.

**Solution:**
- Added `get_demo_documents_root(config)` utility that reads `config.documents.folders[0]`
- Both routing functions default to demo root unless user explicitly overrides with a path
- Handler now accepts `config` parameter to access demo constraints

**Code:** [src/ui/slash_commands.py:39-61](src/ui/slash_commands.py#L39-L61)

### 4. Errors Bubble Directly to Chat
**Issue:** Direct agent call errors gave the impression the system "doesn't know what to do," even though the main orchestrator would succeed.

**Solution:**
- Added graceful error handling in `handle()` method
- Errors from tool execution are caught and analyzed
- Retriable errors (tool not found, missing params, permission issues) return special `retry_with_orchestrator` type
- Friendly error messages: "⚠ Direct /files execution encountered an issue. Let me try routing through the main assistant..."

**Code:** [src/ui/slash_commands.py:966-992](src/ui/slash_commands.py#L966-L992)

## Changes Summary

### Modified Files

#### `src/ui/slash_commands.py`
1. **Parser Hardening (Lines 245-380)**
   - Added `//` escape mechanism for paths
   - Unknown commands return `None` instead of error dict
   - Only tokens in `COMMAND_MAP` are treated as commands

2. **Demo Constraint Utility (Lines 39-61)**
   - `get_demo_documents_root(config)` reads first configured document folder
   - Falls back to `document_directory` for legacy configs

3. **Deterministic Routing (Lines 1408-1489)**
   - `_route_files_command(task)`: Maps keywords to file tools with demo constraints
   - `_route_folder_command(task)`: Maps keywords to folder tools with demo constraints
   - Eliminates LLM calls for /files and /folder

4. **Graceful Error Handling (Lines 966-992)**
   - Catches errors from tool execution
   - Identifies retriable errors (tool not found, missing params, etc.)
   - Returns `retry_with_orchestrator` type for UI to handle

5. **Handler Configuration (Lines 736-748)**
   - Added `config` parameter to `__init__`
   - Stores config for demo constraint lookups

#### `main.py`
- Updated `create_slash_command_handler()` call to pass `config` parameter (Line 76)

#### `src/agent/agent.py`
- Fixed `SlashCommandHandler` instantiation to use keyword arguments (Line 1218)
- Changed from `SlashCommandHandler(registry, self.config)` to `SlashCommandHandler(registry, session_manager=self.session_manager, config=self.config)`
- Ensures config is passed correctly and not mistaken for session_manager

### New Test Files

#### `tests/test_slash_command_routing.py`
Comprehensive unit tests covering:
- Parser path escaping (`//` and `/Users` paths)
- Known vs unknown command recognition
- Demo documents root utility
- Files command routing with demo constraints
- Folder command routing with demo constraints
- Natural language queries with paths
- Valid slash commands still work

#### `tests/test_slash_integration.py`
End-to-end integration tests covering:
- Natural queries with `/Users` paths fall through
- Path escaping with `//`
- `/files` commands use demo folder
- `/folder` commands use demo folder
- `/stock` command routing
- Unknown commands return None
- Known commands are recognized
- Help commands work

## Test Results

All tests passing:

```
SLASH COMMAND ROUTING TESTS
============================================================
✅ Parser path escaping tests passed
✅ Parser known commands tests passed
✅ Demo documents root tests passed
✅ Files command routing tests passed
✅ Folder command routing tests passed
✅ Natural language with paths tests passed
✅ Slash commands work tests passed
============================================================
✅ ALL TESTS PASSED

SLASH COMMAND INTEGRATION TESTS
============================================================
✅ Natural queries with /Users paths correctly fall through to orchestrator
✅ Path escaping with // works correctly
✅ /files commands correctly use demo folder constraint
✅ /folder commands correctly use demo folder constraint
✅ /stock command routing works
✅ Unknown commands correctly return None
✅ All known commands are correctly recognized
✅ Help commands work correctly
============================================================
✅ ALL INTEGRATION TESTS PASSED
```

## Usage Examples

### Natural Language with Paths (Now Works)
```
User: Please organize the files in /Users/john/Documents
System: [Falls through to orchestrator, processes normally]

User: Search /Users/john/Desktop for PDFs about AI
System: [Falls through to orchestrator, processes normally]
```

### Path Escaping
```
User: //Users/john/Documents/report.pdf
System: [Escapes slash command parsing, processes as text]
```

### Demo-Constrained Commands
```
User: /files summarize Edgar Allan Poe
System: [Searches in tests/data/test_docs by default]

User: /folder list
System: [Lists files from tests/data/test_docs]

User: /files organize PDFs
System: [Organizes files in tests/data/test_docs]
```

### Error Fallback
```
User: /files some_invalid_request
System: ⚠ Direct /files execution encountered an issue. Let me try routing through the main assistant...
[Retries via orchestrator]
```

## Architecture Improvements

### Before
```
User: /files summarize X
  ↓
Parser: treats as command
  ↓
LLM: "Which tool should I use?"
  ↓
Tool execution (may fail, no context)
  ↓
Raw error to user
```

### After
```
User: /files summarize X
  ↓
Parser: validates command in COMMAND_MAP
  ↓
Deterministic routing: search_documents
  ↓
Tool execution with demo constraints
  ↓
Success or graceful retry via orchestrator
```

## Benefits

1. **No False Positives**: Natural language queries with paths no longer hijacked
2. **Demo Safety**: File/folder commands always default to test data
3. **Deterministic**: No LLM overhead for simple command routing
4. **Graceful Degradation**: Errors retry through orchestrator instead of failing hard
5. **Better UX**: Clear, friendly error messages
6. **Test Coverage**: Comprehensive test suites prevent regressions

## Backward Compatibility

All existing slash commands continue to work:
- `/files`, `/folder`, `/email`, `/maps`, `/stock`, `/browse`, etc.
- Help system (`/help`, `/help files`)
- Special commands (`/agents`, `/clear`, `/confetti`)

The only breaking change is intentional: unknown commands now fall through to the orchestrator instead of showing an error, which is the desired behavior.

## Future Enhancements

1. Add more deterministic routing for other agents (maps, stock, etc.)
2. Extend demo constraints to other file-accessing commands
3. Add config option to enable/disable demo mode
4. Surface plan cards for slash-triggered orchestrator retries

## Related Issues

- Fixes "test_data" bug where hardcoded values caused incorrect folder usage
- Addresses slash command hijacking of natural queries
- Resolves demo data not being used by default

---

**Author:** Claude Code
**Date:** 2025-11-11
**PR:** #TBD
