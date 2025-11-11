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
    "doc_path": "$step1.doc_path",
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
  "recipient": "string | null - Email address. If null, empty, or contains 'me'/'to me'/'my email', will use default_recipient from config.yaml (null = draft only if no default)",
  "attachments": "list[string] - File paths to attach",
  "send": "bool - If true, send immediately; if false, open draft"
}
```

**Special Behavior:**
- If recipient is None, empty string, "me", "to me", "my email", or "myself", the tool automatically uses the `default_recipient` email address from config.yaml
- This allows users to say "email the link to me" and it will use their configured default email (e.g., `your-email@example.com` from config.yaml)

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
    "attachments": ["$step1.doc_path"],
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

## 9. create_zip_archive

**Purpose:** Compress folders/files into a ZIP archive with optional include/exclude filters.

**Parameters:**
```json
{
  "source_path": "string - OPTIONAL - Folder/file to compress (defaults to primary document directory)",
  "zip_name": "string - OPTIONAL - Output archive name ('.zip' appended automatically)",
  "include_pattern": "string - OPTIONAL - Glob filter (default '*')",
  "include_extensions": "list[string] - OPTIONAL - Only include these extensions (e.g., ['pdf','txt'])",
  "exclude_extensions": 'list[string] - OPTIONAL - Skip these extensions (e.g., ["mp3","wav"])'
}
```

**Returns:**
```json
{
  "zip_path": "string",
  "file_count": "int",
  "total_size": "int",
  "compressed_size": "int",
  "included_extensions": "list[string] | null",
  "excluded_extensions": "list[string] | null",
  "message": "string"
}
```

**Examples:**
```json
{
  "action": "create_zip_archive",
  "parameters": {
    "zip_name": "study_stuff.zip",  // Use user-specified name from request
    "exclude_extensions": ["mp3", "wav", "flac"]
  }
}
```

**Planner Tips:**
- **IMPORTANT**: If `source_path` is omitted or null, the tool automatically zips from the primary configured document directory. Only specify source_path if the user explicitly mentions a specific subfolder.
- Use `include_pattern` for filename patterns (e.g., "A*" for files starting with "A").
- Use `exclude_extensions` for requests like "zip all non-music files".
- Use `include_extensions` to target specific file types (e.g., only PDFs).
- No need to create temporary folders; filtering happens during ZIP creation.
- Pair with `compose_email` when the user wants the ZIP sent out.

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

## 10. synthesize_content

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

## 11. create_slide_deck_content

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

## 12. create_detailed_report

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

## 13. create_meeting_notes

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

## 14. ensure_discord_session

**Purpose:** Bring the Discord desktop app to the front and perform login via macOS automation.

**How it works:**
- Activates Discord.app
- Uses credentials from `.env` (`DISCORD_EMAIL`, `DISCORD_PASSWORD`) through MacMCP UI scripting
- Skips login when credentials are missing or session is already active

**Parameters:**
```json
{}
```

**Returns:**
```json
{
  "status": "string - skipped | login_submitted | already_logged_in",
  "needs_login": "bool",
  "raw_response": "string - Raw AppleScript output"
}
```

**Use this when:**
- Unsure whether Discord is already authenticated
- Before attempting channel reads/posts after a reboot
- Testing MacMCP accessibility permissions for Discord

---

## 15. navigate_discord_channel

**Purpose:** Jump to a Discord server/channel using the Cmd+K quick switcher.

**Parameters:**
```json
{
  "channel_name": "string - REQUIRED - Channel (e.g., \"general\")",
  "server_name": "string | null - Optional guild/server filter"
}
```

**Returns:**
```json
{
  "success": "bool",
  "status": "string - NAVIGATED or raw automation output",
  "channel": "string",
  "server": "string | null"
}
```

**Use this when:**
- Need to focus a channel before reading or posting
- Want to ensure subsequent Discord actions target the right place

---

## 16. discord_send_message

**Purpose:** Post messages to the currently focused Discord channel via macOS automation.

**Parameters:**
```json
{
  "channel_name": "string - REQUIRED unless default configured",
  "message": "string - REQUIRED - Message body (newlines allowed)",
  "server_name": "string | null - Optional guild/server name",
  "confirm_delivery": "bool - Re-read channel afterward to ensure message appeared (default true)"
}
```

**Returns:**
```json
{
  "success": "bool",
  "channel": "string",
  "server": "string | null",
  "message_preview": "string",
  "delivery_confirmed": "bool | null"
}
```

**Use this when:**
- Sending status updates or bot-style responses through the desktop client
- Sharing results from other agents back into Discord

---

## 17. discord_read_channel_messages

**Purpose:** Scrape recent text from a Discord channel using accessibility APIs (no Discord API needed).

**Parameters:**
```json
{
  "channel_name": "string - REQUIRED unless default configured",
  "limit": "int - Number of most recent messages (default 10)",
  "server_name": "string | null - Optional guild/server name"
}
```

**Returns:**
```json
{
  "messages": "list[string] - Most recent messages (newest last)",
  "sample_size": "int",
  "channel": "string",
  "server": "string | null"
}
```

**Use this when:**
- Need context from a Discord conversation before responding
- Verifying that an automated post successfully appeared
- Capturing a text snapshot before taking a screenshot

---

## 18. discord_detect_unread_channels

**Purpose:** Look for unread indicators (bold text, filled dots) across the server/channel list.

**Parameters:**
```json
{
  "server_name": "string | null - Filter results to a specific guild"
}
```

**Returns:**
```json
{
  "unread_channels": "list[string] - Descriptions of unread items",
  "total_detected": "int",
  "filtered": "string | null - Filter that was applied"
}
```

**Use this when:**
- Determining whether attention is needed before sending new updates
- Building automations that triage unread Discord notifications

---

## 19. discord_capture_recent_messages

**Purpose:** Take a screenshot of the current Discord window for audit or sharing.

**Parameters:**
```json
{
  "channel_name": "string - REQUIRED unless default configured",
  "server_name": "string | null",
  "output_path": "string | null - Custom screenshot path (default saved under data/screenshots)"
}
```

**Returns:**
```json
{
  "screenshot_path": "string - Saved PNG path",
  "channel": "string",
  "server": "string | null"
}
```

**Use this when:**
- Need visual evidence of recent Discord messages
- Preparing reports that include chat transcripts
- Double-checking that UI automation reached the correct channel

---

## 20. verify_discord_channel

**Purpose:** Run an end-to-end health check for the Discord automation stack.

**Parameters:**
```json
{
  "channel_name": "string - REQUIRED unless default configured",
  "server_name": "string | null",
  "send_test_message": "bool - Post a probe message (default false)",
  "test_message": "string | null - Custom probe text"
}
```

**Returns:**
```json
{
  "success": "bool",
  "channel": "string",
  "verification": {
    "login_status": "string",
    "able_to_read": "bool",
    "messages_sampled": "int",
    "message_preview": "list[string]",
    "post_check": "object | null - Result from discord_send_message (if used)"
  }
}
```

**Use this when:**
- Validating that MacMCP can still control Discord after permissions or OS updates
- Before running workflows that depend on Discord posting
- Integrating Discord automation into CI smoke tests

---

## 20. scan_subreddit_posts

**Purpose:** Use Playwright to crawl a subreddit, collect posts/comments, and optionally summarize per an instruction.

**Parameters:**
```json
{
  "subreddit": "string - REQUIRED - e.g., \"startups\", \"SideProject\"",
  "instruction": "string | null - Optional natural-language summary request",
  "sort": "string - Sort order: hot | new | rising | top | controversial (default: hot)",
  "limit_posts": "int - Number of posts to return (default: 10)",
  "include_comments": "bool - Fetch top-level comments for each post (default: true)",
  "comments_limit": "int - Comments per post (default: 5)",
  "comment_threads_limit": "int | null - Limit number of posts that receive comment scraping",
  "headless": "bool | null - Override browser headless mode"
}
```

**Returns:**
```json
{
  "subreddit": "string",
  "sort": "string",
  "url": "string",
  "retrieved_at": "timestamp",
  "post_count": "int",
  "posts": [
    {
      "rank": "int",
      "title": "string",
      "url": "string",
      "author": "string",
      "flair": "string | null",
      "snippet": "string | null",
      "preview_image": "string | null",
      "posted_ago": "string | null",
      "upvotes": "int | null",
      "comments_count": "int | null",
      "top_comments": [
        {
          "author": "string",
          "body": "string",
          "posted_ago": "string | null",
          "score": "int | null"
        }
      ]
    }
  ],
  "analysis": "string - Optional summary (present only when instruction provided)"
}
```

**Use this when:**
- You need to gather qualitative signal from Reddit threads
- The user asks for competitive intel, sentiment, or idea validation sourced from a subreddit
- You plan to feed the structured results into another LLM agent for deeper analysis

**Notes:**
- No subreddits are hardcoded; always pass the target via parameters
- Set `instruction` to automatically add an LLM-written summary (uses configured OpenAI model)
- Reduce `include_comments` to false for faster, post-only sweeps

---

## 21. get_directions

**Purpose:** Get simple point-to-point directions with any transportation mode (driving, walking, transit, bicycle).

**Parameters:**
```json
{
  "origin": "string - REQUIRED - Starting location (can be \"Current Location\" or specific address/coordinates)",
  "destination": "string - REQUIRED - End location (address, place name, or coordinates)",
  "transportation_mode": "string - Mode of transportation (default: \"driving\"). Options: \"driving\"/\"car\", \"walking\"/\"walk\", \"transit\"/\"bus\"/\"public transport\", \"bicycle\"/\"bike\"/\"cycling\"",
  "open_maps": "bool - If true, automatically open Maps with the route (default: true)"
}
```

**Returns:**
```json
{
  "origin": "string",
  "destination": "string",
  "transportation_mode": "string - driving/walking/transit/bicycle",
  "maps_url": "string - URL to open in Maps",
  "maps_service": "Apple Maps",
  "maps_opened": "bool - Whether Maps was opened",
  "message": "string - Status message",
  "note": "string - Additional info (e.g., for transit: real-time schedules shown in app)"
}
```

**Use this when:**
- User wants simple point-to-point directions
- User asks for transit/bus schedule ("when's the next bus")
- User wants bicycle or walking directions
- User asks "how do I get to X"
- Origin is often "Current Location" for "from here" queries

**Transportation Mode Mapping:**
- **Driving**: "driving", "car", "drive" → dirflg=d (default)
- **Walking**: "walking", "walk", "on foot" → dirflg=w
- **Transit**: "transit", "bus", "train", "public transport", "BART" → dirflg=r (shows real-time schedules)
- **Bicycle**: "bicycle", "bike", "cycling" → dirflg=b

**Parameter Extraction:**
- **origin**: "from X" → X, "from here"/"from current location" → "Current Location"
- **destination**: "to Y" → Y
- **transportation_mode**: Look for keywords: "bus"/"transit" → "transit", "bike"/"bicycle" → "bicycle", "walk" → "walking", "drive" → "driving"

**Notes:**
- "Current Location" tells Maps to use device's current location automatically
- For transit queries, Maps opens with real-time schedules showing next departure times
- Driving is the default mode if not specified
- Apple Maps will show route-specific info (bike lanes, pedestrian paths, transit schedules)

**Examples:**
```json
// Transit query
{
  "action": "get_directions",
  "parameters": {
    "origin": "Current Location",
    "destination": "Berkeley, CA",
    "transportation_mode": "transit",
    "open_maps": true
  }
}

// Bicycle query
{
  "action": "get_directions",
  "parameters": {
    "origin": "Home",
    "destination": "Office",
    "transportation_mode": "bicycle",
    "open_maps": true
  }
}
```

---

## 22. get_transit_schedule

**Purpose:** Get transit schedule and next departure times for a specific route.

**Parameters:**
```json
{
  "origin": "string - REQUIRED - Starting location (can be \"Current Location\")",
  "destination": "string - REQUIRED - End location",
  "open_maps": "bool - If true, automatically open Maps with transit view (default: true)"
}
```

**Returns:**
```json
{
  "origin": "string",
  "destination": "string",
  "transportation_mode": "transit",
  "maps_url": "string - URL to open in Maps",
  "maps_service": "Apple Maps",
  "maps_opened": "bool - Whether Maps was opened",
  "message": "string - Status message",
  "note": "string - Note about viewing real-time schedules in Maps"
}
```

**Use this when:**
- User specifically asks for transit schedule
- User asks "when's the next bus/train"
- User wants to see departure times
- User asks for BART/metro/subway schedule

**Notes:**
- Opens Apple Maps with transit directions
- Apple Maps shows real-time next departure times
- Cannot programmatically extract schedule data (Apple Maps API limitation)
- User views schedule directly in Maps app

**Example:**
```json
{
  "action": "get_transit_schedule",
  "parameters": {
    "origin": "Current Location",
    "destination": "Downtown Berkeley",
    "open_maps": true
  }
}
```

---

## 23. plan_trip_with_stops

**Purpose:** Plan a road trip from origin to destination with specific numbers of fuel and food stops.

**Parameters:**
```json
{
  "origin": "string - REQUIRED - Starting location (e.g., \"Los Angeles, CA\", \"San Francisco, CA\")",
  "destination": "string - REQUIRED - End location (e.g., \"San Diego, CA\", \"Los Angeles, CA\")",
  "num_fuel_stops": "int - Number of fuel/gas stops (any reasonable number, typically 0-10, default: 0)",
  "num_food_stops": "int - Number of food stops (any reasonable number, default: 0, e.g., 2 for lunch and dinner)",
  "departure_time": "string | null - Departure time in format \"HH:MM AM/PM\" or \"YYYY-MM-DD HH:MM\" (optional)",
  "use_google_maps": "bool - If true, generate Google Maps URL (opens in browser), else Apple Maps (opens in Maps app, default: false). Apple Maps is preferred for macOS and supports waypoints.",
  "open_maps": "bool - If true, automatically open Maps app/browser with the route (default: false)"
}
```

**Returns:**
```json
{
  "origin": "string",
  "destination": "string",
  "stops": [
    {
      "order": "int",
      "location": "string - City/town name",
      "type": "food | fuel"
    }
  ],
  "departure_time": "string | null",
  "maps_url": "string - URL to open in Maps app or browser (ALWAYS provided)",
  "maps_service": "Apple Maps | Google Maps",
  "num_fuel_stops": "int",
  "num_food_stops": "int",
  "total_stops": "int",
  "maps_opened": "bool - Whether Maps was automatically opened",
  "message": "string - Summary message (includes Maps URL)"
}
```

**Use this when:**
- User wants to plan a road trip with stops
- User specifies number of gas/fuel stops needed
- User wants food stops (breakfast, lunch, dinner, etc.)
- User provides departure time
- User wants a route with waypoints

**Parameter Extraction (LLM-Driven):**
- **origin/destination**: Extract from query (handle abbreviations: "LA" → "Los Angeles, CA", "SD" → "San Diego, CA")
- **num_fuel_stops**: Count fuel/gas stops mentioned ("2 gas stops" → 2, "one fuel stop" → 1)
- **num_food_stops**: Count food/meal stops ("lunch and dinner" → 2, "breakfast, lunch, and dinner" → 3)
- **departure_time**: Parse time from query ("5 AM" → "5:00 AM", "7:30 PM" → "7:30 PM")
- **use_google_maps**: Default is false (Apple Maps). Only set to true if user specifically requests Google Maps. Apple Maps supports waypoints and is preferred for macOS.

**Notes:**
- Maximum ~20 total stops (fuel + food combined) - reasonable limit to prevent abuse, but LLM can suggest optimal number
- LLM automatically suggests optimal stop locations along the route (NO hardcoded stops or routes)
- Works for routes worldwide - LLM handles international routes and geographic knowledge
- **Maps URL is ALWAYS provided** in the response - you can use it to open Maps manually or set `open_maps=true` to open automatically
- Apple Maps URL is the default (opens in macOS Maps app, supports waypoints)
- Google Maps URL available as alternative (opens in browser)
- Departure time helps with traffic-aware routing (flexible time format parsing)
- ALL parameter values must be extracted from user's natural language query using LLM reasoning
- NO hardcoded geographic assumptions - LLM determines routes based on origin/destination

**Example:**
```json
{
  "action": "plan_trip_with_stops",
  "parameters": {
    "origin": "Los Angeles, CA",
    "destination": "San Diego, CA",
    "num_fuel_stops": 2,
    "num_food_stops": 2,
    "departure_time": "5:00 AM",
    "use_google_maps": true
  }
}
```

---

## 22. open_maps_with_route

**Purpose:** Open Apple Maps application with a specific route.

**Parameters:**
```json
{
  "origin": "string - REQUIRED - Starting location",
  "destination": "string - REQUIRED - End location",
  "stops": "list[string] | null - Optional list of intermediate stops"
}
```

**Returns:**
```json
{
  "status": "opened",
  "maps_url": "string - URL used to open Maps",
  "message": "string - Status message"
}
```

**Use this when:**
- User wants to open Maps app directly with a route
- You already have a planned route and want to open it
- User wants to see the route in Apple Maps app

**Example:**
```json
{
  "action": "open_maps_with_route",
  "parameters": {
    "origin": "San Francisco, CA",
    "destination": "Los Angeles, CA",
    "stops": ["Gilroy, CA", "Coalinga, CA"]
  }
}
```

---

## 23. summarize_list_activity

**Purpose:** Summarize the top tweets/threads from a configured Twitter List using the official API and LLM.

**Parameters:**
```json
{
  "list_name": "string - OPTIONAL - Logical list key defined under twitter.lists (defaults to twitter.default_list)",
  "lookback_hours": "int - OPTIONAL - Window in hours (default twitter.default_lookback_hours, min 1, max 168)",
  "max_items": "int - OPTIONAL - Number of tweets/threads to highlight (default twitter.max_summary_items, max 10)"
}
```

**Returns:**
```json
{
  "summary": "string - Markdown summary describing trends and highlights",
  "items": [
    {
      "id": "string",
      "text": "string - Combined thread text",
      "author_name": "string",
      "author_handle": "string",
      "created_at": "string - ISO timestamp",
      "score": "float ranking heuristic",
      "url": "string - Canonical tweet URL"
    }
  ],
  "time_window": {
    "hours": "int",
    "start": "ISO timestamp",
    "end": "ISO timestamp"
  },
  "list_name": "string"
}
```

**Example:**
```json
{
  "action": "summarize_list_activity",
  "parameters": {
    "lookback_hours": 6,
    "max_items": 5
  }
}
```

---

## 24. tweet_message

**Purpose:** Publish a tweet using the configured Twitter user credentials.

**Parameters:**
```json
{
  "message": "string - REQUIRED - Tweet content (will be trimmed and must fit Twitter limits)"
}
```

**Returns:**
```json
{
  "success": true,
  "tweet_id": "string",
  "tweet_text": "string",
  "tweet_url": "string",
  "message": "Tweet posted successfully."
}
```

**Example:**
```json
{
  "action": "tweet_message",
  "parameters": {
    "message": "Launch day! 🚀"
  }
}
```

**Notes:**
- Only list names defined in `config.yaml → twitter.lists` are valid.
- Uses official Twitter APIs with credentials from `.env` (`TWITTER_*` variables); scraping is not allowed.
- Automatically expands multi-tweet threads (when available), ranks by engagement, and feeds the content into the configured LLM for a concise summary.

---

## 25. search_bluesky_posts

**Purpose:** Search public Bluesky posts that match a query string.

**Parameters:**
```json
{
  "query": "string - REQUIRED - Search keywords or phrase",
  "max_posts": "int - OPTIONAL - Maximum posts to return (default 10, max 50)"
}
```

**Returns:**
```json
{
  "query": "string",
  "count": "int - number of posts returned",
  "posts": [
    {
      "uri": "string",
      "cid": "string",
      "text": "string",
      "author_handle": "string",
      "author_name": "string",
      "created_at": "ISO timestamp",
      "like_count": "int",
      "repost_count": "int",
      "reply_count": "int",
      "quote_count": "int",
      "score": "float ranking heuristic",
      "url": "string - Public Bluesky URL"
    }
  ]
}
```

**Example:**
```json
{
  "action": "search_bluesky_posts",
  "parameters": {
    "query": "AI agents",
    "max_posts": 10
  }
}
```

---

## 26. summarize_bluesky_posts

**Purpose:** Summarize top Bluesky posts for a query, optionally constrained by time.

**Parameters:**
```json
{
  "query": "string - REQUIRED - Search keywords to focus on",
  "lookback_hours": "int - OPTIONAL - Filter posts newer than this window (default bluesky.default_lookback_hours)",
  "max_items": "int - OPTIONAL - Maximum highlights to summarize (default bluesky.max_summary_items, max 10)"
}
```

**Returns:**
```json
{
  "summary": "string - Markdown overview referencing post numbers",
  "items": [
    {
      "text": "string",
      "author_handle": "string",
      "author_name": "string",
      "created_at": "ISO timestamp",
      "score": "float",
      "url": "string"
    }
  ],
  "query": "string",
  "time_window": {
    "hours": "int",
    "generated_at": "ISO timestamp"
  }
}
```

**Example:**
```json
{
  "action": "summarize_bluesky_posts",
  "parameters": {
    "query": "privacy updates",
    "lookback_hours": 12,
    "max_items": 5
  }
}
```

**Notes:**
- Requires Bluesky credentials in `.env` (`BLUESKY_USERNAME` and `BLUESKY_PASSWORD`).
- Fetches extra posts, ranks by engagement, filters by time, and summarizes with the configured LLM.

---

## 27. post_bluesky_update

**Purpose:** Publish a post (status update) to Bluesky via the AT Protocol.

**Parameters:**
```json
{
  "message": "string - REQUIRED - Post content (must be <= 300 characters)"
}
```

**Returns:**
```json
{
  "success": true,
  "uri": "string - AT Protocol URI of the post",
  "cid": "string",
  "url": "string - Public Bluesky URL (when author handle is known)",
  "message": "Bluesky post published successfully."
}
```

**Example:**
```json
{
  "action": "post_bluesky_update",
  "parameters": {
    "message": "Hello Bluesky! 👋"
  }
}
```

**Notes:**
- Uses the configured account credentials from `.env`.
- Validates that the post respects Bluesky’s 300-character limit.

---

## 28. launch_app

**Purpose:** Launch a macOS application by name.

**Parameters:**
```json
{
  "app_name": "string - REQUIRED - Name of application (e.g., 'Safari', 'Notes', 'Calculator', 'Mail')"
}
```

**Returns:**
```json
{
  "success": true,
  "app_name": "string",
  "status": "launched",
  "message": "string"
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "LaunchFailed | InvalidInput | Timeout",
  "error_message": "string",
  "retry_possible": true
}
```

**Example:**
```json
{
  "action": "launch_app",
  "parameters": {
    "app_name": "Safari"
  }
}
```

**Use this when:**
- User wants to open/launch an application
- Need to start a specific app quickly
- Workflow requires launching an app before other actions

**Notes:**
- Uses `open -a` command (simple and reliable)
- Handles app name variations automatically (e.g., "Safari" or "Safari.app")
- Fast execution without heavy infrastructure

---

## 29. copy_snippet

**Purpose:** Copy text to the macOS clipboard.

**Parameters:**
```json
{
  "text": "string - REQUIRED - Text content to copy to clipboard"
}
```

**Returns:**
```json
{
  "success": true,
  "status": "copied",
  "text_length": "int",
  "text_preview": "string - First 100 characters",
  "message": "string"
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "CopyFailed | InvalidInput | Timeout",
  "error_message": "string",
  "retry_possible": true
}
```

**Example:**
```json
{
  "action": "copy_snippet",
  "parameters": {
    "text": "https://example.com"
  }
}
```

**Use this when:**
- User wants to copy text for pasting elsewhere
- Need to store text temporarily in clipboard
- Preparing content for pasting into other apps

**Notes:**
- Uses `pbcopy` command (standard macOS clipboard utility)
- Fast and reliable clipboard operations
- Supports multi-line text

---

## 30. set_timer

**Purpose:** Set a timer that will notify you when it expires.

**Parameters:**
```json
{
  "duration_minutes": "float - REQUIRED - Duration in minutes (can be decimal, e.g., 0.5 for 30 seconds)",
  "message": "string | null - Optional message to display when timer expires (default: 'Timer expired')"
}
```

**Returns:**
```json
{
  "success": true,
  "status": "set",
  "duration_minutes": "float",
  "duration_seconds": "int",
  "message": "string",
  "expires_at_approx": "string",
  "notification_message": "string"
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "TimerError | InvalidInput",
  "error_message": "string",
  "retry_possible": false
}
```

**Example:**
```json
{
  "action": "set_timer",
  "parameters": {
    "duration_minutes": 25.0,
    "message": "Pomodoro session complete!"
  }
}
```

**Use this when:**
- User wants a reminder after a specific duration
- Need to get notified when time is up
- Creating Pomodoro timers or time-based alerts

**Notes:**
- Uses AppleScript with background process
- Displays notification when timer completes
- Supports decimal minutes (e.g., 0.5 for 30 seconds)
- Non-blocking - runs in background

---

## 31. transcribe_audio_file

**Purpose:** Transcribe an audio file to text using OpenAI Whisper API.

**Parameters:**
```json
{
  "audio_file_path": "string - REQUIRED - Path to audio file (supports: mp3, mp4, mpeg, mpga, m4a, wav, webm)",
  "language": "string | null - Optional language code (e.g., 'en', 'es', 'fr'). If null, auto-detects language"
}
```

**Returns:**
```json
{
  "success": true,
  "text": "string - Transcribed text",
  "language": "string - Language used",
  "file_path": "string",
  "text_length": "int",
  "word_count": "int"
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "TranscriptionError | FileNotFound | InvalidFileType",
  "error_message": "string",
  "retry_possible": true
}
```

**Example:**
```json
{
  "action": "transcribe_audio_file",
  "parameters": {
    "audio_file_path": "/path/to/recording.mp3",
    "language": "en"
  }
}
```

**Use this when:**
- User wants to convert audio/voice recordings to text
- Need to extract text from audio files
- Processing voice memos or recordings

**Notes:**
- Uses OpenAI Whisper API for high-quality transcription
- Supports multiple audio formats (mp3, mp4, wav, webm, etc.)
- Auto-detects language if not specified
- Works with multilingual audio

---

## 32. text_to_speech

**Purpose:** Convert text to speech audio using OpenAI TTS API.

**Parameters:**
```json
{
  "text": "string - REQUIRED - Text to convert to speech (max ~4000 characters)",
  "voice": "string - Voice to use: 'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer' (default: 'alloy')",
  "output_path": "string | null - Optional path to save audio file (default: data/audio/)",
  "speed": "float - Speech speed multiplier 0.25-4.0 (default: 1.0)"
}
```

**Returns:**
```json
{
  "success": true,
  "audio_path": "string - Path to generated audio file",
  "text": "string",
  "voice": "string",
  "speed": "float",
  "text_length": "int",
  "file_size_bytes": "int"
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "TTSError | InvalidInput",
  "error_message": "string",
  "retry_possible": true
}
```

**Example:**
```json
{
  "action": "text_to_speech",
  "parameters": {
    "text": "Hello, your report is ready!",
    "voice": "nova",
    "speed": 1.0
  }
}
```

**Use this when:**
- User wants to generate audio from text
- Need voice responses for queries
- Creating audio versions of text content

**Notes:**
- Uses OpenAI TTS API for natural-sounding speech
- Multiple voice options available
- Adjustable speech speed (0.25x to 4.0x)
- Saves audio files to data/audio/ directory by default

**Available Voices:**
- `alloy` - Balanced, neutral voice
- `echo` - Clear, articulate voice
- `fable` - Expressive, storytelling voice
- `onyx` - Deep, authoritative voice
- `nova` - Bright, energetic voice
- `shimmer` - Soft, gentle voice

---

## 33. reply_to_user

**Purpose:** Deliver the final, user-facing response.

**When to use:**
- After all action steps complete (even for simple, single-tool workflows)
- To summarize outcomes in natural language
- To highlight artifacts (paths, URLs, file names) generated earlier

**When NOT to use:**
- Before the underlying work is done
- As a substitute for action tools

**Parameters:**
```json
{
  "message": "string - REQUIRED - Headline response shown to the user",
  "details": "string - optional - Additional context (Markdown supported)",
  "artifacts": "list[string] - optional - Paths or URLs to surface",
  "status": "string - optional - success | partial_success | info | error (default: success)"
}
```

**Returns:**
```json
{
  "type": "reply",
  "message": "Primary response string",
  "details": "Additional context (if provided)",
  "artifacts": ["List of artifact strings"],
  "status": "Declared status",
  "error": false
}
```

**Example:**
```json
{
  "action": "reply_to_user",
  "parameters": {
    "message": "Summaries delivered! Check the attachment.",
    "details": "- Converted the report to Pages\n- Drafted the email for review",
    "artifacts": ["$step5.pages_path"],
    "status": "success"
  },
  "reasoning": "Provide the user-friendly wrap-up referencing earlier outputs"
}
```

**Common Mistakes:**
- ❌ Skipping this tool and leaving the UI with raw JSON
- ❌ Calling it before action tools complete
- ❌ Forgetting to include attachments/paths in `artifacts` when relevant

---

## 34. whatsapp_ensure_session

**Purpose:** Verify WhatsApp Desktop is running and user is logged in.

**Parameters:**
```json
{}
```

**Returns:**
```json
{
  "success": true,
  "status": "LOGGED_IN | NOT_LOGGED_IN | QR_CODE_REQUIRED",
  "needs_login": false
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "ProcessNotFound | SessionError",
  "error_message": "string",
  "retry_possible": true
}
```

**Example:**
```json
{
  "action": "whatsapp_ensure_session",
  "parameters": {}
}
```

**Use this when:**
- Need to verify WhatsApp is ready before reading messages
- First step in any WhatsApp workflow

**Notes:**
- Activates WhatsApp Desktop app
- Checks for login status
- Required before other WhatsApp operations

---

## 35. whatsapp_navigate_to_chat

**Purpose:** Navigate to a specific WhatsApp chat or group.

**Parameters:**
```json
{
  "contact_name": "string - REQUIRED - Name of contact or group",
  "is_group": "boolean - Whether this is a group chat (default: false)"
}
```

**Returns:**
```json
{
  "success": true,
  "status": "NAVIGATED",
  "contact": "string",
  "is_group": "boolean"
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "NavigationError | MissingContact",
  "error_message": "string",
  "retry_possible": true
}
```

**Example:**
```json
{
  "action": "whatsapp_navigate_to_chat",
  "parameters": {
    "contact_name": "John Doe",
    "is_group": false
  }
}
```

**Use this when:**
- Need to open a specific chat before reading messages
- Preparing to interact with a WhatsApp conversation

**Notes:**
- Uses search (Cmd+F) to find and open the chat
- Works for both individual chats and groups

---

## 36. whatsapp_read_messages

**Purpose:** Read recent messages from a WhatsApp chat or group.

**Parameters:**
```json
{
  "contact_name": "string - REQUIRED - Name of contact or group",
  "limit": "int - Maximum number of messages to return (default: 20)",
  "is_group": "boolean - Whether this is a group chat (default: false)"
}
```

**Returns:**
```json
{
  "success": true,
  "contact": "string",
  "is_group": "boolean",
  "messages": ["array of message strings"],
  "sample_size": "int"
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "ReadError | MissingContact",
  "error_message": "string",
  "retry_possible": true
}
```

**Example:**
```json
{
  "action": "whatsapp_read_messages",
  "parameters": {
    "contact_name": "Team Chat",
    "limit": 30,
    "is_group": true
  }
}
```

**Use this when:**
- User wants to see recent messages from a chat
- Need message content for summarization or analysis
- Reading conversation history

**Notes:**
- Uses macOS UI automation to extract messages
- Returns most recent messages (up to limit)
- Messages include sender names for groups

---

## 37. whatsapp_read_messages_from_sender

**Purpose:** Read messages from a specific sender within a group chat.

**Parameters:**
```json
{
  "contact_name": "string - REQUIRED - Name of the group",
  "sender_name": "string - REQUIRED - Name of sender to filter by",
  "limit": "int - Maximum number of messages to return (default: 20)"
}
```

**Returns:**
```json
{
  "success": true,
  "contact": "string",
  "sender": "string",
  "messages": ["array of filtered message strings"],
  "sample_size": "int",
  "total_messages": "int"
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "ReadError | MissingContact",
  "error_message": "string",
  "retry_possible": true
}
```

**Example:**
```json
{
  "action": "whatsapp_read_messages_from_sender",
  "parameters": {
    "contact_name": "Project Team",
    "sender_name": "Alice",
    "limit": 10
  }
}
```

**Use this when:**
- User asks "What did [person] say in [group]?"
- Need to filter group messages by specific sender
- Tracking messages from a particular person

**Notes:**
- Only works for group chats (is_group=True)
- Filters messages that start with sender name
- Returns messages in chronological order

---

## 38. whatsapp_read_group_messages

**Purpose:** Read recent messages from a WhatsApp group.

**Parameters:**
```json
{
  "group_name": "string - REQUIRED - Name of the group",
  "limit": "int - Maximum number of messages to return (default: 20)"
}
```

**Returns:**
```json
{
  "success": true,
  "contact": "string",
  "is_group": true,
  "messages": ["array of message strings"],
  "sample_size": "int"
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "ReadError | MissingContact",
  "error_message": "string",
  "retry_possible": true
}
```

**Example:**
```json
{
  "action": "whatsapp_read_group_messages",
  "parameters": {
    "group_name": "Family Chat",
    "limit": 50
  }
}
```

**Use this when:**
- User specifically mentions a group
- Need to read group conversation
- Convenience wrapper for group-specific reading

**Notes:**
- Convenience function that sets is_group=True automatically
- Same as whatsapp_read_messages with is_group=True

---

## 39. whatsapp_detect_unread

**Purpose:** Detect chats/groups with unread messages.

**Parameters:**
```json
{}
```

**Returns:**
```json
{
  "success": true,
  "unread_chats": ["array of chat/group names"],
  "total_detected": "int"
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "UnreadCheckError",
  "error_message": "string",
  "retry_possible": true
}
```

**Example:**
```json
{
  "action": "whatsapp_detect_unread",
  "parameters": {}
}
```

**Use this when:**
- User asks "What are my unread messages?"
- Need to find chats with new activity
- Checking for pending conversations

**Notes:**
- Scans chat list for unread indicators
- Returns list of chats with unread messages
- Useful for prioritizing which chats to read

---

## 40. whatsapp_list_chats

**Purpose:** List all available chats and groups in WhatsApp.

**Parameters:**
```json
{}
```

**Returns:**
```json
{
  "success": true,
  "chats": ["array of chat/group names"],
  "total": "int"
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "ChatListError",
  "error_message": "string",
  "retry_possible": true
}
```

**Example:**
```json
{
  "action": "whatsapp_list_chats",
  "parameters": {}
}
```

**Use this when:**
- User asks "What chats do I have?"
- Need to discover available conversations
- Listing all WhatsApp contacts/groups

**Notes:**
- Extracts chat list from WhatsApp sidebar
- Returns all visible chats and groups
- Useful for discovery and navigation

---

## 41. whatsapp_summarize_messages

**Purpose:** Read and summarize messages from a WhatsApp chat/group using AI.

**Parameters:**
```json
{
  "contact_name": "string - REQUIRED - Name of contact or group",
  "is_group": "boolean - Whether this is a group chat (default: false)",
  "limit": "int - Maximum number of messages to read before summarizing (default: 50)"
}
```

**Returns:**
```json
{
  "success": true,
  "contact": "string",
  "is_group": "boolean",
  "summary": "string - AI-generated summary",
  "messages_count": "int",
  "messages_preview": ["first 5 messages"]
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "ConfigError | ReadError",
  "error_message": "string",
  "retry_possible": true
}
```

**Example:**
```json
{
  "action": "whatsapp_summarize_messages",
  "parameters": {
    "contact_name": "Work Team",
    "is_group": true,
    "limit": 100
  }
}
```

**Use this when:**
- User asks "Summarize messages from [chat]"
- Need quick overview of long conversation
- Catching up on group chat activity

**Notes:**
- Uses LLM to generate concise summary
- Highlights key points and decisions
- Includes action items when present
- Reads messages first, then summarizes

---

## 42. whatsapp_extract_action_items

**Purpose:** Read messages and extract action items/tasks using AI.

**Parameters:**
```json
{
  "contact_name": "string - REQUIRED - Name of contact or group",
  "is_group": "boolean - Whether this is a group chat (default: false)",
  "limit": "int - Maximum number of messages to read before extracting (default: 50)"
}
```

**Returns:**
```json
{
  "success": true,
  "contact": "string",
  "is_group": "boolean",
  "action_items": ["array of extracted action items"],
  "messages_count": "int",
  "messages_preview": ["first 5 messages"]
}
```

**Error Returns:**
```json
{
  "error": true,
  "error_type": "ConfigError | ReadError",
  "error_message": "string",
  "retry_possible": true
}
```

**Example:**
```json
{
  "action": "whatsapp_extract_action_items",
  "parameters": {
    "contact_name": "Project Team",
    "is_group": true,
    "limit": 50
  }
}
```

**Use this when:**
- User asks "What are the action items from [group]?"
- Need to extract tasks and deadlines
- Creating todo list from conversation

**Notes:**
- Uses LLM to identify actionable items
- Extracts tasks, deadlines, and commitments
- Returns structured list of action items
- Reads messages first, then extracts

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
