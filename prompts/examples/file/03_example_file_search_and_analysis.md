## Example 23: File Search and Analysis

### User Request
"Find all documents containing 'project timeline' and summarize their key dates"

### Decomposition
```json
{
  "goal": "Search for documents with specific content and extract timeline information",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "project timeline"
      },
      "dependencies": [],
      "reasoning": "Search the document collection for files containing 'project timeline'",
      "expected_output": "List of documents matching the search query with metadata"
    },
    {
      "id": 2,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.results[0].path",
        "section_hint": "timeline"
      },
      "dependencies": [1],
      "reasoning": "Extract timeline-related content from the first matching document",
      "expected_output": "Relevant text sections containing timeline information"
    },
    {
      "id": 3,
      "action": "synthesize_content",
      "parameters": {
        "content": "$step2.extracted_text",
        "task": "Extract and summarize all dates and milestones from project timeline information"
      },
      "dependencies": [2],
      "reasoning": "Use AI to analyze extracted text and identify key dates and milestones",
      "expected_output": "Structured summary of timeline information"
    },
    {
      "id": 4,
      "action": "reply_to_user",
      "parameters": {
        "message": "Project timeline summary",
        "details": "$step3.summary",
        "artifacts": [],
        "status": "success"
      },
      "dependencies": [3],
      "reasoning": "Present the timeline analysis in a clear, organized format",
      "expected_output": "User-friendly summary of project timelines and key dates"
    }
  ],
  "complexity": "medium",
  "task_type": "file_search"
}
```

**Pattern: Search → Extract → Synthesize → Reply**

This pattern applies to content analysis tasks requiring search, extraction, and synthesis. Use `search_documents` first, then `extract_section` for targeted content, followed by `synthesize_content` for analysis.
