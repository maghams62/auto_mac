# Task Feedback UX Design Guide

## Overview

This document describes the task completion feedback system in Cerebro OS, which provides delightful, consistent feedback when tasks complete successfully.

## Architecture

### Backend: Completion Events

The backend generates structured completion events through the `reply_to_user` tool:

```python
reply_to_user(
    message="Email sent successfully!",
    action_type="email_sent",
    summary="Your email has been delivered",
    artifact_metadata={
        "recipients": ["user@example.com"],
        "subject": "Meeting Notes"
    },
    artifacts=["/path/to/attachment.pdf"]
)
```

**Completion Event Schema:**
- `action_type`: Type of action (e.g., `email_sent`, `report_created`, `presentation_created`)
- `summary`: Brief celebratory message
- `status`: `success`, `partial_success`, `info`, or `error`
- `artifact_metadata`: Rich metadata (recipients, file_type, file_size, subject, etc.)
- `artifacts`: List of file paths or URLs

### Frontend: Task Completion Card

The `TaskCompletionCard` component renders completion events with:
- Celebratory emoji and message
- Rich metadata display (recipients, file info, etc.)
- Artifact previews and actions
- Confetti animation for success
- Toast notifications

## Action Types

### Email Sent (`email_sent`)
- **Emoji**: 📧
- **Metadata**: `recipients`, `subject`, `attachments`
- **Celebration**: Confetti + toast

### Report Created (`report_created`)
- **Emoji**: 📊
- **Metadata**: `file_type`, `file_size`, `report_path`
- **Actions**: Preview PDF, Reveal in Finder

### Presentation Created (`presentation_created`)
- **Emoji**: 📽️
- **Metadata**: `keynote_path`, `slide_count`
- **Actions**: Open in Keynote, Reveal in Finder

### File Saved (`file_saved`)
- **Emoji**: 💾
- **Metadata**: `file_path`, `file_size`
- **Actions**: Preview, Reveal

## Usage Guidelines

### For Agents

When completing a task, use `reply_to_user` with completion event parameters:

```python
from src.agent.reply_tool import reply_to_user
from src.utils.message_personality import get_message_for_action

# After sending email
reply_to_user(
    message=get_message_for_action("email_sent"),
    action_type="email_sent",
    summary="Email delivered to recipient@example.com",
    artifact_metadata={
        "recipients": ["recipient@example.com"],
        "subject": "Your Subject Here"
    },
    artifacts=[],
    status="success"
)

# After creating report
reply_to_user(
    message=get_message_for_action("file_saved"),
    action_type="report_created",
    summary="Stock analysis report generated",
    artifact_metadata={
        "file_type": "PDF",
        "file_size": 123456
    },
    artifacts=["data/reports/stock_analysis_2024.pdf"],
    status="success"
)
```

### For Frontend

Completion events are automatically rendered when present in messages:

```typescript
// MessageBubble automatically renders TaskCompletionCard
if (message.completion_event) {
  <TaskCompletionCard completionEvent={message.completion_event} />
}
```

## Preview System

### Supported File Types
- **PDFs**: Rendered in iframe modal
- **HTML**: Rendered in iframe modal
- **Images**: Displayed in modal with full-size view
- **Keynote/Pages**: "Open" button to launch in native app

### Preview Endpoint

`GET /api/files/preview?path=<file_path>`

**Security**: Only files from whitelisted directories:
- `data/reports/`
- `data/presentations/`
- `data/screenshots/`

## Celebratory Elements

### Confetti
Automatically triggered for `status === "success"` completion events.

### Toasts
Short celebratory messages shown in toast stack (bottom-right).

### Emojis
Action-specific emojis provide visual context:
- 📧 Email
- 📊 Reports
- 📽️ Presentations
- 💾 Files
- ✅ Generic success

## Best Practices

1. **Always use completion events** for user-facing actions (email, reports, presentations)
2. **Include rich metadata** to help users understand what was created
3. **Use fun personality messages** from `message_personality.py`
4. **Provide artifact paths** for previewable files
5. **Set appropriate status** (success, partial_success, error)

## Future Enhancements

- [ ] Keynote slide thumbnails
- [ ] Email attachment previews
- [ ] Report section navigation
- [ ] Custom celebration animations per action type
- [ ] Sound effects for major completions

