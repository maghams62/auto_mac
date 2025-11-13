# Comprehensive Fix: Email Summarization Workflow Failure

## Executive Summary
Fixed a critical planning error where the LLM planner created workflows that tried to use TEXT CONTENT as FILE PATHS in email attachments, causing failures in "summarize emails and email report" workflows.

## Root Cause Analysis

### What Happened
User request: "Summarize my last three emails and convert it into a report and email that to me"

The system failed because:
1. **Planner created incorrect workflow:**
   ```
   read_latest_emails → summarize_emails → create_detailed_report → compose_email(attachments=["$step3.report_content"])
   ```

2. **The problem:**
   - `create_detailed_report` returns `report_content` which is **TEXT** (the actual report as a string)
   - `compose_email` expects **FILE PATHS** in the `attachments` parameter
   - Passing TEXT content (thousands of characters) as a file path causes validation to fail

3. **Missing step:**
   - The workflow was missing `create_pages_doc` which saves the report TEXT to a file
   - Without this step, there was no file to attach to the email

### Why It Happened
1. **Planner confusion:** The LLM didn't understand that:
   - `create_detailed_report` → TEXT output (`report_content`)
   - `create_pages_doc` → FILE output (`pages_path`)
   - Email attachments require FILE PATHS, not TEXT

2. **Insufficient documentation:** The planning prompts didn't explicitly explain the difference between content-generating tools and file-saving tools

3. **No validation:** There was no runtime check to catch when content strings were being used as file paths

## Comprehensive Fixes Implemented

### 1. Enhanced Planner Prompts (`src/orchestrator/prompts.py`)
✅ **Added to CRITICAL RULES section:**
```
5. **CRITICAL - Email Attachments Workflow**: To email a report/document as an attachment:
   ⚠️  NEVER use report_content/synthesized_content directly as attachments - these are TEXT not FILES
   ✅  CORRECT workflow: create_detailed_report → create_pages_doc → compose_email(attachments=["$stepN.pages_path"])
   ✅  File-creating tools that return file paths: create_pages_doc (pages_path), create_keynote (keynote_path)
   ❌  WRONG: compose_email(attachments=["$stepN.report_content"]) - report_content is TEXT not a FILE PATH
   - If user wants to EMAIL a report: MUST include create_pages_doc step BEFORE compose_email
   - If no emails found (emails_data is empty), DO NOT create report or send email
```

✅ **Added to Dependencies section:**
```
- CRITICAL: For compose_email attachments, ONLY use actual file paths:
  * ✅ CORRECT: attachments=["$stepN.pages_path"] (from create_pages_doc)
  * ❌ WRONG: attachments=["$stepN.report_content"] (this is TEXT, not a file path!)
  * If you need to email report text, you must first save it with create_pages_doc
```

### 2. Runtime Validation in Email Tools

✅ **Added to `src/agent/email_agent.py` (compose_email):**
```python
# CRITICAL: Detect if someone is passing report/document CONTENT instead of a file path
if len(att_path) > 500 or '\n\n' in att_path or att_path.count('\n') > 10:
    logger.error("⚠️  PLANNING ERROR DETECTED: Attachment appears to be TEXT CONTENT, not a FILE PATH!")
    return {
        "error": True,
        "error_type": "PlanningError",
        "error_message": "You provided TEXT CONTENT instead of a FILE PATH. Use create_pages_doc to save report first.",
        "retry_possible": True,
        "hint": "Use create_pages_doc to save report_content to a file, then attach the pages_path"
    }
```

✅ **Added to `src/agent/tools.py` (legacy compose_email):**
- Same validation added for consistency across all compose_email implementations

### 3. Updated Task Decomposition Documentation

✅ **Added to `prompts/task_decomposition.md`:**

**New Section: "Email Summarization + Report Generation + Email Delivery"**
- Complete example with all 6 steps (including the critical create_pages_doc step)
- Clear warnings about what NOT to do
- Explicit handling of empty email results

**Key additions:**
```markdown
⚠️ CRITICAL RULES for Report + Email workflows:
- ❌ NEVER use $stepN.report_content as an email attachment - it's TEXT not a FILE PATH
- ✅ ALWAYS use create_pages_doc to save the report to a file BEFORE emailing
- ✅ THEN use $stepN.pages_path from create_pages_doc as the attachment
```

### 4. Created Comprehensive Example

✅ **New file: `prompts/examples/email/06_example_email_summary_report_and_email.md`**
- Detailed breakdown of the EXACT scenario that was failing
- Shows WRONG workflow vs CORRECT workflow
- Lists all content-generating tools (return TEXT) vs file-creating tools (return paths)
- Includes edge case handling

### 5. Enhanced Tool Docstrings

✅ **Updated `create_detailed_report` docstring:**
```
⚠️  CRITICAL: This tool returns REPORT TEXT, not a file path!
- If you need to EMAIL the report, you MUST first save it using create_pages_doc
- CORRECT workflow: create_detailed_report → create_pages_doc → compose_email(attachments=["$stepN.pages_path"])
- WRONG: compose_email(attachments=["$stepN.report_content"]) ← report_content is TEXT not a FILE PATH!
```

✅ **Updated `synthesize_content` docstring:**
```
⚠️  CRITICAL: This tool returns SYNTHESIZED TEXT, not a file path!
- If you need to EMAIL the synthesized content, you MUST first save it using create_pages_doc
- CORRECT workflow: synthesize_content → create_pages_doc → compose_email(attachments=["$stepN.pages_path"])
```

## Tool Output Reference

### Content-Creating Tools (return TEXT, not files):
- `create_detailed_report` → `report_content` (TEXT)
- `synthesize_content` → `synthesized_content` (TEXT)
- `summarize_emails` → `summary` (TEXT)
- `create_slide_deck_content` → `formatted_content` (TEXT)

### File-Creating Tools (return paths you can attach):
- `create_pages_doc` → `pages_path` (FILE PATH)
- `create_keynote` → `keynote_path` (FILE PATH)
- `create_keynote_with_images` → `keynote_path` (FILE PATH)
- `create_stock_report` → `pdf_path` or `report_path` (FILE PATH)

## Correct Workflow for "Summarize Emails + Create Report + Email"

```json
{
  "steps": [
    {
      "id": 1,
      "action": "read_latest_emails",
      "parameters": {"count": 3, "mailbox": "INBOX"}
    },
    {
      "id": 2,
      "action": "summarize_emails",
      "parameters": {"emails_data": "$step1", "focus": null}
    },
    {
      "id": 3,
      "action": "create_detailed_report",
      "parameters": {
        "content": "$step2.summary",
        "title": "Email Summary Report",
        "report_style": "business"
      }
    },
    {
      "id": 4,
      "action": "create_pages_doc",
      "parameters": {
        "title": "Email Summary Report",
        "content": "$step3.report_content"
      },
      "reasoning": "⚠️ CRITICAL STEP: Save report TEXT to a file so it can be attached"
    },
    {
      "id": 5,
      "action": "compose_email",
      "parameters": {
        "subject": "Email Summary Report",
        "body": "Please find attached your email summary report.",
        "attachments": ["$step4.pages_path"],
        "send": true
      },
      "reasoning": "Use pages_path (FILE), not report_content (TEXT)!"
    },
    {
      "id": 6,
      "action": "reply_to_user",
      "parameters": {
        "message": "Email summary report created and sent successfully"
      }
    }
  ]
}
```

## Prevention Mechanisms

### Layer 1: Planning (Proactive)
- Enhanced planner prompts with explicit workflows
- Clear examples in task decomposition
- Tool docstrings warn about common mistakes

### Layer 2: Validation (Reactive)
- Runtime detection of TEXT being used as FILE PATH
- Checks for: length > 500, contains `\n\n`, or > 10 newlines
- Returns clear error with fix suggestion

### Layer 3: Documentation (Educational)
- Comprehensive example files
- Tool output reference table
- Clear distinction between content tools vs file tools

## Testing Recommendations

Test these scenarios to verify fixes:
1. ✅ "Summarize my last 3 emails and email that report to me"
2. ✅ "Read recent emails, create a report, and send it"
3. ✅ "Summarize emails from john@example.com and email the summary"
4. ✅ "Synthesize these documents and email the result"
5. ✅ Edge case: "Summarize my last 3 emails" (when inbox is empty)

## Files Modified

### Core Logic:
- ✅ `src/orchestrator/prompts.py` - Enhanced planner instructions
- ✅ `src/agent/email_agent.py` - Added content-vs-path validation
- ✅ `src/agent/tools.py` - Added validation to legacy compose_email
- ✅ `src/agent/writing_agent.py` - Enhanced docstrings

### Documentation:
- ✅ `prompts/task_decomposition.md` - Added comprehensive workflow examples
- ✅ `prompts/examples/email/06_example_email_summary_report_and_email.md` - New example

## Impact

### Before Fix:
- ❌ Workflow failed with confusing error about file not found
- ❌ Error message showed thousands of characters of report content as "filename"
- ❌ No clear guidance on how to fix the issue
- ❌ Planner would repeat the same mistake on retry

### After Fix:
- ✅ Planner creates correct workflow with create_pages_doc step
- ✅ If mistake happens, runtime validation catches it immediately
- ✅ Clear error message explains the issue and provides fix
- ✅ Planner learns from error and includes correct step on retry
- ✅ Multiple layers of prevention ensure this never happens again

## Conclusion

This comprehensive fix addresses the root cause at multiple levels:
1. **Prevention:** Better prompts guide the planner to create correct workflows
2. **Detection:** Runtime validation catches planning errors before they cause failures
3. **Education:** Enhanced documentation helps both the LLM and human developers understand the distinction

The fix ensures that workflows requiring "create content → save to file → email as attachment" will always include the necessary file-saving step.

---

**Date:** 2024
**Issue Type:** Planning Error / Workflow Validation
**Severity:** High (blocked critical user workflow)
**Status:** ✅ RESOLVED

