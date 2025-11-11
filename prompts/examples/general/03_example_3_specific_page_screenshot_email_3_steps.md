## Example 3: Specific Page Screenshot + Email (3 steps)

### User Request
"Find the Q3 earnings report and send page 5 as a screenshot to john@example.com"

### Decomposition
```json
{
  "goal": "Locate document, extract specific page screenshot, email to recipient",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "Q3 earnings report"
      },
      "dependencies": [],
      "reasoning": "Search for the Q3 earnings report document",
      "expected_output": "Document path: /path/to/q3_earnings.pdf"
    },
    {
      "id": 2,
      "action": "take_screenshot",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "pages": [5]
      },
      "dependencies": [1],
      "reasoning": "Capture page 5 as an image for email attachment",
      "expected_output": "Screenshot saved: /tmp/screenshot_page5.png"
    },
    {
      "id": 3,
      "action": "compose_email",
      "parameters": {
        "subject": "Q3 Earnings Report - Page 5",
        "body": "Please find attached page 5 from the Q3 earnings report.",
        "recipient": "john@example.com",
        "attachments": ["$step2.screenshot_path"],
        "send": true
      },
      "dependencies": [2],
      "reasoning": "Send email with screenshot to specified recipient",
      "expected_output": "Email sent successfully"
    }
  ],
  "complexity": "medium"
}
```

---
