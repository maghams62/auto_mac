## Example 30: EMAIL AGENT - Summarize Emails by Time Window

### User Request
"summarize the emails from the last hour"

### Decomposition
```json
{
  "goal": "Read all emails from last hour and provide AI summary with action items",
  "steps": [
    {
      "id": 1,
      "action": "read_emails_by_time",
      "parameters": {
        "hours": 1,
        "mailbox": "INBOX"
      },
      "dependencies": [],
      "reasoning": "Retrieve all emails received in the last 1 hour (time-based filtering)",
      "expected_output": "Dict with 'emails' list, 'time_range', and time metadata"
    },
    {
      "id": 2,
      "action": "summarize_emails",
      "parameters": {
        "emails_data": "$step1",
        "focus": "action items"
      },
      "dependencies": [1],
      "reasoning": "Use AI to create time-contextualized summary, emphasizing action items from recent emails",
      "expected_output": "Dict with 'summary' mentioning time context, 'email_count', 'focus', 'time_range', and 'emails_summarized' array"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Summary of emails from the last hour (focusing on action items)",
        "details": "$step2.summary",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [2],
      "reasoning": "FINAL step - deliver time-contextualized summary with focus highlights",
      "expected_output": "Summary with time window and action items prominently displayed"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Time-Based Email Summarization Pattern**
- ✅ Use `read_emails_by_time(hours=H)` or `read_emails_by_time(minutes=M)` for time-window queries
- ✅ Extract time from phrases like "last hour", "past 2 hours", "last 24 hours", "past day"
- ✅ Parse hours vs minutes: "last hour" → hours=1, "past 30 minutes" → minutes=30
- ✅ Extract focus keywords: "action items", "deadlines", "important", "urgent", "key decisions"
- ✅ Pass focus to `summarize_emails` when user specifies what they care about
- ✅ Summary includes time context in the text (e.g., "in the last hour")
- ✅ All returned emails are within the requested time window

**Intent Hints Support:**
- Slash handler extracts `time_window` dict with hours/minutes keys
- Also extracts `focus` keywords from queries like "/email summarize last hour for action items"
- Hints passed as `intent_hints["time_window"]` and `intent_hints["focus"]`

**Common Variations:**
- "summarize emails from the last hour" → hours=1, focus=None
- "summarize the past 2 hours of emails focusing on deadlines" → hours=2, focus="deadlines"
- "summarize emails from last 24 hours" → hours=24, focus=None
- "summarize the last 30 minutes for urgent items" → minutes=30, focus="urgent"

**Focus Parameter Options:**
- "action items" - extracts tasks and TODOs
- "deadlines" - highlights time-sensitive items
- "important updates" - filters for significant information
- "key decisions" - focuses on decision points
- None - general summary without specific focus

---
