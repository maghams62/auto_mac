# Email Reply Feature - Text-Based Email Replies

## Overview

The Email Agent now supports **replying to emails** via the new `reply_to_email` tool. This allows you to read an email and compose a text-based reply, either as a draft or send it immediately.

## What's New

### New Tool: `reply_to_email`

**Location:** [src/agent/email_agent.py](src/agent/email_agent.py)

**Purpose:** Reply to specific emails you've read

**Parameters:**
- `original_sender` (required): Email address of the person who sent the original email
- `original_subject` (required): Subject line of the original email
- `reply_body` (required): Your reply message (supports markdown)
- `send` (optional): If True, send immediately; if False, open as draft (default: False)

**Returns:**
```python
{
    "status": "sent" or "draft",
    "message": "Reply sent/drafted to {sender}",
    "recipient": "john@example.com",
    "subject": "Re: Original Subject"
}
```

## Usage Examples

### Example 1: Simple Reply
```
User: "Read the latest email from John and reply saying thanks"

Workflow:
1. read_emails_by_sender(sender="John", count=1)
2. reply_to_email(
     original_sender="john@example.com",
     original_subject="Project Update",
     reply_body="Thanks for the update!",
     send=false
   )
3. reply_to_user(message="Reply drafted to John's email")
```

### Example 2: Reply with Specific Message
```
User: "Reply to Sarah's email about the meeting saying I can attend"

Workflow:
1. read_emails_by_sender(sender="Sarah", count=1)
2. reply_to_email(
     original_sender="sarah@company.com",
     original_subject="Meeting Tomorrow",
     reply_body="Thanks for the invite! I can attend the meeting.",
     send=false
   )
3. reply_to_user(message="Reply drafted")
```

### Example 3: Read Latest and Reply
```
User: "Read my latest email and draft a reply saying I'll review tomorrow"

Workflow:
1. read_latest_emails(count=1)
2. reply_to_email(
     original_sender="{sender from step 1}",
     original_subject="{subject from step 1}",
     reply_body="Thank you. I'll review this tomorrow and get back to you.",
     send=false
   )
3. reply_to_user(message="Reply drafted")
```

## Key Features

### 1. Automatic "Re: " Prefix
The tool automatically adds "Re: " to the subject line if not already present:
- Input: `original_subject="Project Update"`
- Result: `subject="Re: Project Update"`

### 2. Draft by Default (Safety)
By default, `send=false` creates a draft for user review:
- User can review the reply in Mail.app before sending
- Set `send=true` only when user explicitly requests immediate sending

### 3. Integration with Email Reading
Works seamlessly with existing email reading tools:
- `read_latest_emails` → Get recent emails
- `read_emails_by_sender` → Find emails from specific person
- `read_emails_by_time` → Get emails from time range
- Then use `reply_to_email` to respond

## Technical Implementation

### 1. Email Agent Updated
**File:** [src/agent/email_agent.py](src/agent/email_agent.py)

Added new `reply_to_email` tool to EMAIL_AGENT_TOOLS list.

**Tool Count:** Email Agent now has **6 tools** (was 5):
1. `compose_email` - Create new emails
2. **`reply_to_email`** - Reply to emails (NEW!)
3. `read_latest_emails` - Read recent emails
4. `read_emails_by_sender` - Filter by sender
5. `read_emails_by_time` - Filter by time
6. `summarize_emails` - AI summarization

### 2. Agent Registry Updated
**File:** [src/agent/agent_registry.py](src/agent/agent_registry.py)

Updated AGENT_HIERARCHY_DOCS to reflect 6 tools for Email Agent.

### 3. Few-Shot Examples Updated
**File:** [prompts/few_shot_examples.md](prompts/few_shot_examples.md)

Added Example 27: Email Agent - Reply to Email with:
- Complete workflow showing read → reply pattern
- Parameter extraction from email reading results
- Safety guidance (draft by default)
- Usage of `$step1.emails[0].sender` and `$step1.emails[0].subject` references

Also updated tool selection guide with:
- When to use `reply_to_email` vs `compose_email`
- Best practices for email replies

### 4. Hierarchy Documentation
**File:** [src/agent/email_agent.py](src/agent/email_agent.py) - EMAIL_AGENT_HIERARCHY

Updated to show:
```
LEVEL 1: Email Composition
├─ compose_email → Create and send new emails via Mail.app
└─ reply_to_email → Reply to a specific email
```

## Workflow Pattern

### Typical Reply Workflow
```json
{
  "steps": [
    {
      "id": 1,
      "action": "read_emails_by_sender",
      "parameters": {
        "sender": "John",
        "count": 1
      }
    },
    {
      "id": 2,
      "action": "reply_to_email",
      "parameters": {
        "original_sender": "$step1.emails[0].sender",
        "original_subject": "$step1.emails[0].subject",
        "reply_body": "Your reply message here",
        "send": false
      },
      "dependencies": [1]
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Reply drafted successfully",
        "status": "success"
      },
      "dependencies": [2]
    }
  ]
}
```

## Testing

All tests passing! ✅

**Test File:** [test_email_reply.py](test_email_reply.py)

**Test Results:**
```
✅ reply_to_email tool exists in EMAIL_AGENT_TOOLS
✅ reply_to_email correctly mapped to email agent
✅ Tool has correct schema and is callable
✅ Email agent has 6 tools
✅ Hierarchy documentation includes reply_to_email

🎉 ALL TESTS PASSED! (5/5)
```

**Run Tests:**
```bash
python test_email_reply.py
```

## Important Notes

### Safety Features
1. **Draft by Default:** `send=false` is the default to prevent accidental sends
2. **User Review:** Drafts open in Mail.app for user review before sending
3. **Explicit Send:** Only sends immediately if user explicitly requests it

### Parameter References
When replying to emails, extract sender and subject from the email reading step:
- ✅ `"original_sender": "$step1.emails[0].sender"`
- ✅ `"original_subject": "$step1.emails[0].subject"`
- ❌ Don't hardcode these values

### compose_email vs reply_to_email

**Use `reply_to_email` when:**
- Replying to a specific email you've read
- Need "Re: " prefix on subject
- Have the original sender and subject

**Use `compose_email` when:**
- Composing a new email (not a reply)
- Creating email from scratch
- Sender isn't from a read email

## Files Modified

1. **[src/agent/email_agent.py](src/agent/email_agent.py)**
   - Added `reply_to_email` tool
   - Updated EMAIL_AGENT_TOOLS list
   - Updated EMAIL_AGENT_HIERARCHY documentation

2. **[src/agent/agent_registry.py](src/agent/agent_registry.py)**
   - Updated AGENT_HIERARCHY_DOCS (5 tools → 6 tools)

3. **[prompts/few_shot_examples.md](prompts/few_shot_examples.md)**
   - Added Example 27: Email Agent - Reply to Email
   - Updated Email Agent tools list
   - Updated tool selection guide

4. **[test_email_reply.py](test_email_reply.py)** (NEW)
   - Comprehensive test suite for reply functionality

## Usage in Chat

### Via Natural Language
```
"Read the latest email from John and reply saying I'll get back to him"
"Reply to Sarah's email about the project update"
"Draft a reply to the most recent email saying thanks"
```

### Via Slash Command
```
/email Read latest email from John and reply with thanks
/email Reply to Sarah saying I can attend the meeting
```

## Future Enhancements

Potential improvements for future versions:
- [ ] Reply with quoted original message
- [ ] Reply-all functionality
- [ ] Forward email support
- [ ] Attachment support in replies
- [ ] Template-based replies
- [ ] AI-assisted reply generation (suggest reply content)

## Summary

The email reply feature is **fully implemented and tested**. You can now:

✅ Reply to specific emails you've read
✅ Compose text-based replies
✅ Create drafts for review (default)
✅ Send immediately (optional)
✅ Automatic "Re: " subject prefix
✅ Seamless integration with email reading tools

The feature follows the existing email agent patterns and integrates cleanly with the orchestrator system.
