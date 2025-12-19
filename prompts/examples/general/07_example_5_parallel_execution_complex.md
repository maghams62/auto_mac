## Example 5: Parallel Execution (Complex)

**Note:** "Tesla Autopilot" is the document name from the user's request - the system searches for whatever documents the user actually has.

### User Request
"Find the Tesla Autopilot doc. Send me a screenshot of page 3, and also create a Pages document with just the introduction section."

### Decomposition
```json
{
  "goal": "Search once, then fork into two parallel paths",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "Tesla Autopilot"
      },
      "dependencies": [],
      "reasoning": "Single search shared by both paths",
      "expected_output": "Document path"
    },
    {
      "id": 2,
      "action": "take_screenshot",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "pages": [3]
      },
      "dependencies": [1],
      "reasoning": "Path A: Screenshot page 3",
      "expected_output": "Screenshot file"
    },
    {
      "id": 3,
      "action": "compose_email",
      "parameters": {
        "subject": "Tesla Autopilot - Page 3",
        "body": "Screenshot of page 3 from Tesla Autopilot document.",
        "recipient": null,
        "attachments": ["$step2.screenshot_path"],
        "send": false
      },
      "dependencies": [2],
      "reasoning": "Path A: Email screenshot",
      "expected_output": "Email draft"
    },
    {
      "id": 4,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "introduction"
      },
      "dependencies": [1],
      "reasoning": "Path B: Extract introduction section",
      "expected_output": "Introduction text"
    },
    {
      "id": 5,
      "action": "create_pages_doc",
      "parameters": {
        "title": "Tesla Autopilot - Introduction",
        "content": "$step4.extracted_text"
      },
      "dependencies": [4],
      "reasoning": "Path B: Create Pages document",
      "expected_output": "Pages document created"
    }
  ],
  "complexity": "complex",
  "execution_note": "Steps 2-3 and steps 4-5 can run in parallel after step 1 completes"
}
```

---
