## Example 32: Error Handling and Recovery

### User Request
"Download the quarterly report from the company website and email it to the team"

### Decomposition
```json
{
  "goal": "Download a file from a website and email it, with proper error handling",
  "steps": [
    {
      "id": 1,
      "action": "google_search",
      "parameters": {
        "query": "company quarterly report download"
      },
      "dependencies": [],
      "reasoning": "Find the official company website and locate the quarterly report download link",
      "expected_output": "Search results pointing to the company website and report location"
    },
    {
      "id": 2,
      "action": "navigate_to_url",
      "parameters": {
        "url": "$step1.results[0].url"
      },
      "dependencies": [1],
      "reasoning": "Navigate to the company website to access the download section",
      "expected_output": "Browser navigation to the target URL"
    },
    {
      "id": 3,
      "action": "extract_page_content",
      "parameters": {
        "selector": "a[href*='quarterly'][href*='report'][href*='.pdf']"
      },
      "dependencies": [2],
      "reasoning": "Extract download links for quarterly reports in PDF format",
      "expected_output": "URL of the quarterly report PDF file"
    },
    {
      "id": 4,
      "action": "download_file",
      "parameters": {
        "url": "$step3.download_url",
        "filename": "quarterly_report.pdf"
      },
      "dependencies": [3],
      "reasoning": "Download the quarterly report PDF to local storage",
      "expected_output": "Local file path of downloaded quarterly report"
    },
    {
      "id": 5,
      "action": "compose_email",
      "parameters": {
        "subject": "Quarterly Report",
        "body": "Please find attached the latest quarterly report.",
        "recipient": "team@company.com",
        "attachments": ["$step4.file_path"]
      },
      "dependencies": [4],
      "reasoning": "Compose email with the downloaded report attached",
      "expected_output": "Email draft ready for sending"
    },
    {
      "id": 6,
      "action": "send_email",
      "parameters": {
        "email_draft": "$step5.email_draft"
      },
      "dependencies": [5],
      "reasoning": "Send the email with the quarterly report attachment",
      "expected_output": "Email sent successfully"
    },
    {
      "id": 7,
      "action": "reply_to_user",
      "parameters": {
        "message": "Quarterly report sent",
        "details": "Successfully downloaded the quarterly report and emailed it to the team.",
        "artifacts": ["$step4.file_path"],
        "status": "success"
      },
      "dependencies": [6],
      "reasoning": "Confirm successful completion of the download and email task",
      "expected_output": "User confirmation of task completion"
    }
  ],
  "complexity": "complex",
  "task_type": "web_scraping"
}
```

**Error Handling Pattern:**

If any step fails:
1. **Navigation fails**: Try alternative URLs from search results
2. **Download fails**: Check if file exists, try different format, or notify user
3. **Email fails**: Verify recipient address, check attachment size limits
4. **Always provide clear error messages** and recovery suggestions

**Key Principle:** Plan for common failure modes and include recovery strategies in your decomposition.
