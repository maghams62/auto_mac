## Example 9: WRITING AGENT - Meeting Notes (NEW!)

### User Request
"Find the Q1 planning meeting transcript and create structured notes with action items"

### Decomposition
```json
{
  "goal": "Extract meeting transcript and create professional notes with action items",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "Q1 planning meeting transcript"
      },
      "dependencies": [],
      "reasoning": "Find the meeting transcript document",
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
      "reasoning": "Extract full transcript content",
      "expected_output": "Meeting transcript text"
    },
    {
      "id": 3,
      "action": "create_meeting_notes",
      "parameters": {
        "content": "$step2.extracted_text",
        "meeting_title": "Q1 Planning Meeting",
        "attendees": null,
        "include_action_items": true
      },
      "dependencies": [2],
      "reasoning": "Structure notes and extract action items with owners",
      "expected_output": "Formatted notes with action items, decisions, takeaways"
    },
    {
      "id": 4,
      "action": "create_pages_doc",
      "parameters": {
        "title": "Q1 Planning Meeting Notes",
        "content": "$step3.formatted_notes"
      },
      "dependencies": [3],
      "reasoning": "Save structured notes as document",
      "expected_output": "Pages document created"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Meeting Notes Pattern**
- ✅ Use `create_meeting_notes` to structure transcripts
- ✅ Automatically extracts action items, decisions, discussion points
- ✅ Identifies owners and deadlines for action items
- ❌ Don't just use `extract_section` - Writing Agent adds structure

---
