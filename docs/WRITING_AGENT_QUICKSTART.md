# Writing Agent - Quick Start Guide

## What is the Writing Agent?

The Writing Agent is a specialized AI agent that can:
- 📚 **Synthesize** information from multiple sources
- 📊 **Create slide decks** with concise bullet points
- 📝 **Generate detailed reports** with flowing prose
- 📋 **Structure meeting notes** with action items

## Quick Examples

### Example 1: Create a Research Report

**User Request:** "Find documents about AI safety and machine learning, then create a comprehensive report"

**What Happens:**
```
1. search_documents("AI safety") → doc1
2. search_documents("machine learning trends") → doc2
3. extract_section(doc1, "all") → content1
4. extract_section(doc2, "all") → content2
5. synthesize_content([content1, content2], "AI Research", "comprehensive") → synthesis
6. create_detailed_report(synthesis, "AI Research Report 2025", "academic") → report
7. create_pages_doc(report.content, "AI Research Report 2025") → saved!
```

**Result:** A professional academic report combining insights from multiple sources

---

### Example 2: Create a Presentation

**User Request:** "Research product launches and create a 5-slide presentation"

**What Happens:**
```
1. google_search("2025 product launches") → results
2. extract_page_content(url1) → content1
3. extract_page_content(url2) → content2
4. synthesize_content([content1, content2], "Product Launches", "concise") → synthesis
5. create_slide_deck_content(synthesis, "2025 Trends", 5) → slides
6. create_keynote(slides.formatted_content, "2025 Trends") → presentation saved!
```

**Result:** A 5-slide Keynote presentation with concise, impactful bullets

---

### Example 3: Process Meeting Notes

**User Request:** "Find the Q1 planning meeting transcript and create structured notes with action items"

**What Happens:**
```
1. search_documents("Q1 planning meeting") → doc
2. extract_section(doc, "all") → transcript
3. create_meeting_notes(transcript, "Q1 Planning", ["Alice", "Bob"]) → notes
4. compose_email("Meeting Notes", notes, "team@company.com", send=True) → sent!
```

**Result:** Structured meeting notes with extracted action items, emailed to team

---

## Tool Descriptions

### 🔄 `synthesize_content`
Combines multiple sources into one cohesive narrative

**When to use:**
- You have 2+ documents/pages to combine
- Need to remove redundancy
- Want unified insights from multiple sources

**Styles:**
- `comprehensive` - All details (for reports)
- `concise` - Key points only (for summaries)
- `comparative` - Highlight differences
- `chronological` - Timeline-based

---

### 📊 `create_slide_deck_content`
Transforms content into presentation-ready bullets

**When to use:**
- Creating a slide deck/Keynote
- Need SHORT, punchy bullets (5-7 words)
- Want concise, visual-friendly content

**Output:** Ready to use with `create_keynote`

---

### 📝 `create_detailed_report`
Generates long-form, detailed reports with structure

**When to use:**
- Need detailed analysis (NOT bullets)
- Want flowing, professional prose
- Creating formal documentation

**Styles:**
- `business` - Professional, action-oriented
- `academic` - Formal, analytical
- `technical` - Detailed, precise
- `executive` - High-level, strategic

**Output:** Ready to use with `create_pages_doc`

---

### 📋 `create_meeting_notes`
Structures meeting transcripts with action items

**When to use:**
- Processing meeting transcripts/rough notes
- Need to extract action items and owners
- Want professional meeting documentation

**Output:** Formatted notes with action items, decisions, takeaways

---

## Common Workflows

### Workflow 1: Multi-Document Report
```
Documents → Extract → Synthesize → Report → Pages Doc
```

### Workflow 2: Web Research Presentation
```
Google Search → Extract Pages → Synthesize → Slides → Keynote
```

### Workflow 3: Hybrid Research
```
[Documents + Web] → Extract All → Synthesize → [Report OR Slides]
```

### Workflow 4: Meeting Documentation
```
Find Transcript → Extract → Meeting Notes → Email Team
```

---

## Tips for Best Results

### ✅ DO:
- Use **synthesis** when combining 2+ sources
- Use **slide deck** for presentations (creates concise bullets)
- Use **detailed report** for documents (creates flowing prose)
- Chain tools together for complete workflows

### ❌ DON'T:
- Don't use slide deck for detailed content (it will make bullets)
- Don't use detailed report for presentations (it will make paragraphs)
- Don't skip synthesis when you have multiple sources

---

## Writing Style Comparison

| Tool | Output Style | Best For | Word Count |
|------|-------------|----------|------------|
| `synthesize_content` | Unified narrative | Research synthesis | Variable |
| `create_slide_deck_content` | Short bullets (5-7 words) | Presentations | ~50-100 |
| `create_detailed_report` | Flowing paragraphs | Reports, documents | 400-1000+ |
| `create_meeting_notes` | Structured lists | Meeting docs | 200-500 |

---

## Real-World Use Cases

### 📊 Business Intelligence Report
1. Search for market research documents
2. Extract relevant sections
3. Synthesize findings
4. Create detailed business report
5. Save as Pages document
6. Email to stakeholders

### 🎓 Academic Literature Review
1. Find research papers
2. Extract methodologies and findings
3. Synthesize with comparative style
4. Create academic report with citations
5. Generate presentation for defense
6. Save both formats

### 💼 Executive Briefing
1. Research recent news and reports
2. Extract key information
3. Synthesize with concise style
4. Create slide deck (3-5 slides)
5. Generate executive-style report
6. Prepare for board meeting

### 📝 Meeting Follow-up
1. Extract meeting transcript
2. Create structured notes
3. Extract action items with owners
4. Email notes to attendees
5. Track action item completion

---

## Test the Writing Agent

Run the test suite to see all tools in action:

```bash
python test_writing_agent.py
```

This will demonstrate:
- ✅ Content synthesis from 3 sources
- ✅ Slide deck with 3 concise slides
- ✅ Technical report with 5 sections
- ✅ Meeting notes with action items

---

## Need Help?

**Check documentation:**
- `WRITING_AGENT_SUMMARY.md` - Full technical documentation
- `prompts/tool_definitions.md` - Complete tool specifications
- `src/agent/writing_agent.py` - Source code with examples

**Common Questions:**

**Q: When should I use synthesize vs. just extract?**
A: Use synthesize when you have 2+ sources. It removes redundancy and creates unified narrative.

**Q: What's the difference between slide deck and detailed report?**
A: Slide deck = short bullets (5-7 words). Detailed report = flowing paragraphs. Use based on output format needed.

**Q: Can I customize the writing style?**
A: Yes! Use `synthesis_style` parameter (comprehensive/concise/comparative/chronological) and `report_style` (business/academic/technical/executive).

**Q: How do I chain with other agents?**
A: Use `$stepN.field` syntax to reference previous outputs. Example: `content="$step3.synthesized_content"`

---

**Status:** ✅ Production Ready | **Tests:** ✅ 4/4 Passed | **Tools:** 4 | **Agent:** Writing Agent
