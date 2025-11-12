# Example 1: Generate Folder Summary with Statistics and Insights

## User Request
"summarize this folder" or "give me an overview of what's in my documents"

## Intent Analysis
- **Primary Goal**: Provide comprehensive overview of folder contents
- **Key Actions**: Analyze file types, sizes, dates, and generate natural language insights
- **Output Format**: Structured summary with statistics and recommendations
- **Complexity**: Simple (2 steps, read-only)

## Correct Plan

```json
{
  "goal": "Generate comprehensive folder overview with statistics and insights",
  "steps": [
    {
      "id": 1,
      "action": "folder_list",
      "parameters": {
        "folder_path": null
      },
      "dependencies": [],
      "reasoning": "Get complete listing of all files and folders with metadata (names, types, sizes, modification dates) to analyze the folder structure.",
      "expected_output": "Complete folder contents with file metadata"
    },
    {
      "id": 2,
      "action": "folder_summarize",
      "parameters": {
        "folder_path": "$step1.folder_path",
        "items": "$step1.items"
      },
      "dependencies": [1],
      "reasoning": "Use LLM to analyze the folder contents and generate natural language summary with statistics, file type distribution, size analysis, and actionable insights.",
      "expected_output": "Structured folder summary with statistics and recommendations"
    }
  ],
  "complexity": "simple"
}
```

## Example Step 1 Output (folder_list)

```json
{
  "items": [
    {"name": "project_plan.pdf", "type": "file", "size": 2457600, "modified": 1703123456, "extension": "pdf"},
    {"name": "meeting_notes.txt", "type": "file", "size": 15360, "modified": 1702987654, "extension": "txt"},
    {"name": "budget.xlsx", "type": "file", "size": 512000, "modified": 1702891256, "extension": "xlsx"},
    {"name": "old_report.pdf", "type": "file", "size": 1843200, "modified": 1680000000, "extension": "pdf"},
    {"name": "images/", "type": "dir", "size": null, "modified": 1702567890, "extension": null},
    {"name": "archive/", "type": "dir", "size": null, "modified": 1690000000, "extension": null}
  ],
  "total_count": 6,
  "folder_path": "/Users/user/Documents",
  "relative_path": "Documents"
}
```

## Example Step 2 Output (folder_summarize)

```json
{
  "summary": "Your documents folder contains 6 items: 4 files and 2 subfolders, totaling approximately 4.8 MB of data.",
  "statistics": {
    "total_files": 4,
    "total_folders": 2,
    "total_size_bytes": 4828160,
    "total_size_mb": 4.6,
    "file_types": {
      "pdf": 2,
      "txt": 1,
      "xlsx": 1
    },
    "oldest_file": "old_report.pdf (6 months ago)",
    "newest_file": "project_plan.pdf (2 days ago)"
  },
  "insights": [
    "Most of your content is PDF documents (50% of files)",
    "Your largest file is project_plan.pdf at 2.3 MB",
    "old_report.pdf hasn't been modified in 6 months and could be archived",
    "You have an existing 'archive' folder for old files"
  ],
  "recommendations": [
    "Consider archiving old_report.pdf to reduce clutter",
    "Your folder is well-organized with clear file naming",
    "You might benefit from organizing by project or date"
  ]
}
```

## Key Reasoning Points

### Why This Plan Works:
1. **Complete Data Gathering**: folder_list provides all necessary metadata
2. **LLM-Powered Analysis**: folder_summarize generates natural insights beyond raw statistics
3. **Actionable Output**: Recommendations help users understand what to do next
4. **Context Preservation**: Uses $step1 context variables for seamless data flow

### What NOT to Do:
❌ **Don't just return raw folder_list data**:
- Users want insights, not just a list
- Raw data is overwhelming and not actionable

❌ **Don't hardcode analysis logic**:
- Let the LLM analyze patterns and generate insights
- Different users have different organization needs

❌ **Don't skip statistics**:
- File counts, sizes, and distributions are crucial context
- Users need quantitative data to make decisions

## Similar Queries

All these should use the SAME pattern (list → summarize):
- "what's in this folder?"
- "give me an overview"
- "analyze my documents"
- "show me folder statistics"
- "what's taking up space here?"
