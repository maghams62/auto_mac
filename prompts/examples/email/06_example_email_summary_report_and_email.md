## Example: EMAIL AGENT - Email Summary Report with Email Delivery (CRITICAL!)

**This example covers the EXACT scenario that was failing**

### User Request
"Summarize my last 3 emails and convert it into a report and email that to me"

### Why This Was Failing
❌ **WRONG Workflow (what was happening before):**
```
Step 1: read_latest_emails(count=3)
Step 2: summarize_emails(emails_data=$step1)
Step 3: create_detailed_report(content=$step2.summary)
Step 4: compose_email(attachments=["$step3.report_content"])  ← FAILED! report_content is TEXT not a FILE PATH
```

The failure occurred because:
- `create_detailed_report` returns `report_content` which is TEXT (the actual report content as a string)
- `compose_email` expects file paths in the `attachments` parameter
- Passing TEXT content as a file path causes validation to fail

### Correct Decomposition
```json
{
  "goal": "Read emails, summarize, create report document, and email it",
  "steps": [
    {
      "id": 1,
      "action": "read_latest_emails",
      "parameters": {
        "count": 3,
        "mailbox": "INBOX"
      },
      "dependencies": [],
      "reasoning": "Retrieve the 3 most recent emails from inbox",
      "expected_output": "List of 3 emails with sender, subject, date, content"
    },
    {
      "id": 2,
      "action": "summarize_emails",
      "parameters": {
        "emails_data": "$step1",
        "focus": null
      },
      "dependencies": [1],
      "reasoning": "Create AI-powered summary of the emails",
      "expected_output": "Structured summary highlighting key information"
    },
    {
      "id": 3,
      "action": "create_detailed_report",
      "parameters": {
        "content": "$step2.summary",
        "title": "Email Summary Report",
        "report_style": "business"
      },
      "dependencies": [2],
      "reasoning": "Transform summary into a professional business report",
      "expected_output": "Formatted report content (TEXT) with sections"
    },
    {
      "id": 4,
      "action": "create_pages_doc",
      "parameters": {
        "title": "Email Summary Report",
        "content": "$step3.report_content"
      },
      "dependencies": [3],
      "reasoning": "CRITICAL: Save the report TEXT to a PAGES FILE so it can be attached to email",
      "expected_output": "Pages document saved to disk with pages_path"
    },
    {
      "id": 5,
      "action": "compose_email",
      "parameters": {
        "subject": "Email Summary Report",
        "body": "Please find attached your email summary report covering the last 3 emails.",
        "recipient": "me",
        "attachments": ["$step4.pages_path"],
        "send": true
      },
      "dependencies": [4],
      "reasoning": "Email the saved Pages document using pages_path (not report_content!)",
      "expected_output": "Email sent successfully"
    },
    {
      "id": 6,
      "action": "reply_to_user",
      "parameters": {
        "message": "Email summary report created and sent successfully",
        "details": "Summarized 3 emails, created a business report, and emailed it to you",
        "artifacts": ["$step4.pages_path"],
        "status": "success"
      },
      "dependencies": [5],
      "reasoning": "Confirm completion to user",
      "expected_output": "Success confirmation"
    }
  ],
  "complexity": "medium"
}
```

### Critical Learning Points

**⚠️ NEVER DO THIS:**
- ❌ `compose_email(attachments=["$step3.report_content"])` - report_content is TEXT
- ❌ `compose_email(attachments=["$step2.summary"])` - summary is TEXT
- ❌ `compose_email(attachments=["$step2.synthesized_content"])` - synthesized_content is TEXT
- ❌ Skipping the `create_pages_doc` step when user wants to email a report

**✅ ALWAYS DO THIS:**
- ✅ Save report/content to a file FIRST using `create_pages_doc`
- ✅ Use the returned `pages_path` from `create_pages_doc` as the attachment
- ✅ Workflow: create_detailed_report → **create_pages_doc** → compose_email

**Output Field Reference:**
- `create_detailed_report` returns: `report_content` (string), `sections` (array), `total_word_count` (number)
- `create_pages_doc` returns: `pages_path` (string - THIS is what you attach!)
- `create_keynote` returns: `keynote_path` (string - THIS is what you attach!)
- `synthesize_content` returns: `synthesized_content` (string - TEXT, not a path!)

**File-Creating Tools (these return paths you can attach):**
- `create_pages_doc` → returns `pages_path`
- `create_keynote` → returns `keynote_path`
- `create_keynote_with_images` → returns `keynote_path`
- `create_stock_report` → returns `pdf_path` or `report_path`

**Content-Creating Tools (these return TEXT, not files):**
- `create_detailed_report` → returns `report_content` (TEXT)
- `synthesize_content` → returns `synthesized_content` (TEXT)
- `summarize_emails` → returns `summary` (TEXT)
- `create_slide_deck_content` → returns `formatted_content` (TEXT)

### Handling Edge Cases

**What if no emails are found?**
```json
{
  "steps": [
    {
      "id": 1,
      "action": "read_latest_emails",
      "parameters": {"count": 3}
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "No emails found in your inbox",
        "status": "info"
      },
      "dependencies": [1],
      "reasoning": "If step1 returns 0 emails, inform user instead of creating empty report"
    }
  ]
}
```

**DO NOT create reports or send emails if no data exists!**

---

**Tags:** #email #report #attachment #planning-error #critical

