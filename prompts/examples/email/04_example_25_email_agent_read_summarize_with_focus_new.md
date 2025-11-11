## Example 25: EMAIL AGENT - Read & Summarize with Focus (NEW!)

### User Request
"Summarize emails from Sarah focusing on action items"

### Decomposition
```json
{
  "goal": "Read emails from Sarah and summarize with focus on action items",
  "steps": [
    {
      "id": 1,
      "action": "read_emails_by_sender",
      "parameters": {
        "sender": "Sarah",
        "count": 10
      },
      "dependencies": [],
      "reasoning": "Find all emails from Sarah (partial name match works)",
      "expected_output": "List of Sarah's emails"
    },
    {
      "id": 2,
      "action": "summarize_emails",
      "parameters": {
        "emails_data": "$step1",
        "focus": "action items"
      },
      "dependencies": [1],
      "reasoning": "Summarize with specific focus on action items and tasks",
      "expected_output": "Summary highlighting action items from Sarah's emails"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Summary of emails from Sarah (focused on action items)",
        "details": "$step2.summary",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [2],
      "reasoning": "FINAL step - present focused summary",
      "expected_output": "Action items clearly highlighted"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Focused Summarization**
- ✅ `focus` parameter guides AI to highlight specific aspects
- ✅ Common focus values: "action items", "deadlines", "important updates", "decisions"
- ✅ Sender matching is flexible - "Sarah" will match "Sarah Johnson <sarah@company.com>"

---
