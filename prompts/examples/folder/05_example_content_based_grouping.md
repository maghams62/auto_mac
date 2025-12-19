# Example 5: Group Files by Content/Topic with Semantic Analysis

## User Request
"group by project" or "organize documents by topic" or "sort files by content category"

## Intent Analysis
- **Primary Goal**: Organize files based on their content/themes using AI analysis
- **Key Actions**: Cross-agent analysis using file search, categorize by topics, group files
- **Output Format**: Semantic categories with explanation, confirmation required for moves
- **Complexity**: Complex (5 steps, cross-agent integration, write operation)

## Correct Plan

```json
{
  "goal": "Analyze file contents and organize them into semantic categories",
  "steps": [
    {
      "id": 1,
      "action": "folder_list",
      "parameters": {
        "folder_path": null
      },
      "dependencies": [],
      "reasoning": "Get all files that need to be analyzed for content-based categorization.",
      "expected_output": "List of files to categorize"
    },
    {
      "id": 2,
      "action": "search_documents",
      "parameters": {
        "query": "$step1.items[0].name + ' ' + $step1.items[1].name + ' ' + $step1.items[2].name",
        "user_request": "categorize these files by content and topic"
      },
      "dependencies": [1],
      "reasoning": "Cross-agent: Use file search to analyze content of multiple files and identify common themes/topics for categorization.",
      "expected_output": "Content analysis results for categorization"
    },
    {
      "id": 3,
      "action": "folder_organize_by_category",
      "parameters": {
        "folder_path": "$step1.folder_path",
        "items": "$step1.items",
        "content_analysis": "$step2",
        "dry_run": true
      },
      "dependencies": [1, 2],
      "reasoning": "Generate semantic grouping plan based on content analysis. Create categories like 'Project_A', 'Marketing', 'Finance' and show which files go where.",
      "expected_output": "Categorization plan with proposed folder structure"
    },
    {
      "id": 4,
      "action": "folder_organize_by_category",
      "parameters": {
        "folder_path": "$step1.folder_path",
        "items": "$step1.items",
        "content_analysis": "$step2",
        "dry_run": false
      },
      "dependencies": [1, 2, 3],
      "reasoning": "AFTER USER CONFIRMATION: Execute the semantic organization by creating category folders and moving files.",
      "expected_output": "Files moved to semantic category folders"
    },
    {
      "id": 5,
      "action": "folder_list",
      "parameters": {
        "folder_path": null
      },
      "dependencies": [4],
      "reasoning": "Show the new semantically organized folder structure.",
      "expected_output": "Updated folder with category subfolders"
    }
  ],
  "complexity": "complex"
}
```

## Example Step 1 Output (folder_list)

```json
{
  "items": [
    {"name": "marketing_campaign_q4.pdf", "type": "file", "size": 2048000, "modified": 1703123456, "extension": "pdf"},
    {"name": "budget_2024_analysis.xlsx", "type": "file", "size": 1536000, "modified": 1702987654, "extension": "xlsx"},
    {"name": "project_timeline.docx", "type": "file", "size": 1024000, "modified": 1702891256, "extension": "docx"},
    {"name": "team_meeting_notes.txt", "type": "file", "size": 51200, "modified": 1702804856, "extension": "txt"},
    {"name": "client_feedback.pdf", "type": "file", "size": 768000, "modified": 1702718456, "extension": "pdf"}
  ],
  "total_count": 5,
  "folder_path": "/Users/user/Documents",
  "relative_path": "Documents"
}
```

## Example Step 2 Output (search_documents - batch analysis)

```json
{
  "content_themes": [
    {
      "theme": "marketing",
      "files": ["marketing_campaign_q4.pdf", "client_feedback.pdf"],
      "confidence": 0.85,
      "keywords": ["campaign", "marketing", "client", "feedback", "Q4"]
    },
    {
      "theme": "finance",
      "files": ["budget_2024_analysis.xlsx"],
      "confidence": 0.92,
      "keywords": ["budget", "analysis", "finance", "2024", "costs"]
    },
    {
      "theme": "project_management",
      "files": ["project_timeline.docx", "team_meeting_notes.txt"],
      "confidence": 0.78,
      "keywords": ["project", "timeline", "meeting", "team", "schedule"]
    }
  ],
  "suggested_categories": [
    "Marketing_Campaigns",
    "Financial_Analysis",
    "Project_Management"
  ]
}
```

## Example Step 3 Output (folder_organize_by_category - dry_run)

```json
{
  "categories": {
    "Marketing_Campaigns": {
      "files": [
        {"name": "marketing_campaign_q4.pdf", "reason": "Contains Q4 marketing campaign content"},
        {"name": "client_feedback.pdf", "reason": "Client feedback on marketing materials"}
      ],
      "description": "Marketing campaign materials and client feedback"
    },
    "Financial_Analysis": {
      "files": [
        {"name": "budget_2024_analysis.xlsx", "reason": "Budget analysis and financial planning"}
      ],
      "description": "Financial documents and budget analysis"
    },
    "Project_Management": {
      "files": [
        {"name": "project_timeline.docx", "reason": "Project timeline and scheduling"},
        {"name": "team_meeting_notes.txt", "reason": "Team meeting notes and project updates"}
      ],
      "description": "Project management documents and meeting notes"
    }
  },
  "new_structure": "Marketing_Campaigns/, Financial_Analysis/, Project_Management/",
  "dry_run": true,
  "needs_confirmation": true,
  "confirmation_message": "This will create 3 new category folders and organize your 5 files by content theme. Each file will be moved to the most relevant category folder. Proceed with semantic organization?"
}
```

## Example Step 4 Output (folder_organize_by_category - execution)

```json
{
  "success": true,
  "folders_created": [
    "/Users/user/Documents/Marketing_Campaigns",
    "/Users/user/Documents/Financial_Analysis",
    "/Users/user/Documents/Project_Management"
  ],
  "files_moved": [
    {
      "file": "marketing_campaign_q4.pdf",
      "from": "/Users/user/Documents/",
      "to": "/Users/user/Documents/Marketing_Campaigns/marketing_campaign_q4.pdf"
    },
    {
      "file": "client_feedback.pdf",
      "from": "/Users/user/Documents/",
      "to": "/Users/user/Documents/Marketing_Campaigns/client_feedback.pdf"
    },
    {
      "file": "budget_2024_analysis.xlsx",
      "from": "/Users/user/Documents/",
      "to": "/Users/user/Documents/Financial_Analysis/budget_2024_analysis.xlsx"
    },
    {
      "file": "project_timeline.docx",
      "from": "/Users/user/Documents/",
      "to": "/Users/user/Documents/Project_Management/project_timeline.docx"
    },
    {
      "file": "team_meeting_notes.txt",
      "from": "/Users/user/Documents/",
      "to": "/Users/user/Documents/Project_Management/team_meeting_notes.txt"
    }
  ],
  "dry_run": false
}
```

## Key Reasoning Points

### Why This Plan Works:
1. **Semantic Analysis**: Uses AI to understand content and create meaningful categories
2. **Cross-Agent Integration**: Leverages file search for content understanding
3. **Flexible Categories**: Creates categories based on actual content themes
4. **Preview Required**: Shows categorization plan before making changes

### What NOT to Do:
❌ **Don't use file extensions for categorization**:
- Content-based grouping requires understanding what's inside files
- Extension-based is simpler but less intelligent

❌ **Don't skip content analysis**:
- Need to analyze file contents to create meaningful semantic groups
- Can't categorize by content without reading the content

❌ **Don't create too many/few categories**:
- Balance between too granular (every file in its own folder) and too broad
- Use content analysis to determine optimal category count

❌ **Don't execute without showing the plan**:
- Users need to see how files will be categorized
- Complex reorganization requires clear preview and confirmation

## Alternative Content Grouping Strategies

### By Project Phase
```json
{
  "grouping_strategy": "project_phase",
  "categories": ["Planning", "Execution", "Review", "Archive"]
}
```

### By Document Type/Content
```json
{
  "grouping_strategy": "document_type",
  "categories": ["Reports", "Presentations", "Correspondence", "Data"]
}
```

### By Time Period
```json
{
  "grouping_strategy": "temporal",
  "categories": ["This_Quarter", "This_Year", "Previous_Years"]
}
```

## Similar Queries

All these should use the SAME pattern (list → analyze content → plan categories → confirm → organize):
- "organize by topic"
- "group documents by project"
- "sort by content category"
- "categorize my files semantically"
- "organize by theme or subject"
