## Example 23: EMAIL AGENT - Read Emails by Sender (NEW!)

### User Request
"Show me emails from john@example.com"

### Decomposition
```json
{
  "goal": "Find and display emails from specific sender",
  "steps": [
    {
      "id": 1,
      "action": "read_emails_by_sender",
      "parameters": {
        "sender": "john@example.com",
        "count": 10
      },
      "dependencies": [],
      "reasoning": "Search inbox for emails from john@example.com",
      "expected_output": "List of emails from specified sender"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "Found emails from john@example.com",
        "details": "Listing all emails with subjects and dates",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [1],
      "reasoning": "FINAL step - present findings to user",
      "expected_output": "Formatted email list"
    }
  ],
  "complexity": "simple"
}
```

---
