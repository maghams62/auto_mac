# Anti-Hallucination System: Multi-Layer Defense

## Overview

We've implemented a **defense-in-depth** strategy to prevent tool hallucination. The LLM cannot bypass these checks.

## Problem

LLMs can "hallucinate" tools that don't exist:
- `list_files`
- `create_folder`
- `create_directory`
- `move_files`
- etc.

This causes plans to fail when execution tries to call non-existent tools.

---

## Solution: 3-Layer Defense

```
┌─────────────────────────────────────────────────────────────┐
│         Layer 1: Prompt Engineering (Soft Constraint)       │
│  - Clear tool list in prompts                              │
│  - Explicit warnings about non-existent tools              │
│  - Visual emphasis with borders and warnings               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│    Layer 2: Programmatic Validation (Hard Constraint)      │
│  - PlanValidator checks every tool exists                  │
│  - Runs IMMEDIATELY after plan creation                    │
│  - BLOCKS invalid plans from entering system               │
│  - Cannot be bypassed by prompt manipulation               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│      Layer 3: Execution-Time Validation (Last Resort)      │
│  - Executor checks tool exists before calling              │
│  - Returns clear error if tool not found                   │
│  - Prevents crashes from invalid tool calls                │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Prompt Engineering

### Location
- `src/orchestrator/prompts.py`

### Implementation

**Planner System Prompt**:
```python
⚠️ CRITICAL RULES:
1. You can ONLY use tools listed in "Available Tools" section
2. NEVER invent or assume tools exist (like "list_files", "create_folder", "create_directory")
3. READ the tool descriptions carefully - some tools are COMPLETE and do everything in one step
```

**Planner Task Prompt**:
```python
═══════════════════════════════════════════════════════════════════════════
⚠️  AVAILABLE TOOLS - YOU CAN ONLY USE THESE TOOLS (NO OTHER TOOLS EXIST!)
═══════════════════════════════════════════════════════════════════════════

{tool_specs}

═══════════════════════════════════════════════════════════════════════════

IMPORTANT REMINDERS:
- Tools like "list_files", "create_folder", "create_directory", "move_files" DO NOT EXIST
- If you need file operations, check if "organize_files" can do it (it's COMPLETE/STANDALONE)
```

**Evaluator Validation Prompt**:
```python
⚠️ CRITICAL: Check that EVERY tool used in the plan exists in the tool list above.
If you see tools like "list_files", "create_folder", "create_directory", "move_files" - these are INVALID!
```

### Limitations
- LLMs can sometimes ignore prompts
- Not 100% reliable
- This is why we need Layer 2

---

## Layer 2: Programmatic Validation ⭐ **KEY DEFENSE**

### Location
- `src/orchestrator/validator.py` - Validation logic
- `src/orchestrator/nodes.py:86-104` - Integration into planner

### Implementation

```python
class PlanValidator:
    """
    Programmatic validator that enforces hard constraints.
    This is NOT LLM-based - it's deterministic code.
    """

    def __init__(self, available_tools):
        self.tool_names = {tool["name"] for tool in available_tools}

    def validate_plan(self, plan):
        errors = []

        for step in plan:
            tool_name = step.get("tool")

            # CRITICAL CHECK: Does tool exist?
            if tool_name not in self.tool_names:
                errors.append({
                    "error_type": "hallucinated_tool",
                    "message": f"Tool '{tool_name}' does not exist. Available tools: {self.tool_names}",
                    "severity": "error",
                    "suggested_tools": self._suggest_similar_tools(tool_name)
                })

        has_errors = any(e["severity"] == "error" for e in errors)
        return not has_errors, errors
```

### Integration

**In PlannerNode** ([nodes.py:86-104](src/orchestrator/nodes.py#L86-L104)):
```python
# After LLM creates plan
plan_steps = self._parse_plan(response_text)

# ⚠️ CRITICAL: Programmatic validation BEFORE storing
validator = PlanValidator(state["tool_specs"])
is_valid, validation_errors = validator.validate_plan(plan_steps)

if not is_valid:
    logger.error("❌ PROGRAMMATIC VALIDATION FAILED")
    for error in validation_errors:
        logger.error(f"  {error['message']}")

    # Force replanning with feedback
    state["notes"].append(f"VALIDATION FAILED: {error_messages}")
    state["need_replan"] = True
    return state

# Only store plan if validation passed
state["plan"] = plan_steps
```

### What It Catches

1. **Hallucinated Tools**
   ```python
   Tool 'list_files' does not exist
   Suggested alternatives: ['organize_files']
   ```

2. **Forward Dependencies** (cycles)
   ```python
   Step depends on future step - this creates a cycle
   ```

3. **Missing Dependencies**
   ```python
   Step depends on non-existent step 'step_99'
   ```

4. **Self-Dependencies**
   ```python
   Step cannot depend on itself
   ```

5. **Dependency Cycles**
   ```python
   Cycle detected: step_1 -> step_2 -> step_3 -> step_1
   ```

### Key Features

**Hallucination Detection with Suggestions**:
```python
def _suggest_similar_tools(self, hallucinated_tool):
    """Suggest correct tools based on hallucinated tool name."""

    hallucination_map = {
        "list_files": ["organize_files"],
        "create_folder": ["organize_files"],
        "create_directory": ["organize_files"],
        "move_files": ["organize_files"],
        "send_email": ["compose_email"],
        "make_presentation": ["create_keynote", "create_keynote_with_images"],
    }

    return hallucination_map.get(hallucinated_tool, [])
```

**Example Error Output**:
```
❌ PROGRAMMATIC VALIDATION FAILED
  hallucinated_tool: Tool 'create_folder' does not exist. Available tools: ['search_documents', 'extract_section', 'take_screenshot', 'compose_email', 'create_keynote', 'create_keynote_with_images', 'create_pages_doc', 'organize_files']
  Suggested alternatives: ['organize_files']
```

---

## Layer 3: Execution-Time Validation

### Location
- `src/orchestrator/executor.py:166-175`

### Implementation

```python
def _execute_step(self, step, state):
    action = step.get("action")
    tool = self.tools.get(action)

    if not tool:
        return {
            "error": True,
            "error_type": "ToolNotFound",
            "error_message": f"Tool '{action}' not found",
            "retry_possible": False
        }

    # Execute tool...
```

### Purpose
- Last line of defense
- Catches any tools that somehow bypass validation
- Prevents crashes from invalid tool calls
- Returns clean error messages

---

## Workflow Example

### Scenario: LLM Hallucinates "create_folder"

```
User Request: "Organize music files into a folder called music_stuff"

┌─────────────────────────────────────────────────────────────┐
│ Step 1: LLM Planning                                        │
├─────────────────────────────────────────────────────────────┤
│ LLM creates plan with hallucinated tool:                    │
│   Step 1: create_folder(name="music_stuff")  ❌            │
│   Step 2: move_files(...)                     ❌            │
└─────────────────────────────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Programmatic Validation (Layer 2)                  │
├─────────────────────────────────────────────────────────────┤
│ PlanValidator checks each tool:                             │
│   ❌ Tool 'create_folder' does not exist                   │
│   ❌ Tool 'move_files' does not exist                      │
│                                                              │
│ Suggested: Use 'organize_files' instead                     │
│                                                              │
│ RESULT: Validation FAILED, plan BLOCKED                     │
└─────────────────────────────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Automatic Replanning                                │
├─────────────────────────────────────────────────────────────┤
│ Feedback to planner:                                         │
│   "VALIDATION FAILED: Tool 'create_folder' does not exist.  │
│    Available tools: [search_documents, ..., organize_files] │
│    Suggested: Use organize_files"                           │
│                                                              │
│ LLM creates NEW plan:                                       │
│   Step 1: organize_files(                                   │
│     category="music files",                                 │
│     target_folder="music_stuff"                             │
│   ) ✅                                                       │
└─────────────────────────────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Second Validation                                   │
├─────────────────────────────────────────────────────────────┤
│ PlanValidator checks:                                        │
│   ✅ Tool 'organize_files' exists                           │
│   ✅ Parameters valid                                       │
│   ✅ No dependency issues                                   │
│                                                              │
│ RESULT: Validation PASSED, plan ACCEPTED                    │
└─────────────────────────────────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 5: Execution                                           │
├─────────────────────────────────────────────────────────────┤
│ Executor runs: organize_files(...)                          │
│ ✅ SUCCESS                                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Testing

### Test Invalid Tool Rejection

```python
# Create a plan with hallucinated tool
plan = [
    {"id": "step_1", "tool": "create_folder", "inputs": {"name": "test"}}
]

# Validate
validator = PlanValidator(available_tools)
is_valid, errors = validator.validate_plan(plan)

assert not is_valid  # Should be invalid
assert errors[0]["error_type"] == "hallucinated_tool"
assert "create_folder" in errors[0]["message"]
assert "organize_files" in errors[0]["suggested_tools"]
```

### Test Valid Tool Acceptance

```python
# Create a plan with valid tool
plan = [
    {
        "id": "step_1",
        "tool": "organize_files",
        "inputs": {
            "category": "music files",
            "target_folder": "music_stuff"
        }
    }
]

# Validate
is_valid, errors = validator.validate_plan(plan)

assert is_valid  # Should be valid
assert len(errors) == 0
```

---

## Guarantees

✅ **Hallucinated tools CANNOT enter the system**
- Blocked by Layer 2 programmatic validation
- LLM cannot bypass code-level checks

✅ **Automatic recovery via replanning**
- Invalid plans trigger replanning with detailed feedback
- Suggestions guide LLM to correct tools

✅ **No crashes from invalid tools**
- Layer 3 catches any tools that somehow get through
- Returns clean errors instead of crashing

✅ **Full audit trail**
- All validation errors logged
- Clear feedback about what went wrong
- Suggestions for fixes

---

## Future Enhancements

1. **Tool Usage Statistics**: Track which tools LLM tries to hallucinate most
2. **Automated Few-Shot Learning**: Add examples of correct plans to prompts
3. **Tool Registry**: Dynamic tool registration with automatic validation
4. **Stricter Parameter Validation**: Check parameter types and ranges
5. **Tool Capability Hints**: Embed tool capabilities in the catalog for better LLM understanding
