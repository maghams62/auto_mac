## Example: BLUESKY POSTS → SLIDESHOW → EMAIL (COMPLETE WORKFLOW)

**Reasoning (chain of thought):**
1. User wants recent Bluesky posts converted to a slideshow and emailed
2. Critical workflow: fetch → synthesize → format for slides → create keynote → email with attachment
3. Must use Writing Agent to transform posts into presentation-ready bullets
4. Must pass keynote file_path as email attachment
5. Must track dependencies so each step receives correct data

**User Request:** "convert the last 1 hour of tweets on bluesky into a slideshow and email it to me"

```json
{
  "goal": "Fetch recent Bluesky posts, create presentation slideshow, and email with slideshow attached",
  "steps": [
    {
      "id": 1,
      "action": "fetch_bluesky_posts",
      "parameters": {
        "query": "recent",
        "lookback_hours": 1,
        "max_items": 10
      },
      "dependencies": [],
      "reasoning": "Fetch recent posts from last hour to use as slideshow content",
      "expected_output": "posts array with text, authors, timestamps"
    },
    {
      "id": 2,
      "action": "synthesize_content",
      "parameters": {
        "source_contents": ["$step1.posts"],
        "topic": "Recent Bluesky Activity",
        "synthesis_style": "concise"
      },
      "dependencies": [1],
      "reasoning": "Synthesize posts into coherent narrative summary",
      "expected_output": "message with synthesized summary text"
    },
    {
      "id": 3,
      "action": "create_slide_deck_content",
      "parameters": {
        "content": "$step2.message",
        "title": "Bluesky Posts Summary",
        "num_slides": 5
      },
      "dependencies": [2],
      "reasoning": "Transform synthesis into presentation-ready slide content with concise bullets (5-7 words each)",
      "expected_output": "formatted_content with slide-ready bullets"
    },
    {
      "id": 4,
      "action": "create_keynote",
      "parameters": {
        "title": "Bluesky Posts Summary",
        "content": "$step3.formatted_content"
      },
      "dependencies": [3],
      "reasoning": "Generate Keynote presentation from formatted slide content",
      "expected_output": "file_path to generated keynote file"
    },
    {
      "id": 5,
      "action": "compose_email",
      "parameters": {
        "subject": "Bluesky Posts Slideshow - Last Hour",
        "body": "Attached is a slideshow summarizing recent Bluesky activity from the last hour.\n\nKey themes:\n$step2.message",
        "attachments": ["$step4.file_path"],
        "send": true
      },
      "dependencies": [4],
      "reasoning": "Email the keynote slideshow as attachment, include summary in body",
      "expected_output": "Email sent confirmation"
    },
    {
      "id": 6,
      "action": "reply_to_user",
      "parameters": {
        "message": "Created slideshow from {$step1.count} Bluesky posts and emailed to you with keynote attached.",
        "details": "$step2.message",
        "artifacts": ["$step4.file_path"],
        "status": "success"
      },
      "dependencies": [5],
      "reasoning": "Confirm completion and show summary in UI",
      "expected_output": "Final user confirmation"
    }
  ],
  "complexity": "complex"
}
```

**CRITICAL PATTERNS FOR SOCIAL MEDIA → SLIDESHOW → EMAIL:**

### ✅ Complete Workflow Chain
```
fetch_bluesky_posts
  → synthesize_content (narrative summary)
  → create_slide_deck_content (presentation bullets)
  → create_keynote (keynote file)
  → compose_email (WITH attachment reference)
  → reply_to_user
```

### ✅ Writing Agent is REQUIRED
- **Must use** `synthesize_content` to create narrative summary from posts
- **Must use** `create_slide_deck_content` to transform summary into slide bullets
- **Don't skip** these steps - raw post data makes poor slides

### ✅ Attachment Flow is REQUIRED
```json
{
  "action": "compose_email",
  "parameters": {
    "attachments": ["$step4.file_path"]  // ✅ Reference keynote from previous step
  },
  "dependencies": [4]  // ✅ Mark dependency
}
```

### ❌ ANTI-PATTERNS (WRONG!)

**❌ Skipping Writing Agent:**
```json
// WRONG: Posts → Keynote (skips synthesis and formatting)
{
  "steps": [
    {"action": "fetch_bluesky_posts", ...},
    {"action": "create_keynote", "parameters": {"content": "$step1.posts"}}  // ❌ Raw posts!
  ]
}
```

**❌ Skipping Slide Formatting:**
```json
// WRONG: Synthesis → Keynote (skips slide formatting)
{
  "steps": [
    {"action": "synthesize_content", ...},
    {"action": "create_keynote", "parameters": {"content": "$step1.message"}}  // ❌ Not slide-ready!
  ]
}
```

**❌ Missing Email Attachment:**
```json
// WRONG: Email sent without keynote attached
{
  "action": "compose_email",
  "parameters": {
    "subject": "...",
    "body": "...",
    // ❌ Missing: "attachments": ["$step4.file_path"]
  }
}
```

### Why Each Step Matters

1. **fetch_bluesky_posts** - Gets raw post data
2. **synthesize_content** - Creates coherent narrative (not just list of posts)
3. **create_slide_deck_content** - Transforms narrative into presentation bullets (5-7 words each, professional formatting)
4. **create_keynote** - Generates actual keynote file from bullets
5. **compose_email** - Sends email WITH `attachments: ["$step4.file_path"]`
6. **reply_to_user** - Confirms to user and shows summary in UI

---
