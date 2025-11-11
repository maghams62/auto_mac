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
