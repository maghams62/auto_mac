# CRITICAL EXAMPLE: How to Format Duplicate Detection Results

## Problem: Generic Messages vs. Actual Data

### ❌ WRONG - What NOT to do:
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
**Result in UI:** User sees "Here are the duplicate files" but NO ACTUAL FILE NAMES!

### ✅ RIGHT - What TO do:
```json
{
  "id": 2,
  "action": "reply_to_user",
  "parameters": {
    "message": "Found {$step1.total_duplicate_groups} group(s) of duplicate files, wasting {$step1.wasted_space_mb} MB of disk space.",
    "details": "$step1.duplicates"
  }
}
```
**Result in UI:** User sees "Found 2 group(s) of duplicate files, wasting 0.38 MB" with actual data!

## How Template Resolution Works

### Template Syntax for message field:
- Use `{$stepN.field}` for simple substitutions
- Example: `"Found {$step1.total_duplicate_groups} groups"` → `"Found 2 groups"`
- Example: `"Wasting {$step1.wasted_space_mb} MB"` → `"Wasting 0.38 MB"`

### Direct Reference Syntax for details field:
- Use `$stepN.field` to pass structured data to UI
- Example: `"details": "$step1.duplicates"` → Passes the full array
- UI will format the array into readable output

## Complete Working Example

### User Request:
"what files are duplicated?"

### Correct Plan:
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
      "reasoning": "Identify files with identical content using SHA-256 hash comparison.",
      "expected_output": "List of duplicate groups with file names, sizes, and wasted space metrics"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "Found {$step1.total_duplicate_groups} group(s) of duplicate files, wasting {$step1.wasted_space_mb} MB.",
        "details": "$step1.duplicates",
        "status": "success"
      },
      "dependencies": [1],
      "reasoning": "Use template syntax {$step1.field} for message, and direct reference $step1.duplicates for structured data in details.",
      "expected_output": "User sees count and metrics in message, full details in formatted output"
    }
  ],
  "complexity": "simple"
}
```

### What Step 1 Returns:
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
    }
  ],
  "total_duplicate_files": 4,
  "total_duplicate_groups": 2,
  "wasted_space_mb": 0.38
}
```

### What Step 2 Does:
1. **Resolves message template:**
   - Input: `"Found {$step1.total_duplicate_groups} group(s), wasting {$step1.wasted_space_mb} MB."`
   - Output: `"Found 2 group(s) of duplicate files, wasting 0.38 MB."`

2. **Passes details data:**
   - Input: `"details": "$step1.duplicates"`
   - Output: Passes the full `duplicates` array to UI for formatting

### Final UI Output:
```
Found 2 group(s) of duplicate files, wasting 0.38 MB.

Group 1 (2 copies, 202353 bytes each):
- Let Her Go 2.pdf
- Let Her Go.pdf

Group 2 (2 copies, 199481 bytes each):
- Perfect - Ed Sheeran 2.pdf
- Perfect - Ed Sheeran.pdf
```

## Key Rules

1. **For counts and metrics** → Use `{$stepN.field}` in message:
   - `{$step1.total_duplicate_groups}`
   - `{$step1.total_duplicate_files}`
   - `{$step1.wasted_space_mb}`

2. **For structured data** → Use `$stepN.field` in details:
   - `$step1.duplicates` (full array)
   - `$step1.some_object` (full object)

3. **NEVER use generic text** when data is available:
   - ❌ "Here are the results"
   - ❌ "Summary of findings"
   - ✅ "Found {$step1.count} items"

4. **Template syntax is simple** - NO loops, NO conditionals:
   - ✅ `{$step1.field}` - YES, this works
   - ❌ `{for each...}` - NO, too complex
   - ❌ `{if...}` - NO, too complex
   - ✅ `$step1.array` - YES, pass full arrays

## Similar Queries

All these should use the SAME pattern:
- "what files are duplicated?" → Use template syntax
- "find duplicate files" → Use template syntax
- "show me duplicate documents" → Use template syntax
- "list duplicates" → Use template syntax
