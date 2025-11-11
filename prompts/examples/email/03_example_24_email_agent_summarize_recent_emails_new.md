## Example 24: EMAIL AGENT - Summarize Recent Emails (NEW!)

### User Request
"Summarize emails from the past hour"

### Decomposition
```json
{
  "goal": "Read emails from last hour and provide AI summary",
  "steps": [
    {
      "id": 1,
      "action": "read_emails_by_time",
      "parameters": {
        "hours": 1,
        "mailbox": "INBOX"
      },
      "dependencies": [],
      "reasoning": "Retrieve all emails received in the last hour",
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
      "reasoning": "Use AI to create concise summary of email content",
      "expected_output": "Summary highlighting key points, senders, and topics"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Email summary for the past hour",
        "details": "$step2.summary",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [2],
      "reasoning": "FINAL step - deliver AI-generated summary to user",
      "expected_output": "Polished summary display"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Email Summarization Pattern**
- ✅ Use `read_emails_by_time` for time-based filtering
- ✅ Pass entire step output to `summarize_emails` using `$step1`
- ✅ `summarize_emails` expects `emails_data` dict with `emails` field
- ✅ ALWAYS end with `reply_to_user` containing the summary
- ✅ Use `$step2.summary` to reference the AI-generated summary text

---
