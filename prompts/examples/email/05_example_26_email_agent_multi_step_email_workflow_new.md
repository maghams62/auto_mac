## Example 26: EMAIL AGENT - Multi-Step Email Workflow (NEW!)

### User Request
"Read the latest 10 emails, summarize them, and create a report document"

### Decomposition
```json
{
  "goal": "Read emails, summarize, and create Pages document with summary",
  "steps": [
    {
      "id": 1,
      "action": "read_latest_emails",
      "parameters": {
        "count": 10,
        "mailbox": "INBOX"
      },
      "dependencies": [],
      "reasoning": "Retrieve 10 most recent emails",
      "expected_output": "List of 10 emails"
    },
    {
      "id": 2,
      "action": "summarize_emails",
      "parameters": {
        "emails_data": "$step1",
        "focus": null
      },
      "dependencies": [1],
      "reasoning": "Create comprehensive summary of all emails",
      "expected_output": "AI-generated email summary"
    },
    {
      "id": 3,
      "action": "create_pages_doc",
      "parameters": {
        "title": "Email Summary Report",
        "content": "$step2.summary"
      },
      "dependencies": [2],
      "reasoning": "Save summary as Pages document for permanent record",
      "expected_output": "Pages document created with summary"
    },
    {
      "id": 4,
      "action": "reply_to_user",
      "parameters": {
        "message": "Created email summary report",
        "details": "Summarized 10 latest emails and saved to Pages document",
        "artifacts": ["$step3.file_path"],
        "status": "success"
      },
      "dependencies": [3],
      "reasoning": "FINAL step - confirm completion with document path",
      "expected_output": "Success message with document artifact"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Multi-Step Email Workflow**
- ✅ Combine email tools with other agents (Writing, Presentation, etc.)
- ✅ Pass summary to document creation tools
- ✅ Include document path in `artifacts` array of reply_to_user
- ✅ ALWAYS end complex workflows with reply_to_user

---
