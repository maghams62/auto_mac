# Email Agent Reply Tool Integration

## Architecture Overview

The Mac Automation Assistant uses a **centralized reply agent pattern** where all agent workflows must end with a `reply_to_user` tool call to deliver polished, UI-friendly responses.

### How It Works

1. **Orchestrator Planning:** The agent planning prompt includes: "After all work steps are complete, add a FINAL step that calls `reply_to_user`"

2. **Every Workflow Ends with reply_to_user:** Instead of returning raw tool outputs, the system uses `reply_to_user` to format responses

3. **UI Consumes Structured Payload:** The reply tool returns:
   ```python
   {
       "type": "reply",
       "message": "Main message",
       "details": "Secondary context",
       "artifacts": ["paths or URLs"],
       "status": "success|partial_success|info|error"
   }
   ```

## Email Reading Integration

### Pattern: Simple Email Read

**User Request:** "Read my latest 5 emails"

**Workflow:**
```
read_latest_emails → reply_to_user
```

**Plan:**
```json
{
  "steps": [
    {
      "id": 1,
      "action": "read_latest_emails",
      "parameters": {"count": 5},
      "expected_output": "List of 5 emails"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "Retrieved your latest 5 emails",
        "details": "Email list with senders, subjects, dates",
        "status": "success"
      },
      "dependencies": [1]
    }
  ]
}
```

### Pattern: Email Summarization

**User Request:** "Summarize emails from the past hour"

**Workflow:**
```
read_emails_by_time → summarize_emails → reply_to_user
```

**Plan:**
```json
{
  "steps": [
    {
      "id": 1,
      "action": "read_emails_by_time",
      "parameters": {"hours": 1},
      "expected_output": "List of emails from past hour"
    },
    {
      "id": 2,
      "action": "summarize_emails",
      "parameters": {
        "emails_data": "$step1",
        "focus": null
      },
      "dependencies": [1],
      "expected_output": "AI-generated summary"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Email summary for the past hour",
        "details": "$step2.summary",
        "status": "success"
      },
      "dependencies": [2]
    }
  ]
}
```

**Key Points:**
- Step 1: `read_emails_by_time` retrieves raw email data
- Step 2: `summarize_emails` processes with AI
- Step 3: `reply_to_user` formats the summary for UI display

### Pattern: Multi-Step Workflow

**User Request:** "Read the latest 10 emails, summarize them, and create a report"

**Workflow:**
```
read_latest_emails → summarize_emails → create_pages_doc → reply_to_user
```

**Plan:**
```json
{
  "steps": [
    {
      "id": 1,
      "action": "read_latest_emails",
      "parameters": {"count": 10}
    },
    {
      "id": 2,
      "action": "summarize_emails",
      "parameters": {"emails_data": "$step1"},
      "dependencies": [1]
    },
    {
      "id": 3,
      "action": "create_pages_doc",
      "parameters": {
        "title": "Email Summary Report",
        "content": "$step2.summary"
      },
      "dependencies": [2]
    },
    {
      "id": 4,
      "action": "reply_to_user",
      "parameters": {
        "message": "Created email summary report",
        "details": "Summarized 10 emails and saved to Pages",
        "artifacts": ["$step3.file_path"],
        "status": "success"
      },
      "dependencies": [3]
    }
  ]
}
```

**Artifacts:**
- The `artifacts` array includes the document path so the UI can highlight it

## Data Flow

### Without Reply Agent (OLD - Not Used)
```
Email Tool → Raw JSON → UI
```
❌ UI receives raw JSON with nested data structures

### With Reply Agent (CURRENT)
```
Email Tool → summarize_emails (optional) → reply_to_user → UI
```
✅ UI receives polished message with formatted details

## Reply Tool Parameters

### message (required)
High-level summary of what was accomplished
```python
"message": "Retrieved your latest 5 emails"
```

### details (optional)
Secondary context, bullet points, or extended information
```python
"details": "Emails from:\n- john@example.com: Project Update\n- sarah@company.com: Meeting Tomorrow"
```

### artifacts (optional)
List of file paths, URLs, or references to outputs
```python
"artifacts": ["/Users/name/Documents/Email Summary.pages"]
```

### status (optional)
Overall outcome indicator
- `"success"` - Task completed successfully
- `"partial_success"` - Completed with some limitations
- `"info"` - Informational response
- `"error"` - Task failed

## Integration with Email Tools

### Email Tool Outputs

**read_latest_emails:**
```python
{
    "emails": [
        {
            "sender": "John Doe <john@example.com>",
            "subject": "Project Update",
            "date": "Nov 10, 2025 at 2:30 PM",
            "content": "...",
            "content_preview": "First 200 chars..."
        }
    ],
    "count": 5,
    "mailbox": "INBOX"
}
```

**summarize_emails:**
```python
{
    "summary": "Well-formatted markdown summary...",
    "email_count": 5,
    "focus": "action items",
    "emails_summarized": [...]
}
```

### Passing to reply_to_user

**Direct Email List:**
```json
{
  "action": "reply_to_user",
  "parameters": {
    "message": "Retrieved emails",
    "details": "Format email list here"
  }
}
```

**AI Summary:**
```json
{
  "action": "reply_to_user",
  "parameters": {
    "message": "Email summary completed",
    "details": "$step2.summary"
  }
}
```

## Few-Shot Examples Updated

The [prompts/few_shot_examples.md](prompts/few_shot_examples.md) file has been updated with:

### New Examples Added:
1. **Example 22:** Email Agent - Read Latest Emails
2. **Example 23:** Email Agent - Read Emails by Sender
3. **Example 24:** Email Agent - Summarize Recent Emails
4. **Example 25:** Email Agent - Read & Summarize with Focus
5. **Example 26:** Email Agent - Multi-Step Email Workflow

### Tool Hierarchy Updated:
- Added Email Agent with all 5 tools
- Added Reply Agent with `reply_to_user` tool
- Emphasized `reply_to_user` as FINAL step requirement

### Parameter Extraction Guide Added:
- Count extraction ("latest 5" → `count: 5`)
- Sender extraction ("from John" → `sender: "John"`)
- Time range extraction ("past hour" → `hours: 1`)
- Focus extraction ("action items" → `focus: "action items"`)

## Critical Rules

### ✅ DO:
- ALWAYS end email workflows with `reply_to_user`
- Pass entire step output to `summarize_emails` using `$step1`
- Use `$step2.summary` to reference AI-generated summary
- Include file paths in `artifacts` array when creating documents
- Format `details` parameter as readable text/markdown

### ❌ DON'T:
- Return raw email data without `reply_to_user`
- Skip the final `reply_to_user` step
- Pass partial data to summarization (use full `$step1` not `$step1.emails`)
- Forget to add dependencies when using step references

## Testing Confirmation

All email reading tools have been tested and verified to work with the reply agent pattern:

**Test Suite Results:**
```
✅ Mail.app Access
✅ Read Latest Emails
✅ Read by Time Range
✅ Email Summarization
✅ Agent Registry Integration
```

**Status:** All 5/5 tests passing

## Documentation Files

1. **[EMAIL_READING_FEATURE.md](EMAIL_READING_FEATURE.md)** - Complete feature documentation
2. **[EMAIL_FEATURE_SUMMARY.md](EMAIL_FEATURE_SUMMARY.md)** - Quick reference guide
3. **[prompts/few_shot_examples.md](prompts/few_shot_examples.md)** - Updated with email + reply patterns
4. **[EMAIL_REPLY_AGENT_INTEGRATION.md](EMAIL_REPLY_AGENT_INTEGRATION.md)** - This document

## Summary

The email reading feature is **fully integrated** with the centralized reply agent pattern:

1. ✅ Email tools return structured data
2. ✅ Summarization tool processes data with AI
3. ✅ `reply_to_user` formats for UI consumption
4. ✅ Few-shot examples teach the pattern
5. ✅ Planning prompt enforces `reply_to_user` as final step

The orchestrator will automatically add `reply_to_user` as the final step for all email-related workflows, ensuring consistent, polished responses to the user interface.
