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
