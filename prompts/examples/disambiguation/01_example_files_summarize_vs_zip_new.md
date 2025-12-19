# Disambiguation – “Summarize or Zip?” Folder Request

**Initial User Prompt**: “Handle the Ed Sheeran files for me.”

**Clarifying Response**: “Do you want me to summarize the contents, or create a ZIP you can download?”

**User Clarifies**: “Summarize them and email me the highlights.”

**Reasoning**:
- First message is ambiguous—ask a clarifying question instead of guessing.
- After the user specifies “summarize … email,” follow the RAG → writing agent → email pattern.
- Attachments should include the source PDFs, and the final reply must confirm delivery.

```json
{
  "goal": "Clarify ambiguous folder request and deliver the requested summary",
  "steps": [
    {
      "id": 1,
      "action": "reply_to_user",
      "parameters": {
        "message": "I can summarize the contents or package them into a ZIP. Which do you prefer?",
        "status": "info"
      },
      "dependencies": [],
      "reasoning": "Clarify the intent before running any tools."
    },
    {
      "id": 2,
      "action": "search_documents",
      "parameters": {
        "query": "Ed Sheeran song PDF"
      },
      "dependencies": [],
      "reasoning": "Use semantic search to locate the requested PDFs once user selects 'summarize'."
    },
    {
      "id": 3,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step2.doc_path",
        "section": "all"
      },
      "dependencies": [2],
      "reasoning": "Provide complete content to the writing agent."
    },
    {
      "id": 4,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": [
          "$step3.extracted_text"
        ],
        "synthesis_style": "concise",
        "format": "bullet_summary"
      },
      "dependencies": [3],
      "reasoning": "Generate a bullet list summarizing the PDFs."
    },
    {
      "id": 5,
      "action": "compose_email",
      "parameters": {
        "subject": "Summary of Ed Sheeran Files",
        "body": "$step4.synthesized_content",
        "attachments": [
          "$step2.doc_path"
        ],
        "send": true
      },
      "dependencies": [4],
      "reasoning": "Email the requested summary with source material attached."
    },
    {
      "id": 6,
      "action": "reply_to_user",
      "parameters": {
        "message": "Summarized the Ed Sheeran PDFs and emailed the recap to you.",
        "details": "$step4.synthesized_content",
        "status": "success"
      },
      "dependencies": [5],
      "reasoning": "Confirm completion and surface the summary to the user."
    }
  ],
  "complexity": "medium"
}
```
