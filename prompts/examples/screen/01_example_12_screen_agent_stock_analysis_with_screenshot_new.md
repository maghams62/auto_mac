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
