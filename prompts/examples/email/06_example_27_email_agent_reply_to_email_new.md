## Example 27: EMAIL AGENT - Reply to Email (NEW!)

### User Request
"Read the latest email from John and reply saying I'll review it tomorrow"

### Decomposition
```json
{
  "goal": "Read email from John and send reply",
  "steps": [
    {
      "id": 1,
      "action": "read_emails_by_sender",
      "parameters": {
        "sender": "John",
        "count": 1
      },
      "dependencies": [],
      "reasoning": "Get the most recent email from John",
      "expected_output": "Latest email from John with sender and subject"
    },
    {
      "id": 2,
      "action": "reply_to_email",
      "parameters": {
        "original_sender": "$step1.emails[0].sender",
        "original_subject": "$step1.emails[0].subject",
        "reply_body": "Thank you for your email. I'll review this tomorrow and get back to you.",
        "send": false
      },
      "dependencies": [1],
      "reasoning": "Reply to John's email with draft (send=false for safety)",
      "expected_output": "Reply draft created"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Reply drafted to John's email",
        "details": "Created reply draft - please review and send from Mail.app",
        "status": "success"
      },
      "dependencies": [2],
      "reasoning": "FINAL step - confirm reply was drafted",
      "expected_output": "Success message"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Email Reply Workflow**
- ✅ Read the email first to get sender and subject
- ✅ Use `$step1.emails[0].sender` to reference the email address from read result
- ✅ Use `$step1.emails[0].subject` to reference the subject line
- ✅ `reply_to_email` automatically adds "Re: " prefix to subject
- ✅ Default `send: false` creates draft for safety
- ✅ **CRITICAL: Set `send: true` when user says:**
  - "email X to me" or "send X to me" → `send: true` (user wants it sent, not drafted)
  - "email X" (without "draft" keyword) → `send: true` (implied sending intent)
  - "send X" → `send: true` (explicit send command)
- ✅ Set `send: false` only when user explicitly says "draft" or "create draft"

---
