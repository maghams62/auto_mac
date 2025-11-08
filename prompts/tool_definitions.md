# Tool Definitions

Complete specification of available tools for the automation agent.

**CRITICAL INSTRUCTIONS FOR TOOL USAGE:**
1. **Tool Validation**: Before using ANY tool, verify it exists in this list
2. **Parameter Requirements**: All REQUIRED parameters must be provided
3. **Type Safety**: Match parameter types exactly (string, int, list, etc.)
4. **Error Handling**: Check return values for "error": true field
5. **Early Rejection**: If a needed tool doesn't exist, reject the task immediately with complexity="impossible"

---

## 1. search_documents

**Purpose:** Find documents using semantic search

**When to use:**
- User asks to "find", "search for", or "locate" a document
- Need to identify document path before extracting/processing
- First step in most document workflows

**When NOT to use:**
- Document path is already known
- User wants to create new content (not search existing)
- Task requires web search (use google_search instead)

**Parameters:**
```json
{
  "query": "string - REQUIRED - Natural language search query describing the document"
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

**Error Returns:**
```json
{
  "error": true,
  "error_type": "NotFoundError",
  "error_message": "No documents found matching query: [query]",
  "retry_possible": true
}
```

**Example:**
```json
{
  "action": "search_documents",
  "parameters": {
    "query": "Tesla Autopilot safety report"
  },
  "reasoning": "First locate the document before we can extract or screenshot from it"
}
```

**Common Mistakes:**
- ❌ Forgetting this step and trying to use doc_path without searching
- ❌ Using vague queries like "document" (be specific!)
- ✅ Use descriptive queries: "Q3 earnings report", "marketing strategy document", "The Night We Met lyrics"

---

## 2. extract_section

**Purpose:** Extract specific content from documents using LLM-based interpretation

**When to use:**
- Need to extract text content from a document
- User specifies section, pages, or content to extract
- Want semantic extraction (e.g., "chorus", "introduction", "key findings")

**When NOT to use:**
- Need visual/image capture (use take_screenshot instead)
- Document hasn't been found yet (use search_documents first)
- Need entire document unchanged (get doc_path from search_documents)

**Parameters:**
```json
{
  "doc_path": "string - REQUIRED - Path to document (usually from search_documents)",
  "section": "string - REQUIRED - Section identifier describing what to extract"
}
```

**Section Identifiers (Examples):**
- `"all"` - Entire document
- `"summary"`, `"introduction"`, `"conclusion"` - Named sections
- `"page 5"` - Specific page number
- `"pages 1-3"` - Page range
- `"last page"` - Last page of document
- `"first 2 pages"` - First N pages
- `"chorus"`, `"pre-chorus"` - For music/lyrics (semantic)
- `"pages containing 'customer engagement'"` - Keyword-based

**Returns:**
```json
{
  "extracted_text": "string - Extracted content as text",
  "page_numbers": "list[int] - Pages included in extraction",
  "word_count": "int - Total words extracted"
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "ExtractionError | ParseError",
  "error_message": "Failed to parse document: [path]",
  "retry_possible": false
}
```

**Example:**
```json
{
  "action": "extract_section",
  "parameters": {
    "doc_path": "$step1.doc_path",
    "section": "summary"
  },
  "dependencies": [1],
  "reasoning": "Extract only the summary section as requested by user"
}
```

**Common Mistakes:**
- ❌ Using hardcoded path instead of $step1.doc_path
- ❌ Asking for "page 1-3" when LLM interprets as "pages 1-3"
- ❌ Not specifying dependencies when using $stepN.doc_path
- ✅ Use semantic descriptions: "chorus", "key findings", "methodology section"
- ✅ Be specific: "last 2 pages" instead of "end"

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

## 6. create_keynote_with_images

**Purpose:** Create Keynote presentation with screenshots/images as slides

**Parameters:**
```json
{
  "title": "string - Presentation title",
  "image_paths": "list[string] - Paths to image files (screenshots, photos, etc.)",
  "output_path": "string | null - Save location (null = default)"
}
```

**Returns:**
```json
{
  "keynote_path": "string - Path to created .key file",
  "slide_count": "int",
  "message": "string"
}
```

**Use this when:**
- User wants a slide deck WITH screenshots
- User wants to create presentation from images
- Screenshots should be displayed as images, not text

**Example:**
```json
{
  "action": "create_keynote_with_images",
  "parameters": {
    "title": "Guitar Tab - Chorus",
    "image_paths": ["$step3.screenshot_paths"],
    "output_path": null
  }
}
```

**Note:** `image_paths` can accept a list from previous step (like `$step3.screenshot_paths`) which will be automatically flattened.

---

## 7. create_pages_doc

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

## 8. organize_files

**Purpose:** Organize files into folders using LLM-driven categorization

**⚠️ IMPORTANT: This is a COMPLETE, STANDALONE tool!**
- Creates the target folder automatically (NO separate folder creation needed!)
- Uses LLM to categorize files
- Moves/copies matching files
- All in ONE step!

**Parameters:**
```json
{
  "category": "string - Description of files to organize (e.g., 'music notes', 'work documents')",
  "target_folder": "string - Name or path of target folder (will be created automatically)",
  "move_files": "bool - If true, move files; if false, copy files (default: true)"
}
```

**Returns:**
```json
{
  "files_moved": "list[string] - Filenames that were moved/copied",
  "files_skipped": "list[string] - Filenames that were skipped",
  "target_path": "string - Absolute path to target folder (created automatically)",
  "total_evaluated": "int - Total files evaluated",
  "reasoning": "dict[string, string] - Filename -> reasoning for inclusion/exclusion",
  "message": "string - Summary message"
}
```

**How It Works:**
- **Step 1:** Creates target folder automatically (if it doesn't exist)
- **Step 2:** Uses LLM to analyze file names and document content
- **Step 3:** LLM decides which files belong to the category (NO hardcoded patterns!)
- **Step 4:** Moves or copies matching files to the folder
- Provides detailed reasoning for each file decision

**Example:**
```json
{
  "action": "organize_files",
  "parameters": {
    "category": "music notes",
    "target_folder": "music stuff",
    "move_files": true
  }
}
```

**Use Cases:**
- "Organize all my music notes to a single folder called music stuff" → Just call organize_files, done!
- "Copy all work-related documents to a Work folder" → Just call organize_files, done!
- "Move research papers into a Research directory" → Just call organize_files, done!

**Common Mistakes to Avoid:**
- ❌ DON'T create a separate `create_folder` step - organize_files does this automatically!
- ❌ DON'T search for files first - organize_files handles file discovery!
- ✅ DO call organize_files directly as a single step

**Note:** The LLM uses semantic understanding to categorize files. For example, when organizing "music notes", it will include files like "Bad Liar.pdf" (song lyrics) but exclude "WebAgents-Oct30th.pdf" (technical document). No hardcoded file type or name pattern matching!

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

### Pattern 6: Screenshot → Presentation → Email
```
search_documents → take_screenshot → create_keynote_with_images → compose_email
```

### Pattern 7: Complex Multi-Output
```
search_documents → extract_section → [create_keynote, create_pages_doc, compose_email]
```

### Pattern 8: File Organization
```
organize_files (standalone - organizes files based on category)
```

### Pattern 9: Multi-Source Research Report (NEW - Writing Agent)
```
search_documents (multiple queries) → extract_section (multiple docs) → synthesize_content → create_detailed_report → create_pages_doc
```

### Pattern 10: Presentation from Multiple Sources (NEW - Writing Agent)
```
search_documents (multiple queries) → extract_section (multiple docs) → synthesize_content → create_slide_deck_content → create_keynote
```

### Pattern 11: Web Research to Report (NEW - Writing Agent)
```
google_search → navigate_to_url → extract_page_content (multiple pages) → synthesize_content → create_detailed_report → create_pages_doc
```

### Pattern 12: Meeting Notes Documentation (NEW - Writing Agent)
```
search_documents → extract_section → create_meeting_notes → compose_email (send to attendees)
```

### Pattern 13: Hybrid Research (Documents + Web) (NEW - Writing Agent)
```
[search_documents, google_search] → [extract_section, extract_page_content] → synthesize_content → create_slide_deck_content → create_keynote
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

## 9. synthesize_content

**Purpose:** Synthesize information from multiple sources into cohesive content

**Parameters:**
```json
{
  "source_contents": "list[string] - List of text contents to synthesize",
  "topic": "string - Main topic or focus for synthesis",
  "synthesis_style": "string - How to synthesize: 'comprehensive' | 'concise' | 'comparative' | 'chronological' (default: comprehensive)"
}
```

**Synthesis Styles:**
- `"comprehensive"` - Include all important details (for reports)
- `"concise"` - Focus on key points only (for summaries)
- `"comparative"` - Highlight differences and similarities
- `"chronological"` - Organize by timeline/sequence

**Returns:**
```json
{
  "synthesized_content": "string - Cohesive synthesized narrative",
  "key_points": "list[string] - Main bullet points",
  "themes_identified": "list[string] - Key themes found",
  "source_count": "int - Number of sources used",
  "word_count": "int"
}
```

**Example:**
```json
{
  "action": "synthesize_content",
  "parameters": {
    "source_contents": ["$step1.extracted_text", "$step2.content"],
    "topic": "AI Safety Research",
    "synthesis_style": "comprehensive"
  }
}
```

**Use this when:**
- You have multiple documents/sources to combine
- Need to remove redundancy across sources
- Want to create a unified narrative from disparate sources
- Building research reports or comprehensive summaries

---

## 10. create_slide_deck_content

**Purpose:** Transform content into concise, bullet-point format for slide decks

**Parameters:**
```json
{
  "content": "string - Source content to transform",
  "title": "string - Presentation title/topic",
  "num_slides": "int | null - Target number of slides (null = auto-determine)"
}
```

**Returns:**
```json
{
  "slides": "list[object] - List of slide objects with title, bullets, notes",
  "total_slides": "int - Number of content slides",
  "formatted_content": "string - Formatted text ready for create_keynote"
}
```

**Slide Format:**
Each slide object contains:
- `slide_number` - Slide number
- `title` - Slide title
- `bullets` - List of 3-5 short bullet points (5-7 words each)
- `notes` - Optional speaker notes

**Example:**
```json
{
  "action": "create_slide_deck_content",
  "parameters": {
    "content": "$step1.synthesized_content",
    "title": "Q4 Marketing Strategy",
    "num_slides": 5
  }
}
```

**Use this when:**
- Creating presentations with concise messaging
- Need bullet-point format (NOT long paragraphs)
- Want presentation-ready content structure
- Prefer to chain with `create_keynote` for final output

---

## 11. create_detailed_report

**Purpose:** Transform content into detailed, well-structured long-form reports

**Parameters:**
```json
{
  "content": "string - Source content to transform",
  "title": "string - Report title",
  "report_style": "string - Writing style: 'business' | 'academic' | 'technical' | 'executive' (default: business)",
  "include_sections": "list[string] | null - Specific sections to include (null = auto-generate)"
}
```

**Report Styles:**
- `"business"` - Professional, action-oriented
- `"academic"` - Formal, analytical, citation-focused
- `"technical"` - Detailed, precise, specification-focused
- `"executive"` - High-level, strategic, concise

**Returns:**
```json
{
  "report_content": "string - Complete formatted report with section headers",
  "sections": "list[object] - List of section objects with name, content, word_count",
  "executive_summary": "string - Brief overview (2-3 sentences)",
  "total_word_count": "int",
  "report_style": "string"
}
```

**Example:**
```json
{
  "action": "create_detailed_report",
  "parameters": {
    "content": "$step1.synthesized_content",
    "title": "Annual Security Audit Report",
    "report_style": "technical",
    "include_sections": ["Executive Summary", "Findings", "Recommendations"]
  }
}
```

**Use this when:**
- Need long-form, detailed writing (NOT bullet points)
- Creating formal reports or documentation
- Want flowing prose with proper structure
- Prefer to chain with `create_pages_doc` for final output

---

## 12. create_meeting_notes

**Purpose:** Transform content into structured meeting notes with action items

**Parameters:**
```json
{
  "content": "string - Source content (transcript, rough notes)",
  "meeting_title": "string - Title/topic of meeting",
  "attendees": "list[string] | null - Attendee names (optional)",
  "include_action_items": "bool - Extract action items (default: true)"
}
```

**Returns:**
```json
{
  "formatted_notes": "string - Complete formatted meeting notes",
  "discussion_points": "list[string] - Key discussion points",
  "decisions": "list[string] - Decisions made",
  "action_items": "list[object] - Action items with owner and deadline",
  "key_takeaways": "list[string] - Main takeaways",
  "meeting_title": "string",
  "attendees": "list[string]"
}
```

**Action Item Format:**
```json
{
  "item": "Action description",
  "owner": "Person name or null",
  "deadline": "Date or null"
}
```

**Example:**
```json
{
  "action": "create_meeting_notes",
  "parameters": {
    "content": "$step1.extracted_text",
    "meeting_title": "Q1 Planning Meeting",
    "attendees": ["Alice", "Bob", "Charlie"],
    "include_action_items": true
  }
}
```

**Use this when:**
- Processing meeting transcripts or rough notes
- Need to extract action items and owners
- Want structured, professional meeting documentation
- Creating notes for distribution to team

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
