## Example 4: Complex Task (7 steps)

### User Request
"Find the marketing strategy document, send me screenshots of pages with 'customer engagement', then create a slide deck summarizing those sections and email it to team@company.com"

### Decomposition
```json
{
  "goal": "Multi-stage workflow: search, filter pages, screenshot, summarize, present, email",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "marketing strategy document"
      },
      "dependencies": [],
      "reasoning": "Find the marketing strategy document",
      "expected_output": "Document path identified"
    },
    {
      "id": 2,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "pages containing 'customer engagement'"
      },
      "dependencies": [1],
      "reasoning": "Identify which pages contain the keyword",
      "expected_output": "Page numbers: [3, 7, 12]"
    },
    {
      "id": 3,
      "action": "take_screenshot",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "pages": "$step2.page_numbers"
      },
      "dependencies": [2],
      "reasoning": "Capture screenshots of relevant pages",
      "expected_output": "3 screenshot files"
    },
    {
      "id": 4,
      "action": "compose_email",
      "parameters": {
        "subject": "Customer Engagement Pages - Marketing Strategy",
        "body": "Here are the pages from the marketing strategy document that discuss customer engagement.",
        "recipient": null,
        "attachments": "$step3.screenshot_paths",
        "send": false
      },
      "dependencies": [3],
      "reasoning": "Email screenshots to user for review",
      "expected_output": "Email draft created"
    },
    {
      "id": 5,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "text from pages " + str($step2.page_numbers)
      },
      "dependencies": [2],
      "reasoning": "Extract text content from those pages for summarization",
      "expected_output": "Full text from pages 3, 7, 12"
    },
    {
      "id": 6,
      "action": "create_keynote",
      "parameters": {
        "title": "Customer Engagement Strategy",
        "content": "$step5.extracted_text"
      },
      "dependencies": [5],
      "reasoning": "Generate presentation summarizing customer engagement sections",
      "expected_output": "Keynote presentation created"
    },
    {
      "id": 7,
      "action": "compose_email",
      "parameters": {
        "subject": "Customer Engagement Strategy - Presentation",
        "body": "Please find attached the Keynote presentation summarizing our customer engagement strategy sections.",
        "recipient": "team@company.com",
        "attachments": ["$step6.keynote_path"],
        "send": true
      },
      "dependencies": [6],
      "reasoning": "Send presentation to team email",
      "expected_output": "Email sent to team"
    }
  ],
  "complexity": "complex"
}
```

**Key Insights:**
- Step 4 and steps 5-7 can run in parallel (independent branches)
- Step 4 sends screenshots directly to user
- Steps 5-7 create and email the presentation
- Dependencies are explicitly tracked

---
