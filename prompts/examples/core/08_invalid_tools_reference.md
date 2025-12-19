# Invalid Tools Reference

This document lists tools that **DO NOT EXIST** in the system. These are commonly hallucinated by LLMs but are not available.

## Critical Rule

**NEVER invent or assume tools exist.** You can ONLY use tools listed in the "Available Tools" section provided during planning.

## Invalid Tools List

### File Operations (DO NOT EXIST)

- ❌ `list_files` - **DOES NOT EXIST**
  - ✅ **Use instead**: `folder_list` (from Folder Agent) or `search_documents` (from File Agent for semantic search)
  - **Why**: File listing is handled by specialized agents, not a generic list_files tool

- ❌ `create_folder` - **DOES NOT EXIST**
  - ✅ **Use instead**: `organize_files` (creates folders automatically) or `folder_organize_by_type` (from Folder Agent)
  - **Why**: Folder creation is handled automatically by organization tools - no separate step needed

- ❌ `create_directory` - **DOES NOT EXIST**
  - ✅ **Use instead**: `organize_files` (creates directories automatically) or `folder_organize_by_type`
  - **Why**: Same as create_folder - directories are created automatically when organizing files

- ❌ `move_files` - **DOES NOT EXIST**
  - ✅ **Use instead**: `organize_files` (moves files as part of organization) or `folder_organize_by_type`
  - **Why**: File movement is handled by organization tools, not a standalone move operation

- ❌ `copy_files` - **DOES NOT EXIST**
  - ✅ **Use instead**: `organize_files` with `move_files=false` parameter
  - **Why**: File copying is handled by organization tools

- ❌ `delete_files` - **DOES NOT EXIST**
  - ✅ **Use instead**: No direct file deletion tool exists - this is intentional for safety
  - **Why**: File deletion is a destructive operation and is not supported

- ❌ `filter_files` - **DOES NOT EXIST**
  - ✅ **Use instead**: `organize_files` (uses LLM reasoning to filter) or `create_zip_archive` with `include_pattern`/`exclude_extensions`
  - **Why**: File filtering is handled by organization or archiving tools

### Document Operations (DO NOT EXIST)

- ❌ `create_pages_doc` - **DISABLED** (was available but unreliable)
  - ✅ **Use instead**: `create_keynote` (for presentations) or `create_local_document_report` (for PDF reports)
  - **Why**: Pages automation was unreliable, so it was disabled. Use Keynote or PDF reports instead.

### Generic Operations (DO NOT EXIST)

- ❌ `execute_command` - **DOES NOT EXIST**
  - ✅ **Use instead**: Use specific agent tools for the operation you need
  - **Why**: Direct command execution is not supported for security reasons

- ❌ `run_script` - **DOES NOT EXIST**
  - ✅ **Use instead**: Use specific agent tools for the operation you need
  - **Why**: Script execution is not supported for security reasons

## Common Patterns to Avoid

### ❌ WRONG Pattern:
```json
{
  "steps": [
    {"action": "list_files", "parameters": {"path": "/Documents"}},
    {"action": "create_folder", "parameters": {"name": "organized"}},
    {"action": "move_files", "parameters": {"files": [...], "destination": "organized"}}
  ]
}
```

### ✅ CORRECT Pattern:
```json
{
  "steps": [
    {"action": "organize_files", "parameters": {
      "category": "PDF files",
      "target_folder": "organized",
      "move_files": true
    }}
  ]
}
```

## Key Principles

1. **Check Available Tools First**: Always verify a tool exists in the "Available Tools" section before using it
2. **Use Complete Tools**: Many tools are "COMPLETE" or "STANDALONE" - they handle multiple operations in one step
3. **Read Tool Descriptions**: Tool descriptions explain what they can do - read them carefully
4. **When in Doubt**: If you're not sure a tool exists, don't use it. Use LLM reasoning to find an alternative approach with available tools.

## How to Handle Missing Capabilities

If you need a capability that doesn't seem to exist:

1. **Check if a similar tool exists**: Look for tools with similar names or purposes
2. **Check if a complete tool handles it**: Some tools like `organize_files` handle multiple operations
3. **Use LLM reasoning**: Chain available tools together to achieve the goal
4. **Return complexity="impossible"**: If truly impossible with available tools, return this in the plan

## Examples of Tool Substitution

| Invalid Tool | Valid Alternative |
|-------------|-------------------|
| `list_files` | `folder_list` or `search_documents` |
| `create_folder` | `organize_files` (creates automatically) |
| `move_files` | `organize_files` (moves as part of organization) |
| `create_pages_doc` | `create_keynote` or `create_local_document_report` |
| `filter_files` | `organize_files` or `create_zip_archive` with patterns |

---

**Remember**: When planning, you can ONLY use tools that are explicitly listed in the "Available Tools" section. If a tool is not listed, it does not exist.

