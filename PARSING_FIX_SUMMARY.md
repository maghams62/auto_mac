# Parsing Fix Summary

**Date:** 2025-11-11
**Issue:** Tool results not displaying in UI - showing generic "Command executed" or incomplete messages

## Problem Description

When using slash commands or natural language queries that trigger tools (e.g., `/bluesky`, `/search`), the UI would display generic messages like:
- "Here is the summary of your last three Blue Sky posts." (without actual summary content)
- "Command executed" (without actual result)

This affected multiple commands including:
- Bluesky summarization
- DuckDuckGo search
- Any tool returning results in `summary`, `content`, or `response` fields

## Root Cause

**TWO BUGS** were causing this issue:

### Bug #1: Message Field Extraction
Two locations in the codebase only checked for `"message"` field when extracting displayable content from tool results:

1. **[src/agent/agent.py](src/agent/agent.py):806** - Slash command result formatting
2. **[api_server.py](api_server.py):265** - `format_result_message()` function

However, different tools return results in different fields:
- Bluesky tools: `{"summary": "...", "items": [...]}`
- Search tools: `{"summary": "...", "results": [...]}`  (also has `message` field)
- Other tools: `{"content": "..."}` or `{"response": "..."}`

When these fields weren't found, the code fell back to:
- "Command executed" (generic default)
- JSON dump of entire result object (not user-friendly)

### Bug #2: Incorrect Status Determination
**[src/agent/agent.py](src/agent/agent.py):813** - Status was incorrectly determined:

```python
"status": "success" if tool_result.get("success") else "error"
```

**The Problem:**
- Search results don't have a `"success"` field
- So they were being marked as `"error"` status
- UI or middleware might ignore messages with error status
- This compounded Bug #1 by hiding the extracted message

## Solution

### Fix #1: Message Field Extraction
Updated both locations to check multiple possible fields in priority order:

#### 1a. Fixed [src/agent/agent.py](src/agent/agent.py):804-811

**Before:**
```python
message = tool_result.get("message", "Command executed")
```

**After:**
```python
message = (
    tool_result.get("message") or
    tool_result.get("summary") or
    tool_result.get("content") or
    tool_result.get("response") or
    "Command executed"
)
```

#### 1b. Fixed [api_server.py](api_server.py):283-292

**Before:**
```python
if "message" in result:
    return result["message"]
return json.dumps(result, indent=2)
```

**After:**
```python
if "message" in result:
    return result["message"]
elif "summary" in result:
    return result["summary"]
elif "content" in result:
    return result["content"]
elif "response" in result:
    return result["response"]
return json.dumps(result, indent=2)
```

### Fix #2: Status Determination
Fixed [src/agent/agent.py](src/agent/agent.py):812-823 to intelligently determine status:

**Before:**
```python
return {
    "status": "success" if tool_result.get("success") else "error",
    "message": message,
    ...
}
```

**After:**
```python
# Determine status: only mark as error if there's an explicit error field
# Otherwise, default to success if we have a message/summary/content
is_error = tool_result.get("error") is True
has_content = bool(message and message != "Command executed")
status = "error" if is_error else ("success" if has_content else "completed")

return {
    "status": status,
    "message": message,
    ...
}
```

**Why This Works:**
- ❌ Old logic: Assumed missing `"success"` field = error
- ✅ New logic: Only marks as error if `"error"` field is explicitly `True`
- ✅ Marks as "success" if we extracted actual content (message/summary/etc.)
- ✅ Marks as "completed" for edge cases with no content

## Testing

### Test Suite #1: Message Field Extraction
Created comprehensive test suite in [test_parsing_fix.py](test_parsing_fix.py) that validates:

✅ **Test 1:** Bluesky summary format (`{"summary": "..."}`)
✅ **Test 2:** Regular message format (`{"message": "..."}`)
✅ **Test 3:** Content format (`{"content": "..."}`)
✅ **Test 4:** Error format (`{"error": true, "error_message": "..."}`)

**Result:** 4/4 tests passed

### Test Suite #2: Status Determination
Created test suite in [test_status_fix.py](test_status_fix.py) that validates:

✅ **Test 1:** Search result with summary (no 'success' field) → Status: success ✅
✅ **Test 2:** Result with explicit error → Status: error ✅
✅ **Test 3:** Empty result (fallback message) → Status: completed ✅
✅ **Test 4:** Result with explicit success field → Status: success ✅

**Result:** 4/4 tests passed

## Affected Commands

This fix resolves display issues for:

### Bluesky Integration
- `/bluesky summarize "query"`
- `Summarize the last 3 tweets on Bluesky`
- `/bluesky last 3 tweets`

### Search
- `/search <query>`
- `Search for <topic>`
- DuckDuckGo searches

### Any Tool Using Alternative Response Fields
- Tools returning `content` field
- Tools returning `response` field
- Tools returning `summary` field

## Verification

1. ✅ Message field extraction tested with unit tests (4/4 passed)
2. ✅ Status determination tested with unit tests (4/4 passed)
3. ✅ Bluesky integration confirmed working
4. ✅ Search integration confirmed working
5. ✅ Backward compatibility maintained (tools with `message` field still work)
6. ✅ Graceful fallback to JSON dump if no known fields found
7. ✅ Error cases handled correctly (explicit `error` field)

## Impact

**Before Fix:**
```
User: "Summarize the last 3 tweets on Bluesky"
Bot: "Here is the summary of your last three Blue Sky posts."
     [no actual summary shown]
```

**After Fix:**
```
User: "Summarize the last 3 tweets on Bluesky"
Bot: "### Overview
     Recent posts highlight testing and exploration [1], [2].

     ### Key Takeaways
     - Testing integration [1]
     - Exploring features [2]

     ### Links
     - [Post 1](https://bsky.app/profile/...)
     - [Post 2](https://bsky.app/profile/...)"
```

## Files Modified

1. [src/agent/agent.py](src/agent/agent.py)
   - Lines 804-811: Message field extraction (Fix #1a)
   - Lines 812-823: Status determination logic (Fix #2)
2. [api_server.py](api_server.py)
   - Lines 283-292: format_result_message() function (Fix #1b)
3. [test_parsing_fix.py](test_parsing_fix.py) - New test file for message extraction
4. [test_status_fix.py](test_status_fix.py) - New test file for status determination

## Recommendation for Tool Developers

When creating new tools, return results with one of these fields for best UI compatibility:
1. `message` - Preferred for simple success messages
2. `summary` - For LLM-generated summaries
3. `content` - For content-heavy results
4. `response` - For API responses

Always include user-friendly text in these fields rather than raw data structures.

---

**Status:** ✅ Fixed and Tested (TWO critical bugs resolved)
**Version:** v2.0 (Complete Fix)
**Author:** Claude Code Agent
**Test Results:** 8/8 tests passed (4 message extraction + 4 status determination)
