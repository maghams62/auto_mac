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
