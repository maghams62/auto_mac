# Example 4: Archive Old Files with Confirmation

## User Request
"archive files older than 6 months" or "move old files to archive" or "cleanup files not touched in a year"

## Intent Analysis
- **Primary Goal**: Move old/unused files to archive folder to reduce clutter
- **Key Actions**: Identify old files, create archive structure, move with confirmation
- **Output Format**: Clear preview of what will be archived, confirmation required
- **Complexity**: Medium (4 steps, write operation with confirmation)

## Correct Plan

```json
{
  "goal": "Identify and archive old files to reduce folder clutter",
  "steps": [
    {
      "id": 1,
      "action": "folder_list",
      "parameters": {
        "folder_path": null
      },
      "dependencies": [],
      "reasoning": "Get all files with modification dates to identify which ones are old enough to archive.",
      "expected_output": "Complete folder contents with modification timestamps"
    },
    {
      "id": 2,
      "action": "folder_archive_old",
      "parameters": {
        "folder_path": "$step1.folder_path",
        "items": "$step1.items",
        "age_threshold_days": 180,
        "dry_run": true
      },
      "dependencies": [1],
      "reasoning": "Analyze files and generate archive plan for items older than 6 months. Use dry_run=true to preview changes before execution.",
      "expected_output": "Archive plan showing what will be moved and where"
    },
    {
      "id": 3,
      "action": "folder_archive_old",
      "parameters": {
        "folder_path": "$step1.folder_path",
        "items": "$step1.items",
        "age_threshold_days": 180,
        "dry_run": false
      },
      "dependencies": [1, 2],
      "reasoning": "AFTER USER CONFIRMATION: Execute the archive operation to move old files to archive folder. This requires explicit user approval.",
      "expected_output": "Confirmation of successful archiving with summary"
    },
    {
      "id": 4,
      "action": "folder_list",
      "parameters": {
        "folder_path": null
      },
      "dependencies": [3],
      "reasoning": "Show the cleaned up folder structure after archiving to confirm the changes.",
      "expected_output": "Updated folder contents showing archived items are gone"
    }
  ],
  "complexity": "medium"
}
```

## Example Step 1 Output (folder_list)

```json
{
  "items": [
    {"name": "current_project.pdf", "type": "file", "size": 2048000, "modified": 1703123456, "extension": "pdf"},
    {"name": "meeting_notes_recent.txt", "type": "file", "size": 25600, "modified": 1702987654, "extension": "txt"},
    {"name": "old_report_2023.pdf", "type": "file", "size": 1536000, "modified": 1680000000, "extension": "pdf"},
    {"name": "archived_proposal.pdf", "type": "file", "size": 1024000, "modified": 1650000000, "extension": "pdf"},
    {"name": "budget_2024.xlsx", "type": "file", "size": 512000, "modified": 1702891256, "extension": "xlsx"}
  ],
  "total_count": 5,
  "folder_path": "/Users/user/Documents",
  "relative_path": "Documents"
}
```

## Example Step 2 Output (folder_archive_old - dry_run)

```json
{
  "archive_plan": {
    "files_to_archive": [
      {
        "name": "old_report_2023.pdf",
        "size": 1536000,
        "modified_days_ago": 240,
        "reason": "Not modified in 8 months"
      },
      {
        "name": "archived_proposal.pdf",
        "size": 1024000,
        "modified_days_ago": 365,
        "reason": "Not modified in over a year"
      }
    ],
    "total_files_to_archive": 2,
    "total_size_bytes": 2560000,
    "total_size_mb": 2.4,
    "archive_path": "/Users/user/Documents/Archive_2024_11_12",
    "age_threshold_days": 180
  },
  "summary": "Found 2 files older than 6 months that could be archived, freeing up 2.4 MB of space.",
  "dry_run": true,
  "needs_confirmation": true,
  "confirmation_message": "This will create an 'Archive_2024_11_12' folder and move 2 old files there. The files will still be accessible but organized separately. Proceed?"
}
```

## Example Step 3 Output (folder_archive_old - execution)

```json
{
  "success": true,
  "files_moved": [
    {
      "original_name": "old_report_2023.pdf",
      "new_path": "/Users/user/Documents/Archive_2024_11_12/old_report_2023.pdf",
      "size": 1536000
    },
    {
      "original_name": "archived_proposal.pdf",
      "new_path": "/Users/user/Documents/Archive_2024_11_12/archived_proposal.pdf",
      "size": 1024000
    }
  ],
  "archive_created": "/Users/user/Documents/Archive_2024_11_12",
  "total_moved": 2,
  "space_freed_mb": 2.4,
  "dry_run": false
}
```

## Key Reasoning Points

### Why This Plan Works:
1. **Two-Step Confirmation**: Preview with dry_run, then execute after approval
2. **Timestamped Archives**: Creates dated archive folders for organization
3. **Space Analysis**: Shows how much space will be freed
4. **Reversible Operation**: Files remain accessible in archive folder

### What NOT to Do:
❌ **Don't execute without preview**:
- Always show what will be archived first
- Users need to see exactly what files will be moved

❌ **Don't hardcode archive names**:
- Use timestamps for unique archive folders
- Avoid conflicts with existing archive folders

❌ **Don't delete files**:
- Archiving means moving, not deleting
- Keep files accessible for future reference

❌ **Don't skip the final listing**:
- Show the cleaned up result to confirm success
- Users want to see the organized outcome

## Alternative Age Thresholds

### Conservative (3 months)
```json
{
  "age_threshold_days": 90,
  "reasoning": "Conservative approach - only archive files not touched in 3 months"
}
```

### Aggressive (1 year)
```json
{
  "age_threshold_days": 365,
  "reasoning": "Aggressive cleanup - archive everything older than 1 year"
}
```

### Custom Date-Based
```json
{
  "archive_before_date": "2024-01-01",
  "reasoning": "Archive everything from before 2024"
}
```

## Similar Queries

All these should use the SAME pattern (list → plan → confirm → execute → show result):
- "move files older than 6 months to archive"
- "archive old documents"
- "cleanup files not used recently"
- "organize by archiving old stuff"
- "create archive for files from last year"
