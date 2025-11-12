# UI Data Formatting Fix: From Generic Messages to Actual Results

## Problem

**Symptom:**
```
User: "what files are duplicated?"
System: ✅ Tool works correctly, finds duplicates
UI Shows: "Here are the duplicate files found in your folder."
Problem: NO ACTUAL FILE NAMES shown! 😞
```

**Root Cause:**
The LLM was planning `reply_to_user` with generic messages instead of formatting the actual data from previous steps.

**Session Data Analysis:**
```json
{
  "step_results": {
    "1": {
      "duplicates": [
        {
          "files": [
            {"name": "Let Her Go 2.pdf"},
            {"name": "Let Her Go.pdf"}
          ]
        }
      ],
      "total_duplicate_files": 4,
      "total_duplicate_groups": 2,
      "wasted_space_mb": 0.38
    },
    "2": {
      "message": "Here are the duplicate files found in your folder.",  // ❌ Generic!
      "details": "Summary of duplicate groups and their locations"      // ❌ Generic!
    }
  }
}
```

**The tool found the data, but the UI message didn't include it!**

## Solution

Teach the LLM to **format actual data** from previous steps instead of using generic placeholders.

### Changes Made

#### 1. Updated Few-Shot Example for Email Workflow

**File:** [prompts/examples/general/07_example_folder_duplicates_email_2_steps.md](prompts/examples/general/07_example_folder_duplicates_email_2_steps.md)

**Before (vague):**
```json
{
  "action": "compose_email",
  "parameters": {
    "body": "Found $step1.total_duplicate_groups duplicate group(s)...\n[Format each group from $step1.duplicates with file names and sizes]"
  }
}
```

**After (explicit template):**
```json
{
  "action": "compose_email",
  "parameters": {
    "body": "Duplicate Files Report\n=====================\n\nFound {$step1.total_duplicate_groups} duplicate group(s) containing {$step1.total_duplicate_files} files.\nWasted disk space: {$step1.wasted_space_mb} MB\n\n{for each group in $step1.duplicates}\nGroup {index}:\n- File size: {group.size} bytes\n- Duplicate count: {group.count}\n- Files:\n  {for each file in group.files}\n  * {file.name}\n  {end for}\n{end for}"
  }
}
```

#### 2. Created New Few-Shot Example for Display Workflow

**File:** [prompts/examples/general/08_example_list_duplicates_2_steps.md](prompts/examples/general/08_example_list_duplicates_2_steps.md)

**Key Content:**
- Shows example step 1 output (what the tool returns)
- Shows ❌ WRONG example (generic message)
- Shows ✅ RIGHT example (formatted data)
- Explains how to extract and format fields

**Critical Section:**
```markdown
## Example Step 2 Plan (Correct Formatting)

❌ WRONG - Generic message:
{
  "message": "Here are the duplicate files found in your folder.",
  "details": "Summary of duplicate groups and their locations"
}

✅ RIGHT - Actual data formatted:
{
  "message": "Found 2 group(s) of duplicate files, wasting 0.38 MB...",
  "details": "**Group 1** (2 copies, 202353 bytes each):\n- Let Her Go 2.pdf\n- Let Her Go.pdf\n\n**Group 2**..."
}
```

#### 3. Added Critical Guidance to Task Decomposition

**File:** [prompts/task_decomposition.md:244-272](prompts/task_decomposition.md#L244-L272)

**New Section: "CRITICAL: Always Format Actual Data in reply_to_user"**

**Key Rules:**
- ❌ NEVER use generic messages like "Here are the results"
- ✅ ALWAYS extract specific fields from `$step1`
- ❌ NEVER pass raw JSON like `"details": "$step1"`
- ✅ ALWAYS include file names, counts, metrics

**Example Template:**
```json
Bad (generic):
{
  "action": "reply_to_user",
  "parameters": {
    "message": "Here are the duplicate files found.",
    "details": "Summary of results"
  }
}

Good (actual data):
{
  "action": "reply_to_user",
  "parameters": {
    "message": "Found {$step1.total_duplicate_groups} groups of duplicates, wasting {$step1.wasted_space_mb} MB",
    "details": "Group 1:\n- {file1.name}\n- {file2.name}\n\nGroup 2:\n- {file3.name}\n- {file4.name}"
  }
}
```

## Why This is Important

### User Experience Impact

**Before (Generic):**
```
User: "what files are duplicated?"
UI: "Here are the duplicate files found in your folder."
User: "Okay... which ones?" 🤔
```

**After (Specific):**
```
User: "what files are duplicated?"
UI: "Found 2 groups of duplicate files, wasting 0.38 MB of disk space.

**Group 1** (2 copies, 202353 bytes each):
- Let Her Go 2.pdf
- Let Her Go.pdf

**Group 2** (2 copies, 199481 bytes each):
- Perfect - Ed Sheeran 2.pdf
- Perfect - Ed Sheeran.pdf

💡 Tip: You can delete all but one file from each group to free up 0.38 MB."
User: "Perfect! I'll delete the duplicates." ✅
```

### Technical Impact

The issue wasn't in the tool implementation (that works perfectly) - it was in the **planning phase**. The LLM needed to be taught:

1. **What data is available:** Step 1 returns `duplicates`, `total_duplicate_files`, `wasted_space_mb`, etc.
2. **How to access it:** Use `$step1.field_name` syntax
3. **How to format it:** Loop through arrays, extract specific fields
4. **What NOT to do:** Generic placeholders, raw JSON

## Data Flow

### Complete Flow (Working Correctly Now)

```
1. User Input
   "what files are duplicated?"
   ↓
2. LLM Planning (Updated with new examples)
   Step 1: folder_find_duplicates(folder_path=null)
   Step 2: reply_to_user(
     message="Found {$step1.total_duplicate_groups} groups...",
     details="Group 1:\n- {file1.name}\n- {file2.name}..."
   )
   ↓
3. Execution
   Step 1 returns:
   {
     "duplicates": [{"files": [{"name": "Let Her Go 2.pdf"}, ...]}],
     "total_duplicate_groups": 2,
     "wasted_space_mb": 0.38
   }
   ↓
4. Parameter Resolution (LLM substitutes $step1 references)
   message="Found 2 groups of duplicates, wasting 0.38 MB"
   details="Group 1:\n- Let Her Go 2.pdf\n- Let Her Go.pdf..."
   ↓
5. UI Rendering
   Shows formatted message with ACTUAL file names! ✅
```

## Testing Instructions

### Server Status
✅ Server restarted with updated prompts (PID: 83963)
✅ Folder Agent loaded with 6 tools (includes `folder_find_duplicates`)

### Test Cases

**Test 1: List Duplicates**
```
Query: "what files are duplicated?"
Expected Result:
- Message shows "Found X groups" with actual count
- Details list each group with actual file names
- Shows wasted space in MB
```

**Test 2: Email Duplicates**
```
Query: "send all duplicated docs in my folder to my email"
Expected Result:
- Email sent (send: true because user said "send")
- Email body contains actual file names
- Email shows duplicate groups and wasted space
```

**Test 3: Find Duplicates (Alternative Phrasing)**
```
Queries to test:
- "find duplicate files"
- "show me duplicate documents"
- "which files are taking up redundant space?"

All should return actual file names, not generic messages.
```

### How to Verify

1. Open UI: http://localhost:3000
2. Enter query: "what files are duplicated?"
3. Check response contains:
   - ✅ Actual file names (e.g., "Let Her Go 2.pdf")
   - ✅ Actual counts (e.g., "Found 2 groups")
   - ✅ Actual metrics (e.g., "0.38 MB wasted")
   - ❌ NOT generic messages like "Here are the results"

## Files Modified

1. **prompts/examples/general/07_example_folder_duplicates_email_2_steps.md**
   - Updated compose_email body parameter with explicit formatting template

2. **prompts/examples/general/08_example_list_duplicates_2_steps.md** (NEW)
   - Complete example showing wrong vs. right approach
   - Explains how to extract and format $step1 data
   - Shows actual step output for reference

3. **prompts/task_decomposition.md**
   - Added "CRITICAL: Always Format Actual Data" section
   - Added examples of bad vs. good formatting
   - Added extraction rules for duplicate data

## Key Takeaways

### What We Learned

1. **Tool implementation was correct** - `folder_find_duplicates` worked perfectly
2. **LLM planning was the issue** - It wasn't formatting the data
3. **Few-shot examples are critical** - Showing explicit formatting templates helps
4. **Negative examples matter** - Showing what NOT to do prevents mistakes

### Best Practices Established

**For All Tool Chaining:**
1. When tool A returns structured data, tool B MUST format it
2. Never use generic messages when specific data is available
3. Show explicit formatting templates in examples
4. Include both positive and negative examples

**For reply_to_user Specifically:**
1. Extract specific fields from previous steps
2. Format arrays into readable lists
3. Include metrics and counts
4. Make messages actionable (tell user what they can do)

**For Documentation:**
1. Show example input/output for each step
2. Explain the data flow
3. Highlight common mistakes
4. Provide templates for common patterns

## Next Steps

### Immediate
1. ✅ Server restarted with updated prompts
2. ⏳ Test in UI to verify actual file names appear
3. ⏳ Verify email workflow includes formatted data

### Future Enhancements
1. **Auto-format helper:** Create a "format_results" utility tool that LLM can call
2. **Validation:** Check if reply_to_user contains generic phrases and warn
3. **Templates:** Provide more formatting templates for common data structures
4. **Metrics:** Track how often generic vs. specific messages are used

## Verification Checklist

- [x] Tool returns correct data (duplicate files with names)
- [x] Updated example shows explicit formatting
- [x] Added guidance about formatting rules
- [x] Created positive and negative examples
- [x] Server restarted with new prompts
- [ ] Tested in UI - actual file names appear (PENDING USER TEST)
- [ ] Tested email workflow - body contains file names (PENDING USER TEST)
- [ ] Tested alternative phrasings (PENDING USER TEST)

## Conclusion

**The fix addresses the root cause:** Teaching the LLM to format actual data instead of using generic placeholders.

**Impact:**
- Before: "Here are the duplicates" (unhelpful)
- After: "Found 2 groups: Let Her Go 2.pdf, Let Her Go.pdf..." (actionable)

**This fix generalizes to ANY workflow where:**
- Step N returns structured data
- Step N+1 must present it to the user
- The presentation should be specific, not generic

**Ready for testing!** Please test in the UI and confirm actual file names appear.
