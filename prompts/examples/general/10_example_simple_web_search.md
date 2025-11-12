## Example 9: Simple Web Search Task

### User Request
"Search for the latest news about Tesla electric vehicles"

### Decomposition
```json
{
  "goal": "Find and summarize recent news about Tesla electric vehicles",
  "steps": [
    {
      "id": 1,
      "action": "google_search",
      "parameters": {
        "query": "Tesla electric vehicles latest news"
      },
      "dependencies": [],
      "reasoning": "Use web search to find recent news articles about Tesla EVs",
      "expected_output": "Search results with titles, URLs, and snippets from relevant news sources"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "Latest Tesla EV news",
        "details": "Summary of recent news articles with key points and source links",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [1],
      "reasoning": "Present search results in a user-friendly format",
      "expected_output": "Formatted response with news summary and links"
    }
  ],
  "complexity": "simple",
  "task_type": "web_search"
}
```

**Pattern: Web Search → Reply**

This pattern applies to informational queries that can be answered through web search. Always use `google_search` for research questions, then format the results with `reply_to_user`.
