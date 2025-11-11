## Example 3: Screenshot + Presentation + Email (5 steps)

**Note:** "The Night We Met" is the document name from the user's request - the system searches for whatever documents the user actually has.

### User Request
"Take a screenshot of the chorus from The Night We Met and create a slide deck with it, then email to user@example.com"

### Decomposition
```json
{
  "goal": "Find song, screenshot chorus, create Keynote with images, email presentation",
  "steps": [
    {
      "id": 1,
      "action": "search_documents",
      "parameters": {
        "query": "The Night We Met"
      },
      "dependencies": [],
      "reasoning": "Locate the document containing the song",
      "expected_output": "Document path"
    },
    {
      "id": 2,
      "action": "extract_section",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "section": "chorus"
      },
      "dependencies": [1],
      "reasoning": "Find which pages contain the chorus",
      "expected_output": "page_numbers: [2, 4]"
    },
    {
      "id": 3,
      "action": "take_screenshot",
      "parameters": {
        "doc_path": "$step1.doc_path",
        "pages": "$step2.page_numbers"
      },
      "dependencies": [2],
      "reasoning": "Capture screenshots of chorus pages",
      "expected_output": "screenshot_paths: ['/tmp/page2.png', '/tmp/page4.png']"
    },
    {
      "id": 4,
      "action": "create_keynote_with_images",
      "parameters": {
        "title": "The Night We Met - Chorus",
        "image_paths": "$step3.screenshot_paths"
      },
      "dependencies": [3],
      "reasoning": "Create Keynote presentation with screenshots as slides (NOT text slides!)",
      "expected_output": "keynote_path: [absolute_path_to_created_keynote_file]"
    },
    {
      "id": 5,
      "action": "compose_email",
      "parameters": {
        "subject": "Chorus from The Night We Met",
        "body": "Attached is the slide deck with the chorus screenshots.",
        "recipient": "user@example.com",
        "attachments": ["$step4.keynote_path"],
        "send": true
      },
      "dependencies": [4],
      "reasoning": "Email the presentation to recipient",
      "expected_output": "Email sent"
    }
  ],
  "complexity": "medium"
}
```

**CRITICAL: Tool Selection**
- ✅ Use `create_keynote_with_images` when user wants screenshots IN a presentation
- ❌ Don't use `create_keynote` (text-based) for screenshots
- ✅ `create_keynote_with_images` accepts `image_paths` and puts images on slides
- ✅ Step 4 uses `"image_paths": "$step3.screenshot_paths"` to pass screenshot list

---
