## Example 28: CROSS-DOMAIN REPORT → SLIDES → EMAIL (NEW!)

**Reasoning (chain of thought):**
1. Confirm capabilities: File, Writing, Presentation, Email, and Reply agents exist and cover all operations.
2. Outline workflow: locate documents → extract relevant sections → synthesize insights → generate slides → draft email → reply.
3. Plan dependencies: later steps use `$stepN` outputs (`doc_path`, `extracted_text`, etc.) so specify dependencies precisely.
4. Ensure plan ends with `reply_to_user` referencing final artifacts.

**User Request:** “Create a competitive summary on Product Aurora using the latest roadmap PDF and the ‘Aurora_feedback.docx’, turn it into a 5-slide deck, then email it to leadership with the deck attached.”

```json
{
  "goal": "Produce competitive summary slides on Product Aurora and email leadership",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "Product Aurora roadmap PDF"
      },
      "dependencies": [],
      "reasoning": "Find the roadmap PDF in local knowledge base",
      "expected_output": "doc_path and metadata for roadmap PDF"
    },
    {
      "id": 2,
      "action": "search_documents",
      "parameters": {
        "query": "Aurora_feedback.docx"
      },
      "dependencies": [],
      "reasoning": "Find internal feedback document for supporting context",
      "expected_output": "doc_path for feedback document"
    },
    {
      "id": 3,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "latest updates"
      },
      "dependencies": [1],
      "reasoning": "Capture recent roadmap updates",
      "expected_output": "extracted_text for roadmap updates"
    },
    {
      "id": 4,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step2.doc_path",
        "section": "top customer pain points"
      },
      "dependencies": [2],
      "reasoning": "Surface key customer feedback themes",
      "expected_output": "extracted_text for pain points"
    },
    {
      "id": 5,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": [
          "$step3.extracted_text",
          "$step4.extracted_text"
        ],
        "topic": "Product Aurora competitive summary",
        "synthesis_style": "comparative"
      },
      "dependencies": [3, 4],
      "reasoning": "Blend roadmap insights with customer pain points",
      "expected_output": "message with synthesized summary"
    },
    {
      "id": 6,
      "action": "create_slide_deck_content",
      "parameters": {
        "content": "$step5.message",
        "slide_count": 5
      },
      "dependencies": [5],
      "reasoning": "Turn synthesis into 5-slide outline",
      "expected_output": "slide deck outline text"
    },
    {
      "id": 7,
      "action": "create_keynote",
      "parameters": {
        "title": "Product Aurora Competitive Summary",
        "content": "$step6.content"
      },
      "dependencies": [6],
      "reasoning": "Produce Keynote presentation from outline",
      "expected_output": "keynote_path and message"
    },
    {
      "id": 8,
      "action": "compose_email",
      "parameters": {
        "subject": "Product Aurora Competitive Summary",
        "body": "Hi leadership – please find attached the latest competitive summary on Aurora. Let me know if you need more detail.",
        "attachments": [
          "$step7.keynote_path"
        ],
        "send": false
      },
      "dependencies": [7],
      "reasoning": "Draft email to leadership with deck attached (draft for review)",
      "expected_output": "Email draft status"
    },
    {
      "id": 9,
      "action": "reply_to_user",
      "parameters": {
        "message": "Prepared the Aurora competitive summary slides and drafted an email for leadership review.",
        "details": "- Slides created: `$step7.keynote_path`\n- Email draft prepared with attachment\n- Sources: roadmap + customer feedback docs",
        "artifacts": [
          "$step7.keynote_path"
        ],
        "status": "success"
      },
      "dependencies": [7, 8],
      "reasoning": "Summarize final deliverables to the user",
      "expected_output": "User-facing confirmation"
    }
  ],
  "complexity": "complex"
}
```

---
