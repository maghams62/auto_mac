# Example 3: Sort Files by Various Criteria with Explanation

## User Request
"sort by date" or "arrange by size descending" or "organize by modification time"

## Intent Analysis
- **Primary Goal**: Reorganize view of files by specific criteria for better understanding
- **Key Actions**: Sort existing files and explain the arrangement rationale
- **Output Format**: Sorted list with explanation of why this arrangement is useful
- **Complexity**: Simple (2 steps, read-only)

## Correct Plan

```json
{
  "goal": "Sort folder contents by specified criteria and explain the arrangement",
  "steps": [
    {
      "id": 1,
      "action": "folder_list",
      "parameters": {
        "folder_path": null
      },
      "dependencies": [],
      "reasoning": "Get current folder contents with full metadata needed for sorting (names, sizes, modification dates, types).",
      "expected_output": "Complete folder listing with sortable metadata"
    },
    {
      "id": 2,
      "action": "folder_sort_by",
      "parameters": {
        "folder_path": "$step1.folder_path",
        "items": "$step1.items",
        "criteria": "date",
        "direction": "descending"
      },
      "dependencies": [1],
      "reasoning": "Sort the files by modification date (newest first) and provide explanation of why this arrangement is useful for understanding file recency and activity patterns.",
      "expected_output": "Sorted file list with explanation and insights"
    }
  ],
  "complexity": "simple"
}
```

## Example Step 1 Output (folder_list)

```json
{
  "items": [
    {"name": "urgent_report.pdf", "type": "file", "size": 1024000, "modified": 1703123456, "extension": "pdf"},
    {"name": "old_meeting_notes.txt", "type": "file", "size": 51200, "modified": 1680000000, "extension": "txt"},
    {"name": "budget_2024.xlsx", "type": "file", "size": 2048000, "modified": 1702987654, "extension": "xlsx"},
    {"name": "project_photos/", "type": "dir", "size": null, "modified": 1702567890, "extension": null},
    {"name": "archive_2023/", "type": "dir", "size": null, "modified": 1670000000, "extension": null}
  ],
  "total_count": 5,
  "folder_path": "/Users/user/Documents",
  "relative_path": "Documents"
}
```

## Example Step 2 Output (folder_sort_by)

```json
{
  "sorted_items": [
    {"name": "urgent_report.pdf", "type": "file", "size": 1024000, "modified": 1703123456, "extension": "pdf", "sort_key": 1703123456},
    {"name": "budget_2024.xlsx", "type": "file", "size": 2048000, "modified": 1702987654, "extension": "xlsx", "sort_key": 1702987654},
    {"name": "project_photos/", "type": "dir", "size": null, "modified": 1702567890, "extension": null, "sort_key": 1702567890},
    {"name": "old_meeting_notes.txt", "type": "file", "size": 51200, "modified": 1680000000, "extension": "txt", "sort_key": 1680000000},
    {"name": "archive_2023/", "type": "dir", "size": null, "modified": 1670000000, "extension": null, "sort_key": 1670000000}
  ],
  "criteria": "date",
  "direction": "descending",
  "explanation": "Files sorted by modification date (newest first) to show most recently worked on items at the top. This helps you see what's current and what might need attention.",
  "insights": [
    "Your most recent activity was on 'urgent_report.pdf' (modified today)",
    "'old_meeting_notes.txt' hasn't been touched in 8 months",
    "You have one folder ('archive_2023') that's over a year old",
    "Consider archiving items older than 6 months to reduce clutter"
  ],
  "statistics": {
    "total_items": 5,
    "files_modified_this_week": 2,
    "files_modified_this_month": 3,
    "files_older_than_6_months": 2,
    "oldest_item_days": 240
  }
}
```

## Key Reasoning Points

### Why This Plan Works:
1. **Flexible Criteria**: Supports date, size, name, type, extension sorting
2. **Directional Control**: Ascending/descending options for different use cases
3. **Added Value**: Provides insights and statistics beyond just sorting
4. **Contextual Explanation**: Explains why this arrangement is useful

### What NOT to Do:
❌ **Don't just return raw sorted list**:
- Users need explanation of why this sorting matters
- Provide insights about patterns and recommendations

❌ **Don't hardcode sort logic**:
- Let the LLM decide the best sorting approach
- Different criteria need different explanations

❌ **Don't ignore direction**:
- "sort by size" vs "sort by size descending" mean different things
- Be explicit about sort direction in parameters

❌ **Don't skip metadata validation**:
- Ensure all items have the required metadata for sorting
- Handle missing data gracefully

## Alternative Criteria Examples

### Sort by Size (Largest First)
```json
{
  "criteria": "size",
  "direction": "descending",
  "explanation": "Largest files first to identify storage hogs and cleanup candidates"
}
```

### Sort by Type (Group Similar Files)
```json
{
  "criteria": "extension",
  "direction": "ascending",
  "explanation": "Grouped by file type to see content distribution and organization patterns"
}
```

### Sort by Name (Alphabetical)
```json
{
  "criteria": "name",
  "direction": "ascending",
  "explanation": "Alphabetical order for easy browsing and finding specific files"
}
```

## Similar Queries

All these should use the SAME pattern (list → sort):
- "show me files by date"
- "sort by file size"
- "arrange by type"
- "organize by modification time"
- "group by extension"
