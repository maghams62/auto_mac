# /folder Command - LLM-First Folder Management

## Overview

The `/folder` command provides LLM-driven folder management with security guardrails. It follows an **LLM-first design** where the LLM interprets user intent and selects tools, rather than hardcoded routing logic.

## Key Features

✅ **LLM-Driven**: LLM parses intent, selects tools, determines parameters
✅ **Security First**: All operations sandboxed to configured folder (default: `test_data`)
✅ **Confirmation Discipline**: Write operations require explicit user confirmation
✅ **Dry-Run First**: Always validate with dry-run before actual execution
✅ **Scope Transparency**: Every response shows sandbox boundaries
✅ **Error Recovery**: Graceful conflict handling with actionable options

## Architecture

### Three-Layer Design

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: UI (Slash Commands)                               │
│  - Parses /folder commands                                  │
│  - Routes to Folder Agent                                   │
│  - Displays formatted results with scope badge              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: LLM Orchestrator (folder_agent_llm.py)            │
│  - Interprets user intent using LLM                         │
│  - Selects tool chain (list → plan → apply)                 │
│  - Enforces confirmation discipline                         │
│  - Formats output with scope badge                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Deterministic Tools (folder_tools.py)             │
│  - folder_check_sandbox: Validate paths                     │
│  - folder_list: List contents (alphabetically)              │
│  - folder_plan_alpha: Generate normalization plan           │
│  - folder_apply: Execute renames (atomic)                   │
└─────────────────────────────────────────────────────────────┘
```

## Available Tools

### Level 0: Security
**`folder_check_sandbox(path)`**
- Verifies path is within sandbox
- Detects symlink attacks and parent traversal
- Returns: `is_safe`, `message`, `resolved_path`, `allowed_folder`

### Level 1: Discovery
**`folder_list(folder_path)`**
- Lists folder contents (non-recursive)
- Alphabetically sorted
- Returns: `items`, `total_count`, `folder_path`
- Item structure: `{name, type, size, modified, extension}`

### Level 2: Planning (Dry-Run)
**`folder_plan_alpha(folder_path)`**
- Generates normalization plan:
  - Lowercase names
  - Spaces → underscores
  - Remove special characters
  - Collapse multiple underscores
- NO writes - always safe
- Returns: `plan`, `needs_changes`, `total_items`, `changes_count`

### Level 3: Execution (Writes)
**`folder_apply(plan, folder_path, dry_run=True)`**
- Applies rename plan
- **CRITICAL**: Always use `dry_run=True` first
- Atomic operations (no partial renames)
- Detects conflicts (destination exists)
- Returns: `success`, `applied`, `skipped`, `errors`, `dry_run`

## Usage Examples

### Example 1: List Folder Contents

```
User: /folder list

Response:
🔒 Folder scope: test_data (absolute: /Users/.../test_data)

📁 Contents of test_data/ (8 items)

NAME                    TYPE    SIZE        MODIFIED
────────────────────────────────────────────────────
Music Notes/            dir     -           2 days ago
Work Documents/         dir     -           1 week ago
photo 2023.jpg          file    2.3 MB      3 days ago
random-file.pdf         file    856 KB      1 month ago
...
```

### Example 2: Organize with Normalization

```
User: /folder organize alpha

Response:
🔒 Folder scope: test_data (absolute: /Users/.../test_data)

📁 Current State:
  Music Notes/
  Work Documents/
  photo 2023.jpg
  random-file.pdf

📋 Normalization Plan (3 changes needed)

CURRENT NAME            →  PROPOSED NAME           REASON
────────────────────────────────────────────────────────────────
Music Notes/            →  music_notes/            Lowercase + underscores
Work Documents/         →  work_documents/         Lowercase + underscores
photo 2023.jpg          →  photo_2023.jpg          Space to underscore

✓ 1 items already normalized
⚠️ 3 items need changes

Would you like me to apply these changes? (I'll validate first with a dry-run)

User: yes

Response:
✓ Dry-run validation successful

This will rename 3 items. Proceed? (yes/no)

User: yes

Response:
✅ Successfully renamed 3 items

  ✓ Music Notes/ → music_notes/
  ✓ Work Documents/ → work_documents/
  ✓ photo 2023.jpg → photo_2023.jpg

📁 Updated folder structure:
  music_notes/
  photo_2023.jpg
  random-file.pdf
  work_documents/
```

### Example 3: Check Sandbox Scope

```
User: /folder check scope

Response:
🔒 Folder scope: test_data (absolute: /Users/.../test_data)

✅ Path is within sandbox
   Resolved: /Users/.../test_data
   Allowed:  /Users/.../test_data

All folder operations are restricted to this directory for security.
```

### Example 4: Quick Organize (Alias)

```
User: /organize

Response:
[Same as /folder organize alpha]
```

## Security Guarantees

### Sandbox Enforcement

1. **Configuration-Based**: Sandbox root from `config.yaml`:
   ```yaml
   documents:
     folders:
       - "/Users/.../test_data"
   ```

2. **Path Validation**:
   - Resolves symlinks (prevents symlink attacks)
   - Checks for parent traversal (`..`)
   - Validates all paths before ANY operation

3. **Hard Failures**:
   - Tools reject operations outside sandbox
   - LLM receives clear error messages
   - User sees security violation notice

### Example Security Violations

```
User: /folder ../../../etc

Response:
🚫 Security Error: Path is outside allowed folder

Requested: /etc
Allowed:   /Users/.../test_data

Folder operations are restricted to: test_data
```

## Confirmation Discipline

### Two-Step Confirmation for Writes

**Step 1: Show Plan**
```
I found X files/folders that need renaming. Here's the plan:

[DIFF TABLE]

Would you like me to proceed with these changes?
```

**Step 2: Validate & Confirm**
```
Dry-run validation successful. Ready to apply changes.

This will rename X items. Proceed? (yes/no)
```

### Rules

1. **NEVER auto-apply**: Even if user says "organize", show plan first
2. **Dry-run first**: Always validate with `dry_run=True`
3. **Explicit confirmation**: Get clear "yes/no" from user
4. **Scope reminder**: Show scope badge in every response

## Error Handling

### Conflict Detection

```
⚠️ Found 2 conflicts:
- File One.txt → file_one.txt (conflict: file_one.txt already exists)
- Photo 2023.jpg → photo_2023.jpg (conflict: exists)

Options:
1. Skip conflicting files and apply others
2. Manual resolution (you choose new names)
3. Cancel operation

What would you like to do?
```

### Locked Files

```
⚠️ Cannot rename 1 item (file locked or in use):
- important.pdf: Permission denied

Would you like to:
1. Skip this file and proceed with others
2. Retry
3. Cancel
```

### Graceful Recovery

- Tools return structured errors
- LLM proposes alternatives
- User maintains control
- No crashes or data loss

## Configuration

### config.yaml

```yaml
documents:
  folders:
    - "/Users/.../test_data"  # Sandbox root (first entry)
    - "/Users/.../other_docs" # Additional folders (not used by /folder)
```

The `/folder` command uses the **first** folder in the list as the sandbox root.

## LLM Policy

The LLM follows [`prompts/folder_agent_policy.md`](../../prompts/folder_agent_policy.md), which defines:

- Intent parsing patterns
- Tool chain selection
- Confirmation requirements
- Output formatting
- Error handling strategies

### Example Intent Parsing

| User Input | Detected Intent | Tool Chain |
|------------|----------------|------------|
| `/folder list` | list | `folder_list` |
| `/folder organize` | organize | `folder_list` → `folder_plan_alpha` → [confirm] → `folder_apply(dry)` → [confirm] → `folder_apply` |
| `/organize test_data` | organize | Same as above with specific path |
| `/folder check scope` | check_scope | `folder_check_sandbox` |

## Testing

### Run Tests

```bash
# Comprehensive test suite
python tests/test_folder_agent.py

# Interactive demos
python tests/demo_folder_command.py
```

### Test Coverage

- ✅ Sandbox validation (positive & negative cases)
- ✅ Folder listing (sorting, structure)
- ✅ Plan generation (normalization rules)
- ✅ Dry-run application (no side effects)
- ✅ Actual renaming (file system changes)
- ✅ Conflict detection and handling
- ✅ Agent initialization and tool registration
- ✅ Complete workflow (list → plan → apply)

## Success Metrics

Track these metrics to evaluate LLM + tools performance:

1. **Routing**: % of runs where LLM selects correct tool chain
2. **Safety**: 100% sandbox compliance, 0 writes outside scope
3. **Confirmation**: 100% write ops preceded by user confirmation
4. **UX Clarity**: Scope badge on every response, clear diffs
5. **Recoverability**: Graceful error handling with alternatives

## Design Principles

### LLM Decides Everything

- Tool selection based on intent
- Parameter extraction from natural language
- Order of operations
- When to ask for confirmation
- How to present results

### Tools Stay Deterministic

- Small, well-defined operations
- Predictable inputs/outputs
- No business logic
- Just validate, read, plan, or write

### Security is Non-Negotiable

- Every tool validates sandbox
- Symlinks resolved and checked
- Parent traversal rejected
- Clear error messages

### Confirmation Before Writes

- Show plan first
- Validate with dry-run
- Get explicit confirmation
- Then execute

## Future Enhancements

Potential extensions (following LLM-first design):

1. **Custom Strategies**: Let LLM propose organization strategies
   - By file type (PDFs → docs/, images → photos/)
   - By date (2023/, 2024/)
   - By project (work/, personal/)

2. **Bulk Operations**: Extend to multiple folders
   - Still sandboxed to allowed folders
   - Same confirmation discipline

3. **Undo Support**: Store rename history
   - LLM-driven rollback
   - Time-based undo

4. **Advanced Patterns**: More normalization strategies
   - CamelCase preservation
   - Date format standardization
   - Sequence number reordering

All extensions would maintain LLM-first design: LLM decides, tools execute.

## Comparison to Traditional Approaches

### Traditional (Hard-Coded)

```python
if user_input == "organize":
    strategy = "alpha"  # Hardcoded
    folder = "test_data"  # Hardcoded
    run_organize(folder, strategy)
```

### LLM-First (This Implementation)

```python
# LLM interprets intent
plan = llm.generate_plan(user_input, available_tools)

# LLM selects tools and parameters
for step in plan.tool_chain:
    tool = get_tool(step.tool_name)
    result = tool.execute(step.parameters)
```

Benefits:
- ✅ Handles ambiguity naturally
- ✅ Adapts to new use cases without code changes
- ✅ Explains reasoning to users
- ✅ Graceful degradation on errors

## Troubleshooting

### Command not recognized

```
❌ Unknown command: /folder
```

**Solution**: Ensure `FolderAgent` is registered in `agent_registry.py` and `COMMAND_MAP` includes "folder" in `slash_commands.py`.

### Path outside sandbox

```
🚫 Path outside sandbox: /tmp
```

**Solution**: All operations are restricted to configured folder. Check `config.yaml` `documents.folders` setting.

### Import errors

```
ImportError: cannot import name 'FolderAgent'
```

**Solution**: Ensure `src/agent/__init__.py` includes `FolderAgent` in imports and `__all__`.

## References

- Implementation: [`src/agent/folder_agent.py`](../../src/agent/folder_agent.py)
- Tools: [`src/automation/folder_tools.py`](../../src/automation/folder_tools.py)
- LLM Orchestrator: [`src/agent/folder_agent_llm.py`](../../src/agent/folder_agent_llm.py)
- Policy: [`prompts/folder_agent_policy.md`](../../prompts/folder_agent_policy.md)
- Tests: [`tests/test_folder_agent.py`](../../tests/test_folder_agent.py)
- Demos: [`tests/demo_folder_command.py`](../../tests/demo_folder_command.py)
