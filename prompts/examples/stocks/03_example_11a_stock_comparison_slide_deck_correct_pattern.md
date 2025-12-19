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
