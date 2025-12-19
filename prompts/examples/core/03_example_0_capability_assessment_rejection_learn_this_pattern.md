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
