# Example 6: Duplicate File Detection and Cleanup Recommendations

## User Request
"find duplicates and help me clean them up" or "show me duplicate files" or "what's wasting space with duplicates"

## Intent Analysis
- **Primary Goal**: Identify duplicate files and provide cleanup guidance
- **Key Actions**: Detect content duplicates, analyze space waste, suggest actions
- **Output Format**: Duplicate groups with recommendations, optional cleanup execution
- **Complexity**: Medium (3-4 steps, analysis + optional write operations)

## Correct Plan

```json
{
  "goal": "Find duplicate files, analyze space waste, and provide cleanup recommendations",
  "steps": [
    {
      "id": 1,
      "action": "folder_find_duplicates",
      "parameters": {
        "folder_path": null,
        "recursive": false
      },
      "dependencies": [],
      "reasoning": "Scan folder for duplicate files by content (SHA-256 hash) to identify files with identical content that could be consolidated.",
      "expected_output": "List of duplicate groups with file details and space analysis"
    },
    {
      "id": 2,
      "action": "folder_summarize",
      "parameters": {
        "folder_path": null,
        "duplicate_analysis": "$step1",
        "focus": "duplicate_cleanup"
      },
      "dependencies": [1],
      "reasoning": "Generate natural language summary of duplicate findings with specific recommendations for which files to keep/delete and space that could be freed.",
      "expected_output": "Analysis and recommendations for duplicate cleanup"
    },
    {
      "id": 3,
      "action": "folder_archive_old",
      "parameters": {
        "folder_path": null,
        "duplicate_groups": "$step1.duplicates",
        "action": "archive_duplicates",
        "dry_run": true
      },
      "dependencies": [1, 2],
      "reasoning": "OPTIONAL: If user wants automated cleanup, generate plan to archive duplicate files (keeping one copy of each). Show preview before execution.",
      "expected_output": "Archive plan for duplicate cleanup"
    }
  ],
  "complexity": "medium"
}
```

## Example Step 1 Output (folder_find_duplicates)

```json
{
  "duplicates": [
    {
      "hash": "eb5801928f4b4c3a9d1e5f2b8c7a9e0f",
      "size": 202353,
      "count": 3,
      "wasted_bytes": 404706,
      "files": [
        {"name": "Let Her Go.pdf", "path": "/Users/user/Documents/Let Her Go.pdf", "size": 202353},
        {"name": "Let Her Go 2.pdf", "path": "/Users/user/Documents/Let Her Go 2.pdf", "size": 202353},
        {"name": "Let Her Go (Copy).pdf", "path": "/Users/user/Documents/Let Her Go (Copy).pdf", "size": 202353}
      ]
    },
    {
      "hash": "a78b4fc2d9e1f5a8b2c9d0e8f3a7b6c5",
      "size": 199481,
      "count": 2,
      "wasted_bytes": 199481,
      "files": [
        {"name": "Perfect - Ed Sheeran.pdf", "path": "/Users/user/Documents/Perfect - Ed Sheeran.pdf", "size": 199481},
        {"name": "Perfect Song.pdf", "path": "/Users/user/Documents/Perfect Song.pdf", "size": 199481}
      ]
    }
  ],
  "total_duplicate_files": 5,
  "total_duplicate_groups": 2,
  "wasted_space_bytes": 604187,
  "wasted_space_mb": 0.57,
  "folder_path": "/Users/user/Documents"
}
```

## Example Step 2 Output (folder_summarize - duplicate focus)

```json
{
  "summary": "Found 2 groups of duplicate files containing 5 total files, wasting 0.57 MB of disk space.",
  "duplicate_analysis": {
    "space_waste": "You could free up 0.57 MB by removing duplicate copies",
    "groups_found": 2,
    "recommendations": [
      "Keep the file with the clearest name and archive/delete the others",
      "Consider keeping the most recently modified version of each duplicate",
      "'Let Her Go.pdf' appears 3 times - keep one and remove the '(Copy)' versions",
      "'Perfect - Ed Sheeran.pdf' has a duplicate with different name - consolidate naming"
    ]
  },
  "cleanup_suggestions": [
    {
      "group": "Let Her Go",
      "action": "Keep 'Let Her Go.pdf', archive 'Let Her Go 2.pdf' and 'Let Her Go (Copy).pdf'",
      "space_saved": "0.39 MB"
    },
    {
      "group": "Perfect Song",
      "action": "Keep 'Perfect - Ed Sheeran.pdf', archive 'Perfect Song.pdf'",
      "space_saved": "0.19 MB"
    }
  ],
  "automated_cleanup_available": true
}
```

## Example Step 3 Output (folder_archive_old - duplicate cleanup)

```json
{
  "archive_plan": {
    "action_type": "duplicate_cleanup",
    "files_to_archive": [
      {
        "name": "Let Her Go 2.pdf",
        "reason": "Duplicate of 'Let Her Go.pdf' - keeping original"
      },
      {
        "name": "Let Her Go (Copy).pdf",
        "reason": "Duplicate of 'Let Her Go.pdf' - keeping original"
      },
      {
        "name": "Perfect Song.pdf",
        "reason": "Duplicate of 'Perfect - Ed Sheeran.pdf' - keeping better named version"
      }
    ],
    "keep_files": [
      "Let Her Go.pdf",
      "Perfect - Ed Sheeran.pdf"
    ],
    "archive_path": "/Users/user/Documents/Duplicates_Archive_2024_11_12",
    "space_to_free": "0.57 MB"
  },
  "dry_run": true,
  "needs_confirmation": true,
  "confirmation_message": "This will keep the best version of each duplicate and archive 3 duplicate files to 'Duplicates_Archive_2024_11_12', freeing 0.57 MB. Proceed?"
}
```

## Key Reasoning Points

### Why This Plan Works:
1. **Content-Based Detection**: Uses SHA-256 hashing for true duplicate detection
2. **Space Analysis**: Quantifies wasted space and potential savings
3. **Smart Recommendations**: Suggests which files to keep based on naming and dates
4. **Flexible Cleanup**: Offers manual guidance or automated archiving

### What NOT to Do:
❌ **Don't just list duplicates without analysis**:
- Users need guidance on which copies to keep
- Provide space savings and cleanup recommendations

❌ **Don't automatically delete duplicates**:
- Always keep at least one copy
- Let users decide which version to preserve

❌ **Don't confuse similar names with actual duplicates**:
- Use content hashing, not filename matching
- True duplicates have identical content regardless of name

❌ **Don't skip the space analysis**:
- Quantify the benefit of cleanup
- Help users understand the value of organizing

## Alternative Duplicate Handling Strategies

### Conservative (Manual Review)
```json
{
  "strategy": "manual_review",
  "output": "List all duplicates with recommendations but require manual deletion"
}
```

### Automated (Smart Selection)
```json
{
  "strategy": "smart_cleanup",
  "rules": ["prefer_original_names", "prefer_newer_files", "avoid_copy_suffixes"]
}
```

### Archive-Based (Preserve Everything)
```json
{
  "strategy": "archive_duplicates",
  "keep_original_location": true,
  "create_separate_archive": true
}
```

## Similar Queries

All these should use the SAME pattern (detect → analyze → recommend → optional cleanup):
- "find duplicate files"
- "show me what's duplicated"
- "clean up duplicate documents"
- "which files are wasting space"
- "help me remove duplicates"
