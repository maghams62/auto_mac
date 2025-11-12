## Example 28: EMAIL AGENT - Summarize Last N Emails

### User Request
"summarize my last 3 emails"

### Decomposition
```json
{
  "goal": "Read the 3 most recent emails and provide AI summary",
  "steps": [
    {
      "id": 1,
      "action": "read_latest_emails",
      "parameters": {
        "count": 3,
        "mailbox": "INBOX"
      },
      "dependencies": [],
      "reasoning": "Retrieve the 3 most recent emails from inbox",
      "expected_output": "Dict with 'emails' list containing 3 most recent emails with full metadata (sender, subject, date, content)"
    },
    {
      "id": 2,
      "action": "summarize_emails",
      "parameters": {
        "emails_data": "$step1",
        "focus": null
      },
      "dependencies": [1],
      "reasoning": "Use AI to create concise summary of the 3 emails, highlighting key points from each",
      "expected_output": "Dict with 'summary' text, 'email_count', and 'emails_summarized' metadata array"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Summary of your last 3 emails",
        "details": "$step2.summary",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [2],
      "reasoning": "FINAL step - deliver AI-generated summary with email metadata to user",
      "expected_output": "Polished summary display with sender/subject/date for each email"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Count-Based Email Summarization Pattern**
- ✅ Use `read_latest_emails(count=N)` when user specifies "last N emails"
- ✅ Extract count from phrases like "last 3", "5 emails", "recent 10 emails"
- ✅ Pass entire step output to `summarize_emails` using `$step1`
- ✅ `summarize_emails` returns structured data: `summary`, `email_count`, `emails_summarized`
- ✅ ALWAYS end with `reply_to_user` to format the summary for UI display
- ✅ UI will render summary headline, bullet points, and compact email list

**Intent Hints Support:**
- When called via `/email` slash command, the handler extracts count and passes it as `intent_hints["count"]`
- Planner can use these hints to build the correct plan without re-parsing the query

---
