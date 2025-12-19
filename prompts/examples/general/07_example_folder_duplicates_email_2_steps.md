# Example: Send Duplicate Files Report via Email (2 Steps)

## User Request
"send all duplicated docs in my folder to my email"

## Intent Analysis
- **Primary Goal**: Find duplicate files and email the report
- **Key Actions**:
  1. Detect duplicates by content (not filename)
  2. Send results via email (user said "send" → auto-send)
- **Output Format**: Email with duplicate file list
- **Complexity**: Simple (2 steps, no semantic search needed)

## Correct Plan

```json
{
  "goal": "Find duplicate files in folder and email the report",
  "steps": [
    {
      "id": 1,
      "action": "folder_find_duplicates",
      "parameters": {
        "folder_path": null,
        "recursive": false
      },
      "dependencies": [],
      "reasoning": "User requested duplicated docs. Use folder_find_duplicates to identify files with identical content (SHA-256 hash). folder_path=null uses the sandbox root from config.yaml. Non-recursive searches only top-level files.",
      "expected_output": "List of duplicate groups with file names, sizes, and wasted space"
    },
    {
      "id": 2,
      "action": "compose_email",
      "parameters": {
        "to": "user@example.com",
        "subject": "Duplicate Files Report",
        "body": "Duplicate Files Report\n=====================\n\nFound {$step1.total_duplicate_groups} duplicate group(s) containing {$step1.total_duplicate_files} files.\nWasted disk space: {$step1.wasted_space_mb} MB\n\n{for each group in $step1.duplicates}\nGroup {index}:\n- File size: {group.size} bytes\n- Duplicate count: {group.count}\n- Wasted space: {group.wasted_bytes} bytes\n- Files:\n  {for each file in group.files}\n  * {file.name}\n  {end for}\n{end for}\n\nRecommendation: Keep one copy from each group and delete the others to free up {$step1.wasted_space_mb} MB.",
        "send": true
      },
      "dependencies": [1],
      "reasoning": "User said 'send to my email' - this is an action verb requiring send=true (not a draft). Format the duplicate detection results from step 1 into a readable email body with actual file names and sizes from $step1.duplicates. The 'to' address comes from config.yaml email settings.",
      "expected_output": "Email sent with duplicate files report"
    }
  ],
  "complexity": "simple"
}
```

## Key Reasoning Points

### Why This Plan Works:
1. **Correct Tool Selection**:
   - `folder_find_duplicates` identifies files by CONTENT (SHA-256 hash), not name
   - This is the RIGHT tool for "duplicate docs" - not `search_documents` (semantic search)

2. **Path Handling**:
   - `folder_path=null` uses the configured sandbox root (no hardcoding!)
   - All folder tools resolve paths automatically from config.yaml

3. **Intent Recognition**:
   - "send...to my email" → `send: true` (auto-send, not draft)
   - User wants the ACTION completed, not just prepared

4. **Tool Chaining**:
   - Step 1 produces duplicate list → Step 2 consumes it via `$step1.duplicates`
   - Dependencies: [1] ensures step 2 waits for step 1

### What NOT to Do:
❌ **Don't use `search_documents` for duplicates**:
   - `search_documents` = semantic search INSIDE documents (embeddings)
   - `folder_find_duplicates` = structural analysis (file hashes)

❌ **Don't hardcode paths**:
   - Bad: `"folder_path": "/Users/me/Documents/my_folder"`
   - Good: `"folder_path": null` (uses config.yaml)

❌ **Don't set `send: false` when user says "send"**:
   - User said "send to my email" → they want it SENT, not drafted!

❌ **Don't mark as impossible**:
   - The tool EXISTS (`folder_find_duplicates`) and can complete this task
   - Complexity is "simple", not "impossible"

## Similar Queries

- "Find duplicate files in my folder" → Same as above, but step 2 uses `reply_to_user` instead of email
- "Email me a list of duplicate documents" → Same workflow
- "Which files are duplicated in my documents?" → Use `folder_find_duplicates` + `reply_to_user`
- "Show me files that are taking up redundant space" → Same as above
