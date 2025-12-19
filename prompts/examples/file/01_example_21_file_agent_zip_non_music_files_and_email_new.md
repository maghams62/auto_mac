## Example 21: FILE AGENT - Zip Non-Music Files and Email (NEW!)

**⚠️ Important Note:** The folder name `"study_stuff"` in this example is extracted from the user's request. Always use the folder name specified by the user, not this example value.

### User Request
"Zip all the non-music files into a folder called study_stuff and email the zip to me."

### Decomposition
```json
{
  "goal": "Collect non-music files as study_stuff, zip them, and email the archive",
  "steps": [
    {
      "id": 1,
      "action": "organize_files",
      "parameters": {
        "category": "non-music study files",
        "target_folder": "study_stuff",
        "move_files": false
      },
      "dependencies": [],
      "reasoning": "LLM-driven categorization copies only the non-music files into the study_stuff folder",
      "expected_output": "Filtered study_stuff folder containing non-music files"
    },
    {
      "id": 2,
      "action": "create_zip_archive",
      "parameters": {
        "source_path": "study_stuff",
        "zip_name": "study_stuff.zip",
        "exclude_extensions": ["mp3", "wav", "flac", "m4a"]
      },
      "dependencies": [1],
      "reasoning": "Create a ZIP archive of the curated folder while guarding against music extensions",
      "expected_output": "ZIP archive path"
    },
    {
      "id": 3,
      "action": "compose_email",
      "parameters": {
        "recipient": null,
        "subject": "study_stuff.zip",
        "body": "Attached is the study_stuff archive (non-music files).",
        "attachments": ["$step2.zip_path"],
        "send": true
      },
      "dependencies": [2],
      "reasoning": "User said 'email the zip to me' - this means send immediately, not draft",
      "expected_output": "Email sent successfully"
    }
  ],
  "complexity": "medium"
}
```

---
