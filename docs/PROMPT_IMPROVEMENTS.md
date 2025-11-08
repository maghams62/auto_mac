# Prompt Improvements: Clear Tool Availability

## Problem

The planner was inventing non-existent tools like:
- `list_files`
- `create_folder`
- `create_directory`
- `move_files`

Instead of using the actual available tools like `organize_files`.

## Root Cause

The prompts didn't make it **crystal clear** which tools are available and that these are the ONLY tools that exist.

## Solution

Updated all orchestrator prompts to:
1. **Prominently display available tools**
2. **Explicitly forbid inventing tools**
3. **List common invalid tools**
4. **Emphasize COMPLETE/STANDALONE tools**

---

## Changes Made

### 1. Planner System Prompt ([prompts.py:5-50](src/orchestrator/prompts.py#L5-L50))

**Before**:
```
Your role is to analyze goals and create structured, executable plans using available tools.

Key Requirements:
1. Output ONLY a JSON array of Steps - no prose, no explanations
2. Each step must use tools from tool_specs only - never invent tools
```

**After**:
```
Your role is to analyze goals and create structured, executable plans using ONLY the available tools.

⚠️ CRITICAL RULES:
1. You can ONLY use tools listed in "Available Tools" section
2. NEVER invent or assume tools exist (like "list_files", "create_folder", "create_directory")
3. READ the tool descriptions carefully - some tools are COMPLETE and do everything in one step
4. If a tool says "COMPLETE" or "STANDALONE", don't break it into sub-steps

Key Requirements:
1. Output ONLY a JSON array of Steps - no prose, no explanations
2. Each step must use tools from the provided tool list ONLY
```

### 2. Planner Task Prompt ([prompts.py:52-74](src/orchestrator/prompts.py#L52-L74))

**Before**:
```
Goal: {goal}
Context: {context}
Available Tools:
{tool_specs}
Create a plan to achieve the goal.
```

**After**:
```
Goal: {goal}
Context: {context}

═══════════════════════════════════════════════════════════════════════════
⚠️  AVAILABLE TOOLS - YOU CAN ONLY USE THESE TOOLS (NO OTHER TOOLS EXIST!)
═══════════════════════════════════════════════════════════════════════════

{tool_specs}

═══════════════════════════════════════════════════════════════════════════

IMPORTANT REMINDERS:
- Tools like "list_files", "create_folder", "create_directory", "move_files" DO NOT EXIST
- If you need file operations, check if "organize_files" can do it (it's COMPLETE/STANDALONE)
- READ each tool's "strengths" section to understand what it can do
- Some tools handle multiple operations in ONE step

Create a plan to achieve the goal using ONLY the tools listed above.
```

### 3. Evaluator System Prompt ([prompts.py:76-89](src/orchestrator/prompts.py#L76-L89))

**Before**:
```
1. PRE-EXECUTION VALIDATION (full):
   - DAG soundness: No cycles, all deps exist, topological order possible
   - Tool validity: All tools exist in tool_specs
   - IO presence: All required inputs provided or computable from deps
```

**After**:
```
1. PRE-EXECUTION VALIDATION (full):
   - DAG soundness: No cycles, all deps exist, topological order possible
   - Tool validity: ALL tools must exist in tool_specs - Flag ANY tool not in the list as "missing_tool" error
   - Common invalid tools: "list_files", "create_folder", "create_directory", "move_files" - these DO NOT EXIST
   - IO presence: All required inputs provided or computable from deps
```

### 4. Evaluator Validation Prompt ([prompts.py:130-146](src/orchestrator/prompts.py#L130-L146))

**Before**:
```
Perform PRE-EXECUTION validation on this plan.

Goal: {goal}
Plan: {plan}
Tool Specs: {tool_specs}
Budget: {budget}

Validate the plan and return a JSON response.
```

**After**:
```
Perform PRE-EXECUTION validation on this plan.

Goal: {goal}
Plan: {plan}

═══════════════════════════════════════════════════════════════════════════
AVAILABLE TOOLS (these are the ONLY valid tools):
═══════════════════════════════════════════════════════════════════════════
{tool_specs}
═══════════════════════════════════════════════════════════════════════════

Budget: {budget}

⚠️ CRITICAL: Check that EVERY tool used in the plan exists in the tool list above.
If you see tools like "list_files", "create_folder", "create_directory", "move_files" - these are INVALID!

Validate the plan and return a JSON response with any invalid tools flagged as "missing_tool" errors.
```

---

## Expected Behavior

### Before Fix:
```
Request: "Move all non-PDF files into a folder called 'misc_stuff'"

Plan created:
  Step 1: list_files (directory="test_data")         ❌ INVALID TOOL
  Step 2: filter_files (by_extension="!pdf")         ❌ INVALID TOOL
  Step 3: create_directory (name="misc_stuff")       ❌ INVALID TOOL
  Step 4: move_files (files=$step2.files)            ❌ INVALID TOOL

Result: All steps fail with "Tool not found"
```

### After Fix:
```
Request: "Move all non-PDF files into a folder called 'misc_stuff'"

Plan created:
  Step 1: organize_files                             ✅ VALID TOOL
    Parameters:
      category: "non-PDF files"
      target_folder: "misc_stuff"
      move_files: true

Result: organize_files handles everything in ONE step:
  - Scans directory
  - LLM categorizes files
  - Creates folder
  - Moves files
  - Returns detailed reasoning
```

---

## Key Improvements

### 1. **Visual Separation**
Using `═══` lines to make tool lists stand out visually in the prompt

### 2. **Explicit Warnings**
Warning symbols (⚠️) draw attention to critical rules

### 3. **Specific Examples**
Listing exact tool names that DON'T exist helps LLM avoid them

### 4. **Tool Capability Hints**
Reminding planner to check if tools are "COMPLETE/STANDALONE"

### 5. **Validation Strengthening**
Evaluator now explicitly checks for commonly invented tools

---

## Testing Recommendations

1. **Test Invalid Tool Detection**:
   ```python
   # Planner should NOT create plans with these tools
   invalid_tools = ["list_files", "create_folder", "create_directory", "move_files"]
   ```

2. **Test Standalone Tool Recognition**:
   ```python
   # Request: "Organize music files"
   # Should create 1-step plan with organize_files
   # NOT multi-step plan with folder creation + file moving
   ```

3. **Test Evaluator Catching**:
   ```python
   # If planner somehow creates invalid plan,
   # evaluator should flag "missing_tool" errors
   # and force replanning
   ```

---

## Future Enhancements

1. **Tool Registry Validation**: Programmatically validate tool names before LLM planning
2. **Few-Shot Examples**: Add examples of correct vs incorrect plans
3. **Tool Suggestions**: If planner tries invalid tool, suggest closest valid alternative
4. **Dynamic Tool Loading**: Tools could register themselves with descriptions
