## Example 22: EMAIL AGENT - Read Latest Emails (NEW!)

### User Request
"Read my latest 5 emails"

### Decomposition
```json
{
  "goal": "Read latest 5 emails and present to user",
  "steps": [
    {
      "id": 1,
      "action": "read_latest_emails",
      "parameters": {
        "count": 5,
        "mailbox": "INBOX"
      },
      "dependencies": [],
      "reasoning": "Retrieve the 5 most recent emails from inbox",
      "expected_output": "List of 5 emails with sender, subject, date, content"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "Retrieved your latest 5 emails",
        "details": "Email list with senders, subjects, dates, and previews",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [1],
      "reasoning": "FINAL step - deliver polished summary to UI",
      "expected_output": "User-friendly email listing"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Email Reading Pattern**
- ✅ Use `read_latest_emails` to retrieve recent emails
- ✅ ALWAYS end with `reply_to_user` to format response for UI
- ✅ Single-step pattern: read → reply
- ❌ DON'T return raw email data - use reply_to_user for polished output

---
