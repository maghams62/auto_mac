## Example 7: WRITING AGENT - Multi-Source Research Report (NEW!)

### User Request
"Create a detailed report comparing machine learning and deep learning approaches"

### Decomposition
```json
{
  "goal": "Research multiple sources and create comprehensive comparative report",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "machine learning approaches"
      },
      "dependencies": [],
      "reasoning": "Find document about machine learning",
      "expected_output": "ML document path"
    },
    {
      "id": 2,
      "action": "search_documents",
      "parameters": {
        "query": "deep learning techniques"
      },
      "dependencies": [],
      "reasoning": "Find document about deep learning",
      "expected_output": "DL document path"
    },
    {
      "id": 3,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "all"
      },
      "dependencies": [1],
      "reasoning": "Extract ML content",
      "expected_output": "ML text content"
    },
    {
      "id": 4,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step2.doc_path",
        "section": "all"
      },
      "dependencies": [2],
      "reasoning": "Extract DL content",
      "expected_output": "DL text content"
    },
    {
      "id": 5,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": ["$step3.extracted_text", "$step4.extracted_text"],
        "topic": "Machine Learning vs Deep Learning",
        "synthesis_style": "comparative"
      },
      "dependencies": [3, 4],
      "reasoning": "Combine sources with comparative analysis, removing redundancy",
      "expected_output": "Synthesized comparative analysis"
    },
    {
      "id": 6,
      "action": "create_detailed_report",
      "parameters": {
        "content": "$step5.synthesized_content",
        "title": "ML vs DL: Comparative Analysis",
        "report_style": "technical",
        "include_sections": null
      },
      "dependencies": [5],
      "reasoning": "Generate detailed technical report with proper structure",
      "expected_output": "Comprehensive report with sections"
    },
    {
      "id": 7,
      "action": "create_pages_doc",
      "parameters": {
        "title": "ML vs DL: Comparative Analysis",
        "content": "$step6.report_content"
      },
      "dependencies": [6],
      "reasoning": "Save report as Pages document",
      "expected_output": "Pages document created"
    }
  ],
  "complexity": "complex"
}
```

**CRITICAL: Writing Agent Workflow**
- ✅ Use `synthesize_content` to combine multiple sources (removes redundancy)
- ✅ Use `create_detailed_report` to transform into long-form prose
- ✅ Choose appropriate `synthesis_style` (comparative for comparing sources)
- ✅ Choose appropriate `report_style` (technical, business, academic, or executive)
- ❌ Don't pass multiple sources directly to `create_pages_doc` - synthesize first!

---
