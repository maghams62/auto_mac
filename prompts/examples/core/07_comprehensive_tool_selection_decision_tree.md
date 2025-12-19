## Comprehensive Tool Selection Decision Tree

### Step 1: Capability Assessment (ALWAYS START HERE!)

**Question: Do I have ALL the tools needed?**
- YES → Proceed to Step 2
- NO → Return `complexity="impossible"` with reason
- UNSURE → Check tool list carefully, if still unsure → REJECT

### Step 2: Determine Primary Task Type

#### A. Content Creation Tasks

**User wants a SLIDE DECK?**
```
Flow: Source → synthesize_content (if multiple sources) → create_slide_deck_content → create_keynote
Tools:
  - For documents: search_documents, extract_section
  - For web: google_search, extract_page_content
  - For synthesis: synthesize_content (if 2+ sources)
  - For formatting: create_slide_deck_content
  - For creation: create_keynote
```

**User wants SLIDE DECK WITH IMAGES/SCREENSHOTS?**
```
Flow: Source → extract/screenshot → create_keynote_with_images
Tools:
  - For PDF screenshots: take_screenshot
  - For app/screen screenshots: capture_screenshot
  - For creation: create_keynote_with_images (NOT create_keynote!)
CRITICAL: create_keynote_with_images requires BOTH:
  - content: Text for slides (from create_slide_deck_content)
  - image_paths: List of image files
```

**User wants a DETAILED REPORT?**
```
Flow: Source → synthesize_content (if multiple) → create_detailed_report → create_pages_doc
Tools:
  - For research: search_documents, google_search
  - For extraction: extract_section, extract_page_content
  - For synthesis: synthesize_content
  - For formatting: create_detailed_report
  - For creation: create_pages_doc
```

**User wants MEETING NOTES?**
```
Flow: search_documents → extract_section → create_meeting_notes → create_pages_doc OR compose_email
Tools:
  - For finding: search_documents
  - For extraction: extract_section
  - For structuring: create_meeting_notes
  - For output: create_pages_doc or compose_email
```

#### B. Data & Analysis Tasks

**User wants STOCK ANALYSIS/DATA?** (CRITICAL!)
```
Flow: get_stock_price + get_stock_history → synthesize_content → create_slide_deck_content OR create_detailed_report

DECISION TREE:
1. Do I know the ticker symbol?
   - YES → Use symbol directly (AAPL, MSFT, GOOGL, TSLA, NVDA, etc.)
   - NO → Use search_stock_symbol first (e.g., "Tesla" → "TSLA")

2. What data do I need?
   - Current price → get_stock_price
   - Historical trend → get_stock_history
   - Compare multiple → compare_stocks

3. What format does user want?
   - Presentation → synthesize_content → create_slide_deck_content → create_keynote
   - Report → synthesize_content → create_detailed_report → create_pages_doc

IMPORTANT:
  ✅ ALWAYS use stock tools for stock data (NOT google_search!)
  ✅ ALWAYS synthesize before formatting (compare_stocks returns list, not string!)
  ❌ NEVER pass structured data directly to writing tools
```

**User wants to COMPARE data/documents?**
```
Flow: Extract from multiple sources → synthesize_content (synthesis_style="comparative") → format

Tools:
  - For documents: search_documents (multiple calls), extract_section
  - For stocks: compare_stocks
  - For synthesis: synthesize_content with style="comparative"
  - For output: create_slide_deck_content OR create_detailed_report
```

#### C. File & Organization Tasks

**User wants to ORGANIZE FILES?**
```
Tool: organize_files (STANDALONE - handles everything!)

IMPORTANT:
  - Creates target folder automatically (NO separate folder creation!)
  - Uses LLM to categorize files (NO pattern matching!)
  - Moves or copies files in one step
  ❌ DON'T create separate steps for folder creation or file filtering
  ✅ Just call organize_files with category and target_folder
```

**User wants to FIND and EMAIL document?**
```
Flow: search_documents → compose_email
Tools:
  - search_documents (returns doc_path)
  - compose_email (attachments: ["$step1.doc_path"])
```

**User wants to SCREENSHOT and EMAIL?**
```
Flow: search_documents → take_screenshot → compose_email
Tools:
  - For finding: search_documents
  - For PDF pages: take_screenshot
  - For app/screen: capture_screenshot
  - For sending: compose_email (attachments: "$step2.screenshot_paths")
```

#### D. Web Research Tasks

**User wants WEB RESEARCH?**
```
Flow: google_search → navigate_to_url (or extract_page_content) → synthesize_content → format

Tools:
  - For search: google_search
  - For content: extract_page_content (multiple URLs)
  - For synthesis: synthesize_content
  - For output: create_slide_deck_content OR create_detailed_report
```

**User wants SCREENSHOT of webpage?**
```
Flow: google_search → take_web_screenshot OR navigate_to_url → capture_screenshot

Tools:
  - For search: google_search
  - For screenshot: take_web_screenshot (if URL known) OR capture_screenshot
```

### Step 3: Parameter Validation

**Before finalizing plan, check:**

1. **Data Type Compatibility**
   - Writing tools need STRINGS, not lists/dicts
   - Use `.message` field for pre-formatted text
   - Use `synthesize_content` to convert structured → text

2. **Required Parameters**
   - Check each tool's required parameters
   - Don't leave required parameters as null or missing
   - Use context variables correctly ($stepN.field)

3. **Dependencies**
   - If using $stepN.field, list N in dependencies array
   - Ensure dependency order is correct (no circular dependencies)

4. **Tool Existence**
   - Double-check tool name spelling
   - Verify tool exists in available tools list
   - Don't assume tools exist without confirmation

### Step 4: Common Validation Patterns

❌ **WRONG - Type Mismatch:**
```json
{
  "action": "create_slide_deck_content",
  "parameters": {
    "content": "$step1.stocks"  // stocks is a list!
  }
}
```

✅ **CORRECT - Use String Field:**
```json
{
  "action": "synthesize_content",
  "parameters": {
    "source_contents": ["$step1.message"],  // message is string
    "topic": "Stock Analysis"
  }
},
{
  "action": "create_slide_deck_content",
  "parameters": {
    "content": "$step2.synthesized_content"  // Now it's a string!
  }
}
```

❌ **WRONG - Missing Tool:**
```json
{
  "action": "delete_file",  // This tool doesn't exist!
  "parameters": {"file_path": "/some/path"}
}
```

✅ **CORRECT - Reject Early:**
```json
{
  "goal": "Unable to complete request",
  "steps": [],
  "complexity": "impossible",
  "reason": "Missing required capability: file deletion. Available file operations include: search_documents, extract_section, take_screenshot, organize_files, but no file deletion tool exists."
}
```

❌ **WRONG - Missing Dependency:**
```json
{
  "id": 2,
  "action": "compose_email",
  "parameters": {
    "attachments": ["$step1.doc_path"]
  },
  "dependencies": []  // WRONG! Should include [1]
}
```

✅ **CORRECT - Explicit Dependency:**
```json
{
  "id": 2,
  "action": "compose_email",
  "parameters": {
    "attachments": ["$step1.doc_path"]
  },
  "dependencies": [1]  // CORRECT!
}
```

### Step 5: Synthesis Style Selection

**When using `synthesize_content`, choose appropriate style:**

- **`comprehensive`** - For detailed reports (include all important details)
- **`concise`** - For summaries and slide decks (key points only)
- **`comparative`** - For comparing sources (highlight differences/similarities)
- **`chronological`** - For timelines and sequential content

---
