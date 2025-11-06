# Few-Shot Examples: Task Decomposition

## Important: Context Variable Usage

When passing data between steps:
- ✅ For lists: Use `$stepN.field_name` directly (e.g., `$step2.page_numbers`, `$step2.screenshot_paths`)
- ❌ Don't wrap in brackets: `["$step2.page_numbers"]` is WRONG
- ❌ Don't use singular when field is plural: `$step2.page_number` when tool returns `page_numbers`

**Common Fields:**
- `extract_section` returns: `page_numbers` (list of ints)
- `take_screenshot` returns: `screenshot_paths` (list of strings)
- `search_documents` returns: `doc_path` (string)

## Example 1: Simple Task (2 steps)

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
        "send": false
      },
      "dependencies": [1],
      "reasoning": "Compose email with the found document attached",
      "expected_output": "Email draft opened in Mail.app"
    }
  ],
  "complexity": "simple"
}
```

---

## Example 2: Screenshot Section + Email (4 steps)

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

## Example 3: Medium-Complex Task (5 steps)

### User Request
"Create a Keynote presentation from the AI research paper — just use the summary section"

### Decomposition
```json
{
  "goal": "Find paper, extract summary, generate Keynote slides",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "AI research paper"
      },
      "dependencies": [],
      "reasoning": "Locate the AI research paper in the document index",
      "expected_output": "Document: /Documents/ai_research.pdf"
    },
    {
      "id": 2,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "summary"
      },
      "dependencies": [1],
      "reasoning": "Extract only the summary section as requested",
      "expected_output": "Summary text (5-10 paragraphs)"
    },
    {
      "id": 3,
      "action": "create_keynote",
      "parameters": {
        "title": "AI Research Summary",
        "content": "$step2.extracted_text"
      },
      "dependencies": [2],
      "reasoning": "Generate Keynote presentation from extracted summary",
      "expected_output": "Keynote file created and opened"
    }
  ],
  "complexity": "medium"
}
```

---

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

## Example 5: Parallel Execution (Complex)

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

## Pattern Recognition

### Simple Pattern (Linear Chain)
```
Search → Extract → Action
```

### Medium Pattern (Sequential with Context)
```
Search → Extract → Transform → Output
```

### Complex Pattern (Multi-Stage)
```
Search → Extract → [Branch A, Branch B] → Merge/Multiple Outputs
```

### Parallel Pattern (Fork-Join)
```
       ┌→ Path A → Output A
Search ┤
       └→ Path B → Output B
```

---

## Common Mistakes to Avoid

❌ **Skipping search step**
```json
{
  "steps": [
    {"action": "extract_section", "parameters": {"doc_path": "unknown"}}
  ]
}
```

✅ **Always search first**
```json
{
  "steps": [
    {"action": "search_documents", "parameters": {"query": "..."}},
    {"action": "extract_section", "parameters": {"doc_path": "$step1.doc_path"}}
  ]
}
```

---

❌ **Missing dependencies**
```json
{
  "steps": [
    {"id": 1, "action": "search_documents"},
    {"id": 2, "action": "compose_email", "dependencies": []}  // Wrong!
  ]
}
```

✅ **Explicit dependencies**
```json
{
  "steps": [
    {"id": 1, "action": "search_documents"},
    {"id": 2, "action": "compose_email", "dependencies": [1]}  // Correct
  ]
}
```

---

❌ **Vague parameters**
```json
{
  "action": "extract_section",
  "parameters": {"section": "the important part"}
}
```

✅ **Specific parameters**
```json
{
  "action": "extract_section",
  "parameters": {"section": "summary" | "page 5" | "introduction"}
}
```

---

## Context Passing Syntax

Use `$step{N}.{field}` to reference outputs from earlier steps:

- `$step1.doc_path` - Document path from search
- `$step2.extracted_text` - Text from extraction
- `$step3.screenshot_path` - Screenshot file path
- `$step4.keynote_path` - Keynote file path

This enables chaining steps together with explicit data flow.
