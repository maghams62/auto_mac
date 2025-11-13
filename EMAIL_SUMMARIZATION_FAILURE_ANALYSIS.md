# Email Summarization Failure - Root Cause Analysis

## What Happened

User request: "Can you summarize my last three emails and convert it into a report and email that to me?"

**Result**: Email composition failed with error: "All 1 attachment(s) failed validation: '/Users/siddharthsuresh/Downloads/auto_mac/Email Summary Report\n\nIntroduction...' - file not found"

## Root Causes

### 1. **Missing File-Saving Step in Workflow**
The planner created this workflow:
```
1. read_latest_emails(count=3)
2. summarize_emails(emails_data=$step1)
3. create_detailed_report(content=$step2.summary, title="Email Summary Report")
4. compose_email(attachments=[$step3.report_content], send=true)  ❌ WRONG
```

**Problem**: `create_detailed_report` returns a dictionary with `report_content` (string), NOT a file path. The planner incorrectly passed the report TEXT CONTENT as if it were a file path.

**Correct workflow**:
```
1. read_latest_emails(count=3)
2. CHECK if emails exist (if empty, stop and inform user)
3. summarize_emails(emails_data=$step1)
4. create_detailed_report(content=$step2.summary, title="Email Summary Report")
5. create_pages_doc(title="Email Summary Report", content=$step3.report_content) ✅ SAVE TO FILE
6. compose_email(attachments=[$step5.pages_path], send=true) ✅ USE FILE PATH
7. reply_to_user
```

### 2. **No Validation for Empty Email Results**
- `read_latest_emails` returned: `{"emails": [], "count": 0, "message": "No emails found"}`
- The planner should have stopped here and informed the user
- Instead, it continued and `create_detailed_report` generated a generic business report about email communication (!)

### 3. **LLM Generated Generic Report with No Input**
When `create_detailed_report` received empty/minimal content, it hallucinated a business report about "the strategic importance of email communication" instead of failing gracefully.

### 4. **Type Mismatch Not Caught Early**
The system only detected the error when `compose_email` tried to validate the attachment path. Earlier validation could have caught that a string was being used where a file path was expected.

## Systemic Issues to Fix

### Issue 1: Planner Prompt Lacks Clear Workflow Guidance
**Location**: `src/orchestrator/prompts.py`, `prompts/task_decomposition.md`

**Problem**: No clear examples showing:
- Report content must be saved to file before emailing as attachment
- Need to validate intermediate results before proceeding
- How to handle empty/no-result scenarios

### Issue 2: No Early Validation for Empty Results
**Location**: `src/orchestrator/executor.py`, planner logic

**Problem**: When a step returns empty/no results, execution continues blindly

### Issue 3: Tool Output Types Not Enforced
**Location**: Tool definitions, planner prompts

**Problem**: No clear indication that `create_detailed_report.report_content` is TEXT, not a file path

### Issue 4: Missing Validation Examples
**Location**: `prompts/few_shot_examples.md`

**Problem**: No examples showing proper "create report → save to file → email" workflow

## Fixes Required

### Fix 1: Update Planner Prompts ✅
Add explicit rules:
- Report/document content must be saved to file before emailing
- Always validate intermediate results before proceeding
- Add "Report + Email" workflow examples

### Fix 2: Add Result Validation in Executor ✅
Check for empty/error results and stop execution early with helpful message

### Fix 3: Add Type Validation ✅
Detect when strings are incorrectly used as file paths (e.g., strings > 1000 chars or containing newlines)

### Fix 4: Add Workflow Examples ✅
Add clear examples to few-shot prompts showing correct patterns

### Fix 5: Improve Error Messages ✅
When attachment validation fails, provide better guidance on the correct workflow

## Prevention Strategy

1. **Planner Level**: Clear workflow patterns and validation requirements
2. **Execution Level**: Early validation and type checking
3. **Tool Level**: Better error messages and return type documentation
4. **Examples Level**: Comprehensive few-shot examples covering edge cases

## Files to Modify

1. `src/orchestrator/prompts.py` - Add validation rules and workflow patterns
2. `prompts/task_decomposition.md` - Add report+email examples
3. `prompts/few_shot_examples.md` - Add comprehensive workflow examples
4. `src/orchestrator/executor.py` - Add result validation
5. `src/agent/email_agent.py` - Improve attachment validation error messages
6. Tool definitions - Clarify output types

## Test Case

After fixes, this request should work correctly:
```
User: "Summarize my last three emails and convert it into a report and email that to me"

Expected workflow:
1. read_latest_emails(count=3)
2. IF emails.count == 0 → reply_to_user("No emails found") and STOP
3. ELSE summarize_emails(emails_data=$step1)
4. create_detailed_report(content=$step2.summary, title="Email Summary Report")
5. create_pages_doc(title="Email Summary Report", content=$step3.report_content)
6. compose_email(body="Please find attached...", attachments=[$step5.pages_path], send=true)
7. reply_to_user("Email sent with report attached")
```

## Similar Scenarios to Check

Search codebase for any workflows that:
1. Create content and immediately try to email without saving
2. Pass non-file-path values to `attachments` parameter
3. Continue execution after receiving empty/no-result responses
4. Create reports/documents without proper file-saving step

