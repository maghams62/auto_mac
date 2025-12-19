# File Agent – Summarize PDFs via RAG and Email Results

**User Request**: “Summarize the Ed Sheeran song PDFs in my documents and email me the highlights.”

**Reasoning**:
- User wants a textual recap, not re-organization → use semantic document search (RAG) instead of folder tools.
- Need full content for the writing agent → extract the document before summarizing.
- Delivery verb “email” → include `compose_email` with `send: true` and attach the source material.
- Always finish with `reply_to_user` so the UI displays the summary.

```json
{
  "goal": "Summarize Ed Sheeran song PDFs and email the bullet recap to the user",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "Ed Sheeran song PDF"
      },
      "dependencies": [],
      "reasoning": "Use precomputed embeddings to locate the relevant PDFs."
    },
    {
      "id": 2,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "all"
      },
      "dependencies": [1],
      "reasoning": "Pull the entire PDF so the writing agent has complete context."
    },
    {
      "id": 3,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": [
          "$step2.extracted_text"
        ],
        "synthesis_style": "concise",
        "format": "bullet_summary"
      },
      "dependencies": [2],
      "reasoning": "Generate a concise set of bullet points describing the PDFs."
    },
    {
      "id": 4,
      "action": "compose_email",
      "parameters": {
        "subject": "Summary of Ed Sheeran Song PDFs",
        "body": "$step3.synthesized_content",
        "attachments": [
          "$step1.doc_path"
        ],
        "send": true
      },
      "dependencies": [3],
      "reasoning": "Email the bullet summary and attach the source PDF as requested."
    },
    {
      "id": 5,
      "action": "reply_to_user",
      "parameters": {
        "message": "Shared a bullet recap of your Ed Sheeran PDFs and emailed it to you.",
        "details": "$step3.synthesized_content",
        "artifacts": [
          "$step1.doc_path"
        ],
        "status": "success"
      },
      "dependencies": [4],
      "reasoning": "Confirm delivery and surface the summary in the UI."
    }
  ],
  "complexity": "medium"
}
```
