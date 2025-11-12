# Example 2: Explain File Content and Purpose

## User Request
"explain this report.pdf" or "what is this document about?" or "tell me about my notes.txt"

## Intent Analysis
- **Primary Goal**: Understand what a specific file contains and its purpose
- **Key Actions**: Combine file metadata with content analysis using cross-agent search
- **Output Format**: Natural language explanation with key topics and suggested actions
- **Complexity**: Medium (3 steps, cross-agent handoff)

## Correct Plan

```json
{
  "goal": "Explain file content, purpose, and suggest actions using metadata and semantic analysis",
  "steps": [
    {
      "id": 1,
      "action": "folder_check_sandbox",
      "parameters": {
        "path": "report.pdf"
      },
      "dependencies": [],
      "reasoning": "Validate that the requested file is within the allowed sandbox before attempting to analyze it.",
      "expected_output": "Sandbox validation result confirming file access"
    },
    {
      "id": 2,
      "action": "search_documents",
      "parameters": {
        "query": "report.pdf",
        "user_request": "explain this report.pdf"
      },
      "dependencies": [1],
      "reasoning": "Cross-agent handoff: Use file agent's semantic search to find content matches and get document metadata. This provides content preview and relevance scoring.",
      "expected_output": "Document search results with content preview and metadata"
    },
    {
      "id": 3,
      "action": "folder_explain_file",
      "parameters": {
        "file_path": "$step1.resolved_path",
        "search_results": "$step2",
        "metadata": {
          "file_name": "report.pdf",
          "file_size": "2.3 MB",
          "modified": "2 days ago"
        }
      },
      "dependencies": [1, 2],
      "reasoning": "Combine file metadata with content analysis to generate natural language explanation of what the file contains, its purpose, and suggest relevant actions.",
      "expected_output": "Comprehensive file explanation with key topics and recommendations"
    }
  ],
  "complexity": "medium"
}
```

## Example Step 1 Output (folder_check_sandbox)

```json
{
  "is_safe": true,
  "message": "Path is within allowed folder: /Users/user/Documents",
  "resolved_path": "/Users/user/Documents/project_report.pdf",
  "allowed_folder": "/Users/user/Documents"
}
```

## Example Step 2 Output (search_documents)

```json
{
  "doc_path": "/Users/user/Documents/project_report.pdf",
  "doc_title": "project_report",
  "relevance_score": 0.95,
  "content_preview": "Project Timeline and Budget Report\n\nExecutive Summary:\nThis report outlines the Q4 2024 project timeline and budget allocation for the new marketing campaign. Key milestones include market research completion by Dec 15, content creation by Jan 10, and launch scheduled for Feb 1.\n\nBudget Breakdown:\n- Research: $25,000\n- Content Creation: $45,000\n- Media Buying: $80,000\n- Analytics: $15,000\nTotal: $165,000",
  "metadata": {
    "file_type": "pdf",
    "chunk_count": 3,
    "page_count": 8
  }
}
```

## Example Step 3 Output (folder_explain_file)

```json
{
  "explanation": "This is a project report PDF (2.3 MB) that you modified 2 days ago. It contains a comprehensive overview of a Q4 2024 marketing campaign project.",
  "key_topics": [
    "Q4 2024 marketing campaign timeline",
    "Project budget allocation ($165,000 total)",
    "Key milestones: market research, content creation, campaign launch",
    "Executive summary and detailed budget breakdown"
  ],
  "content_summary": "The document appears to be a business report covering project planning and financials. It includes timelines, budget allocations across different project phases, and strategic planning for a marketing initiative.",
  "suggested_actions": [
    "Review the Feb 1 launch deadline",
    "Check if the $165,000 budget aligns with current plans",
    "Consider sharing with team members for project updates",
    "Archive if this is a completed project report"
  ],
  "file_insights": {
    "size_context": "Reasonably sized for a business report",
    "modification_context": "Recently updated - likely current project",
    "content_richness": "Detailed document with structured sections"
  }
}
```

## Key Reasoning Points

### Why This Plan Works:
1. **Security First**: Always validate file access before analysis
2. **Cross-Agent Integration**: Seamlessly uses file agent for content understanding
3. **Metadata + Content**: Combines file stats with semantic analysis
4. **Actionable Insights**: Provides specific recommendations based on content

### What NOT to Do:
❌ **Don't skip sandbox validation**:
- Security is paramount - always check access first
- Users might request files outside allowed folders

❌ **Don't just return file metadata**:
- Users want to know WHAT the file contains
- Pure metadata (size, date) is insufficient for understanding

❌ **Don't use folder tools for content analysis**:
- Folder tools are for organization, not content understanding
- Cross-agent handoff to file agent is required for content analysis

❌ **Don't assume file type capabilities**:
- Different file types need different analysis approaches
- PDFs need text extraction, images need different handling

## Similar Queries

All these should use the SAME pattern (validate → search → explain):
- "what's in this PDF?"
- "explain my budget.xlsx file"
- "tell me about this document"
- "what does this file contain?"
- "analyze this report for me"
