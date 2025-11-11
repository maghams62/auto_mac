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
