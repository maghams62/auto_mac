# Tool Definitions

Complete specification of available tools for the automation agent.

---

## 1. search_documents

**Purpose:** Find documents using semantic search

**Parameters:**
```json
{
  "query": "string - Natural language search query"
}
```

**Returns:**
```json
{
  "doc_path": "string - Absolute path to document",
  "doc_title": "string - Document title",
  "relevance_score": "float - Similarity score (0-1)",
  "metadata": {
    "file_type": "pdf | docx | txt",
    "page_count": "int",
    "last_modified": "datetime"
  }
}
```

**Example:**
```json
{
  "action": "search_documents",
  "parameters": {
    "query": "Tesla Autopilot safety report"
  }
}
```

---

## 2. extract_section

**Purpose:** Extract specific content from documents

**Parameters:**
```json
{
  "doc_path": "string - Path to document",
  "section": "string - Section identifier (see below)"
}
```

**Section Identifiers:**
- `"all"` - Entire document
- `"summary"` - Summary section
- `"introduction"` - Introduction section
- `"conclusion"` - Conclusion section
- `"page N"` - Specific page number
- `"pages N-M"` - Page range
- `"pages containing 'keyword'"` - Pages with keyword

**Returns:**
```json
{
  "extracted_text": "string - Extracted content",
  "page_numbers": "list[int] - Pages included",
  "word_count": "int"
}
```

**Example:**
```json
{
  "action": "extract_section",
  "parameters": {
    "doc_path": "/Users/me/Documents/report.pdf",
    "section": "summary"
  }
}
```

---

## 3. take_screenshot

**Purpose:** Capture page images from documents

**Parameters:**
```json
{
  "doc_path": "string - Path to document",
  "pages": "list[int] - Page numbers to capture"
}
```

**Returns:**
```json
{
  "screenshot_paths": "list[string] - Paths to saved images",
  "pages_captured": "list[int]"
}
```

**Example:**
```json
{
  "action": "take_screenshot",
  "parameters": {
    "doc_path": "/Users/me/Documents/report.pdf",
    "pages": [3, 5, 7]
  }
}
```

---

## 4. compose_email

**Purpose:** Create and optionally send emails via Mail.app

**Parameters:**
```json
{
  "subject": "string - Email subject",
  "body": "string - Email body (supports markdown)",
  "recipient": "string | null - Email address (null = draft only)",
  "attachments": "list[string] - File paths to attach",
  "send": "bool - If true, send immediately; if false, open draft"
}
```

**Returns:**
```json
{
  "status": "sent | draft",
  "message_id": "string - Mail.app message ID"
}
```

**Example:**
```json
{
  "action": "compose_email",
  "parameters": {
    "subject": "Q3 Report",
    "body": "Please find the Q3 earnings report attached.",
    "recipient": "john@example.com",
    "attachments": ["/Users/me/Documents/q3.pdf"],
    "send": true
  }
}
```

---

## 5. create_keynote

**Purpose:** Generate Keynote presentation from content

**Parameters:**
```json
{
  "title": "string - Presentation title",
  "content": "string - Source content to transform into slides",
  "output_path": "string | null - Save location (null = default)"
}
```

**Returns:**
```json
{
  "keynote_path": "string - Path to created .key file",
  "slide_count": "int"
}
```

**Example:**
```json
{
  "action": "create_keynote",
  "parameters": {
    "title": "AI Research Overview",
    "content": "Introduction: AI has transformed...\n\nKey Findings: ...",
    "output_path": null
  }
}
```

---

## 6. create_pages_doc

**Purpose:** Generate Pages document from content

**Parameters:**
```json
{
  "title": "string - Document title",
  "content": "string - Source content to format",
  "output_path": "string | null - Save location (null = default)"
}
```

**Returns:**
```json
{
  "pages_path": "string - Path to created .pages file",
  "page_count": "int"
}
```

**Example:**
```json
{
  "action": "create_pages_doc",
  "parameters": {
    "title": "Meeting Notes",
    "content": "# Meeting Summary\n\nAttendees: ...\n\nKey Decisions: ...",
    "output_path": null
  }
}
```

---

## Tool Chaining Patterns

### Pattern 1: Search → Email
```
search_documents → compose_email (attach doc_path)
```

### Pattern 2: Search → Extract → Email
```
search_documents → extract_section → compose_email (attach text)
```

### Pattern 3: Search → Screenshot → Email
```
search_documents → take_screenshot → compose_email (attach screenshots)
```

### Pattern 4: Search → Extract → Create Presentation
```
search_documents → extract_section → create_keynote
```

### Pattern 5: Search → Extract → Create Document
```
search_documents → extract_section → create_pages_doc
```

### Pattern 6: Complex Multi-Output
```
search_documents → extract_section → [create_keynote, create_pages_doc, compose_email]
```

---

## Error Handling

Each tool returns an error structure if execution fails:

```json
{
  "error": true,
  "error_type": "NotFoundError | PermissionError | ValidationError",
  "error_message": "Detailed error description",
  "retry_possible": "bool"
}
```

**Agent should:**
1. Check for `error: true` in tool output
2. If `retry_possible: true`, attempt alternative approach
3. If error persists, inform user and suggest manual action

---

## Context Variables

Tools can reference outputs from previous steps using the `$stepN.field` syntax:

```json
{
  "action": "compose_email",
  "parameters": {
    "attachments": ["$step2.screenshot_paths", "$step1.doc_path"]
  }
}
```

This is resolved at execution time by the agent framework.
