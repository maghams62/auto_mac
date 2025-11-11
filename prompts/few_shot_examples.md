# Few-Shot Examples: Task Decomposition

## Critical Planning Rules (READ FIRST!)

### Tool Hierarchy Snapshot (KNOW YOUR SPECIALISTS!)
- **File Agent (docs):** `search_documents`, `extract_section`, `take_screenshot`, `organize_files`
- **Writing Agent (content):** `synthesize_content`, `create_slide_deck_content`, `create_detailed_report`, `create_meeting_notes`
- **Presentation Agent (surface):** `create_keynote`, `create_keynote_with_images`, `create_pages_doc`
- **Browser Agent (web/Playwright):** `google_search`, `navigate_to_url`, `extract_page_content`, `take_web_screenshot`, `close_browser`
- **Email Agent (mail ops):** `compose_email`, `reply_to_email`, `read_latest_emails`, `read_emails_by_sender`, `read_emails_by_time`, `summarize_emails`
- **Bluesky Agent (social):** `search_bluesky_posts`, `summarize_bluesky_posts`, `post_bluesky_update`
- **Ticker Discovery Rule:** Unless the user explicitly provides a ticker symbol (e.g., "MSFT"), ALWAYS run the Browser Agent sequence (search → navigate → extract) on allowlisted finance domains to confirm the ticker before invoking stock tools.
- **Screen Agent (visual desktop):** `capture_screenshot` (focused window only)
- **Stock Agent:** `get_stock_price`, `get_stock_history`, `capture_stock_chart`, `compare_stocks`
- **Maps Agent (trip planning + transit):** `get_google_transit_directions` (real-time transit with actual times), `get_directions`, `get_transit_schedule`, `plan_trip_with_stops`, `open_maps_with_route`
- **Spotify Agent (music control):** `play_music`, `pause_music`, `get_spotify_status`
- **Reply Agent (UI formatting):** `reply_to_user` (ALWAYS use as FINAL step to format responses for UI)

Reference this hierarchy when picking tools—if a capability lives in a specific agent, route the plan through that agent’s tools.

### Single-Step Patterns (Plan → Execute → Reply Loop)
Some requests are intentionally one-and-done for the **action** step. Mirror these micro-patterns exactly—perform the action, then call `reply_to_user` so the UI gets a polished response:

| User Request | Plan (action → reply) | Execution Expectation | Verification |
|--------------|-----------------------|-----------------------|--------------|
| "Find the 'EV Readiness Memo' and tell me where it lives." | `search_documents` → `reply_to_user` | Return top doc metadata, then summarize it for the user. | Skip critic unless the user explicitly asked for validation. |
| "Run a Google search for 'WWDC 2024 keynote recap' and list the top domains." | `google_search` → `reply_to_user` | Provide the domains from search results; no extra steps. | No reflection/critic unless search fails. |
| "Capture whatever is on my main display as 'status_check'." | `capture_screenshot` → `reply_to_user` | Produce screenshot path, then tell the user where it is saved. | Only re-plan if capture fails. |
| "Scan r/electricvehicles (hot, limit 5) and summarize the titles." | `scan_subreddit_posts` → `reply_to_user` | Summarize the titles from the returned payload. | Critic is optional—only call it on demand. |
| "Play music" | `play_music` → `reply_to_user` | Start/resume Spotify playback, then confirm to user. | Skip critic—simple action. |
| "Pause" or "Pause music" | `pause_music` → `reply_to_user` | Pause Spotify playback, then confirm to user. | Skip critic—simple action. |

If your plan has more than one action step for these shapes, revise before execution. Deterministic AppleScript-backed tools should not trigger verification loops unless something goes wrong. The only post-action step should be the reply.

### 1. Capability Assessment (MUST DO BEFORE PLANNING!)
**BEFORE creating any plan, verify you have the necessary tools:**

✅ **DO THIS:**
```
1. List all required capabilities from user request
2. Check if tools exist for EACH capability
3. If ANY tool is missing → Respond with complexity="impossible"
4. Only proceed with planning if ALL tools are available
```

❌ **NEVER:**
- Create a plan with tools that don't exist
- Assume a tool exists without checking
- Hallucinate tool names or parameters
- Proceed if uncertain about tool availability

**Example Rejection Response:**
```json
{
  "goal": "Unable to complete request",
  "steps": [],
  "complexity": "impossible",
  "reason": "Missing required capabilities: [list specific tools/capabilities needed]. Available tools can only perform: [summarize what IS possible]"
}
```

### 2. Context Variable Usage

When passing data between steps:
- ✅ For lists: Use `$stepN.field_name` directly (e.g., `$step2.page_numbers`, `$step2.screenshot_paths`)
- ❌ Don't wrap in brackets: `["$step2.page_numbers"]` is WRONG
- ❌ Don't use singular when field is plural: `$step2.page_number` when tool returns `page_numbers`

**Common Fields:**
- `extract_section` returns: `page_numbers` (list of ints), `extracted_text` (string)
- `take_screenshot` returns: `screenshot_paths` (list of strings), `pages_captured` (list of ints)
- `search_documents` returns: `doc_path` (string), `doc_title` (string)
- `capture_screenshot` returns: `screenshot_path` (string)
- `compare_stocks` returns: `stocks` (list of dicts), `message` (string)
- `get_stock_price` returns: `current_price` (float), `message` (string)

### 3. Data Type Compatibility (CRITICAL!)

**Writing Agent Tools REQUIRE String Input:**
- `synthesize_content` accepts: `source_contents` (list of **STRINGS**)
- `create_slide_deck_content` accepts: `content` (**STRING**)
- `create_detailed_report` accepts: `content` (**STRING**)
- `create_meeting_notes` accepts: `content` (**STRING**)

**If previous step returns structured data (list/dict), you MUST convert to string:**
```json
{
  "id": 2,
  "action": "synthesize_content",
  "parameters": {
    "source_contents": ["$step1.message"],  // Use .message field (string) NOT .stocks (list)!
    "topic": "Analysis Topic",
    "synthesis_style": "concise"
  }
}
```

❌ **WRONG - Type Mismatch:**
```json
"source_contents": ["$step1.stocks"]  // stocks is a list, not a string!
```

✅ **CORRECT - Use String Field:**
```json
"source_contents": ["$step1.message"]  // message is pre-formatted text
```

---

## Example 0: Capability Assessment & Rejection (LEARN THIS PATTERN!)

### User Request 1: "Delete all my emails from yesterday"

**Capability Check:**
- Required: email deletion tool
- Available: compose_email (creates/sends only), no deletion capability
- Decision: REJECT

### Decomposition
```json
{
  "goal": "Unable to complete request",
  "steps": [],
  "complexity": "impossible",
  "reason": "Missing required capabilities: email deletion. The available email tool (compose_email) can only CREATE and SEND emails, not delete them. To complete this request, we would need a 'delete_email' or 'manage_inbox' tool which does not exist in the current system."
}
```

---

### User Request 2: "Convert this video to audio"

**Capability Check:**
- Required: video processing, audio extraction
- Available: document tools, email, presentations, web browsing
- Decision: REJECT

### Decomposition
```json
{
  "goal": "Unable to complete request",
  "steps": [],
  "complexity": "impossible",
  "reason": "Missing required capabilities: video processing and audio extraction. The available tools can work with documents (PDFs, DOCX), images, presentations, and web content, but cannot process video or audio files. To complete this request, we would need tools like 'extract_audio_from_video' or 'convert_media' which are not available."
}
```

---

### User Request 3: "Run this Python script and email me the output"

**Capability Check:**
- Required: Python script execution, output capture
- Available: document search, screenshots, presentations, email, web browsing
- Decision: REJECT

### Decomposition
```json
{
  "goal": "Unable to complete request",
  "steps": [],
  "complexity": "impossible",
  "reason": "Missing required capabilities: code execution. The available tools cannot execute Python scripts or any other code. Available capabilities include: searching documents, extracting content, taking screenshots, creating presentations, composing emails, and web browsing. To execute code, we would need a tool like 'execute_script' which does not exist."
}
```

---

### User Request 4: "Get real-time traffic data for my commute"

**Capability Check:**
- Required: real-time traffic API, location services
- Available: web search, stock data, document processing
- Decision: REJECT (no real-time traffic API)

### Decomposition
```json
{
  "goal": "Unable to complete request",
  "steps": [],
  "complexity": "impossible",
  "reason": "Missing required capabilities: real-time traffic data access. While we have web browsing capabilities (google_search, navigate_to_url), we don't have integration with traffic APIs or location services needed for accurate real-time commute data. We would need a dedicated 'get_traffic_data' tool with API access to services like Google Maps Traffic API, which is not available."
}
```

---

### User Request 5: "Create a slide deck with today's OpenAI stock price analysis"

**Capability Check:**
- Required: Public stock ticker for OpenAI
- Reality: OpenAI is not publicly traded; `search_stock_symbol` returns `SymbolNotFound`
- Decision: REJECT

### Decomposition
```json
{
  "goal": "Unable to complete request",
  "steps": [],
  "complexity": "impossible",
  "reason": "OpenAI is a private company with no public stock ticker. Our stock tools only work with publicly traded symbols (e.g., AAPL, MSFT). Please provide a company with an exchange-listed ticker."
}
```

---

### Example 0b: International Stock With Unknown Ticker + News (Bosch)

### User Request
"Create a quick analysis of today's Bosch stock price, include a slide deck, and email it with a screenshot."

### Decomposition
```json
{
  "goal": "Research Bosch ticker, gather price + news data, create slides, attach screenshot, email result",
  "steps": [
    {
      "id": 1,
      "action": "google_search",
      "parameters": {
        "query": "Bosch stock ticker site:finance.yahoo.com",
        "num_results": 3
      },
      "dependencies": [],
      "reasoning": "Use Playwright to find the ticker on an allowlisted finance site",
      "expected_output": "Search results mentioning ticker (e.g., BOSCHLTD.NS)"
    },
    {
      "id": 2,
      "action": "navigate_to_url",
      "parameters": {
        "url": "$step1.results[0].link"
      },
      "dependencies": [1],
      "reasoning": "Open the Yahoo Finance result to confirm the ticker",
      "expected_output": "Page info for Yahoo Finance ticker page"
    },
    {
      "id": 3,
      "action": "extract_page_content",
      "parameters": {
        "url": null
      },
      "dependencies": [2],
      "reasoning": "Extract text to capture the ticker string (e.g., BOSCHLTD.NS)",
      "expected_output": "Content containing the precise ticker"
    },
    {
      "id": 4,
      "action": "google_search",
      "parameters": {
        "query": "Bosch latest news site:bloomberg.com",
        "num_results": 3
      },
      "dependencies": [],
      "reasoning": "Always fetch current news to enrich the analysis",
      "expected_output": "News search results on an allowlisted site"
    },
    {
      "id": 5,
      "action": "navigate_to_url",
      "parameters": {
        "url": "$step4.results[0].link"
      },
      "dependencies": [4],
      "reasoning": "Open the top news article (allowlisted domain) to pull qualitative insights",
      "expected_output": "Browser context positioned on news article"
    },
    {
      "id": 6,
      "action": "extract_page_content",
      "parameters": {
        "url": null
      },
      "dependencies": [5],
      "reasoning": "Extract article text so news can be folded into the report",
      "expected_output": "Clean article content describing the latest Bosch news"
    },
    {
      "id": 7,
      "action": "get_stock_price",
      "parameters": {
        "symbol": "BOSCHLTD.NS"
      },
      "dependencies": [3],
      "reasoning": "Fetch canonical real-time metrics with the confirmed ticker",
      "expected_output": "Current Bosch stock metrics"
    },
    {
      "id": 8,
      "action": "get_stock_history",
      "parameters": {
        "symbol": "BOSCHLTD.NS",
        "period": "1mo"
      },
      "dependencies": [7],
      "reasoning": "Obtain recent trend data for analysis",
      "expected_output": "Historical Bosch price series"
    },
    {
      "id": 9,
      "action": "capture_stock_chart",
      "parameters": {
        "symbol": "BOSCHLTD.NS",
        "output_name": "bosch_stock_today"
      },
      "dependencies": [7],
      "reasoning": "Open Mac Stocks app to the ticker and capture a focused-window screenshot",
      "expected_output": "Screenshot path for Bosch chart"
    },
    {
      "id": 10,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": [
          "$step7.message",
          "$step8.message",
          "$step6.content"
        ],
        "topic": "Bosch Stock Analysis",
        "synthesis_style": "comprehensive"
      },
      "dependencies": [7, 8, 6],
      "reasoning": "Combine quantitative metrics/history with the extracted news narrative",
      "expected_output": "Bosch analysis text"
    },
    {
      "id": 11,
      "action": "create_slide_deck_content",
      "parameters": {
        "content": "$step10.synthesized_content",
        "title": "Bosch Stock Update",
        "num_slides": 5
      },
      "dependencies": [10],
      "reasoning": "Generate concise slide bullets",
      "expected_output": "Formatted slide content"
    },
    {
      "id": 12,
      "action": "create_keynote_with_images",
      "parameters": {
        "title": "Bosch Stock Update",
        "content": "$step11.formatted_content",
        "image_paths": ["$step9.screenshot_path"]
      },
      "dependencies": [11, 9],
      "reasoning": "Create Keynote deck that includes the screenshot",
      "expected_output": "Keynote path"
    },
    {
      "id": 13,
      "action": "compose_email",
      "parameters": {
        "subject": "Bosch Stock Analysis with Screenshot",
        "body": "Attached is the slide deck summarizing Bosch's latest stock performance and news.",
        "recipient": "user@example.com",
        "attachments": [
          "$step12.keynote_path",
          "$step9.screenshot_path"
        ],
        "send": true
      },
      "dependencies": [12],
      "reasoning": "Deliver the deck and screenshot to the user",
      "expected_output": "Email sent"
    }
  ],
  "complexity": "complex"
}
```

**Key Takeaways:**
- Browser Agent (Playwright) is used twice: once to confirm the ticker, once to gather latest allowable-news content.
- Stock tools only run after the ticker is confirmed; synthesized output blends quantitative data with fresh news insights.

---

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

## Example 3: Screenshot + Presentation + Email (5 steps)

### User Request
"Take a screenshot of the chorus from The Night We Met and create a slide deck with it, then email to user@example.com"

### Decomposition
```json
{
  "goal": "Find song, screenshot chorus, create Keynote with images, email presentation",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "The Night We Met"
      },
      "dependencies": [],
      "reasoning": "Locate the document containing the song",
      "expected_output": "Document path"
    },
    {
      "id": 2,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "chorus"
      },
      "dependencies": [1],
      "reasoning": "Find which pages contain the chorus",
      "expected_output": "page_numbers: [2, 4]"
    },
    {
      "id": 3,
      "action": "take_screenshot",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "pages": "$step2.page_numbers"
      },
      "dependencies": [2],
      "reasoning": "Capture screenshots of chorus pages",
      "expected_output": "screenshot_paths: ['/tmp/page2.png', '/tmp/page4.png']"
    },
    {
      "id": 4,
      "action": "create_keynote_with_images",
      "parameters": {
        "title": "The Night We Met - Chorus",
        "image_paths": "$step3.screenshot_paths"
      },
      "dependencies": [3],
      "reasoning": "Create Keynote presentation with screenshots as slides (NOT text slides!)",
      "expected_output": "keynote_path: ~/Documents/The Night We Met - Chorus.key"
    },
    {
      "id": 5,
      "action": "compose_email",
      "parameters": {
        "subject": "Chorus from The Night We Met",
        "body": "Attached is the slide deck with the chorus screenshots.",
        "recipient": "user@example.com",
        "attachments": ["$step4.keynote_path"],
        "send": true
      },
      "dependencies": [4],
      "reasoning": "Email the presentation to recipient",
      "expected_output": "Email sent"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Tool Selection**
- ✅ Use `create_keynote_with_images` when user wants screenshots IN a presentation
- ❌ Don't use `create_keynote` (text-based) for screenshots
- ✅ `create_keynote_with_images` accepts `image_paths` and puts images on slides
- ✅ Step 4 uses `"image_paths": "$step3.screenshot_paths"` to pass screenshot list

---

## Example 4: Medium-Complex Task (5 steps)

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

---

## Example 6: WRITING AGENT - Create Slide Deck on Topic (NEW!)

### User Request
"Create a slide deck on AI safety"

### Decomposition
```json
{
  "goal": "Research AI safety and create presentation with concise, well-structured slides",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "AI safety"
      },
      "dependencies": [],
      "reasoning": "Find relevant documents about AI safety",
      "expected_output": "Document path"
    },
    {
      "id": 2,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "all"
      },
      "dependencies": [1],
      "reasoning": "Extract content to synthesize into slides",
      "expected_output": "Full document text"
    },
    {
      "id": 3,
      "action": "create_slide_deck_content",
      "parameters": {
        "content": "$step2.extracted_text",
        "title": "AI Safety Overview",
        "num_slides": 5
      },
      "dependencies": [2],
      "reasoning": "Use Writing Agent to create concise, bullet-point slides from content",
      "expected_output": "Formatted slides with bullets (5-7 words each)"
    },
    {
      "id": 4,
      "action": "create_keynote",
      "parameters": {
        "title": "AI Safety Overview",
        "content": "$step3.formatted_content"
      },
      "dependencies": [3],
      "reasoning": "Generate Keynote presentation from formatted slide content",
      "expected_output": "Keynote file created"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Writing Agent for Slide Decks**
- ✅ Use `create_slide_deck_content` to transform content into concise bullets BEFORE `create_keynote`
- ✅ Writing Agent creates professional, presentation-ready bullets (5-7 words each)
- ✅ Better than passing raw text to `create_keynote` directly
- ❌ Don't skip the Writing Agent step - raw text makes poor slides

---

## Example 7: WRITING AGENT - Multi-Source Research Report (NEW!)

### User Request
"Create a detailed report comparing machine learning and deep learning approaches"

### Decomposition
```json
{
  "goal": "Research multiple sources and create comprehensive comparative report",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "machine learning approaches"
      },
      "dependencies": [],
      "reasoning": "Find document about machine learning",
      "expected_output": "ML document path"
    },
    {
      "id": 2,
      "action": "search_documents",
      "parameters": {
        "query": "deep learning techniques"
      },
      "dependencies": [],
      "reasoning": "Find document about deep learning",
      "expected_output": "DL document path"
    },
    {
      "id": 3,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "all"
      },
      "dependencies": [1],
      "reasoning": "Extract ML content",
      "expected_output": "ML text content"
    },
    {
      "id": 4,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step2.doc_path",
        "section": "all"
      },
      "dependencies": [2],
      "reasoning": "Extract DL content",
      "expected_output": "DL text content"
    },
    {
      "id": 5,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": ["$step3.extracted_text", "$step4.extracted_text"],
        "topic": "Machine Learning vs Deep Learning",
        "synthesis_style": "comparative"
      },
      "dependencies": [3, 4],
      "reasoning": "Combine sources with comparative analysis, removing redundancy",
      "expected_output": "Synthesized comparative analysis"
    },
    {
      "id": 6,
      "action": "create_detailed_report",
      "parameters": {
        "content": "$step5.synthesized_content",
        "title": "ML vs DL: Comparative Analysis",
        "report_style": "technical",
        "include_sections": null
      },
      "dependencies": [5],
      "reasoning": "Generate detailed technical report with proper structure",
      "expected_output": "Comprehensive report with sections"
    },
    {
      "id": 7,
      "action": "create_pages_doc",
      "parameters": {
        "title": "ML vs DL: Comparative Analysis",
        "content": "$step6.report_content"
      },
      "dependencies": [6],
      "reasoning": "Save report as Pages document",
      "expected_output": "Pages document created"
    }
  ],
  "complexity": "complex"
}
```

**CRITICAL: Writing Agent Workflow**
- ✅ Use `synthesize_content` to combine multiple sources (removes redundancy)
- ✅ Use `create_detailed_report` to transform into long-form prose
- ✅ Choose appropriate `synthesis_style` (comparative for comparing sources)
- ✅ Choose appropriate `report_style` (technical, business, academic, or executive)
- ❌ Don't pass multiple sources directly to `create_pages_doc` - synthesize first!

---

## Example 8: WRITING AGENT - Web Research to Presentation (NEW!)

### User Request
"Research the latest product launches and create a 5-slide presentation"

### Decomposition
```json
{
  "goal": "Search web for product launches, synthesize findings, create presentation",
  "steps": [
    {
      "id": 1,
      "action": "google_search",
      "parameters": {
        "query": "latest product launches 2025",
        "num_results": 3
      },
      "dependencies": [],
      "reasoning": "Search web for recent product launch information",
      "expected_output": "Search results with URLs"
    },
    {
      "id": 2,
      "action": "extract_page_content",
      "parameters": {
        "url": "<first_result_url>"
      },
      "dependencies": [1],
      "reasoning": "Extract content from top result",
      "expected_output": "Clean page content"
    },
    {
      "id": 3,
      "action": "extract_page_content",
      "parameters": {
        "url": "<second_result_url>"
      },
      "dependencies": [1],
      "reasoning": "Extract content from second result",
      "expected_output": "Clean page content"
    },
    {
      "id": 4,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": ["$step2.content", "$step3.content"],
        "topic": "2025 Product Launch Trends",
        "synthesis_style": "concise"
      },
      "dependencies": [2, 3],
      "reasoning": "Combine web sources into concise synthesis for slides",
      "expected_output": "Synthesized trends and insights"
    },
    {
      "id": 5,
      "action": "create_slide_deck_content",
      "parameters": {
        "content": "$step4.synthesized_content",
        "title": "2025 Product Launch Trends",
        "num_slides": 5
      },
      "dependencies": [4],
      "reasoning": "Transform synthesis into 5 concise slides",
      "expected_output": "5 slides with bullets"
    },
    {
      "id": 6,
      "action": "create_keynote",
      "parameters": {
        "title": "2025 Product Launch Trends",
        "content": "$step5.formatted_content"
      },
      "dependencies": [5],
      "reasoning": "Generate Keynote presentation",
      "expected_output": "Presentation created"
    }
  ],
  "complexity": "complex"
}
```

**CRITICAL: Web Research Pattern**
- ✅ Extract from multiple web pages (steps 2-3)
- ✅ Synthesize web content with `concise` style for presentations
- ✅ Use Writing Agent to create slide-ready bullets
- ✅ This produces better slides than using raw web content

---

## Example 9: WRITING AGENT - Meeting Notes (NEW!)

### User Request
"Find the Q1 planning meeting transcript and create structured notes with action items"

### Decomposition
```json
{
  "goal": "Extract meeting transcript and create professional notes with action items",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "Q1 planning meeting transcript"
      },
      "dependencies": [],
      "reasoning": "Find the meeting transcript document",
      "expected_output": "Document path"
    },
    {
      "id": 2,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "all"
      },
      "dependencies": [1],
      "reasoning": "Extract full transcript content",
      "expected_output": "Meeting transcript text"
    },
    {
      "id": 3,
      "action": "create_meeting_notes",
      "parameters": {
        "content": "$step2.extracted_text",
        "meeting_title": "Q1 Planning Meeting",
        "attendees": null,
        "include_action_items": true
      },
      "dependencies": [2],
      "reasoning": "Structure notes and extract action items with owners",
      "expected_output": "Formatted notes with action items, decisions, takeaways"
    },
    {
      "id": 4,
      "action": "create_pages_doc",
      "parameters": {
        "title": "Q1 Planning Meeting Notes",
        "content": "$step3.formatted_notes"
      },
      "dependencies": [3],
      "reasoning": "Save structured notes as document",
      "expected_output": "Pages document created"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Meeting Notes Pattern**
- ✅ Use `create_meeting_notes` to structure transcripts
- ✅ Automatically extracts action items, decisions, discussion points
- ✅ Identifies owners and deadlines for action items
- ❌ Don't just use `extract_section` - Writing Agent adds structure

---

## Example 10: STOCK AGENT - Stock Analysis Slide Deck (NEW!)

### User Request
"Create a slide deck with analysis on today's Apple stock price and email it to user@example.com"

### Decomposition
```json
{
  "goal": "Get Apple stock data, create analysis slide deck, and email",
  "steps": [
    {
      "id": 1,
      "action": "get_stock_price",
      "parameters": {
        "symbol": "AAPL"
      },
      "dependencies": [],
      "reasoning": "Get current Apple stock price and metrics - USE THIS instead of google_search!",
      "expected_output": "Stock price, change, volume, market cap, day high/low"
    },
    {
      "id": 2,
      "action": "get_stock_history",
      "parameters": {
        "symbol": "AAPL",
        "period": "1mo"
      },
      "dependencies": [],
      "reasoning": "Get recent price history for trend analysis",
      "expected_output": "Historical price data for last month"
    },
    {
      "id": 3,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": [
          "$step1.message",
          "$step2.message"
        ],
        "topic": "Apple Stock Analysis",
        "synthesis_style": "comprehensive"
      },
      "dependencies": [1, 2],
      "reasoning": "Combine current price data and historical trend using pre-formatted message fields that contain actual values",
      "expected_output": "Comprehensive stock analysis narrative combining current and historical data"
    },
    {
      "id": 4,
      "action": "create_slide_deck_content",
      "parameters": {
        "content": "$step3.synthesized_content",
        "title": "Apple Stock Analysis",
        "num_slides": 5
      },
      "dependencies": [3],
      "reasoning": "Create concise slide deck from analysis",
      "expected_output": "Formatted slide content with bullets"
    },
    {
      "id": 5,
      "action": "create_keynote",
      "parameters": {
        "title": "Apple Stock Analysis",
        "content": "$step4.formatted_content"
      },
      "dependencies": [4],
      "reasoning": "Generate Keynote presentation",
      "expected_output": "Keynote file created"
    },
    {
      "id": 6,
      "action": "compose_email",
      "parameters": {
        "subject": "Apple Stock Analysis Presentation",
        "body": "Please find attached the analysis of today's Apple stock price.",
        "recipient": "user@example.com",
        "attachments": ["$step5.keynote_path"],
        "send": true
      },
      "dependencies": [5],
      "reasoning": "Email presentation to recipient",
      "expected_output": "Email sent"
    }
  ],
  "complexity": "complex"
}
```

**CRITICAL: Stock Data Pattern**
- ✅ Use `get_stock_price` for current stock data (NOT google_search!)
- ✅ Use `get_stock_history` for historical trends
- ✅ Use `search_stock_symbol` if you need to find ticker (e.g., "Apple" → "AAPL")
- ✅ Synthesize stock data into analysis before creating slides
- ✅ Stock tools work for: AAPL (Apple), MSFT (Microsoft), GOOGL (Google), TSLA (Tesla), etc.
- ❌ DON'T use google_search or navigate_to_url for stock prices!
- ❌ DON'T use web browsing for stock data - use stock tools!

---

## Example 11: STOCK AGENT - Compare Multiple Stocks (NEW!)

### User Request
"Compare Apple, Microsoft, and Google stocks and create a report"

### Decomposition
```json
{
  "goal": "Compare multiple tech stocks and generate detailed report",
  "steps": [
    {
      "id": 1,
      "action": "compare_stocks",
      "parameters": {
        "symbols": ["AAPL", "MSFT", "GOOGL"]
      },
      "dependencies": [],
      "reasoning": "Get comparative data for all three stocks",
      "expected_output": "Comparison of price, change, market cap, P/E ratio"
    },
    {
      "id": 2,
      "action": "create_detailed_report",
      "parameters": {
        "content": "$step1.stocks",
        "title": "Tech Stock Comparison Report",
        "report_style": "business",
        "include_sections": null
      },
      "dependencies": [1],
      "reasoning": "Create professional business report from comparison data",
      "expected_output": "Detailed comparison report"
    },
    {
      "id": 3,
      "action": "create_pages_doc",
      "parameters": {
        "title": "Tech Stock Comparison Report",
        "content": "$step2.report_content"
      },
      "dependencies": [2],
      "reasoning": "Save report as document",
      "expected_output": "Pages document created"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Stock Comparison Pattern**
- ✅ Use `compare_stocks` for side-by-side comparison
- ✅ Pass ticker symbols directly (AAPL, MSFT, GOOGL)
- ✅ **ALWAYS use `synthesize_content` to convert structured data to text FIRST**
- ✅ Then use Writing Agent tools (create_slide_deck_content, create_detailed_report, etc.)
- ❌ DON'T pass `$step1.stocks` (list) directly to slide/report tools - they expect strings!
- ❌ DON'T search web for stock comparisons - use stock tools!

**Correct Flow for Comparison → Presentation:**
```
compare_stocks → synthesize_content → create_slide_deck_content → create_keynote
                     (converts list       (formats text         (creates presentation)
                      to text)            to bullets)
```

---

## Example 11a: Stock Comparison → Slide Deck (CORRECT PATTERN!)

### User Request
"Compare Apple and Google stocks and create a presentation"

### Decomposition
```json
{
  "goal": "Compare two tech stocks and create presentation",
  "steps": [
    {
      "id": 1,
      "action": "compare_stocks",
      "parameters": {
        "symbols": ["AAPL", "GOOGL"]
      },
      "dependencies": [],
      "reasoning": "Get comparative data for both stocks",
      "expected_output": "Comparison data with price, change, market cap, P/E ratio"
    },
    {
      "id": 2,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": ["$step1.message"],
        "topic": "Apple vs Google Stock Comparison",
        "synthesis_style": "concise"
      },
      "dependencies": [1],
      "reasoning": "CRITICAL: Convert structured comparison data to text format",
      "expected_output": "Text summary of comparison"
    },
    {
      "id": 3,
      "action": "create_slide_deck_content",
      "parameters": {
        "content": "$step2.synthesized_content",
        "title": "Apple vs Google Stock Comparison",
        "num_slides": 3
      },
      "dependencies": [2],
      "reasoning": "Format text into slide-friendly bullet points",
      "expected_output": "Formatted slide content"
    },
    {
      "id": 4,
      "action": "create_keynote",
      "parameters": {
        "title": "Apple vs Google Stock Comparison",
        "content": "$step3.formatted_content"
      },
      "dependencies": [3],
      "reasoning": "Create final Keynote presentation",
      "expected_output": "Keynote presentation file"
    }
  ],
  "complexity": "medium"
}
```

**WHY THE SYNTHESIS STEP IS REQUIRED:**
- `compare_stocks` returns structured data: `{"stocks": [...], "count": 2, "message": "..."}`
- `create_slide_deck_content` expects TEXT (string), not structured data (list)
- `synthesize_content` bridges the gap by converting data → text
- ❌ WRONG: `compare_stocks → create_slide_deck_content` (type error!)
- ✅ CORRECT: `compare_stocks → synthesize_content → create_slide_deck_content`

---

## Example 12: SCREEN AGENT - Stock Analysis with Screenshot (NEW!)

### User Request
"Create a slide deck with analysis on today's Apple stock price, include a screenshot of the stock app, and email it"

### Decomposition
```json
{
  "goal": "Get Apple stock data, capture screenshot of Stocks app, create slide deck, and email",
  "steps": [
    {
      "id": 1,
      "action": "get_stock_price",
      "parameters": {
        "symbol": "AAPL"
      },
      "dependencies": [],
      "reasoning": "Get current Apple stock price data",
      "expected_output": "Stock price, change, volume, market cap"
    },
    {
      "id": 2,
      "action": "get_stock_history",
      "parameters": {
        "symbol": "AAPL",
        "period": "1mo"
      },
      "dependencies": [],
      "reasoning": "Get historical data for trend analysis",
      "expected_output": "Historical price data"
    },
    {
      "id": 3,
      "action": "capture_stock_chart",
      "parameters": {
        "symbol": "AAPL",
        "output_name": "apple_stock_today"
      },
      "dependencies": [],
      "reasoning": "Capture chart from Mac Stocks app - opens Stocks app to AAPL and captures the window with chart",
      "expected_output": "Screenshot path of AAPL chart from Stocks app"
    },
    {
      "id": 4,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": [
          "$step1.message",
          "$step2.message"
        ],
        "topic": "Apple Stock Analysis",
        "synthesis_style": "comprehensive"
      },
      "dependencies": [1, 2],
      "reasoning": "Combine stock data into analysis text",
      "expected_output": "Comprehensive analysis narrative"
    },
    {
      "id": 5,
      "action": "create_slide_deck_content",
      "parameters": {
        "content": "$step4.synthesized_content",
        "title": "Apple Stock Analysis",
        "num_slides": 5
      },
      "dependencies": [4],
      "reasoning": "Create concise slide content",
      "expected_output": "Formatted slides"
    },
    {
      "id": 6,
      "action": "create_keynote_with_images",
      "parameters": {
        "title": "Apple Stock Analysis",
        "content": "$step5.formatted_content",
        "image_paths": ["$step3.screenshot_path"]
      },
      "dependencies": [5, 3],
      "reasoning": "Create presentation with screenshot included",
      "expected_output": "Keynote file with embedded screenshot"
    },
    {
      "id": 7,
      "action": "compose_email",
      "parameters": {
        "subject": "Apple Stock Analysis with Screenshot",
        "body": "Please find attached the analysis with today's stock screenshot.",
        "recipient": "user@example.com",
        "attachments": ["$step6.keynote_path"],
        "send": true
      },
      "dependencies": [6],
      "reasoning": "Email the presentation",
      "expected_output": "Email sent"
    }
  ],
  "complexity": "complex"
}
```

**CRITICAL: Screenshot Pattern for Stock Analysis**
- ✅ Use `capture_screenshot(app_name="Stocks")` to capture Stocks app
- ✅ The tool activates the app automatically before capturing
- ✅ Works for ANY macOS app - Stocks, Safari, Calculator, etc.
- ✅ Use `create_keynote_with_images` to include screenshot in presentation
- ⚠️  **IMPORTANT**: `create_keynote_with_images` requires BOTH:
  - `content`: The slide text (e.g., `$step5.formatted_content`)
  - `image_paths`: Array of screenshot paths (e.g., `["$step3.screenshot_path"]`)
  - ❌ DON'T forget the `content` parameter - presentation needs both text AND images!
- ⚠️  **CRITICAL - Stock Charts**: Use `capture_stock_chart(symbol="NVDA")` NOT `capture_screenshot`!
  - ✅ `capture_stock_chart` opens Mac Stocks app and ensures correct symbol is shown
  - ✅ Captures ONLY the Stocks app window (not desktop)
  - ❌ DON'T use generic `capture_screenshot(app_name="Stocks")` - won't navigate to symbol!
- ❌ DON'T use `take_screenshot` (PDF only) - use `capture_screenshot` for general screenshots!
- ❌ DON'T use `take_web_screenshot` (web only) - use `capture_screenshot` instead!
- ✅ `capture_screenshot` is universal - works for screen, apps, anything visible

---

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

## Example 13: MAPS AGENT - Simple Trip with Fuel Stops (NEW!)

### User Request
"Plan a trip from New York to Los Angeles with 3 fuel stops"

### Decomposition
```json
{
  "goal": "Plan route from New York to Los Angeles with 3 fuel stops and open Maps",
  "steps": [
    {
      "id": 1,
      "action": "plan_trip_with_stops",
      "parameters": {
        "origin": "New York, NY",
        "destination": "Los Angeles, CA",
        "num_fuel_stops": 3,
        "num_food_stops": 0,
        "departure_time": null,
        "use_google_maps": false,
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "Plan trip with 3 fuel stops. Maps will open automatically (open_maps=true by default)",
      "expected_output": "Route with 3 fuel stops, Maps URL, and Apple Maps opened automatically"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Maps Agent Pattern**
- ✅ Use `plan_trip_with_stops` for ALL trip planning (it's the PRIMARY tool)
- ✅ `open_maps` defaults to `true` - Maps opens automatically
- ✅ LLM automatically suggests optimal fuel stop locations along the route
- ✅ Returns `maps_url` (always provided) and `maps_opened` status
- ✅ Works for ANY route worldwide (not limited to US)

---

## Example 14: MAPS AGENT - Trip with Food Stops (NEW!)

### User Request
"Plan a trip from San Francisco to San Diego with stops for breakfast and lunch"

### Decomposition
```json
{
  "goal": "Plan route with 2 food stops (breakfast and lunch)",
  "steps": [
    {
      "id": 1,
      "action": "plan_trip_with_stops",
      "parameters": {
        "origin": "San Francisco, CA",
        "destination": "San Diego, CA",
        "num_fuel_stops": 0,
        "num_food_stops": 2,
        "departure_time": null,
        "use_google_maps": false,
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "User wants breakfast and lunch stops = 2 food stops. LLM will suggest optimal locations",
      "expected_output": "Route with 2 food stops, Maps URL, Apple Maps opened"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Food Stops Pattern**
- ✅ Count food stops: "breakfast and lunch" = 2 food stops
- ✅ "breakfast, lunch, and dinner" = 3 food stops
- ✅ LLM suggests optimal cities/towns along route for meals
- ✅ No hardcoded locations - LLM uses geographic knowledge

---

## Example 15: MAPS AGENT - Trip with Fuel and Food Stops (NEW!)

### User Request
"Plan a trip from Los Angeles to Las Vegas with 2 gas stops and a lunch stop, leaving at 8 AM"

### Decomposition
```json
{
  "goal": "Plan route with fuel stops, food stop, and departure time",
  "steps": [
    {
      "id": 1,
      "action": "plan_trip_with_stops",
      "parameters": {
        "origin": "Los Angeles, CA",
        "destination": "Las Vegas, NV",
        "num_fuel_stops": 2,
        "num_food_stops": 1,
        "departure_time": "8:00 AM",
        "use_google_maps": false,
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "2 fuel stops + 1 food stop = 3 total stops. Departure time helps with traffic-aware routing",
      "expected_output": "Route with stops, departure time, Maps URL, Apple Maps opened"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Combined Stops Pattern**
- ✅ Count fuel stops separately: "2 gas stops" = `num_fuel_stops: 2`
- ✅ Count food stops separately: "a lunch stop" = `num_food_stops: 1`
- ✅ Departure time format: "8 AM" → "8:00 AM" (flexible parsing)
- ✅ Total stops = fuel + food (e.g., 2 + 1 = 3 stops)

---

## Example 16: MAPS AGENT - Trip Planning with Google Maps (NEW!)

### User Request
"Plan a trip from Seattle to Portland with 2 fuel stops using Google Maps"

### Decomposition
```json
{
  "goal": "Plan route using Google Maps instead of Apple Maps",
  "steps": [
    {
      "id": 1,
      "action": "plan_trip_with_stops",
      "parameters": {
        "origin": "Seattle, WA",
        "destination": "Portland, OR",
        "num_fuel_stops": 2,
        "num_food_stops": 0,
        "departure_time": null,
        "use_google_maps": true,
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "User explicitly requested Google Maps. Opens in browser instead of Maps app",
      "expected_output": "Route with stops, Google Maps URL, opens in browser"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Maps Service Selection**
- ✅ Default: `use_google_maps: false` → Apple Maps (native macOS integration)
- ✅ If user requests Google Maps: `use_google_maps: true` → Opens in browser
- ✅ Apple Maps preferred for macOS (better integration, AppleScript automation)
- ✅ Google Maps available as alternative (better waypoint support for complex routes)

---

## Example 17: MAPS AGENT - Open Maps with Existing Route (NEW!)

### User Request
"Open Maps with a route from Chicago to Detroit via Toledo"

### Decomposition
```json
{
  "goal": "Open Maps app with specific route and waypoints",
  "steps": [
    {
      "id": 1,
      "action": "open_maps_with_route",
      "parameters": {
        "origin": "Chicago, IL",
        "destination": "Detroit, MI",
        "stops": ["Toledo, OH"],
        "start_navigation": false
      },
      "dependencies": [],
      "reasoning": "User wants to open Maps with specific route. Use open_maps_with_route when route is already known",
      "expected_output": "Apple Maps opened with route, waypoint shown"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: open_maps_with_route Pattern**
- ✅ Use `open_maps_with_route` when route/stops are already known
- ✅ Use `plan_trip_with_stops` when you need LLM to suggest stops
- ✅ `stops` parameter: List of waypoint locations (e.g., `["Toledo, OH", "Cleveland, OH"]`)
- ✅ `start_navigation: false` = Just open directions (default)
- ✅ `start_navigation: true` = Automatically start navigation

---

## Example 18: MAPS AGENT - Complex Trip Planning (NEW!)

### User Request
"Plan a cross-country trip from Boston to San Francisco with 5 fuel stops, breakfast, lunch, and dinner stops, leaving tomorrow at 6 AM"

### Decomposition
```json
{
  "goal": "Plan complex cross-country route with multiple stops and departure time",
  "steps": [
    {
      "id": 1,
      "action": "plan_trip_with_stops",
      "parameters": {
        "origin": "Boston, MA",
        "destination": "San Francisco, CA",
        "num_fuel_stops": 5,
        "num_food_stops": 3,
        "departure_time": "6:00 AM",
        "use_google_maps": false,
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "5 fuel + 3 food = 8 total stops. LLM will suggest optimal locations across the country. Departure time helps with traffic routing",
      "expected_output": "Route with 8 stops distributed across cross-country route, Maps URL, Apple Maps opened"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Complex Trip Planning**
- ✅ Supports any reasonable number of stops (typically 0-20 total)
- ✅ LLM distributes stops evenly along route
- ✅ Works for ANY route worldwide (not just US)
- ✅ Departure time helps with traffic-aware routing
- ✅ LLM uses geographic knowledge - no hardcoded routes

---

## Example 19: MAPS AGENT - Trip Planning Without Opening Maps (NEW!)

### User Request
"Plan a trip from Miami to Key West with 1 fuel stop and give me the link"

### Decomposition
```json
{
  "goal": "Plan route and return URL without opening Maps",
  "steps": [
    {
      "id": 1,
      "action": "plan_trip_with_stops",
      "parameters": {
        "origin": "Miami, FL",
        "destination": "Key West, FL",
        "num_fuel_stops": 1,
        "num_food_stops": 0,
        "departure_time": null,
        "use_google_maps": false,
        "open_maps": false
      },
      "dependencies": [],
      "reasoning": "User wants 'the link' = URL only, not auto-opening. Set open_maps=false",
      "expected_output": "Route with 1 fuel stop, Maps URL in response (maps_opened: false)"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: open_maps Parameter**
- ✅ `open_maps: true` (default) → Automatically opens Maps app/browser
- ✅ `open_maps: false` → Returns URL only, doesn't open Maps
- ✅ Use `false` when user says "give me the link" or "just the URL"
- ✅ Use `true` when user says "open it in Maps" or "show me the route"
- ✅ Maps URL is ALWAYS provided in response, regardless of `open_maps` value

---

## Example 20: MAPS AGENT - International Trip Planning (NEW!)

### User Request
"Plan a trip from London to Paris with 2 fuel stops"

### Decomposition
```json
{
  "goal": "Plan international route with fuel stops",
  "steps": [
    {
      "id": 1,
      "action": "plan_trip_with_stops",
      "parameters": {
        "origin": "London, UK",
        "destination": "Paris, France",
        "num_fuel_stops": 2,
        "num_food_stops": 0,
        "departure_time": null,
        "use_google_maps": false,
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "International route - LLM handles geographic knowledge for any country. Works worldwide",
      "expected_output": "Route with 2 fuel stops between London and Paris, Maps URL, Apple Maps opened"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: International Routes**
- ✅ Works for ANY route worldwide (not limited to US)
- ✅ LLM uses geographic knowledge for international routes
- ✅ No hardcoded geographic assumptions
- ✅ Supports cities in any country (UK, France, Germany, Japan, etc.)

---

## Example 20a: MAPS AGENT - Transit Directions with Google Maps API (NEW! RECOMMENDED)

### User Request
"When's the next bus to Berkeley"

### Decomposition
```json
{
  "goal": "Get real-time transit directions with actual departure times using Google Maps API",
  "steps": [
    {
      "id": 1,
      "action": "get_google_transit_directions",
      "parameters": {
        "origin": "Current Location",
        "destination": "Berkeley, CA",
        "departure_time": "now"
      },
      "dependencies": [],
      "reasoning": "User asking for next bus time. Use Google Maps API to get PROGRAMMATIC transit schedule with actual departure times that can be returned in chat response",
      "expected_output": "Returns actual next departure time (e.g., 'Next departure: 3:45 PM') in chat, plus Google Maps URL"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "[Generated based on step 1 result with actual departure time]"
      },
      "dependencies": [1],
      "reasoning": "Format the transit schedule response for UI display",
      "expected_output": "User sees 'Next bus at 3:45 PM' directly in chat"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Transit Directions Pattern (GOOGLE MAPS RECOMMENDED)**
- ✅ **ALWAYS use `get_google_transit_directions` for transit queries** - Returns actual times programmatically
- ✅ Returns "Next departure: 3:45 PM" directly in chat response
- ✅ Opens Google Maps in browser with full transit directions
- ✅ Provides step-by-step transit details with line numbers and stops
- ✅ Requires GOOGLE_MAPS_API_KEY in .env file
- ⚠️ If Google Maps API not configured, fallback to `get_directions` with Apple Maps (but no programmatic times)

**Transit Query Variations:**
- "when's the next bus to [place]" → `get_google_transit_directions`
- "show me the train schedule to [place]" → `get_google_transit_directions`
- "what time is the next BART to [place]" → `get_google_transit_directions`
- "when's the next bus to UCSC Silicon Valley" → `get_google_transit_directions`

**Fallback Pattern (if Google Maps API not available):**
```json
{
  "action": "get_directions",
  "parameters": {
    "origin": "Current Location",
    "destination": "Berkeley, CA",
    "transportation_mode": "transit",
    "open_maps": true
  }
}
```
Note: Fallback opens Apple Maps but cannot return programmatic departure times

---

## Example 20b: MAPS AGENT - Bicycle Directions (NEW! Multi-Modal)

### User Request
"How do I bike to the office from here"

### Decomposition
```json
{
  "goal": "Get bicycle directions from current location to office",
  "steps": [
    {
      "id": 1,
      "action": "get_directions",
      "parameters": {
        "origin": "Current Location",
        "destination": "Office",
        "transportation_mode": "bicycle",
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "User wants bicycle route. Use bicycle mode for bike-friendly paths and lanes",
      "expected_output": "Maps opens with bicycle directions showing bike paths, lanes, and estimated time"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Bicycle Directions Pattern**
- ✅ Use `get_directions` with `transportation_mode: "bicycle"`
- ✅ Maps will show bike-friendly routes, bike lanes, paths
- ✅ Provides elevation info and time estimates
- ✅ Aliases: "bicycle", "bike", "cycling" all map to bicycle mode
- ✅ "from here" → use "Current Location" as origin

**Bicycle Query Variations:**
- "bike to the coffee shop" → `transportation_mode: "bicycle"`
- "cycling directions to downtown" → `transportation_mode: "bicycle"`
- "show me the bike route" → `transportation_mode: "bicycle"`

---

## Example 20c: MAPS AGENT - Walking Directions (NEW! Multi-Modal)

### User Request
"Walk me to the nearest coffee shop"

### Decomposition
```json
{
  "goal": "Get walking directions to nearest coffee shop",
  "steps": [
    {
      "id": 1,
      "action": "get_directions",
      "parameters": {
        "origin": "Current Location",
        "destination": "nearest coffee shop",
        "transportation_mode": "walking",
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "User wants walking directions. Use walking mode for pedestrian paths",
      "expected_output": "Maps opens with walking directions showing pedestrian routes and time"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Walking Directions Pattern**
- ✅ Use `get_directions` with `transportation_mode: "walking"`
- ✅ Maps will show pedestrian-friendly routes, sidewalks, crosswalks
- ✅ Provides walking time estimates
- ✅ Aliases: "walking", "walk" map to walking mode
- ✅ "nearest coffee shop" → Maps will find closest match

**Walking Query Variations:**
- "walk to the park" → `transportation_mode: "walking"`
- "how far is it on foot" → `transportation_mode: "walking"`
- "walking directions to downtown" → `transportation_mode: "walking"`

---

## Example 20d: MAPS AGENT - Driving Directions (NEW! Multi-Modal)

### User Request
"Drive me to San Francisco"

### Decomposition
```json
{
  "goal": "Get driving directions to San Francisco",
  "steps": [
    {
      "id": 1,
      "action": "get_directions",
      "parameters": {
        "origin": "Current Location",
        "destination": "San Francisco, CA",
        "transportation_mode": "driving",
        "open_maps": true
      },
      "dependencies": [],
      "reasoning": "User wants driving route. Driving is default but explicit for clarity",
      "expected_output": "Maps opens with driving directions showing route, traffic, and time"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Driving Directions Pattern**
- ✅ Use `get_directions` with `transportation_mode: "driving"` (or omit, it's default)
- ✅ Maps will show fastest driving route with real-time traffic
- ✅ Provides driving time with traffic conditions
- ✅ Aliases: "driving", "car" map to driving mode
- ✅ Default mode if not specified

**Driving Query Variations:**
- "directions to the airport" → `transportation_mode: "driving"` (or omit)
- "drive to Los Angeles" → `transportation_mode: "driving"`
- "how do I get there by car" → `transportation_mode: "car"`

---

## Example 21: FILE AGENT - Zip Non-Music Files and Email (NEW!)

### User Request
"Zip all the non-music files into a folder called study_stuff and email the zip to me."

### Decomposition
```json
{
  "goal": "Collect non-music files as study_stuff, zip them, and email the archive",
  "steps": [
    {
      "id": 1,
      "action": "organize_files",
      "parameters": {
        "category": "non-music study files",
        "target_folder": "study_stuff",
        "move_files": false
      },
      "dependencies": [],
      "reasoning": "LLM-driven categorization copies only the non-music files into the study_stuff folder",
      "expected_output": "Filtered study_stuff folder containing non-music files"
    },
    {
      "id": 2,
      "action": "create_zip_archive",
      "parameters": {
        "source_path": "study_stuff",
        "zip_name": "study_stuff.zip",
        "exclude_extensions": ["mp3", "wav", "flac", "m4a"]
      },
      "dependencies": [1],
      "reasoning": "Create a ZIP archive of the curated folder while guarding against music extensions",
      "expected_output": "ZIP archive path"
    },
    {
      "id": 3,
      "action": "compose_email",
      "parameters": {
        "recipient": null,
        "subject": "study_stuff.zip",
        "body": "Attached is the study_stuff archive (non-music files).",
        "attachments": ["$step2.zip_path"],
        "send": false
      },
      "dependencies": [2],
      "reasoning": "Draft the email with the ZIP attached so the user can send it",
      "expected_output": "Email draft with ZIP attached"
    }
  ],
  "complexity": "medium"
}
```

---

## Maps Agent Tool Selection Decision Tree

### When to Use Each Tool

**Use `plan_trip_with_stops` when:**
- ✅ User wants to plan a trip with stops
- ✅ User specifies number of fuel/food stops needed
- ✅ You need LLM to suggest optimal stop locations
- ✅ User provides origin and destination

**Use `open_maps_with_route` when:**
- ✅ Route and stops are already known/determined
- ✅ User wants to open Maps with specific waypoints
- ✅ You have a pre-planned route to display

### Parameter Extraction Guide

**Origin/Destination:**
- Extract from query: "from X to Y" → `origin: "X"`, `destination: "Y"`
- Handle abbreviations: "LA" → "Los Angeles, CA", "NYC" → "New York, NY"
- International: "London" → "London, UK", "Paris" → "Paris, France"

**Fuel Stops:**
- "3 fuel stops" → `num_fuel_stops: 3`
- "2 gas stops" → `num_fuel_stops: 2`
- "one fuel stop" → `num_fuel_stops: 1`
- "no fuel stops" → `num_fuel_stops: 0`

**Food Stops:**
- "breakfast and lunch" → `num_food_stops: 2`
- "breakfast, lunch, and dinner" → `num_food_stops: 3`
- "a lunch stop" → `num_food_stops: 1`
- "no food stops" → `num_food_stops: 0`

**Departure Time:**
- "leaving at 8 AM" → `departure_time: "8:00 AM"`
- "departure at 7:30 PM" → `departure_time: "7:30 PM"`
- "tomorrow at 6 AM" → `departure_time: "6:00 AM"` (or parse relative date)
- Flexible format parsing supported

**Maps Service:**
- Default: `use_google_maps: false` (Apple Maps)
- If user says "Google Maps" → `use_google_maps: true`
- If user says "Apple Maps" → `use_google_maps: false` (explicit)

**Auto-Open:**
- Default: `open_maps: true` (opens automatically)
- If user says "give me the link" → `open_maps: false`
- If user says "open it in Maps" → `open_maps: true`
- If user says "show me the route" → `open_maps: true`

### Common Patterns

**Simple Trip:**
```
plan_trip_with_stops(origin, destination, num_fuel_stops=X, open_maps=true)
```

**Trip with Food:**
```
plan_trip_with_stops(origin, destination, num_food_stops=X, open_maps=true)
```

**Complex Trip:**
```
plan_trip_with_stops(origin, destination, num_fuel_stops=X, num_food_stops=Y, departure_time="...", open_maps=true)
```

**Open Existing Route:**
```
open_maps_with_route(origin, destination, stops=[...], start_navigation=false)
```

---

## Example 22: EMAIL AGENT - Read Latest Emails (NEW!)

### User Request
"Read my latest 5 emails"

### Decomposition
```json
{
  "goal": "Read latest 5 emails and present to user",
  "steps": [
    {
      "id": 1,
      "action": "read_latest_emails",
      "parameters": {
        "count": 5,
        "mailbox": "INBOX"
      },
      "dependencies": [],
      "reasoning": "Retrieve the 5 most recent emails from inbox",
      "expected_output": "List of 5 emails with sender, subject, date, content"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "Retrieved your latest 5 emails",
        "details": "Email list with senders, subjects, dates, and previews",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [1],
      "reasoning": "FINAL step - deliver polished summary to UI",
      "expected_output": "User-friendly email listing"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: Email Reading Pattern**
- ✅ Use `read_latest_emails` to retrieve recent emails
- ✅ ALWAYS end with `reply_to_user` to format response for UI
- ✅ Single-step pattern: read → reply
- ❌ DON'T return raw email data - use reply_to_user for polished output

---

## Example 23: EMAIL AGENT - Read Emails by Sender (NEW!)

### User Request
"Show me emails from john@example.com"

### Decomposition
```json
{
  "goal": "Find and display emails from specific sender",
  "steps": [
    {
      "id": 1,
      "action": "read_emails_by_sender",
      "parameters": {
        "sender": "john@example.com",
        "count": 10
      },
      "dependencies": [],
      "reasoning": "Search inbox for emails from john@example.com",
      "expected_output": "List of emails from specified sender"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "Found emails from john@example.com",
        "details": "Listing all emails with subjects and dates",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [1],
      "reasoning": "FINAL step - present findings to user",
      "expected_output": "Formatted email list"
    }
  ],
  "complexity": "simple"
}
```

---

## Example 24: EMAIL AGENT - Summarize Recent Emails (NEW!)

### User Request
"Summarize emails from the past hour"

### Decomposition
```json
{
  "goal": "Read emails from last hour and provide AI summary",
  "steps": [
    {
      "id": 1,
      "action": "read_emails_by_time",
      "parameters": {
        "hours": 1,
        "mailbox": "INBOX"
      },
      "dependencies": [],
      "reasoning": "Retrieve all emails received in the last hour",
      "expected_output": "List of emails from past hour"
    },
    {
      "id": 2,
      "action": "summarize_emails",
      "parameters": {
        "emails_data": "$step1",
        "focus": null
      },
      "dependencies": [1],
      "reasoning": "Use AI to create concise summary of email content",
      "expected_output": "Summary highlighting key points, senders, and topics"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Email summary for the past hour",
        "details": "$step2.summary",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [2],
      "reasoning": "FINAL step - deliver AI-generated summary to user",
      "expected_output": "Polished summary display"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Email Summarization Pattern**
- ✅ Use `read_emails_by_time` for time-based filtering
- ✅ Pass entire step output to `summarize_emails` using `$step1`
- ✅ `summarize_emails` expects `emails_data` dict with `emails` field
- ✅ ALWAYS end with `reply_to_user` containing the summary
- ✅ Use `$step2.summary` to reference the AI-generated summary text

---

## Example 25: EMAIL AGENT - Read & Summarize with Focus (NEW!)

### User Request
"Summarize emails from Sarah focusing on action items"

### Decomposition
```json
{
  "goal": "Read emails from Sarah and summarize with focus on action items",
  "steps": [
    {
      "id": 1,
      "action": "read_emails_by_sender",
      "parameters": {
        "sender": "Sarah",
        "count": 10
      },
      "dependencies": [],
      "reasoning": "Find all emails from Sarah (partial name match works)",
      "expected_output": "List of Sarah's emails"
    },
    {
      "id": 2,
      "action": "summarize_emails",
      "parameters": {
        "emails_data": "$step1",
        "focus": "action items"
      },
      "dependencies": [1],
      "reasoning": "Summarize with specific focus on action items and tasks",
      "expected_output": "Summary highlighting action items from Sarah's emails"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Summary of emails from Sarah (focused on action items)",
        "details": "$step2.summary",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [2],
      "reasoning": "FINAL step - present focused summary",
      "expected_output": "Action items clearly highlighted"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Focused Summarization**
- ✅ `focus` parameter guides AI to highlight specific aspects
- ✅ Common focus values: "action items", "deadlines", "important updates", "decisions"
- ✅ Sender matching is flexible - "Sarah" will match "Sarah Johnson <sarah@company.com>"

---

## Example 26: EMAIL AGENT - Multi-Step Email Workflow (NEW!)

### User Request
"Read the latest 10 emails, summarize them, and create a report document"

### Decomposition
```json
{
  "goal": "Read emails, summarize, and create Pages document with summary",
  "steps": [
    {
      "id": 1,
      "action": "read_latest_emails",
      "parameters": {
        "count": 10,
        "mailbox": "INBOX"
      },
      "dependencies": [],
      "reasoning": "Retrieve 10 most recent emails",
      "expected_output": "List of 10 emails"
    },
    {
      "id": 2,
      "action": "summarize_emails",
      "parameters": {
        "emails_data": "$step1",
        "focus": null
      },
      "dependencies": [1],
      "reasoning": "Create comprehensive summary of all emails",
      "expected_output": "AI-generated email summary"
    },
    {
      "id": 3,
      "action": "create_pages_doc",
      "parameters": {
        "title": "Email Summary Report",
        "content": "$step2.summary"
      },
      "dependencies": [2],
      "reasoning": "Save summary as Pages document for permanent record",
      "expected_output": "Pages document created with summary"
    },
    {
      "id": 4,
      "action": "reply_to_user",
      "parameters": {
        "message": "Created email summary report",
        "details": "Summarized 10 latest emails and saved to Pages document",
        "artifacts": ["$step3.file_path"],
        "status": "success"
      },
      "dependencies": [3],
      "reasoning": "FINAL step - confirm completion with document path",
      "expected_output": "Success message with document artifact"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Multi-Step Email Workflow**
- ✅ Combine email tools with other agents (Writing, Presentation, etc.)
- ✅ Pass summary to document creation tools
- ✅ Include document path in `artifacts` array of reply_to_user
- ✅ ALWAYS end complex workflows with reply_to_user

---

## Example 27: EMAIL AGENT - Reply to Email (NEW!)

### User Request
"Read the latest email from John and reply saying I'll review it tomorrow"

### Decomposition
```json
{
  "goal": "Read email from John and send reply",
  "steps": [
    {
      "id": 1,
      "action": "read_emails_by_sender",
      "parameters": {
        "sender": "John",
        "count": 1
      },
      "dependencies": [],
      "reasoning": "Get the most recent email from John",
      "expected_output": "Latest email from John with sender and subject"
    },
    {
      "id": 2,
      "action": "reply_to_email",
      "parameters": {
        "original_sender": "$step1.emails[0].sender",
        "original_subject": "$step1.emails[0].subject",
        "reply_body": "Thank you for your email. I'll review this tomorrow and get back to you.",
        "send": false
      },
      "dependencies": [1],
      "reasoning": "Reply to John's email with draft (send=false for safety)",
      "expected_output": "Reply draft created"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Reply drafted to John's email",
        "details": "Created reply draft - please review and send from Mail.app",
        "status": "success"
      },
      "dependencies": [2],
      "reasoning": "FINAL step - confirm reply was drafted",
      "expected_output": "Success message"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Email Reply Workflow**
- ✅ Read the email first to get sender and subject
- ✅ Use `$step1.emails[0].sender` to reference the email address from read result
- ✅ Use `$step1.emails[0].subject` to reference the subject line
- ✅ `reply_to_email` automatically adds "Re: " prefix to subject
- ✅ Default `send: false` creates draft for safety
- ✅ Set `send: true` only if user explicitly requests immediate sending

---

## Example 28: CROSS-DOMAIN REPORT → SLIDES → EMAIL (NEW!)

**Reasoning (chain of thought):**
1. Confirm capabilities: File, Writing, Presentation, Email, and Reply agents exist and cover all operations.
2. Outline workflow: locate documents → extract relevant sections → synthesize insights → generate slides → draft email → reply.
3. Plan dependencies: later steps use `$stepN` outputs (`doc_path`, `extracted_text`, etc.) so specify dependencies precisely.
4. Ensure plan ends with `reply_to_user` referencing final artifacts.

**User Request:** “Create a competitive summary on Product Aurora using the latest roadmap PDF and the ‘Aurora_feedback.docx’, turn it into a 5-slide deck, then email it to leadership with the deck attached.”

```json
{
  "goal": "Produce competitive summary slides on Product Aurora and email leadership",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "Product Aurora roadmap PDF"
      },
      "dependencies": [],
      "reasoning": "Find the roadmap PDF in local knowledge base",
      "expected_output": "doc_path and metadata for roadmap PDF"
    },
    {
      "id": 2,
      "action": "search_documents",
      "parameters": {
        "query": "Aurora_feedback.docx"
      },
      "dependencies": [],
      "reasoning": "Find internal feedback document for supporting context",
      "expected_output": "doc_path for feedback document"
    },
    {
      "id": 3,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "latest updates"
      },
      "dependencies": [1],
      "reasoning": "Capture recent roadmap updates",
      "expected_output": "extracted_text for roadmap updates"
    },
    {
      "id": 4,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step2.doc_path",
        "section": "top customer pain points"
      },
      "dependencies": [2],
      "reasoning": "Surface key customer feedback themes",
      "expected_output": "extracted_text for pain points"
    },
    {
      "id": 5,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": [
          "$step3.extracted_text",
          "$step4.extracted_text"
        ],
        "topic": "Product Aurora competitive summary",
        "synthesis_style": "comparative"
      },
      "dependencies": [3, 4],
      "reasoning": "Blend roadmap insights with customer pain points",
      "expected_output": "message with synthesized summary"
    },
    {
      "id": 6,
      "action": "create_slide_deck_content",
      "parameters": {
        "content": "$step5.message",
        "slide_count": 5
      },
      "dependencies": [5],
      "reasoning": "Turn synthesis into 5-slide outline",
      "expected_output": "slide deck outline text"
    },
    {
      "id": 7,
      "action": "create_keynote",
      "parameters": {
        "title": "Product Aurora Competitive Summary",
        "content": "$step6.content"
      },
      "dependencies": [6],
      "reasoning": "Produce Keynote presentation from outline",
      "expected_output": "keynote_path and message"
    },
    {
      "id": 8,
      "action": "compose_email",
      "parameters": {
        "subject": "Product Aurora Competitive Summary",
        "body": "Hi leadership – please find attached the latest competitive summary on Aurora. Let me know if you need more detail.",
        "attachments": [
          "$step7.keynote_path"
        ],
        "send": false
      },
      "dependencies": [7],
      "reasoning": "Draft email to leadership with deck attached (draft for review)",
      "expected_output": "Email draft status"
    },
    {
      "id": 9,
      "action": "reply_to_user",
      "parameters": {
        "message": "Prepared the Aurora competitive summary slides and drafted an email for leadership review.",
        "details": "- Slides created: `$step7.keynote_path`\n- Email draft prepared with attachment\n- Sources: roadmap + customer feedback docs",
        "artifacts": [
          "$step7.keynote_path"
        ],
        "status": "success"
      },
      "dependencies": [7, 8],
      "reasoning": "Summarize final deliverables to the user",
      "expected_output": "User-facing confirmation"
    }
  ],
  "complexity": "complex"
}
```

---

## Example 29: WEB + LOCAL RESEARCH WITH BLUESKY SIGNALS (NEW!)

**Reasoning (chain of thought):**
1. Validate tools: BrowserAgent (web search/extraction), FileAgent (local notes), BlueskyAgent (social chatter), WritingAgent (synthesis), ReplyAgent (final response).
2. Plan sequence: local doc → web article → Bluesky trending → combine into briefing.
3. Use context variables to label sources inside synthesis input for clarity.
4. Reply summarizes each source type and links to artifacts.

**User Request:** “Give me a quick briefing on ‘Project Atlas’ using the latest local notes, the top web article you find, and mention what people are saying on Bluesky.”

```json
{
  "goal": "Brief user on Project Atlas across internal notes, web coverage, and Bluesky chatter",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "Project Atlas status notes"
      },
      "dependencies": [],
      "reasoning": "Locate internal notes for baseline status",
      "expected_output": "doc_path for local notes"
    },
    {
      "id": 2,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "summary"
      },
      "dependencies": [1],
      "reasoning": "Pull latest internal summary section",
      "expected_output": "extracted_text from internal notes"
    },
    {
      "id": 3,
      "action": "google_search",
      "parameters": {
        "query": "\"Project Atlas\" product update",
        "num_results": 3
      },
      "dependencies": [],
      "reasoning": "Find recent public article on Atlas",
      "expected_output": "Search results metadata"
    },
    {
      "id": 4,
      "action": "navigate_to_url",
      "parameters": {
        "url": "$step3.results[0].link",
        "wait_until": "load"
      },
      "dependencies": [3],
      "reasoning": "Open the top article before extraction",
      "expected_output": "Loaded page handle"
    },
    {
      "id": 5,
      "action": "extract_page_content",
      "parameters": {
        "url": "$step3.results[0].link"
      },
      "dependencies": [4],
      "reasoning": "Get the clean article text for synthesis",
      "expected_output": "Article content string"
    },
    {
      "id": 6,
      "action": "summarize_bluesky_posts",
      "parameters": {
        "query": "Project Atlas",
        "lookback_hours": 24,
        "max_items": 3
      },
      "dependencies": [],
      "reasoning": "Collect social sentiment from Bluesky",
      "expected_output": "Summary markdown plus post metadata"
    },
    {
      "id": 7,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": [
          "Internal Notes\\n$step2.extracted_text",
          "Public Coverage\\n$step5.content",
          "Bluesky Discussion\\n$step6.summary"
        ],
        "topic": "Project Atlas briefing",
        "synthesis_style": "comprehensive"
      },
      "dependencies": [2, 5, 6],
      "reasoning": "Blend internal updates, press coverage, and social chatter",
      "expected_output": "Combined briefing text"
    },
    {
      "id": 8,
      "action": "reply_to_user",
      "parameters": {
        "message": "Here’s the Project Atlas briefing from internal, press, and Bluesky sources.",
        "details": "- **Internal:** latest notes summarized\n- **Press:** $step3.results[0].title\n- **Bluesky:** key themes from recent posts\n\n$step7.message",
        "artifacts": [
          "$step1.doc_path",
          "$step3.results[0].link"
        ],
        "status": "success"
      },
      "dependencies": [7],
      "reasoning": "Deliver consolidated summary and share references",
      "expected_output": "Final user-facing briefing"
    }
  ],
  "complexity": "complex"
}
```

---

## Example 30: SAFETY GUARDRAIL – UNSUPPORTED MEDIA EDIT (NEW!)

**Reasoning (chain of thought):**
- Request: “Trim interview.mp4 to the first minute and replace the audio track.” No available tools perform video or audio editing.
- Capability assessment → only document, presentation, email, web, social, writing, mapping, etc. Tools exist. Multimedia editing is unsupported.
- Respond with impossibility rationale outlining what *is* supported.

```json
{
  "goal": "Unable to complete request",
  "steps": [],
  "complexity": "impossible",
  "reason": "Missing required capabilities: video trimming and audio replacement. Available tools handle document search/extraction, writing/presentation generation, email automation, social summaries, mapping, and folder management. Multimedia editing is not supported."
}
```

---

## Email Agent Tool Selection Guide

### When to Use Each Email Tool

**Use `read_latest_emails` when:**
- ✅ User wants recent/latest emails
- ✅ User specifies number of emails: "latest 5", "recent 10"
- ✅ No specific sender or time filter

**Use `read_emails_by_sender` when:**
- ✅ User specifies sender: "from John", "emails from sarah@company.com"
- ✅ Partial names work: "John" matches "John Doe <john@example.com>"
- ✅ Email addresses work: "john@example.com"

**Use `read_emails_by_time` when:**
- ✅ User specifies time range: "past hour", "last 2 hours", "past 30 minutes"
- ✅ Extract hours/minutes from query
- ✅ Can use `hours` OR `minutes` parameter

**Use `summarize_emails` when:**
- ✅ User wants "summary", "summarize", "key points"
- ✅ ALWAYS takes output from read_* tools as input
- ✅ Can specify optional focus area
- ✅ Returns AI-generated summary text

**Use `reply_to_email` when:**
- ✅ User wants to reply to a specific email
- ✅ First read the email to get sender and subject
- ✅ Use sender's email address from read result
- ✅ Subject automatically gets "Re: " prefix
- ✅ Default creates draft (send=false) for user review

**Use `compose_email` when:**
- ✅ User wants to compose NEW email (not a reply)
- ✅ User provides recipient, subject, and body
- ✅ Can attach files with attachments parameter
- ✅ Default creates draft (send=false)

### Parameter Extraction Guide

**Count (read_latest_emails, read_emails_by_sender):**
- "latest 5" → `count: 5`
- "recent 10" → `count: 10`
- "all emails from John" → `count: 10` (reasonable default)
- Default: 10 (if not specified)

**Sender (read_emails_by_sender):**
- "john@example.com" → `sender: "john@example.com"`
- "Sarah" → `sender: "Sarah"` (partial match works!)
- "my manager" → `sender: "manager"` (if you know their name)

**Time Range (read_emails_by_time):**
- "past hour" → `hours: 1`
- "last 2 hours" → `hours: 2`
- "past 30 minutes" → `minutes: 30`
- "past day" → `hours: 24`

**Focus (summarize_emails):**
- "action items" → `focus: "action items"`
- "deadlines" → `focus: "deadlines"`
- "important updates" → `focus: "important updates"`
- No focus specified → `focus: null`

### Common Email Patterns

**Simple Read:**
```
read_latest_emails → reply_to_user
```

**Read and Summarize:**
```
read_emails_by_time → summarize_emails → reply_to_user
```

**Complex Workflow:**
```
read_emails_by_sender → summarize_emails → create_pages_doc → reply_to_user
```

**Multi-Source Summary:**
```
read_latest_emails → summarize_emails → create_slide_deck_content → create_keynote → reply_to_user
```

---

### Step 6: Final Checklist

Before submitting plan:
- [ ] All tools exist in available tools list
- [ ] All required parameters are provided
- [ ] All dependencies are correctly specified
- [ ] Data types match between steps
- [ ] No circular dependencies
- [ ] Context variables use correct field names
- [ ] **CRITICAL: Plan ends with `reply_to_user` as FINAL step**
- [ ] If impossible task, returned complexity="impossible" with clear reason
