# Slash Command Regression Test Plan

## Overview

This document describes the comprehensive regression test plan for slash commands, `/files` preview flow, and telemetry validation.

## Test Scope

### Supported Commands
- `/email` - Email operations
- `/explain` - RAG pipeline for document explanation
- `/files` - Special UI command (opens palette, not chat)
- `/bluesky` - Bluesky social media operations
- `/report` - Local report generation
- `/help` - Help system
- `/agents` - Agent directory
- `/clear` - Session clearing
- `/confetti` - Celebration effects

### Unsupported Commands
Commands like `/maps` should fall back to natural language mode without telemetry.

## Test Cases

### 1. Frontend UI Tests (Playwright)

#### 1.1 Command Dropdown
- **Test**: Typing `/` shows only supported commands
- **Expected**: Only `/email`, `/explain`, `/bluesky`, `/report`, `/help`, `/agents`, `/clear`, `/confetti` appear
- **Not Expected**: `/files` (special-ui), `/maps` (unsupported)

#### 1.2 Command Palette Parity
- **Test**: `⌘K` opens palette with same command list
- **Expected**: Command list matches dropdown (names, ordering)
- **Not Expected**: Unsupported commands

#### 1.3 /files Preview Flow
- **Test**: Type `/files guitar tabs` and press Enter
- **Expected**:
  - No chat bubble created
  - Command palette opens with query prefilled
  - Search results appear
  - Network request to `/api/universal-search` returns 200
  - Keyboard shortcuts work:
    - `␣` toggles preview
    - `↵` opens document
    - `⌘↵` reveals file

#### 1.4 Command Execution
- **Test**: Execute each supported command
- **Expected**:
  - `/email read my latest 3 emails` → deterministic result
  - `/email summarize my inbox` → orchestrator path
  - `/explain "Project Kickoff"` → RAG summary + preview metadata
  - `/bluesky search ...` and `/bluesky post ...` → distinct responses
  - `/report`, `/help`, `/agents`, `/clear`, `/confetti` → correct behavior
  - No console errors
  - All network requests return 2xx

#### 1.5 Unsupported Commands
- **Test**: Enter `/maps plan trip from la to sf`
- **Expected**:
  - Falls back to natural language
  - No telemetry logged
  - Command doesn't appear in dropdown/palette

### 2. Backend Python Tests

#### 2.1 Command Parsing
- **Test**: Parse each supported command
- **Expected**: Correct command name and agent mapping

#### 2.2 Unsupported Command Fallback
- **Test**: Parse unsupported commands
- **Expected**: Returns `None`, falls through to orchestrator with leading slash stripped

#### 2.3 Telemetry Behavior
- **Test**: Invoke supported commands
- **Expected**:
  - Exactly one `slash_command_usage` record per invocation
  - Usage metrics increment correctly
  - No telemetry for unsupported commands

#### 2.4 Command Routing
- **Test**: Route commands to correct agents/tools
- **Expected**:
  - `/email` → email agent
  - `/explain` → RAG pipeline
  - `/bluesky` → bluesky agent with correct parser routing

### 3. Telemetry Validation

#### 3.1 Frontend Telemetry
- **Test**: Emit telemetry events
- **Expected**:
  - One event per command invocation
  - Event includes: `command_name`, `invocation_source`, `timestamp`
  - Events sent to `/api/telemetry/slash-command`

#### 3.2 Backend Telemetry
- **Test**: Record telemetry in backend
- **Expected**:
  - `[SLASH COMMANDS] Command invoked` log entries
  - `record_batch_operation("slash_command_usage", 1)` called
  - Telemetry failures don't break user flows

## Success Criteria

### Pass Criteria
1. ✅ Only supported commands appear in dropdown and palette
2. ✅ `/files` opens palette with prefilled query, no chat bubble
3. ✅ All supported commands execute correctly
4. ✅ Unsupported commands fall back to natural language
5. ✅ Exactly one telemetry event per command invocation
6. ✅ No console errors during test runs
7. ✅ All network requests return 2xx
8. ✅ No stack traces in backend logs

### Fail Criteria
- Unsupported commands appear in UI
- `/files` creates chat bubble
- Commands fail to execute
- Multiple telemetry events per invocation
- Console errors or network failures
- Stack traces in logs

## Test Execution

### Run All Tests
```bash
./tests/run_slash_regression.sh
```

### Run Python Tests Only
```bash
./tests/run_slash_regression.sh --python-only
```

### Run Playwright Tests Only
```bash
./tests/run_slash_regression.sh --playwright-only
```

### Run with Verbose Output
```bash
./tests/run_slash_regression.sh --verbose
```

## Example Telemetry Records

### Frontend Event
```json
{
  "command_name": "email",
  "invocation_source": "input_dropdown",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Backend Log Entry
```
[SLASH COMMANDS] Command invoked
extra={"command": "email", "count": 1, "invocation_source": "input_dropdown"}
```

## Sample Log Excerpts

### Successful Command Execution
```
[SLASH COMMANDS] Command invoked
extra={"command": "email", "count": 1}
[SLASH COMMANDS] Handler initialized
```

### Unsupported Command Fallback
```
[SLASH COMMANDS] Ignoring unsupported command: /maps plan trip...
```

## Test Artifacts

- Playwright test results: `tests/ui/test-results/`
- Python test output: Console logs
- Telemetry logs: `api_server.log`
- Test reports: Generated on request

## Maintenance

- Update test cases when adding new commands
- Review telemetry logs regularly
- Update success criteria as needed
- Keep test helpers reusable and documented

