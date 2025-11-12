# Delivery Intent – Send vs Draft Email

**User Request**: “Draft an email with the quarterly summary so I can review it.”

**Reasoning**:
- User says “draft” (no send) → set `send: false`.
- Use writing agent to format the summary before drafting the email.
- Final reply should clarify that the email is waiting for review.

```json
{
  "goal": "Prepare a quarterly summary email for user review (do not send automatically)",
  "steps": [
    {
      "id": 1,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": [
          "$session.quarterly_summary_notes"
        ],
        "synthesis_style": "concise",
        "format": "email_bullets",
        "title": "Quarterly Highlights"
      },
      "dependencies": [],
      "reasoning": "Transform the raw notes into email-ready bullet points."
    },
    {
      "id": 2,
      "action": "compose_email",
      "parameters": {
        "subject": "Quarterly Highlights (Draft)",
        "body": "$step1.synthesized_content",
        "send": false
      },
      "dependencies": [1],
      "reasoning": "Create an email draft so the user can review before sending."
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Drafted the quarterly summary email—ready for your review.",
        "details": "$step1.synthesized_content",
        "status": "info"
      },
      "dependencies": [2],
      "reasoning": "Let the user know the draft is saved and awaiting approval."
    }
  ],
  "complexity": "simple"
}
```
