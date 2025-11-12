# Delivery Intent Detection Rules

**Purpose:** Ensure plans include email delivery steps when user explicitly requests sending/emailing results.

---

## Detection Criteria

When the user request contains ANY of these delivery verbs:
- **email** (e.g., "email the report to me")
- **send** (e.g., "send me the analysis")
- **mail** (e.g., "mail the document")
- **attach** (e.g., "attach the file and send")

→ **The plan MUST include a `compose_email` step.**

---

## Required Pattern

```
[work_step(s)] → compose_email → reply_to_user
```

### Example Flow

**User Request:** "search for tesla stock price and email it to me"

**Required Steps:**
1. `google_search` → Fetch stock price
2. `compose_email` → Email the result with `body: "$step1.summary"`
3. `reply_to_user` → Confirm email was sent

---

## Compose Email Parameters

When delivery intent is detected:

- **`send: true`** - Always set to send immediately
- **`body`** - Reference previous step outputs: `"$stepN.summary"`, `"$stepN.content"`, `"$stepN.message"`
- **`attachments`** - If artifacts created: `["$stepN.file_path"]`, `["$stepN.zip_path"]`
- **`recipient`** - Use configured default when user says "to me"

---

## Examples

### Example 1: Search + Email
```
User: "search email arsenal's last scoreline to me"

Plan:
{
  "steps": [
    {
      "id": 1,
      "action": "google_search",
      "parameters": {"query": "arsenal last match score"},
      "reasoning": "Search for Arsenal's latest game result"
    },
    {
      "id": 2,
      "action": "compose_email",
      "parameters": {
        "subject": "Arsenal Latest Score",
        "body": "$step1.summary",
        "send": true
      },
      "dependencies": [1],
      "reasoning": "User asked to email the results"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Searched for Arsenal's score and emailed you the results.",
        "status": "success"
      },
      "dependencies": [2],
      "reasoning": "Confirm delivery"
    }
  ]
}
```

### Example 2: Create Artifact + Send
```
User: "create a slideshow on nvidia stock and send it to me"

Plan:
{
  "steps": [
    {
      "id": 1,
      "action": "google_finance_get_stock_data",
      "parameters": {"symbol": "NVDA"},
      "reasoning": "Get NVIDIA stock data"
    },
    {
      "id": 2,
      "action": "create_keynote",
      "parameters": {
        "title": "NVIDIA Stock Analysis",
        "content": "$step1.summary"
      },
      "dependencies": [1],
      "reasoning": "Create presentation from stock data"
    },
    {
      "id": 3,
      "action": "compose_email",
      "parameters": {
        "subject": "NVIDIA Stock Presentation",
        "body": "Attached is the NVIDIA stock analysis slideshow.",
        "attachments": ["$step2.file_path"],
        "send": true
      },
      "dependencies": [2],
      "reasoning": "User asked to send the slideshow"
    },
    {
      "id": 4,
      "action": "reply_to_user",
      "parameters": {
        "message": "Created NVIDIA slideshow and emailed it to you.",
        "artifacts": ["$step2.file_path"],
        "status": "success"
      },
      "dependencies": [3],
      "reasoning": "Confirm completion"
    }
  ]
}
```

### Example 3: Find Files + Attach
```
User: "find duplicates and attach them to an email"

Plan:
{
  "steps": [
    {
      "id": 1,
      "action": "folder_find_duplicates",
      "parameters": {},
      "reasoning": "Find duplicate files in configured folder"
    },
    {
      "id": 2,
      "action": "compose_email",
      "parameters": {
        "subject": "Duplicate Files Report",
        "body": "Found $step1.total_duplicate_files duplicates. Details: $step1.duplicates",
        "send": true
      },
      "dependencies": [1],
      "reasoning": "User wants duplicates attached/emailed"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Found duplicates and emailed you the report.",
        "details": "$step1.duplicates",
        "status": "success"
      },
      "dependencies": [2],
      "reasoning": "Confirm email sent"
    }
  ]
}
```

---

## Anti-Patterns (DO NOT DO)

### ❌ Missing compose_email
```
User: "search for latest AI news and send it to me"

Bad Plan:
{
  "steps": [
    {
      "id": 1,
      "action": "google_search",
      "parameters": {"query": "latest AI news"}
    },
    {
      "id": 2,
      "action": "reply_to_user",  // ❌ No compose_email!
      "parameters": {"message": "$step1.summary"}
    }
  ]
}
```
**Why Wrong:** User said "send it to me" but plan has no email step.

### ❌ send: false
```
User: "email the report to me"

Bad Plan:
{
  "steps": [
    {"id": 1, "action": "create_report", ...},
    {
      "id": 2,
      "action": "compose_email",
      "parameters": {
        "body": "$step1.content",
        "send": false  // ❌ Should be true!
      }
    }
  ]
}
```
**Why Wrong:** User explicitly asked to email, must set `send: true`.

### ❌ Empty email body
```
User: "search tesla stock and email results"

Bad Plan:
{
  "steps": [
    {"id": 1, "action": "google_finance_get_stock_data", ...},
    {
      "id": 2,
      "action": "compose_email",
      "parameters": {
        "subject": "Tesla Stock",
        "body": "",  // ❌ Empty body!
        "send": true
      }
    }
  ]
}
```
**Why Wrong:** Email must reference step results: `"body": "$step1.summary"`

---

## Cross-Domain Combination Examples

### Example 4: Tweets + Email
```
User: "Summarize the last 5 tweets and email them to me"

Plan:
{
  "steps": [
    {
      "id": 1,
      "action": "summarize_bluesky_posts",
      "parameters": {
        "query": "last 5 tweets",
        "max_items": 5
      },
      "reasoning": "Get last 5 tweets from authenticated user"
    },
    {
      "id": 2,
      "action": "compose_email",
      "parameters": {
        "subject": "Bluesky Summary - Last 5 Tweets",
        "body": "$step1.summary",
        "send": true
      },
      "dependencies": [1],
      "reasoning": "User asked to email the tweets summary"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Summarized your last 5 tweets and emailed them to you.",
        "status": "success"
      },
      "dependencies": [2]
    }
  ]
}
```

### Example 5: Presentation + Email
```
User: "Create a presentation about NVIDIA and email it to me"

Plan:
{
  "steps": [
    {
      "id": 1,
      "action": "create_enriched_stock_presentation",
      "parameters": {"company": "NVIDIA"},
      "reasoning": "Create stock presentation for NVIDIA"
    },
    {
      "id": 2,
      "action": "compose_email",
      "parameters": {
        "subject": "NVIDIA Stock Analysis Report",
        "body": "Please find the NVIDIA stock analysis presentation attached.",
        "attachments": ["$step1.presentation_path"],
        "send": true
      },
      "dependencies": [1],
      "reasoning": "User asked to email the presentation - MUST attach file"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Created NVIDIA presentation and emailed it to you.",
        "artifacts": ["$step1.presentation_path"],
        "status": "success"
      },
      "dependencies": [2]
    }
  ]
}
```

**CRITICAL:** For presentations/reports, MUST use `attachments: ["$step1.presentation_path"]` and verify file exists before attaching.

### Example 6: Reminders + Email
```
User: "Remind me to call John tomorrow and email me confirmation"

Plan:
{
  "steps": [
    {
      "id": 1,
      "action": "create_reminder",
      "parameters": {
        "title": "Call John",
        "due_time": "tomorrow"
      },
      "reasoning": "Create reminder as requested"
    },
    {
      "id": 2,
      "action": "compose_email",
      "parameters": {
        "subject": "Reminder Created",
        "body": "Reminder set: Call John (due: tomorrow)",
        "send": true
      },
      "dependencies": [1],
      "reasoning": "User asked for email confirmation of reminder"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Reminder created and confirmation emailed to you.",
        "status": "success"
      },
      "dependencies": [2]
    }
  ]
}
```

### Example 7: Notes + Email
```
User: "Create a note about the meeting and email it to me"

Plan:
{
  "steps": [
    {
      "id": 1,
      "action": "create_note",
      "parameters": {
        "title": "Meeting Notes",
        "body": "[meeting content from context]"
      },
      "reasoning": "Create note as requested"
    },
    {
      "id": 2,
      "action": "compose_email",
      "parameters": {
        "subject": "Meeting Notes",
        "body": "$step1.note_content",
        "send": true
      },
      "dependencies": [1],
      "reasoning": "User asked to email the note content"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Created meeting note and emailed it to you.",
        "status": "success"
      },
      "dependencies": [2]
    }
  ]
}
```

---

## Summary

**If user says:** email, send, mail, attach
**Then plan must:** Include `compose_email` with `send: true` and proper content references

**Always follow:** work → compose_email → reply_to_user pattern

**Cross-Domain Patterns:**
- **Tweets + Email**: `summarize_bluesky_posts` → `compose_email(body="$step1.summary")`
- **Presentation + Email**: `create_enriched_stock_presentation` → `compose_email(attachments=["$step1.presentation_path"])`
- **Reminders + Email**: `create_reminder` → `compose_email(body="Reminder created: ...")`
- **Notes + Email**: `create_note` → `compose_email(body="$step1.note_content")`

**CRITICAL:** For attachments, ALWAYS verify file exists before attaching. Use absolute paths.
