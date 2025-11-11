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
