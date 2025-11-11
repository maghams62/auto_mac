## Example 1: Simple Task (2 steps)

**Note:** "Tesla Autopilot" is the document name from the user's request - the system searches for whatever documents the user actually has.

### User Request
"Send me the Tesla Autopilot document"

### Decomposition
```json
{
  "goal": "Find and email the Tesla Autopilot document",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "Tesla Autopilot"
      },
      "dependencies": [],
      "reasoning": "First, we need to locate the document in the indexed collection",
      "expected_output": "Document path and metadata"
    },
    {
      "id": 2,
      "action": "compose_email",
      "parameters": {
        "subject": "Tesla Autopilot Document",
        "body": "Here is the Tesla Autopilot document you requested.",
        "recipient": null,
        "attachments": ["$step1.doc_path"],
        "send": true
      },
      "dependencies": [1],
      "reasoning": "User said 'Send me' - this means send immediately, not draft",
      "expected_output": "Email sent successfully"
    }
  ],
  "complexity": "simple"
}
```

---
