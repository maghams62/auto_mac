## Example 2: Screenshot Section + Email (4 steps)

**Note:** "The Night We Met" is the document name from the user's request - the system searches for whatever documents the user actually has.

### User Request
"Send screenshots of the pre-chorus from The Night We Met to user@example.com"

### Decomposition
```json
{
  "goal": "Find document, identify pages with pre-chorus, screenshot them, and email",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "The Night We Met"
      },
      "dependencies": [],
      "reasoning": "Locate the document containing 'The Night We Met'",
      "expected_output": "Document path"
    },
    {
      "id": 2,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "pre-chorus"
      },
      "dependencies": [1],
      "reasoning": "Find which pages contain the pre-chorus section",
      "expected_output": "page_numbers: [3]"
    },
    {
      "id": 3,
      "action": "take_screenshot",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "pages": "$step2.page_numbers"
      },
      "dependencies": [2],
      "reasoning": "Capture screenshots of pages containing pre-chorus",
      "expected_output": "screenshot_paths: ['/tmp/page3.png']"
    },
    {
      "id": 4,
      "action": "compose_email",
      "parameters": {
        "subject": "Pre-Chorus from The Night We Met",
        "body": "Attached are screenshots of the pre-chorus section.",
        "recipient": "user@example.com",
        "attachments": "$step3.screenshot_paths",
        "send": true
      },
      "dependencies": [3],
      "reasoning": "Email the screenshots to the specified recipient",
      "expected_output": "Email sent"
    }
  ],
  "complexity": "medium"
}
```

**Critical Notes:**
- ✅ Step 3 uses `"pages": "$step2.page_numbers"` (correct - pass the list directly)
- ❌ NOT `"pages": ["$step2.page_numbers"]` (wrong - wrapping in array)
- ❌ NOT `"pages": "$step2.page_number"` (wrong - field doesn't exist)
- ✅ Step 4 uses `"attachments": "$step3.screenshot_paths"` (correct - pass the list)

---
