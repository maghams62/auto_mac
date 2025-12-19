## Example 29: EMAIL AGENT - Summarize Emails by Sender

### User Request
"summarize the last 3 emails sent by john@example.com"

### Decomposition
```json
{
  "goal": "Read last 3 emails from specific sender and provide AI summary",
  "steps": [
    {
      "id": 1,
      "action": "read_emails_by_sender",
      "parameters": {
        "sender": "john@example.com",
        "count": 3
      },
      "dependencies": [],
      "reasoning": "Retrieve the 3 most recent emails from john@example.com",
      "expected_output": "Dict with 'emails' list containing 3 emails from specified sender, plus sender metadata"
    },
    {
      "id": 2,
      "action": "summarize_emails",
      "parameters": {
        "emails_data": "$step1",
        "focus": null
      },
      "dependencies": [1],
      "reasoning": "Use AI to create summary focusing on communication from this specific sender",
      "expected_output": "Dict with 'summary' text contextualizing sender relationship, 'email_count', 'sender', and 'emails_summarized' array"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Summary of last 3 emails from john@example.com",
        "details": "$step2.summary",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [2],
      "reasoning": "FINAL step - deliver sender-contextualized summary to user",
      "expected_output": "Summary with sender context prominently displayed"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Sender-Based Email Summarization Pattern**
- ✅ Use `read_emails_by_sender(sender="...", count=N)` when user mentions "from [person]" or "by [person]"
- ✅ Extract sender from phrases like "from john@example.com", "by John Doe", "sent by Alice"
- ✅ Sender can be email address or name (partial match supported)
- ✅ Extract count if specified, otherwise default to 10
- ✅ Pass entire step output to `summarize_emails` - it includes sender context
- ✅ Summary will contextualize that all emails are from the same sender
- ✅ UI displays sender prominently in the summary view

**Intent Hints Support:**
- Slash handler extracts both `sender` and `count` from queries like "/email summarize last 5 from john@example.com"
- Hints passed as `intent_hints["sender"]` and `intent_hints["count"]`
- Planner uses hints to choose `read_emails_by_sender` over other read tools

**Common Variations:**
- "summarize emails from john@example.com" → count defaults to 10
- "summarize the last 5 emails by John Doe" → sender="John Doe", count=5
- "summarize john's emails" → sender="john", count=10

---
