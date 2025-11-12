# Stock Agent – Generate PDF Report via Pages and Email It

**User Request**: “Create a detailed stock report on NVIDIA and email it to me.”

**Reasoning**:
- Report (PDF) rather than slideshow → use Pages workflow, not Keynote.
- Pull fresh market data before writing.
- Use writing agent to synthesize sections, then call the Pages tool with `export_pdf: true`.
- Delivery verb “email” → include `compose_email` with attachment and `send: true`.
- Finish with `reply_to_user` summarizing the sections and confirming email delivery.

```json
{
  "goal": "Produce a PDF stock report on NVIDIA and email it to the user",
  "steps": [
    {
      "id": 1,
      "action": "get_stock_price",
      "parameters": {
        "symbol": "NVDA"
      },
      "dependencies": [],
      "reasoning": "Fetch the current price and key metrics from yfinance."
    },
    {
      "id": 2,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": [
          "$step1"
        ],
        "synthesis_style": "comprehensive",
        "format": "report_sections",
        "title": "NVIDIA Corporation Stock Analysis"
      },
      "dependencies": [1],
      "reasoning": "Generate structured report sections (overview, fundamentals, outlook)."
    },
    {
      "id": 3,
      "action": "create_pages_doc",
      "parameters": {
        "title": "NVIDIA Corporation (NVDA) Stock Analysis Report",
        "sections": "$step2.synthesized_content",
        "export_pdf": true
      },
      "dependencies": [2],
      "reasoning": "Render the report in Pages and export it to PDF."
    },
    {
      "id": 4,
      "action": "compose_email",
      "parameters": {
        "subject": "NVIDIA Stock Report",
        "body": "Attached is the latest NVIDIA (NVDA) stock analysis.",
        "attachments": [
          "$step3.pdf_path"
        ],
        "send": true
      },
      "dependencies": [3],
      "reasoning": "Email the PDF report to the user automatically."
    },
    {
      "id": 5,
      "action": "reply_to_user",
      "parameters": {
        "message": "Created the NVIDIA stock report and emailed you the PDF.",
        "details": "$step2.synthesized_content.summary",
        "artifacts": [
          "$step3.pdf_path"
        ],
        "status": "success"
      },
      "dependencies": [4],
      "reasoning": "Confirm delivery and provide a quick summary."
    }
  ],
  "complexity": "medium"
}
```
