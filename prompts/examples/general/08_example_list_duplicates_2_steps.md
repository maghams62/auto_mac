# Example: List Duplicate Files (2 Steps)

## User Request
"what files are duplicated?" or "find duplicate files in my folder"

## Intent Analysis
- **Primary Goal**: Find and display duplicate files
- **Key Action**: Detect duplicates by content and show results in UI
- **Output Format**: User-facing message with actual file names
- **Complexity**: Simple (2 steps)

## Correct Plan

```json
{
  "goal": "Find and list duplicate files in the user's folder",
  "steps": [
    {
      "id": 1,
      "action": "folder_find_duplicates",
      "parameters": {
        "folder_path": null,
        "recursive": false
      },
      "dependencies": [],
      "reasoning": "Use folder_find_duplicates to identify files with identical content (SHA-256 hash). This returns duplicate groups with file names, sizes, and wasted space calculations.",
      "expected_output": "List of duplicate groups with metadata"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "Found {$step1.total_duplicate_groups} group(s) of duplicate files, wasting {$step1.wasted_space_mb} MB of disk space.",
        "details": "{for each group in $step1.duplicates}\n**Group {index}** ({group.count} copies, {group.size} bytes each):\n{for each file in group.files}\n- {file.name}\n{end for}\n{end for}\n\n💡 Tip: You can delete all but one file from each group to free up {$step1.wasted_space_mb} MB.",
        "status": "success"
      },
      "dependencies": [1],
      "reasoning": "Format the actual duplicate data from step 1 into a user-friendly message. CRITICAL: Must include actual file names from $step1.duplicates, not just a generic 'here are your duplicates' message. The details field should list each group with the actual file names.",
      "expected_output": "User sees the actual duplicate file names and groups"
    }
  ],
  "complexity": "simple"
}
```

## Example Step 1 Output (What reply_to_user Receives)

```json
{
  "duplicates": [
    {
      "hash": "eb580192...",
      "size": 202353,
      "count": 2,
      "wasted_bytes": 202353,
      "files": [
        {"name": "Let Her Go 2.pdf", "size": 202353},
        {"name": "Let Her Go.pdf", "size": 202353}
      ]
    },
    {
      "hash": "a78b4fc2...",
      "size": 199481,
      "count": 2,
      "wasted_bytes": 199481,
      "files": [
        {"name": "Perfect - Ed Sheeran 2.pdf", "size": 199481},
        {"name": "Perfect - Ed Sheeran.pdf", "size": 199481}
      ]
    }
  ],
  "total_duplicate_files": 4,
  "total_duplicate_groups": 2,
  "wasted_space_bytes": 401834,
  "wasted_space_mb": 0.38
}
```

## Example Step 2 Plan (Correct Formatting)

**❌ WRONG - Generic message (what NOT to do):**
```json
{
  "id": 2,
  "action": "reply_to_user",
  "parameters": {
    "message": "Here are the duplicate files found in your folder.",
    "details": "Summary of duplicate groups and their locations"
  }
}
```
This is BAD because the user sees a generic message without any actual file names!

**✅ RIGHT - Actual data formatted:**
```json
{
  "id": 2,
  "action": "reply_to_user",
  "parameters": {
    "message": "Found 2 group(s) of duplicate files, wasting 0.38 MB of disk space.",
    "details": "**Group 1** (2 copies, 202353 bytes each):\n- Let Her Go 2.pdf\n- Let Her Go.pdf\n\n**Group 2** (2 copies, 199481 bytes each):\n- Perfect - Ed Sheeran 2.pdf\n- Perfect - Ed Sheeran.pdf\n\n💡 Tip: You can delete all but one file from each group to free up 0.38 MB.",
    "status": "success"
  }
}
```
This is GOOD because the user sees the actual file names and can take action!

## Key Reasoning Points

### Critical Rule: Always Format Actual Data
**NEVER use generic messages like:**
- ❌ "Here are the duplicate files"
- ❌ "Summary of duplicate groups"
- ❌ "Duplicate files found"

**ALWAYS include actual data:**
- ✅ "Found 2 groups containing 4 files"
- ✅ "Let Her Go 2.pdf and Let Her Go.pdf are duplicates"
- ✅ "Wasting 0.38 MB of disk space"

### How to Format $step1 Data

When step 1 returns duplicate data, step 2 MUST:
1. **Extract counts** from `$step1.total_duplicate_groups` and `$step1.total_duplicate_files`
2. **Extract wasted space** from `$step1.wasted_space_mb`
3. **Loop through** `$step1.duplicates` array
4. **For each group**, list the actual file names from `group.files[].name`

### Template for reply_to_user with Duplicate Data

```json
{
  "message": "Found {$step1.total_duplicate_groups} group(s) of duplicate files, wasting {$step1.wasted_space_mb} MB.",
  "details": "[Format each group from $step1.duplicates showing actual file names]",
  "status": "success"
}
```

## Similar Queries

All these should use the SAME pattern (format actual data, don't use generic messages):
- "what files are duplicated?"
- "find duplicate files"
- "show me duplicate documents"
- "which files are taking up redundant space?"
- "list duplicates in my folder"

## What NOT to Do

❌ **Don't plan this:**
```json
{
  "id": 2,
  "action": "reply_to_user",
  "parameters": {
    "message": "Here are the results.",
    "details": "$step1"  // ❌ Wrong - don't pass raw JSON!
  }
}
```

❌ **Don't plan this:**
```json
{
  "id": 2,
  "action": "reply_to_user",
  "parameters": {
    "message": "Duplicate files found.",
    "details": "Check the results"  // ❌ Wrong - no actual data!
  }
}
```

✅ **DO plan this:**
```json
{
  "id": 2,
  "action": "reply_to_user",
  "parameters": {
    "message": "Found {$step1.total_duplicate_groups} groups of duplicates ({$step1.total_duplicate_files} files total)",
    "details": "[List each group with actual file names from $step1.duplicates]"
  }
}
```
