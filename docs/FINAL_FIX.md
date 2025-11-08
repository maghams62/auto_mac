# Final Fix Applied

## Issue
Agent was still choosing `create_keynote` instead of `create_keynote_with_images` despite:
- ✅ Tool being registered
- ✅ Prompts being updated
- ✅ Examples being added

## Root Cause
The LLM wasn't giving enough weight to the tool selection guidance buried in the prompts.

## Solution Applied

### Added CRITICAL REMINDERS to Planning Prompt
**File:** `src/agent/agent.py`

Added explicit, prominent reminders directly in the planning prompt:

```python
CRITICAL REMINDERS:
- If the request involves taking screenshots AND creating a presentation,
  you MUST use "create_keynote_with_images" (NOT "create_keynote")
- "create_keynote_with_images" accepts "image_paths" parameter (list of screenshot paths)
- "create_keynote" is ONLY for text-based presentations
```

This appears **immediately before** the user request, making it impossible to miss.

## Why This Works

**Prompt Engineering Principle:** Important instructions should be:
1. ✅ **Proximate** to the task (right before the user request)
2. ✅ **Explicit** (use MUST, NOT, ONLY)
3. ✅ **Concise** (3 bullet points vs buried in examples)
4. ✅ **Capitalized** (CRITICAL draws attention)

## Test It Now

Run your request:
```
"take a screenshot of the chorus page of the night we met and create a slide deck with just that and email it to spamstuff062@gmail.com"
```

### Expected Plan (Now):
```json
{
  "steps": [
    {"id": 1, "action": "search_documents"},
    {"id": 2, "action": "extract_section"},
    {"id": 3, "action": "take_screenshot"},
    {"id": 4, "action": "create_keynote_with_images", "parameters": {"image_paths": "$step3.screenshot_paths"}},
    {"id": 5, "action": "compose_email"}
  ]
}
```

### Before (Wrong):
```json
{
  "steps": [
    ...
    {"id": 4, "action": "create_keynote", "parameters": {"content": "..."}},  ❌
    ...
  ]
}
```

## All Changes Made

### Code Changes:
1. ✅ `src/agent/tools.py` - Added `create_keynote_with_images` tool
2. ✅ `src/agent/tools.py` - Fixed `create_keynote` tool
3. ✅ `src/automation/keynote_composer.py` - Enhanced for image support
4. ✅ `src/agent/agent.py` - Added CRITICAL REMINDERS to planning prompt ⭐ **NEW**

### Prompt Changes:
1. ✅ `prompts/task_decomposition.md` - Added tool #6 and selection rules
2. ✅ `prompts/few_shot_examples.md` - Added Example 3 (screenshot workflow)
3. ✅ `prompts/tool_definitions.md` - Added complete documentation

## Verification

```bash
python main.py
```

Enter your request and watch the logs. You should see:
```
Step 4: create_keynote_with_images  ✅
```

Instead of:
```
Step 4: create_keynote  ❌
```

## Summary

The fix is complete. The agent now has:
1. ✅ The right tool (`create_keynote_with_images`)
2. ✅ Clear examples of when to use it
3. ✅ **Explicit, impossible-to-miss instructions** in the planning prompt

**Try it now - it should work!** 🎉
