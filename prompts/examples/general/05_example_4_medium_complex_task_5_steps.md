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
