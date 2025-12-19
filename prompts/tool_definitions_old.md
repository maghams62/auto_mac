# Tool Definitions

Complete specification of available tools for the automation agent.

**Generated from tool catalog with 115 tools.**

**CRITICAL INSTRUCTIONS FOR TOOL USAGE:**
1. **Tool Validation**: Before using ANY tool, verify it exists in this list
2. **Parameter Requirements**: All REQUIRED parameters must be provided
3. **Type Safety**: Match parameter types exactly (string, int, list, etc.)
4. **Error Handling**: Check return values for "error": true field
5. **Early Rejection**: If a needed tool doesn't exist, reject the task immediately with complexity="impossible"

---

## BROWSER Agent (4 tools)

### close_browser
**Purpose:** Close browser and clean up resources. LEVEL 4 tool - use at the end of web browsing sessions.

**Complete Call Example:**
```json
{
  "action": "close_browser",
  "parameters": {
  }
}
```

**Strengths:**
- Frees up system resources
- Closes browser windows
- Clean up temporary files

**Limitations:**
- Cannot reuse browser after closing - must reinitialize
- All open pages will be closed

---

### extract_page_content
**Purpose:** Extract clean text content from webpages using langextract. LEVEL 2 tool - use for reading and analyzing webpage content. Perfect for sending to LLM for disambiguation.

**Complete Call Example:**
```json
{
  "action": "extract_page_content",
  "parameters": {
  }
}
```

**Parameters:**
- `url` (optional)

**Strengths:**
- INTELLIGENT content extraction using langextract
- Removes navigation, ads, headers, footers automatically
- Extracts clean, readable text perfect for LLM processing
- Can navigate to URL first or extract from current page
- Returns word count and metadata

**Limitations:**
- May miss content from JavaScript-heavy sites
- Extraction quality depends on page structure
- Text-only (no images or formatting)

---

### navigate_to_url
**Purpose:** Navigate to a specific URL. LEVEL 2 tool - use after google_search to visit specific pages.

**Complete Call Example:**
```json
{
  "action": "navigate_to_url",
  "parameters": {
    "url": "https://example.com"
  }
}
```

**Parameters:**
- `url` (required)
- `wait_until` (optional)

**Strengths:**
- Navigate to specific URLs directly
- Waits for page load completion
- Returns page title and status
- Good for visiting known URLs from search results

**Limitations:**
- Requires valid URL with protocol (http/https)
- May timeout on slow-loading pages
- Doesn't extract content automatically

---

### take_web_screenshot
**Purpose:** Capture webpage screenshots. LEVEL 3 tool - use when you need visual proof or reference of webpage content.

**Complete Call Example:**
```json
{
  "action": "take_web_screenshot",
  "parameters": {
  }
}
```

**Parameters:**
- `url` (optional)
- `full_page` (optional)

**Strengths:**
- Capture visual snapshots of webpages
- Supports full-page or viewport-only capture
- Preserves visual appearance and layout
- Can navigate to URL first or capture current page

**Limitations:**
- Creates image files (larger storage)
- No text extraction from screenshots
- May timeout on very long pages

---

## CRITIC Agent (4 tools)

### check_quality
**Purpose:** check_quality(output: Dict[str, Any], quality_criteria: Dict[str, Any]) -> Dict[str, Any] - Check if output meets quality criteria.

CRITIC AGENT - LEVEL 4: Quality Assurance
Use this to validate outputs meet specific quality standards.

Args:
    output: The output to check
    quality_criteria: Dictionary of quality criteria to validate
                     e.g., {"min_word_count": 100, "has_attachment": True}

Returns:
    Dictionary with passed (bool), failed_criteria (list), score (float)

**Complete Call Example:**
```json
{
  "action": "check_quality",
  "parameters": {
    "output": "example_value",
    "quality_criteria": "example_value"
  }
}
```

**Parameters:**
- `output` (required)
- `quality_criteria` (required)

**Strengths:**
- Supports the output to check
- Supports dictionary of quality criteria to validate
- Supports 100, "has_attachment": true}
- Returns structured data

**Limitations:**
- See tool documentation for specific constraints

---

### reflect_on_failure
**Purpose:** reflect_on_failure(step_description: str, error_message: str, context: Dict[str, Any]) -> Dict[str, Any] - Analyze why a step failed and generate corrective actions.

CRITIC AGENT - LEVEL 2: Failure Reflection
Use this when a step fails to understand root cause and fixes.

Args:
    step_description: Description of what the step was trying to do
    error_message: The error that occurred
    context: Context about the execution (previous steps, inputs, etc.)

Returns:
    Dictionary with root_cause, corrective_actions, retry_recommended

**Complete Call Example:**
```json
{
  "action": "reflect_on_failure",
  "parameters": {
    "step_description": "example_value",
    "error_message": "example_value",
    "context": "example_value"
  }
}
```

**Parameters:**
- `step_description` (required)
- `error_message` (required)
- `context` (required)

**Strengths:**
- a step fails to understand root cause and fixes.
- Supports description of what the step was trying to do
- Supports the error that occurred
- Supports context about the execution (previous steps, inputs, etc.)
- Returns structured data

**Limitations:**
- See tool documentation for specific constraints

---

### validate_plan
**Purpose:** validate_plan(plan: List[Dict[str, Any]], goal: str, available_tools: List[str]) -> Dict[str, Any] - Validate a plan before execution.

CRITIC AGENT - LEVEL 3: Plan Validation
Use this to check if a plan is sound before executing.

Args:
    plan: List of plan steps to validate
    goal: The goal the plan is trying to achieve
    available_tools: List of available tool names

Returns:
    Dictionary with valid (bool), errors (list), warnings (list)

**Complete Call Example:**
```json
{
  "action": "validate_plan",
  "parameters": {
    "plan": "example_value",
    "goal": "example_value",
    "available_tools": "example_value"
  }
}
```

**Parameters:**
- `plan` (required)
- `goal` (required)
- `available_tools` (required)

**Strengths:**
- Supports list of plan steps to validate
- Supports the goal the plan is trying to achieve
- Supports list of available tool names
- Returns structured data

**Limitations:**
- See tool documentation for specific constraints

---

### verify_output
**Purpose:** verify_output(step_description: str, user_intent: str, actual_output: Dict[str, Any], constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any] - Verify that a step's output matches user intent and constraints.

CRITIC AGENT - LEVEL 1: Output Verification
Use this to validate that outputs meet requirements.

Args:
    step_description: Description of what the step was supposed to do
    user_intent: Original user request/intent
    actual_output: The actual output produced
    constraints: Optional constraints to check (e.g., {"page_count": 1})

Returns:
    Dictionary with valid (bool), confidence (float), issues (list), suggestions (list)

**Complete Call Example:**
```json
{
  "action": "verify_output",
  "parameters": {
    "step_description": "example_value",
    "user_intent": "example_value",
    "actual_output": "example_value"
  }
}
```

**Parameters:**
- `step_description` (required)
- `user_intent` (required)
- `actual_output` (required)
- `constraints` (optional)

**Strengths:**
- Supports description of what the step was supposed to do
- Supports original user request/intent
- Supports the actual output produced
- Supports optional constraints to check (e.g., {"page_count": 1})
- Returns structured data

**Limitations:**
- See tool documentation for specific constraints

---

## DISCORD Agent (7 tools)

### discord_capture_recent_messages
**Purpose:** discord_capture_recent_messages(channel_name: 'str', server_name: 'Optional[str]' = None, output_path: 'Optional[str]' = None) -> 'Dict[str, Any]' - Take a screenshot of the active Discord channel for auditing or sharing.

Args:
    channel_name: Channel to capture
    server_name: Optional server/guild
    output_path: Optional custom screenshot path

**Complete Call Example:**
```json
{
  "action": "discord_capture_recent_messages",
  "parameters": {
    "channel_name": "example_value"
  }
}
```

**Parameters:**
- `channel_name` (required)
- `server_name` (optional)
- `output_path` (optional)

**Strengths:**
- Supports channel to capture
- Supports optional server/guild
- Supports optional custom screenshot path

**Limitations:**
- See tool documentation for specific constraints

---

### discord_detect_unread_channels
**Purpose:** discord_detect_unread_channels(server_name: 'Optional[str]' = None) -> 'Dict[str, Any]' - Inspect the server/channel list for unread indicators (bold text, dot badges).

Args:
    server_name: Optional substring filter for the server/guild

**Complete Call Example:**
```json
{
  "action": "discord_detect_unread_channels",
  "parameters": {
  }
}
```

**Parameters:**
- `server_name` (optional)

**Strengths:**
- Supports optional substring filter for the server/guild

**Limitations:**
- See tool documentation for specific constraints

---

### discord_read_channel_messages
**Purpose:** discord_read_channel_messages(channel_name: 'str', limit: 'int' = 10, server_name: 'Optional[str]' = None) -> 'Dict[str, Any]' - Read recent messages from a Discord channel using macOS accessibility text scraping.

Args:
    channel_name: Channel to read from
    limit: Maximum number of messages to return (most recent)
    server_name: Optional server/guild

**Complete Call Example:**
```json
{
  "action": "discord_read_channel_messages",
  "parameters": {
    "channel_name": "example_value"
  }
}
```

**Parameters:**
- `channel_name` (required)
- `limit` (optional)
- `server_name` (optional)

**Strengths:**
- Supports channel to read from
- Supports maximum number of messages to return (most recent)
- Supports optional server/guild

**Limitations:**
- macOS only
- May require API keys or credentials

---

### discord_send_message
**Purpose:** discord_send_message(channel_name: 'str', message: 'str', server_name: 'Optional[str]' = None, confirm_delivery: 'bool' = True) -> 'Dict[str, Any]' - Post a message to a Discord channel via the desktop app.

Args:
    channel_name: Channel to post to
    message: Text body (newlines supported)
    server_name: Optional server/guild
    confirm_delivery: When true, re-read the channel afterward to confirm the text appears

**Complete Call Example:**
```json
{
  "action": "discord_send_message",
  "parameters": {
    "channel_name": "example_value",
    "message": "example_value"
  }
}
```

**Parameters:**
- `channel_name` (required)
- `message` (required)
- `server_name` (optional)
- `confirm_delivery` (optional)

**Strengths:**
- Supports channel to post to
- Supports text body (newlines supported)
- Supports optional server/guild
- Supports when true, re-read the channel afterward to confirm the text appears

**Limitations:**
- See tool documentation for specific constraints

---

### ensure_discord_session
**Purpose:** ensure_discord_session() -> 'Dict[str, Any]' - Bring Discord to the foreground and log in if needed (uses DISCORD_EMAIL/DISCORD_PASSWORD from .env).

Use this before any other Discord actions if you're unsure whether the desktop client
is authenticated. Returns details about whether a login was performed or skipped.

**Complete Call Example:**
```json
{
  "action": "ensure_discord_session",
  "parameters": {
  }
}
```

**Strengths:**
- Provides functionality for the requested operation

**Limitations:**
- See tool documentation for specific constraints

---

### navigate_discord_channel
**Purpose:** navigate_discord_channel(channel_name: 'str', server_name: 'Optional[str]' = None) -> 'Dict[str, Any]' - Navigate to a Discord channel using the Cmd+K quick switcher.

Args:
    channel_name: Channel to open (e.g., "general")
    server_name: Optional server/guild name to disambiguate

**Complete Call Example:**
```json
{
  "action": "navigate_discord_channel",
  "parameters": {
    "channel_name": "example_value"
  }
}
```

**Parameters:**
- `channel_name` (required)
- `server_name` (optional)

**Strengths:**
- Supports channel to open (e.g., "general")
- Supports optional server/guild name to disambiguate

**Limitations:**
- See tool documentation for specific constraints

---

### verify_discord_channel
**Purpose:** verify_discord_channel(channel_name: 'str', server_name: 'Optional[str]' = None, send_test_message: 'bool' = False, test_message: 'Optional[str]' = None) -> 'Dict[str, Any]' - Verify the agent can log in, locate, and interact with a channel.

Args:
    channel_name: Target channel
    server_name: Optional server/guild
    send_test_message: When true, posts a probe message (may remain in channel history)
    test_message: Optional override for the probe text

**Complete Call Example:**
```json
{
  "action": "verify_discord_channel",
  "parameters": {
    "channel_name": "example_value"
  }
}
```

**Parameters:**
- `channel_name` (required)
- `server_name` (optional)
- `send_test_message` (optional)
- `test_message` (optional)

**Strengths:**
- Supports target channel
- Supports optional server/guild
- Supports when true, posts a probe message (may remain in channel history)
- Supports optional override for the probe text

**Limitations:**
- See tool documentation for specific constraints

---

## EMAIL Agent (6 tools)

### compose_email
**Purpose:** Compose and send emails via Mail.app

**Complete Call Example:**
```json
{
  "action": "compose_email",
  "parameters": {
    "subject": "example_value",
    "body": "example_value"
  }
}
```

**Parameters:**
- `subject` (required)
- `body` (required)
- `recipient` (optional)
- `attachments` (optional)
- `send` (optional)

**Strengths:**
- Direct Mail.app integration
- Supports attachments
- Can send immediately or create draft

**Limitations:**
- macOS Mail.app only
- Requires Mail.app to be configured
- May trigger user prompts

---

### read_emails_by_sender
**Purpose:** read_emails_by_sender(sender: str, count: int = 10) -> Dict[str, Any] - Read emails from a specific sender.

EMAIL AGENT - LEVEL 2: Email Reading
Use this to find emails from a particular person or email address. Often used before summarize_emails().

Typical use cases:
- "summarize the last 3 emails sent by John Doe" → read_emails_by_sender(sender="John Doe", count=3) → summarize_emails()
- "can you summarize emails from [person]" → read_emails_by_sender(sender="[person]", count=10) → summarize_emails()

Args:
    sender: Email address or name of sender (can be partial match, e.g., "John Doe" or "john@example.com")
    count: Maximum number of emails to retrieve (default: 10, max: 50)

Returns:
    Dictionary with:
    - emails: List of email dictionaries from the specified sender
    - count: Number of emails retrieved
    - sender: Sender identifier used
    - account: Account email used

Note: The result can be passed directly to summarize_emails() for summarization.

Security:
    Only reads from the email account specified in config.yaml (email.account_email)

**Complete Call Example:**
```json
{
  "action": "read_emails_by_sender",
  "parameters": {
    "sender": "example_value"
  }
}
```

**Parameters:**
- `sender` (required)
- `count` (optional)

**Strengths:**
- Supports email address or name of sender (can be partial match, e.g., "john doe" or "john@example.com")
- Supports maximum number of emails to retrieve (default: 10, max: 50)
- Returns structured data

**Limitations:**
- Security:
    Only reads from the email account specified in config.yaml (email.account_email)

---

### read_emails_by_time
**Purpose:** read_emails_by_time(hours: Optional[int] = None, minutes: Optional[int] = None, mailbox: str = 'INBOX') -> Dict[str, Any] - Read emails within a specific time range.

EMAIL AGENT - LEVEL 2: Email Reading
Use this to retrieve emails from the last N hours or minutes.

Args:
    hours: Number of hours to look back (e.g., 1 for last hour, 24 for last day)
    minutes: Number of minutes to look back (alternative to hours)
    mailbox: Mailbox name (default: INBOX)

Returns:
    Dictionary with list of emails within the time range

Security:
    Only reads from the email account specified in config.yaml (email.account_email)

**Complete Call Example:**
```json
{
  "action": "read_emails_by_time",
  "parameters": {
  }
}
```

**Parameters:**
- `hours` (optional)
- `minutes` (optional)
- `mailbox` (optional)

**Strengths:**
- Supports number of hours to look back (e.g., 1 for last hour, 24 for last day)
- Supports number of minutes to look back (alternative to hours)
- Supports mailbox name (default: inbox)
- Returns structured data

**Limitations:**
- Args:
    hours: Number of hours to look back (e.g., 1 for last hour, 24 for last day)
    minutes: Number of minutes to look back (alternative to hours)
    mailbox: Mailbox name (default: INBOX)

Returns:
    Dictionary with list of emails within the time range

Security:
    Only reads from the email account specified in config.yaml (email.account_email)

---

### read_latest_emails
**Purpose:** read_latest_emails(count: int = 10, mailbox: str = 'INBOX') -> Dict[str, Any] - Read the latest emails from Mail.app.

EMAIL AGENT - LEVEL 2: Email Reading
Use this to retrieve recent emails. Often used before summarize_emails().

Typical use cases:
- "summarize my last 3 emails" → read_latest_emails(count=3) → summarize_emails()
- "what are my recent emails" → read_latest_emails(count=10)

Args:
    count: Number of emails to retrieve (default: 10, max: 50)
    mailbox: Mailbox name (default: INBOX)

Returns:
    Dictionary with:
    - emails: List of email dictionaries (sender, subject, date, content, content_preview)
    - count: Number of emails retrieved
    - mailbox: Mailbox name used
    - account: Account email used

Note: The result can be passed directly to summarize_emails() for summarization.

Security:
    Only reads from the email account specified in config.yaml (email.account_email)

**Complete Call Example:**
```json
{
  "action": "read_latest_emails",
  "parameters": {
  }
}
```

**Parameters:**
- `count` (optional)
- `mailbox` (optional)

**Strengths:**
- Supports number of emails to retrieve (default: 10, max: 50)
- Supports mailbox name (default: inbox)
- Returns structured data

**Limitations:**
- Security:
    Only reads from the email account specified in config.yaml (email.account_email)

---

### reply_to_email
**Purpose:** reply_to_email(original_sender: str, original_subject: str, reply_body: str, send: bool = False) -> Dict[str, Any] - Reply to a specific email.

EMAIL AGENT - LEVEL 1: Email Composition
Use this to reply to an email you've read. The subject will automatically have "Re: " prepended.

Args:
    original_sender: Email address of the person who sent the original email
    original_subject: Subject line of the original email
    reply_body: Your reply message (supports markdown)
    send: If True, send immediately; if False, open as draft (default: False)

Returns:
    Dictionary with status ('sent' or 'draft')

**Complete Call Example:**
```json
{
  "action": "reply_to_email",
  "parameters": {
    "original_sender": "example_value",
    "original_subject": "example_value",
    "reply_body": "example_value"
  }
}
```

**Parameters:**
- `original_sender` (required)
- `original_subject` (required)
- `reply_body` (required)
- `send` (optional)

**Strengths:**
- Supports email address of the person who sent the original email
- Supports subject line of the original email
- Supports your reply message (supports markdown)
- Supports if true, send immediately; if false, open as draft (default: false)
- Returns structured data

**Limitations:**
- See tool documentation for specific constraints

---

### summarize_emails
**Purpose:** summarize_emails(emails_data: Dict[str, Any], focus: Optional[str] = None) -> Dict[str, Any] - Summarize a list of emails with key information.

EMAIL AGENT - LEVEL 3: Email Summarization
Use this to create a concise summary of emails, highlighting key information.

This tool should be used AFTER reading emails with one of the read_* tools:
- read_latest_emails() → summarize_emails() - for summarizing recent emails
- read_emails_by_sender() → summarize_emails() - for summarizing emails from a specific person
- read_emails_by_time() → summarize_emails() - for summarizing emails from a time range

The emails_data parameter should be the result dictionary from a read_* tool call.

Args:
    emails_data: Dictionary containing 'emails' list from read_* tools (required).
                 Must be the output from read_latest_emails, read_emails_by_sender, or read_emails_by_time.
    focus: Optional focus area (e.g., "action items", "deadlines", "important updates", "key decisions")

Returns:
    Dictionary with:
    - summary: Text summary of the emails
    - email_count: Number of emails summarized
    - focus: The focus area used (if any)
    - emails_summarized: List of email metadata (sender, subject, date)

**Complete Call Example:**
```json
{
  "action": "summarize_emails",
  "parameters": {
    "emails_data": "example_value"
  }
}
```

**Parameters:**
- `emails_data` (required)
- `focus` (optional)

**Strengths:**
- Supports dictionary containing 'emails' list from read_* tools (required).
- Supports optional focus area (e.g., "action items", "deadlines", "important updates", "key decisions")
- Returns structured data

**Limitations:**
- Must be the output from read_latest_emails, read_emails_by_sender, or read_emails_by_time

---

## FILE Agent (9 tools)

### create_zip_archive
**Purpose:** Create ZIP archives with optional filename pattern and extension filters.

**Complete Call Example:**
```json
{
  "action": "create_zip_archive",
  "parameters": {
  }
}
```

**Parameters:**
- `source_path` (optional)
- `zip_name` (optional)
- `include_pattern` (optional)
- `include_extensions` (optional)
- `exclude_extensions` (optional)

**Strengths:**
- Flexible filtering with glob patterns and extension allow/deny lists
- Defaults to primary document directory when source_path is omitted
- Returns archive statistics (file count, size, compression ratio)

**Limitations:**
- Operates within the configured document directory
- Does not bundle sub-folder creation (combine with organize_files if needed)

---

### explain_files
**Purpose:** explain_files() -> Dict[str, Any] - List and explain all indexed/authorized files with brief descriptions.

FILE AGENT - LEVEL 1: File Explanation
Use this to get a high-level overview of all files you have access to with 1-2 line explanations.

Returns:
    Dictionary with:
    - files: List of file entries, each with file_path, file_name, file_type, explanation
    - total_count: Number of files found

Security:
    - Only returns files from folders explicitly allowed in config.yaml (documents.folders)

**Complete Call Example:**
```json
{
  "action": "explain_files",
  "parameters": {
  }
}
```

**Strengths:**
- Returns structured data

**Limitations:**
- Returns:
    Dictionary with:
    - files: List of file entries, each with file_path, file_name, file_type, explanation
    - total_count: Number of files found

Security:
    - Only returns files from folders explicitly allowed in config.yaml (documents.folders)

---

### explain_folder
**Purpose:** explain_folder(folder_path: Optional[str] = None) -> Dict[str, Any] - List and explain all files in an authorized folder with brief descriptions.

FILE AGENT - LEVEL 1: File Explanation
Use this to get a high-level overview of files in a folder with 1-2 line explanations.

Args:
    folder_path: Optional path to folder (must be in authorized folders from config).
                 If None, lists files from all authorized folders.

Returns:
    Dictionary with:
    - files: List of file entries, each with file_path, file_name, file_type, explanation
    - folder_path: The folder that was queried (or "all authorized folders")
    - total_count: Number of files found

Security:
    - Only operates on folders explicitly allowed in config.yaml (documents.folders)
    - Validates folder_path against authorized paths

**Complete Call Example:**
```json
{
  "action": "explain_folder",
  "parameters": {
  }
}
```

**Parameters:**
- `folder_path` (optional)

**Strengths:**
- Supports optional path to folder (must be in authorized folders from config).
- Returns structured data

**Limitations:**
- Args:
    folder_path: Optional path to folder (must be in authorized folders from config)
- Returns:
    Dictionary with:
    - files: List of file entries, each with file_path, file_name, file_type, explanation
    - folder_path: The folder that was queried (or "all authorized folders")
    - total_count: Number of files found

Security:
    - Only operates on folders explicitly allowed in config.yaml (documents.folders)
    - Validates folder_path against authorized paths

---

### extract_section
**Purpose:** Extract specific sections or pages from a document

**Complete Call Example:**
```json
{
  "action": "extract_section",
  "parameters": {
    "doc_path": "/path/to/example",
    "section": "example_value"
  }
}
```

**Parameters:**
- `doc_path` (required)
- `section` (required)

**Strengths:**
- Supports multiple extraction methods (all, page N, pages containing keyword)
- Semantic search within document
- Returns page numbers for context

**Limitations:**
- Requires valid document path
- PDF and DOCX only
- May miss content if section query is ambiguous

---

### list_documents
**Purpose:** list_documents(filter: Optional[str] = None, folder_path: Optional[str] = None, max_results: int = 20) -> Dict[str, Any] - List indexed documents with optional filtering.

FILE AGENT - LEVEL 1: Document Discovery
Use this when the user wants to browse or list their indexed documents.
Shows a directory-style listing of all indexed documents with metadata.

Args:
    filter: Text to filter documents by (name, folder, or semantic query)
    folder_path: Specific folder path to list documents from
    max_results: Maximum number of documents to return (default: 20)

Returns:
    Dictionary with:
    - type: "document_list"
    - message: Summary message
    - documents: List of document entries with name, path, size, modified, preview
    - total_count: Total number of documents found
    - has_more: Boolean indicating if there are more results

**Complete Call Example:**
```json
{
  "action": "list_documents",
  "parameters": {
  }
}
```

**Parameters:**
- `filter` (optional)
- `folder_path` (optional)
- `max_results` (optional)

**Strengths:**
- the user wants to browse or list their indexed documents.
Shows a directory-style listing of all indexed documents with metadata.
- Supports text to filter documents by (name, folder, or semantic query)
- Supports specific folder path to list documents from
- Supports maximum number of documents to return (default: 20)
- Returns structured data

**Limitations:**
- See tool documentation for specific constraints

---

### list_related_documents
**Purpose:** list_related_documents(query: str, max_results: int = 10) -> Dict[str, Any] - List multiple related documents matching a semantic query.

FILE AGENT - LEVEL 1: Document Discovery
Use this when the user wants to see multiple matching files (e.g., "show all guitar tab files").
This tool groups search results by document and returns structured metadata.

Args:
    query: Natural language search query describing the documents to find
    max_results: Maximum number of documents to return (default: 10, cap: 25)

Returns:
    Dictionary with:
    - type: "file_list"
    - message: Summary message with count
    - files: List of document entries, each with:
      - name: Basename of file
      - path: Full absolute path
      - score: Similarity score (0-1)
      - meta: Dictionary with file_type and optional total_pages
    - summary_blurb: Optional contextual summary (empty initially, LLM can populate)
    - total_count: Number of documents found

**Complete Call Example:**
```json
{
  "action": "list_related_documents",
  "parameters": {
    "query": "example search query"
  }
}
```

**Parameters:**
- `query` (required)
- `max_results` (optional)

**Strengths:**
- the user wants to see multiple matching files (e.g., "show all guitar tab files").
This tool groups search results by document and returns structured metadata.
- Supports natural language search query describing the documents to find
- Supports maximum number of documents to return (default: 10, cap: 25)
- Returns structured data

**Limitations:**
- See tool documentation for specific constraints

---

### organize_files
**Purpose:** Organize files into folders using LLM-driven categorization. Creates target folder automatically and moves/copies matching files. NO separate folder creation needed!

**Complete Call Example:**
```json
{
  "action": "organize_files",
  "parameters": {
    "category": "example_value",
    "target_folder": "example_value"
  }
}
```

**Parameters:**
- `category` (required)
- `target_folder` (required)
- `move_files` (optional)

**Strengths:**
- COMPLETE standalone tool - creates folder AND moves files in ONE step
- LLM-driven file categorization (NO hardcoded patterns)
- Semantic understanding of file relevance
- Detailed reasoning for each file decision
- Handles naming conflicts automatically
- Supports both moving and copying files

**Limitations:**
- Only works on files in configured document directory
- Categorization based on filenames (content analysis optional)
- Conservative approach - excludes ambiguous files

---

### search_documents
**Purpose:** Search for documents using semantic similarity

**Complete Call Example:**
```json
{
  "action": "search_documents",
  "parameters": {
    "query": "example search query"
  }
}
```

**Parameters:**
- `query` (required)
- `user_request` (optional)

**Strengths:**
- Semantic search across indexed documents
- Returns most relevant document
- Includes file metadata

**Limitations:**
- Only searches indexed documents
- Returns single best match
- Requires documents to be pre-indexed

---

### take_screenshot
**Purpose:** Capture page images from PDF documents

**Complete Call Example:**
```json
{
  "action": "take_screenshot",
  "parameters": {
    "doc_path": "/path/to/example",
    "pages": "example_value"
  }
}
```

**Parameters:**
- `doc_path` (required)
- `pages` (required)

**Strengths:**
- High-quality page images
- Multiple pages at once
- Preserves visual formatting

**Limitations:**
- PDF documents only
- Creates temporary files
- Larger file sizes

---

## FOLDER Agent (11 tools)

### folder_apply
**Purpose:** folder_apply(plan: List[Dict[str, Any]], folder_path: Optional[str] = None, dry_run: bool = True) -> Dict[str, Any] - Apply a folder reorganization plan (atomic renames).

FOLDER AGENT - LEVEL 3: Execution (WRITE OPERATION)
Use this ONLY after getting user confirmation on the plan.

This performs actual file/folder renames based on a plan
generated by folder_plan_alpha.

IMPORTANT: Always use dry_run=True first to validate, then
get user confirmation before setting dry_run=False.

Args:
    plan: List of rename operations from folder_plan_alpha
    folder_path: Base folder path (defaults to sandbox root)
    dry_run: If True, validate but don't execute (default: True)

Returns:
    Dictionary with:
    - success: Boolean indicating if all operations succeeded
    - applied: List of successfully renamed items
    - skipped: List of items that didn't need changes
    - errors: List of items that failed with error messages
    - dry_run: Boolean indicating if this was a dry run

Security:
    - All paths validated against sandbox
    - Each rename validated before execution
    - Conflicts detected (destination exists)
    - Atomic operations (no partial renames)

Error Handling:
    - Conflicts: Destination already exists -> skip with error
    - Locked files: OS-level lock -> skip with error
    - Invalid paths: Outside sandbox -> skip with error
    - Missing source: File doesn't exist -> skip with error

**Complete Call Example:**
```json
{
  "action": "folder_apply",
  "parameters": {
    "plan": "example_value"
  }
}
```

**Parameters:**
- `plan` (required)
- `folder_path` (optional)
- `dry_run` (optional)

**Strengths:**
- Supports list of rename operations from folder_plan_alpha
- Supports base folder path (defaults to sandbox root)
- Supports if true, validate but don't execute (default: true)
- Returns structured data

**Limitations:**
- FOLDER AGENT - LEVEL 3: Execution (WRITE OPERATION)
Use this ONLY after getting user confirmation on the plan

---

### folder_archive_old
**Purpose:** folder_archive_old(folder_path: Optional[str] = None, items: Optional[List[Dict[str, Any]]] = None, age_threshold_days: int = 180, dry_run: bool = True) -> Dict[str, Any] - Archive old files to reduce folder clutter.

FOLDER AGENT - LEVEL 3: Execution (WRITE OPERATION)
Use this to move old/unused files to timestamped archive folders.

Args:
    folder_path: Source folder path (defaults to sandbox root)
    items: Pre-fetched folder items (optional)
    age_threshold_days: Files older than this many days will be archived
    dry_run: If True, only show plan (default: True, requires confirmation)

Returns:
    Dictionary with archive plan or execution results:
    - archive_plan: What will be archived (dry_run=True)
    - files_moved: Successfully archived files (dry_run=False)
    - archive_created: Archive folder path
    - space_freed_mb: Space recovered

Security:
    - All paths validated against sandbox
    - Files are moved, not deleted
    - Atomic operations with rollback on failure

**Complete Call Example:**
```json
{
  "action": "folder_archive_old",
  "parameters": {
  }
}
```

**Parameters:**
- `folder_path` (optional)
- `items` (optional)
- `age_threshold_days` (optional)
- `dry_run` (optional)

**Strengths:**
- Supports source folder path (defaults to sandbox root)
- Supports pre-fetched folder items (optional)
- Supports files older than this many days will be archived
- Supports if true, only show plan (default: true, requires confirmation)
- Returns structured data

**Limitations:**
- Args:
    folder_path: Source folder path (defaults to sandbox root)
    items: Pre-fetched folder items (optional)
    age_threshold_days: Files older than this many days will be archived
    dry_run: If True, only show plan (default: True, requires confirmation)

Returns:
    Dictionary with archive plan or execution results:
    - archive_plan: What will be archived (dry_run=True)
    - files_moved: Successfully archived files (dry_run=False)
    - archive_created: Archive folder path
    - space_freed_mb: Space recovered

Security:
    - All paths validated against sandbox
    - Files are moved, not deleted
    - Atomic operations with rollback on failure

---

### folder_check_sandbox
**Purpose:** folder_check_sandbox(path: str) -> Dict[str, Any] - Verify a path is within the allowed sandbox.

FOLDER AGENT - LEVEL 0: Security Validation
Use this to verify scope before operations.

This validates that a given path is within the configured
sandbox directory (configured document folders). All folder tools
perform this check internally, but you can call this explicitly
to verify scope or show the user the sandbox boundaries.

Args:
    path: Path to validate

Returns:
    Dictionary with:
    - is_safe: Boolean indicating if path is within sandbox
    - message: Human-readable explanation
    - resolved_path: Absolute path after resolving symlinks
    - allowed_folder: The configured sandbox root

Security:
    - Resolves symlinks to prevent symlink attacks
    - Checks for parent directory traversal (..)
    - Validates against configured sandbox root

**Complete Call Example:**
```json
{
  "action": "folder_check_sandbox",
  "parameters": {
    "path": "/path/to/example"
  }
}
```

**Parameters:**
- `path` (required)

**Strengths:**
- Supports path to validate
- Returns structured data

**Limitations:**
- See tool documentation for specific constraints

---

### folder_explain_file
**Purpose:** folder_explain_file(file_path: str) -> Dict[str, Any] - Explain file content and purpose using metadata and semantic analysis.

FOLDER AGENT - LEVEL 2: Analysis (READ-ONLY) with Cross-Agent Integration
Use this when users want to understand what a specific file contains.

This tool combines file metadata with content analysis from the file agent
to provide comprehensive explanations of files.

Args:
    file_path: Path to the file to explain

Returns:
    Dictionary with:
    - explanation: Natural language file description
    - key_topics: Main topics/content areas
    - suggested_actions: Recommended next steps
    - content_summary: Brief content overview

Security:
    - File path validated against sandbox
    - No write operations performed

**Complete Call Example:**
```json
{
  "action": "folder_explain_file",
  "parameters": {
    "file_path": "/path/to/example"
  }
}
```

**Parameters:**
- `file_path` (required)

**Strengths:**
- users want to understand what a specific file contains.
- Supports path to the file to explain
- Returns structured data

**Limitations:**
- FOLDER AGENT - LEVEL 2: Analysis (READ-ONLY) with Cross-Agent Integration
Use this when users want to understand what a specific file contains

---

### folder_find_duplicates
**Purpose:** folder_find_duplicates(folder_path: Optional[str] = None, recursive: bool = False) -> Dict[str, Any] - Find duplicate files by content hash (SHA-256).

FOLDER AGENT - LEVEL 2: Analysis (READ-ONLY)
Use this when user asks to find, list, or identify duplicate files.

This is a read-only operation that identifies files with identical
content by computing SHA-256 hashes. Files are grouped by hash,
and the tool reports wasted disk space.

Behavior:
- Compares files by content (not just name or size)
- Groups duplicates together with metadata
- Calculates wasted disk space
- Can search recursively or just top-level

Args:
    folder_path: Path to analyze (defaults to primary document directory from config)
    recursive: Search subdirectories (default: False, top-level only)

Returns:
    Dictionary with:
    - duplicates: List of duplicate groups (hash, size, count, files)
    - total_duplicate_files: Total count of duplicate files
    - total_duplicate_groups: Number of duplicate groups
    - wasted_space_bytes: Total bytes wasted
    - wasted_space_mb: Wasted space in MB

Security:
    - All paths validated against sandbox
    - No write operations performed
    - Skips hidden files and directories

Example workflow:
1. User: "Find duplicate files in my folder"
2. Agent: folder_find_duplicates(folder_path=None, recursive=False)
3. Agent: Summarize results and present to user

**Complete Call Example:**
```json
{
  "action": "folder_find_duplicates",
  "parameters": {
  }
}
```

**Parameters:**
- `folder_path` (optional)
- `recursive` (optional)

**Strengths:**
- user asks to find
- or identify duplicate files.
- Supports path to analyze (defaults to primary document directory from config)
- Supports search subdirectories (default: false, top-level only)
- Returns structured data

**Limitations:**
- FOLDER AGENT - LEVEL 2: Analysis (READ-ONLY)
Use this when user asks to find, list, or identify duplicate files
- This is a read-only operation that identifies files with identical
content by computing SHA-256 hashes
- Behavior:
- Compares files by content (not just name or size)
- Groups duplicates together with metadata
- Calculates wasted disk space
- Can search recursively or just top-level

Args:
    folder_path: Path to analyze (defaults to primary document directory from config)
    recursive: Search subdirectories (default: False, top-level only)

Returns:
    Dictionary with:
    - duplicates: List of duplicate groups (hash, size, count, files)
    - total_duplicate_files: Total count of duplicate files
    - total_duplicate_groups: Number of duplicate groups
    - wasted_space_bytes: Total bytes wasted
    - wasted_space_mb: Wasted space in MB

Security:
    - All paths validated against sandbox
    - No write operations performed
    - Skips hidden files and directories

Example workflow:
1

---

### folder_list
**Purpose:** folder_list(folder_path: Optional[str] = None) -> Dict[str, Any] - List contents of a folder (non-recursive, alphabetically sorted).

FOLDER AGENT - LEVEL 1: Discovery
Use this as the first step to understand current folder structure.

This is a read-only operation that shows all files and folders
in the specified directory. Returns items sorted alphabetically.

Args:
    folder_path: Path to list (defaults to primary document directory from config)

Returns:
    Dictionary with items (list), total_count (int), folder_path (str)
    Each item includes: name, type (file/dir), size, modified, extension

Security:
    - All paths validated against sandbox (configured document folders)
    - Symlinks resolved and validated
    - Parent directory traversal (..) rejected

**Complete Call Example:**
```json
{
  "action": "folder_list",
  "parameters": {
  }
}
```

**Parameters:**
- `folder_path` (optional)

**Strengths:**
- Supports path to list (defaults to primary document directory from config)
- Returns structured data

**Limitations:**
- This is a read-only operation that shows all files and folders
in the specified directory

---

### folder_organize_by_category
**Purpose:** folder_organize_by_category(folder_path: Optional[str] = None, items: Optional[List[Dict[str, Any]]] = None, categorization: Optional[Dict[str, Any]] = None, dry_run: bool = True) -> Dict[str, Any] - Organize files into semantic categories based on content analysis.

FOLDER AGENT - LEVEL 3: Execution (WRITE OPERATION) with Cross-Agent Integration
Use this for intelligent content-based file organization.

This tool uses content analysis to group files by topics/themes
and creates category folders automatically.

Args:
    folder_path: Source folder path (defaults to sandbox root)
    items: Pre-fetched folder items (optional)
    categorization: Pre-computed categorization results (optional)
    dry_run: If True, only show plan (default: True, requires confirmation)

Returns:
    Dictionary with organization plan or execution results:
    - categories: Semantic categories and file assignments
    - new_structure: Proposed folder structure
    - folders_created: New category folders
    - files_moved: Successfully organized files

Security:
    - All paths validated against sandbox
    - Atomic operations with rollback on failure
    - Cross-agent calls for content analysis

**Complete Call Example:**
```json
{
  "action": "folder_organize_by_category",
  "parameters": {
  }
}
```

**Parameters:**
- `folder_path` (optional)
- `items` (optional)
- `categorization` (optional)
- `dry_run` (optional)

**Strengths:**
- Supports source folder path (defaults to sandbox root)
- Supports pre-fetched folder items (optional)
- Supports pre-computed categorization results (optional)
- Supports if true, only show plan (default: true, requires confirmation)
- Returns structured data

**Limitations:**
- Args:
    folder_path: Source folder path (defaults to sandbox root)
    items: Pre-fetched folder items (optional)
    categorization: Pre-computed categorization results (optional)
    dry_run: If True, only show plan (default: True, requires confirmation)

Returns:
    Dictionary with organization plan or execution results:
    - categories: Semantic categories and file assignments
    - new_structure: Proposed folder structure
    - folders_created: New category folders
    - files_moved: Successfully organized files

Security:
    - All paths validated against sandbox
    - Atomic operations with rollback on failure
    - Cross-agent calls for content analysis

---

### folder_organize_by_type
**Purpose:** folder_organize_by_type(folder_path: Optional[str] = None, dry_run: bool = True) -> Dict[str, Any] - Group files into subfolders based on file extension (e.g., PDF, TXT).

FOLDER AGENT - LEVEL 3: Type-Based Organization
Use this when the user requests "organize by file type" or similar.

Behavior:
- Looks at top-level files in the specified folder (defaults to sandbox root)
- Creates one folder per extension (e.g., PDF/, TXT/, NO_EXTENSION/)
- Moves each file into its matching folder
- Respects dry_run flag for preview vs execution

Args:
    folder_path: Folder to organize (defaults to sandbox root)
    dry_run: If True, only generate plan (default). Set False after confirmation.

Returns:
    Dictionary with plan, summary, and optional applied moves

Security:
    - Validates sandbox boundaries
    - Skips hidden files and directories
    - Avoids overwriting existing files (skips with reason)

**Complete Call Example:**
```json
{
  "action": "folder_organize_by_type",
  "parameters": {
  }
}
```

**Parameters:**
- `folder_path` (optional)
- `dry_run` (optional)

**Strengths:**
- the user requests "organize by file type" or similar.
- Supports folder to organize (defaults to sandbox root)
- Supports if true, only generate plan (default). set false after confirmation.
- Returns structured data

**Limitations:**
- Behavior:
- Looks at top-level files in the specified folder (defaults to sandbox root)
- Creates one folder per extension (e.g., PDF/, TXT/, NO_EXTENSION/)
- Moves each file into its matching folder
- Respects dry_run flag for preview vs execution

Args:
    folder_path: Folder to organize (defaults to sandbox root)
    dry_run: If True, only generate plan (default)

---

### folder_plan_alpha
**Purpose:** folder_plan_alpha(folder_path: Optional[str] = None) -> Dict[str, Any] - Generate a plan to normalize folder/file names alphabetically.

FOLDER AGENT - LEVEL 2: Planning (DRY-RUN)
Use this to preview changes before applying them.

This is a read-only operation that proposes normalized names:
- Lowercase
- Spaces converted to underscores
- Special characters removed
- Multiple underscores collapsed

NO files are modified. This is always a dry-run.

Args:
    folder_path: Path to analyze (defaults to primary document directory from config)

Returns:
    Dictionary with:
    - plan: List of proposed changes (current_name, proposed_name, reason)
    - needs_changes: Boolean indicating if any changes are needed
    - total_items: Total number of items analyzed
    - changes_count: Number of items that need renaming

Security:
    - All paths validated against sandbox
    - No write operations performed

**Complete Call Example:**
```json
{
  "action": "folder_plan_alpha",
  "parameters": {
  }
}
```

**Parameters:**
- `folder_path` (optional)

**Strengths:**
- Supports path to analyze (defaults to primary document directory from config)
- Returns structured data

**Limitations:**
- This is a read-only operation that proposes normalized names:
- Lowercase
- Spaces converted to underscores
- Special characters removed
- Multiple underscores collapsed

NO files are modified

---

### folder_sort_by
**Purpose:** folder_sort_by(folder_path: Optional[str] = None, items: Optional[List[Dict[str, Any]]] = None, criteria: str = 'name', direction: str = 'ascending') -> Dict[str, Any] - Sort folder contents by specified criteria with explanation.

FOLDER AGENT - LEVEL 2: Analysis (READ-ONLY)
Use this when users want to view files in a specific order.

Supported criteria: name, date, size, type, extension

Args:
    folder_path: Path to analyze (defaults to sandbox root)
    items: Pre-fetched folder items (optional)
    criteria: Sort criteria (name|date|size|type|extension)
    direction: Sort direction (ascending|descending)

Returns:
    Dictionary with:
    - sorted_items: Sorted file list
    - criteria: Sort criteria used
    - direction: Sort direction used
    - explanation: Why this sorting is useful
    - insights: Key observations from the sorted view

Security:
    - All paths validated against sandbox
    - No write operations performed

**Complete Call Example:**
```json
{
  "action": "folder_sort_by",
  "parameters": {
  }
}
```

**Parameters:**
- `folder_path` (optional)
- `items` (optional)
- `criteria` (optional)
- `direction` (optional)

**Strengths:**
- users want to view files in a specific order.
- Supports path to analyze (defaults to sandbox root)
- Supports pre-fetched folder items (optional)
- Supports sort criteria (name|date|size|type|extension)
- Supports sort direction (ascending|descending)

**Limitations:**
- FOLDER AGENT - LEVEL 2: Analysis (READ-ONLY)
Use this when users want to view files in a specific order

---

### folder_summarize
**Purpose:** folder_summarize(folder_path: Optional[str] = None, items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any] - Generate comprehensive folder overview with statistics and insights.

FOLDER AGENT - LEVEL 2: Analysis (READ-ONLY)
Use this to provide users with natural language summaries of folder contents.

This tool analyzes file types, sizes, dates, and generates actionable insights
about the folder's contents and potential organization improvements.

Args:
    folder_path: Path to analyze (defaults to sandbox root)
    items: Pre-fetched folder items (optional, avoids redundant listing)

Returns:
    Dictionary with:
    - summary: Natural language overview
    - statistics: Quantitative data (counts, sizes, distributions)
    - insights: Key observations about the folder
    - recommendations: Actionable suggestions

Security:
    - All paths validated against sandbox
    - No write operations performed

**Complete Call Example:**
```json
{
  "action": "folder_summarize",
  "parameters": {
  }
}
```

**Parameters:**
- `folder_path` (optional)
- `items` (optional)

**Strengths:**
- Supports path to analyze (defaults to sandbox root)
- Supports pre-fetched folder items (optional, avoids redundant listing)
- Returns structured data

**Limitations:**
- FOLDER AGENT - LEVEL 2: Analysis (READ-ONLY)
Use this to provide users with natural language summaries of folder contents

---

## GOOGLE Agent (3 tools)

### google_search
**Purpose:** Perform DuckDuckGo web searches and extract structured results. LEVEL 1 tool in browser hierarchy—use this first when you need to find information on the web.

**Complete Call Example:**
```json
{
  "action": "google_search",
  "parameters": {
    "query": "example search query"
  }
}
```

**Parameters:**
- `query` (required)
- `num_results` (optional)
- `search_type` (optional)
- `reasoning_context` (optional)

**Strengths:**
- PRIMARY web search tool (DuckDuckGo HTML endpoint) - use this first for finding information online
- Returns structured results with titles, links, and snippets
- Fast and reliable, no API keys required
- Good for finding documentation, websites, and general information

**Limitations:**
- Requires internet connection
- Limited to search results (doesn't extract page content)
- DuckDuckGo HTML payload occasionally omits snippets for certain pages

---

### google_search_images
**Purpose:** google_search_images(query: str, num_results: int = 5) -> Dict[str, Any] - Perform an image-oriented DuckDuckGo web search (query tweak only).

SEARCH AGENT - LEVEL 2: Image-Oriented Search
Note: DuckDuckGo HTML results do not provide direct image API access.
This function simply biases the query toward images.

Args:
    query: Image search query
    num_results: Number of results to return (default: 5)

Returns:
    Dictionary with search results (may include image-related pages)

**Complete Call Example:**
```json
{
  "action": "google_search_images",
  "parameters": {
    "query": "example search query"
  }
}
```

**Parameters:**
- `query` (required)
- `num_results` (optional)

**Strengths:**
- Supports image search query
- Supports number of results to return (default: 5)
- Returns structured data

**Limitations:**
- google_search_images(query: str, num_results: int = 5) -> Dict[str, Any] - Perform an image-oriented DuckDuckGo web search (query tweak only)

---

### google_search_site
**Purpose:** google_search_site(query: str, site: str, num_results: int = 5) -> Dict[str, Any] - Search within a specific website using DuckDuckGo's `site:` operator.

SEARCH AGENT - LEVEL 3: Site-Specific Search
Limit search to a specific domain or website.

This adds "site:domain.com" to the query for site-restricted searches.
Useful for searching documentation, specific blogs, or corporate sites.

Args:
    query: Search query
    site: Domain to search within (e.g., "stackoverflow.com", "github.com")
    num_results: Number of results (1-10, default: 5)

Returns:
    Search results limited to the specified site

Examples:
    - google_search_site("python async", "stackoverflow.com")
    - google_search_site("machine learning", "github.com")
    - google_search_site("API docs", "openai.com")

**Complete Call Example:**
```json
{
  "action": "google_search_site",
  "parameters": {
    "query": "example search query",
    "site": "example_value"
  }
}
```

**Parameters:**
- `query` (required)
- `site` (required)
- `num_results` (optional)

**Strengths:**
- Supports search query
- Supports domain to search within (e.g., "stackoverflow.com", "github.com")
- Supports number of results (1-10, default: 5)

**Limitations:**
- Args:
    query: Search query
    site: Domain to search within (e.g., "stackoverflow.com", "github.com")
    num_results: Number of results (1-10, default: 5)

Returns:
    Search results limited to the specified site

Examples:
    - google_search_site("python async", "stackoverflow.com")
    - google_search_site("machine learning", "github.com")
    - google_search_site("API docs", "openai.com")

---

## GOOGLE FINANCE Agent (4 tools)

### capture_google_finance_chart
**Purpose:** capture_google_finance_chart(url: str, output_name: Optional[str] = None) -> Dict[str, Any] - Capture a screenshot of the stock chart from Google Finance.

Args:
    url: Google Finance URL
    output_name: Optional custom filename

Returns:
    Dictionary with screenshot path

Example:
    capture_google_finance_chart("https://www.google.com/finance/quote/PLTR:NASDAQ")

**Complete Call Example:**
```json
{
  "action": "capture_google_finance_chart",
  "parameters": {
    "url": "https://example.com"
  }
}
```

**Parameters:**
- `url` (required)
- `output_name` (optional)

**Strengths:**
- Supports google finance url
- Supports optional custom filename
- Returns structured data

**Limitations:**
- See tool documentation for specific constraints

---

### create_stock_report_from_google_finance
**Purpose:** create_stock_report_from_google_finance(company: str, output_format: str = 'pdf') -> Dict[str, Any] - Create a complete stock report using Google Finance data.

This HIGH-LEVEL tool orchestrates:
1. Search Google Finance for the company
2. Extract price data and AI research
3. Capture chart screenshot
4. Compile into PDF report or Keynote presentation

Args:
    company: Company name or ticker (e.g., "Palantir", "PLTR")
    output_format: "pdf" for report, "presentation" for Keynote (default: "pdf")

Returns:
    Dictionary with report/presentation path and all extracted data

Example:
    create_stock_report_from_google_finance("Palantir", "pdf")
    create_stock_report_from_google_finance("MSFT", "presentation")

**Complete Call Example:**
```json
{
  "action": "create_stock_report_from_google_finance",
  "parameters": {
    "company": "example_value"
  }
}
```

**Parameters:**
- `company` (required)
- `output_format` (optional)

**Strengths:**
- Supports company name or ticker (e.g., "palantir", "pltr")
- Supports "pdf" for report, "presentation" for keynote (default: "pdf")
- Returns structured data

**Limitations:**
- May require API keys or credentials

---

### extract_google_finance_data
**Purpose:** extract_google_finance_data(url: str) -> Dict[str, Any] - Extract stock data and AI research from a Google Finance page.

Extracts:
- Current price and change
- AI-generated research summary
- Key statistics
- About section

Args:
    url: Google Finance URL (e.g., "https://www.google.com/finance/quote/PLTR:NASDAQ")

Returns:
    Dictionary with price, research, statistics, and raw content

Example:
    extract_google_finance_data("https://www.google.com/finance/quote/PLTR:NASDAQ")

**Complete Call Example:**
```json
{
  "action": "extract_google_finance_data",
  "parameters": {
    "url": "https://example.com"
  }
}
```

**Parameters:**
- `url` (required)

**Strengths:**
- Supports google finance url (e.g., "https://www.google.com/finance/quote/pltr:nasdaq")
- Returns structured data

**Limitations:**
- May require API keys or credentials

---

### search_google_finance_stock
**Purpose:** search_google_finance_stock(company: str) -> Dict[str, Any] - Search for a company on Google Finance and get the stock page URL.

Args:
    company: Company name or ticker symbol (e.g., "Palantir", "PLTR", "Microsoft")

Returns:
    Dictionary with stock page URL, ticker, and company name

Example:
    search_google_finance_stock("Palantir")
    # Returns: {"url": "https://www.google.com/finance/quote/PLTR:NASDAQ", "ticker": "PLTR", ...}

**Complete Call Example:**
```json
{
  "action": "search_google_finance_stock",
  "parameters": {
    "company": "example_value"
  }
}
```

**Parameters:**
- `company` (required)

**Strengths:**
- Supports company name or ticker symbol (e.g., "palantir", "pltr", "microsoft")
- Returns structured data

**Limitations:**
- See tool documentation for specific constraints

---

## IMESSAGE Agent (1 tools)

### send_imessage
**Purpose:** send_imessage(message: str, recipient: Optional[str] = None) -> Dict[str, Any] - Send a text message via iMessage on macOS.

**PREFERRED METHOD for sending Maps URLs, trip details, and quick messages to user.**

Use this tool when you need to:
- Send Maps URLs to the user's phone (HIGHLY RECOMMENDED for trips)
- Send trip details, route information, or travel plans
- Share any information via text message
- Send quick notifications or updates

This is BETTER than email for:
- Maps URLs (can be opened directly on iPhone)
- Time-sensitive information
- Quick updates and notifications

Args:
    message: The message text to send (supports URLs, emojis, newlines)
    recipient: Phone number (e.g., "+16618572957") or email address.
              If None, empty, or contains "me"/"to me"/"my phone", will use default_phone_number from config.yaml.

Returns:
    Dictionary with status and message details

Example:
    send_imessage(
        message="Your trip from Phoenix to LA is planned! Maps URL: maps://...",
        recipient="+16618572957"  # or None/"me" for default
    )

**Complete Call Example:**
```json
{
  "action": "send_imessage",
  "parameters": {
    "message": "example_value"
  }
}
```

**Parameters:**
- `message` (required)
- `recipient` (optional)

**Strengths:**
- Supports the message text to send (supports urls, emojis, newlines)
- Supports phone number (e.g., "+16618572957") or email address.
- Returns structured data

**Limitations:**
- macOS only

---

## MAPS Agent (5 tools)

### get_directions
**Purpose:** get_directions(origin: str, destination: str, transportation_mode: str = 'driving', open_maps: bool = True) -> Dict[str, Any] - Get simple directions from one location to another with specified transportation mode.

Use this for simple point-to-point navigation queries like:
- "When's the next bus to Berkeley"
- "How do I bike to the office"
- "Walk me to the coffee shop"
- "Drive to San Francisco"

IMPORTANT: For "current location" queries, use the location service to detect current location first,
then call this tool with the actual coordinates or "Current Location" string.

Args:
    origin: Starting location (can be "Current Location" or specific address/coordinates)
    destination: End location (address, place name, or coordinates)
    transportation_mode: Mode of transportation:
        - "driving" or "car" = Driving (default)
        - "walking" or "walk" = Walking
        - "transit" or "bus" or "public transport" = Public Transportation/Transit
        - "bicycle" or "bike" or "cycling" = Bicycle
    open_maps: If True, automatically open Maps with the route (default: True)

Returns:
    Dictionary with route details and maps URL

Example:
    get_directions(
        origin="Current Location",
        destination="Berkeley, CA",
        transportation_mode="transit"
    )

**Complete Call Example:**
```json
{
  "action": "get_directions",
  "parameters": {
    "origin": "example_value",
    "destination": "example_value"
  }
}
```

**Parameters:**
- `origin` (required)
- `destination` (required)
- `transportation_mode` (optional)
- `open_maps` (optional)

**Strengths:**
- Supports starting location (can be "current location" or specific address/coordinates)
- Supports end location (address, place name, or coordinates)
- Supports mode of transportation:
- Supports if true, automatically open maps with the route (default: true)
- Returns structured data

**Limitations:**
- See tool documentation for specific constraints

---

### get_google_transit_directions
**Purpose:** get_google_transit_directions(origin: str, destination: str, departure_time: Optional[str] = 'now') -> Dict[str, Any] - Get real-time transit directions with actual departure times using Google Maps API.

This tool provides PROGRAMMATIC access to transit schedules including:
- Next bus/train departure time
- Step-by-step transit directions
- Line numbers and vehicle types
- Real-time schedule data

Use this for queries like:
- "When's the next bus to UCSC Silicon Valley"
- "What time is the next train to downtown"
- "Show me transit directions to Berkeley"

Args:
    origin: Starting location (address, place name, or "Current Location")
    destination: End location (address or place name)
    departure_time: When to depart - "now" (default) or specific time

Returns:
    Dictionary with real-time transit schedule data including next departure time

Example:
    get_google_transit_directions(
        origin="Current Location",
        destination="UCSC Silicon Valley",
        departure_time="now"
    )

**Complete Call Example:**
```json
{
  "action": "get_google_transit_directions",
  "parameters": {
    "origin": "example_value",
    "destination": "example_value"
  }
}
```

**Parameters:**
- `origin` (required)
- `destination` (required)
- `departure_time` (optional)

**Strengths:**
- Supports starting location (address, place name, or "current location")
- Supports end location (address or place name)
- Supports when to depart - "now" (default) or specific time
- Returns structured data

**Limitations:**
- May require API keys or credentials

---

### get_transit_schedule
**Purpose:** get_transit_schedule(origin: str, destination: str, open_maps: bool = True) -> Dict[str, Any] - Get transit schedule and next departures from one location to another.

Use this specifically for transit/bus/train queries like:
- "When's the next bus to downtown"
- "Show me the train schedule to the airport"
- "What time is the next BART to San Francisco"

NOTE: Apple Maps API does not provide programmatic access to real-time schedule data.
This tool opens Apple Maps with transit directions, where users can see:
- Next departure times
- Multiple route options
- Real-time transit updates
- Step-by-step transit directions

Args:
    origin: Starting location (can be "Current Location" or specific address)
    destination: End location (address or place name)
    open_maps: If True, automatically open Maps with transit view (default: True)

Returns:
    Dictionary with transit information and maps URL

Example:
    get_transit_schedule(
        origin="Current Location",
        destination="Downtown Berkeley"
    )

**Complete Call Example:**
```json
{
  "action": "get_transit_schedule",
  "parameters": {
    "origin": "example_value",
    "destination": "example_value"
  }
}
```

**Parameters:**
- `origin` (required)
- `destination` (required)
- `open_maps` (optional)

**Strengths:**
- Supports starting location (can be "current location" or specific address)
- Supports end location (address or place name)
- Supports if true, automatically open maps with transit view (default: true)
- Returns structured data

**Limitations:**
- May require API keys or credentials

---

### open_maps_with_route
**Purpose:** Open Apple Maps application with a specific route. Use after plan_trip_with_stops to display the route in Maps app.

**Complete Call Example:**
```json
{
  "action": "open_maps_with_route",
  "parameters": {
    "origin": "example_value",
    "destination": "example_value"
  }
}
```

**Parameters:**
- `origin` (required)
- `destination` (required)
- `stops` (optional)
- `start_navigation` (optional)

**Strengths:**
- Opens Apple Maps app directly on macOS using AppleScript
- Uses MapsAutomation class for native macOS integration
- Supports routes with multiple waypoints
- Can optionally start navigation automatically
- Falls back to URL method if AppleScript fails
- Direct integration with macOS Maps application

**Limitations:**
- macOS only
- Requires Maps app to be installed
- Waypoints limited by Maps app capabilities

---

### plan_trip_with_stops
**Purpose:** Plan a road trip with fuel and food stops. ALL parameters must be extracted from user's natural language query using LLM reasoning. Handles variations like 'LA' → 'Los Angeles, CA', '2 gas stops' → num_fuel_stops=2, 'lunch and dinner' → num_food_stops=2. Returns simple response with Maps URL - no verbose reasoning chain shown to user.

**Complete Call Example:**
```json
{
  "action": "plan_trip_with_stops",
  "parameters": {
    "origin": "example_value",
    "destination": "example_value"
  }
}
```

**Parameters:**
- `origin` (required)
- `destination` (required)
- `num_fuel_stops` (optional)
- `num_food_stops` (optional)
- `departure_time` (optional)
- `use_google_maps` (optional)
- `open_maps` (optional)
- `reasoning_context` (optional)

**Strengths:**
- LLM-driven stop location suggestions (NO hardcoded routes)
- Handles multiple fuel and food stops
- Supports departure time for traffic-aware routing
- ALWAYS returns Maps URL in https://maps.apple.com/ format (browser/UI compatible)
- URL format automatically converted from maps:// to https://maps.apple.com/ if needed
- Returns simple, clean message: 'Here's your trip, enjoy: [URL]' (no verbose reasoning chain)
- Optional automatic Maps opening (open_maps parameter)
- Apple Maps URL is default (opens in macOS Maps app, supports waypoints)
- Uses AppleScript automation (MapsAutomation) for native macOS integration
- Falls back to URL method if AppleScript fails
- Google Maps URL available as alternative (opens in browser)
- Automatic route optimization using LLM geographic knowledge
- Orchestrator extracts Maps URL to top level for easy access

**Limitations:**
- Maximum ~20 total stops (fuel + food combined) - reasonable limit, but LLM can suggest optimal number
- Stop locations determined by LLM (may vary based on route knowledge)
- Requires valid origin and destination locations
- Works for routes worldwide - no geographic limitations

---

## MICRO ACTIONS Agent (3 tools)

### copy_snippet
**Purpose:** copy_snippet(text: str) -> Dict[str, Any] - Copy text to the macOS clipboard.

    Use this tool when you need to:
    - Copy text snippets for pasting elsewhere
    - Store text temporarily in clipboard
    - Prepare content for pasting into other apps

    This is useful for:
    - Quick text copying ("copy this text")
    - Workflow automation (copy result, then paste in another app)
    - Content sharing ("copy the link to clipboard")

    Args:
        text: Text content to copy to clipboard (required)

    Returns:
        Dictionary with copy status and text details

    Examples:
        # Copy a simple text
        copy_snippet(text="Hello, world!")

        # Copy a URL
        copy_snippet(text="https://example.com")

        # Copy formatted text
        copy_snippet(text="Meeting Notes
- Item 1
- Item 2")

**Complete Call Example:**
```json
{
  "action": "copy_snippet",
  "parameters": {
    "text": "example_value"
  }
}
```

**Parameters:**
- `text` (required)

**Strengths:**
- Supports text content to copy to clipboard (required)
- Returns structured data

**Limitations:**
- macOS only

---

### launch_app
**Purpose:** launch_app(app_name: str) -> Dict[str, Any] - Launch a macOS application by name.

Use this tool when you need to:
- Open an application quickly
- Start a specific app (e.g., "Safari", "Notes", "Calculator")
- Launch apps without navigating through Finder

This is useful for:
- Quick app access ("launch Safari")
- Workflow automation ("open Notes before writing")
- App switching ("launch Calculator")

Args:
    app_name: Name of the application to launch (e.g., "Safari", "Notes", "Calculator", "Mail")
              Can be the app name without .app extension

Returns:
    Dictionary with launch status and app details

Examples:
    # Launch Safari
    launch_app(app_name="Safari")

    # Launch Notes
    launch_app(app_name="Notes")

    # Launch Calculator
    launch_app(app_name="Calculator")

**Complete Call Example:**
```json
{
  "action": "launch_app",
  "parameters": {
    "app_name": "example_value"
  }
}
```

**Parameters:**
- `app_name` (required)

**Strengths:**
- Supports name of the application to launch (e.g., "safari", "notes", "calculator", "mail")
- Returns structured data

**Limitations:**
- macOS only

---

### set_timer
**Purpose:** set_timer(duration_minutes: float, message: Optional[str] = None) -> Dict[str, Any] - Set a timer that will notify you when it expires.

Use this tool when you need to:
- Set a reminder after a specific duration
- Get notified when time is up
- Create time-based alerts

This is useful for:
- Pomodoro timers ("set a 25 minute timer")
- Reminders ("remind me in 10 minutes")
- Time tracking ("set a 30 minute timer for this task")

Args:
    duration_minutes: Duration in minutes (can be decimal, e.g., 0.5 for 30 seconds)
    message: Optional message to display when timer expires (default: "Timer expired")

Returns:
    Dictionary with timer status and details

Examples:
    # Simple 5 minute timer
    set_timer(duration_minutes=5.0)

    # 25 minute Pomodoro timer with message
    set_timer(duration_minutes=25.0, message="Pomodoro session complete!")

    # 30 second quick timer
    set_timer(duration_minutes=0.5, message="Quick reminder")

**Complete Call Example:**
```json
{
  "action": "set_timer",
  "parameters": {
    "duration_minutes": "example_value"
  }
}
```

**Parameters:**
- `duration_minutes` (required)
- `message` (optional)

**Strengths:**
- Supports duration in minutes (can be decimal, e.g., 0.5 for 30 seconds)
- Supports optional message to display when timer expires (default: "timer expired")
- Returns structured data

**Limitations:**
- See tool documentation for specific constraints

---

## NOTIFICATIONS Agent (1 tools)

### send_notification
**Purpose:** send_notification(title: str, message: str, sound: Optional[str] = None, subtitle: Optional[str] = None) -> Dict[str, Any] - Send a system notification via macOS Notification Center.

Use this tool when you need to:
- Alert the user of task completion
- Notify about important events or errors
- Send time-sensitive updates
- Display status messages

This is useful for:
- Background task completion (e.g., "Report generated successfully")
- Error notifications (e.g., "Failed to send email")
- Progress updates (e.g., "File processing complete")
- Reminders and alerts

Args:
    title: Notification title (required, shown in bold)
    message: Notification body text (required, main content)
    sound: Optional sound name (e.g., "default", "Glass", "Hero", "Submarine")
           Use None for silent notification
    subtitle: Optional subtitle (shown between title and message)

Returns:
    Dictionary with status and notification details

Examples:
    # Simple notification
    send_notification(
        title="Task Complete",
        message="Your stock report has been generated"
    )

    # With sound
    send_notification(
        title="Email Sent",
        message="Message delivered to recipient",
        sound="Glass"
    )

    # With subtitle
    send_notification(
        title="Automation Update",
        subtitle="Trip Planning",
        message="Your LA to Phoenix route is ready",
        sound="default"
    )

Available sounds: default, Basso, Blow, Bottle, Frog, Funk, Glass, Hero,
                 Morse, Ping, Pop, Purr, Sosumi, Submarine, Tink

**Complete Call Example:**
```json
{
  "action": "send_notification",
  "parameters": {
    "title": "Example Title",
    "message": "example_value"
  }
}
```

**Parameters:**
- `title` (required)
- `message` (required)
- `sound` (optional)
- `subtitle` (optional)

**Strengths:**
- Supports notification title (required, shown in bold)
- Supports notification body text (required, main content)
- Supports optional sound name (e.g., "default", "glass", "hero", "submarine")
- Supports optional subtitle (shown between title and message)
- Returns structured data

**Limitations:**
- macOS only

---

## PRESENTATION Agent (3 tools)

### create_keynote
**Purpose:** Create Keynote presentations from text content

**Complete Call Example:**
```json
{
  "action": "create_keynote",
  "parameters": {
    "title": "Example Title",
    "content": "example content"
  }
}
```

**Parameters:**
- `title` (required)
- `content` (required)
- `output_path` (optional)

**Strengths:**
- Generates structured slides from text
- Automatic layout
- macOS Keynote integration

**Limitations:**
- macOS Keynote required
- Basic layouts only
- Text-based slides only (no images)

---

### create_keynote_with_images
**Purpose:** Create Keynote presentations with images/screenshots as slides. Use this when user wants to display screenshots or images in a presentation.

**Complete Call Example:**
```json
{
  "action": "create_keynote_with_images",
  "parameters": {
    "title": "Example Title",
    "image_paths": "/path/to/example"
  }
}
```

**Parameters:**
- `title` (required)
- `image_paths` (required)
- `content` (optional)
- `output_path` (optional)

**Strengths:**
- Creates slides with screenshots/images
- Each image becomes a full slide
- Perfect for displaying document pages
- macOS Keynote integration
- Accepts list of image paths from previous steps

**Limitations:**
- macOS Keynote required
- One image per slide
- No text overlays on images

---

### create_pages_doc
**Purpose:** Create Pages documents from content

**Complete Call Example:**
```json
{
  "action": "create_pages_doc",
  "parameters": {
    "title": "Example Title",
    "content": "example content"
  }
}
```

**Parameters:**
- `title` (required)
- `content` (required)
- `output_path` (optional)

**Strengths:**
- Formatted document creation
- macOS Pages integration
- Preserves text structure

**Limitations:**
- macOS Pages required
- Basic formatting only
- No advanced styling

---

## REDDIT Agent (1 tools)

### scan_subreddit_posts
**Purpose:** scan_subreddit_posts(subreddit: 'str', instruction: 'Optional[str]' = None, sort: 'str' = 'hot', limit_posts: 'int' = 10, include_comments: 'bool' = True, comments_limit: 'int' = 5, comment_threads_limit: 'Optional[int]' = None, headless: 'Optional[bool]' = None) -> 'Dict[str, Any]' - Crawl a subreddit, returning structured post/comment data (and optional summary).

Args:
    subreddit: Target subreddit (e.g., "startups", "SideProject")
    instruction: Optional natural-language question to summarize results
    sort: Reddit sort key ("hot", "new", "top", "rising", "controversial")
    limit_posts: Number of posts to return (default 10)
    include_comments: When True, fetch top-level comments for each post
    comments_limit: Max comments per post (default 5)
    comment_threads_limit: Limit how many posts include comment scraping
    headless: Override headless browser setting

**Complete Call Example:**
```json
{
  "action": "scan_subreddit_posts",
  "parameters": {
    "subreddit": "example_value"
  }
}
```

**Parameters:**
- `subreddit` (required)
- `instruction` (optional)
- `sort` (optional)
- `limit_posts` (optional)
- `include_comments` (optional)
- `comments_limit` (optional)
- `comment_threads_limit` (optional)
- `headless` (optional)

**Strengths:**
- Supports target subreddit (e.g., "startups", "sideproject")
- Supports optional natural-language question to summarize results
- Supports reddit sort key ("hot", "new", "top", "rising", "controversial")
- Supports number of posts to return (default 10)
- Supports when true, fetch top-level comments for each post

**Limitations:**
- May require API keys or credentials

---

## REPORT Agent (2 tools)

### create_local_document_report
**Purpose:** create_local_document_report(topic: str, query: Optional[str] = None, max_documents: int = 2, min_similarity: float = 0.5, output_name: Optional[str] = None) -> Dict[str, Any] - Create a PDF report using ONLY locally stored documents (RAG workflow).

Steps:
1. Search configured document folders for content related to the topic
2. Require a matching file (reject if nothing relevant is found)
3. Summarize the retrieved text with strict "no outside knowledge" rules
4. Produce a short PDF report that cites the local sources

Returns error if no local files match the request or if summarization fails.

**Complete Call Example:**
```json
{
  "action": "create_local_document_report",
  "parameters": {
    "topic": "example_value"
  }
}
```

**Parameters:**
- `topic` (required)
- `query` (optional)
- `max_documents` (optional)
- `min_similarity` (optional)
- `output_name` (optional)

**Strengths:**
- Creates content
- Searches for information

**Limitations:**
- create_local_document_report(topic: str, query: Optional[str] = None, max_documents: int = 2, min_similarity: float = 0.5, output_name: Optional[str] = None) -> Dict[str, Any] - Create a PDF report using ONLY locally stored documents (RAG workflow)

---

### create_stock_report
**Purpose:** create_stock_report(company: str, ticker: Optional[str] = None, include_analysis: bool = True, output_name: Optional[str] = None) -> Dict[str, Any] - Create a comprehensive stock report with chart and analysis for any company.

This is a HIGH-LEVEL tool that orchestrates the entire stock report workflow:
1. Resolves stock ticker (if not provided)
2. Detects if company is publicly traded
3. Fetches stock data
4. Captures stock chart (Mac Stocks app or web fallback)
5. Generates AI analysis
6. Creates PDF report with embedded chart

Use this when the user requests:
- "Create a report on [company] stock"
- "Generate stock analysis for [company]"
- "I need a report about [company] stock price"

Args:
    company: Company name (e.g., "Microsoft", "Bosch", "Apple")
    ticker: Optional ticker symbol (if known)
    include_analysis: Whether to include AI-generated analysis (default: True)
    output_name: Optional custom filename for report

Returns:
    Dictionary with report_path (PDF), chart_path, and generation status

Examples:
    create_stock_report("Microsoft")  # Auto-resolves to MSFT
    create_stock_report("Bosch")  # Detects if public/private
    create_stock_report(company="Apple", ticker="AAPL")  # Explicit ticker

**Complete Call Example:**
```json
{
  "action": "create_stock_report",
  "parameters": {
    "company": "example_value"
  }
}
```

**Parameters:**
- `company` (required)
- `ticker` (optional)
- `include_analysis` (optional)
- `output_name` (optional)

**Strengths:**
- the user requests:
- "Create a report on [company] stock"
- "Generate stock analysis for [company]"
- "I need a report about [company] stock price"
- Supports company name (e.g., "microsoft", "bosch", "apple")

**Limitations:**
- macOS only

---

## SCREEN Agent (1 tools)

### capture_screenshot
**Purpose:** capture_screenshot(app_name: Optional[str] = None, output_name: Optional[str] = None, mode: str = 'full', window_title: Optional[str] = None, region: Optional[Dict[str, int]] = None) -> Dict[str, Any] - Capture a screenshot of the screen, window, or region.

SCREEN AGENT - LEVEL 1: Universal Screen Capture
Use this to capture ANY visible content on screen.

Works for:
- Stock app (app_name="Stocks", mode="focused")
- Safari or any browser (app_name="Safari", mode="focused")
- Calculator (app_name="Calculator", mode="focused")
- Any macOS application window
- Specific screen regions (mode="region")
- Entire screen (mode="full")

Args:
    app_name: Name of application to capture (e.g., "Stocks", "Safari", "Calculator")
             Used for focused window capture
    output_name: Optional custom name for screenshot file
    mode: Capture mode - "full" (entire screen), "focused" (app window), "region" (specific coords)
    window_title: Optional window title filter (best-effort)
    region: For mode="region", dict with x, y, width, height keys

Returns:
    Dictionary with screenshot_path, app_name, mode, and success status

Examples:
    capture_screenshot(app_name="Stocks", mode="focused")  # Capture Stock app window only
    capture_screenshot(app_name="Safari", mode="focused")  # Capture browser window only
    capture_screenshot(mode="region", region={"x": 100, "y": 100, "width": 800, "height": 600})  # Capture specific area
    capture_screenshot()  # Capture entire screen

IMPORTANT:
- For focused windows: Use mode="focused" with app_name for precise window capture
- For stock prices: Use app_name="Stocks", mode="focused"
- For web pages: Use app_name="Safari", mode="focused"
- For regions: Use mode="region" with region parameter
- The app must be visible/open on screen (tool activates it automatically)
- Falls back gracefully if focused capture unavailable

**Complete Call Example:**
```json
{
  "action": "capture_screenshot",
  "parameters": {
  }
}
```

**Parameters:**
- `app_name` (optional)
- `output_name` (optional)
- `mode` (optional)
- `window_title` (optional)
- `region` (optional)

**Strengths:**
- Supports name of application to capture (e.g., "stocks", "safari", "calculator")
- Supports optional custom name for screenshot file
- Supports capture mode - "full" (entire screen), "focused" (app window), "region" (specific coords)
- Supports optional window title filter (best-effort)
- Supports for mode="region", dict with x, y, width, height keys

**Limitations:**
- Works for:
- Stock app (app_name="Stocks", mode="focused")
- Safari or any browser (app_name="Safari", mode="focused")
- Calculator (app_name="Calculator", mode="focused")
- Any macOS application window
- Specific screen regions (mode="region")
- Entire screen (mode="full")

Args:
    app_name: Name of application to capture (e.g., "Stocks", "Safari", "Calculator")
             Used for focused window capture
    output_name: Optional custom name for screenshot file
    mode: Capture mode - "full" (entire screen), "focused" (app window), "region" (specific coords)
    window_title: Optional window title filter (best-effort)
    region: For mode="region", dict with x, y, width, height keys

Returns:
    Dictionary with screenshot_path, app_name, mode, and success status

Examples:
    capture_screenshot(app_name="Stocks", mode="focused")  # Capture Stock app window only
    capture_screenshot(app_name="Safari", mode="focused")  # Capture browser window only
    capture_screenshot(mode="region", region={"x": 100, "y": 100, "width": 800, "height": 600})  # Capture specific area
    capture_screenshot()  # Capture entire screen

IMPORTANT:
- For focused windows: Use mode="focused" with app_name for precise window capture
- For stock prices: Use app_name="Stocks", mode="focused"
- For web pages: Use app_name="Safari", mode="focused"
- For regions: Use mode="region" with region parameter
- The app must be visible/open on screen (tool activates it automatically)
- Falls back gracefully if focused capture unavailable

---

## STOCK Agent (5 tools)

### capture_stock_chart
**Purpose:** capture_stock_chart(symbol: str, output_name: Optional[str] = None, use_web_fallback: bool = True) -> Dict[str, Any] - Capture a screenshot of stock chart with automatic fallback options.

This tool provides multiple chart capture methods:
1. PRIMARY: Mac Stocks app (fast, native, works for major stocks)
2. FALLBACK: Yahoo Finance web chart (works for all symbols including international)

Use this when you need a visual chart/graph of a stock for presentations or reports.

Args:
    symbol: Stock ticker symbol (e.g., 'NVDA', 'AAPL', 'TSLA', 'BOSCHLTD.NS')
    output_name: Optional custom name for screenshot file
    use_web_fallback: If True, tries web capture if Mac Stocks fails (default: True)

Returns:
    Dictionary with screenshot path and capture method used

Examples:
    capture_stock_chart("NVDA")  # Capture Nvidia chart from Stocks app
    capture_stock_chart("BOSCHLTD.NS")  # International stock, uses web fallback
    capture_stock_chart("AAPL", "apple_analysis")  # Custom name

**Complete Call Example:**
```json
{
  "action": "capture_stock_chart",
  "parameters": {
    "symbol": "example_value"
  }
}
```

**Parameters:**
- `symbol` (required)
- `output_name` (optional)
- `use_web_fallback` (optional)

**Strengths:**
- you need a visual chart/graph of a stock for presentations or reports.
- Supports stock ticker symbol (e.g., 'nvda', 'aapl', 'tsla', 'boschltd.ns')
- Supports optional custom name for screenshot file
- Supports if true, tries web capture if mac stocks fails (default: true)
- Returns structured data

**Limitations:**
- macOS only

---

### compare_stocks
**Purpose:** compare_stocks(symbols: list) -> Dict[str, Any] - Compare multiple stocks side by side.

Use this when you need to:
- Compare performance of multiple stocks
- Analyze multiple companies at once
- Get comparative stock data

Args:
    symbols: List of stock ticker symbols (e.g., ['AAPL', 'MSFT', 'GOOGL'])

Returns:
    Dictionary with comparison data

Example:
    compare_stocks(['AAPL', 'MSFT', 'GOOGL'])

**Complete Call Example:**
```json
{
  "action": "compare_stocks",
  "parameters": {
    "symbols": "example_value"
  }
}
```

**Parameters:**
- `symbols` (required)

**Strengths:**
- you need to:
- Compare performance of multiple stocks
- Analyze multiple companies at once
- Get comparative stock data
- Supports list of stock ticker symbols (e.g., ['aapl', 'msft', 'googl'])

**Limitations:**
- See tool documentation for specific constraints

---

### get_stock_history
**Purpose:** get_stock_history(symbol: str, period: str = '1mo', reasoning_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any] - Get historical stock price data for a given ticker symbol.

Use this when you need to:
- See stock price trends over time
- Get historical price data
- Analyze stock performance over a period

Args:
    symbol: Stock ticker symbol (e.g., 'AAPL')
    period: Time period - "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"
    reasoning_context: Optional memory context for learning from past attempts

Returns:
    Dictionary with historical price data

Example:
    get_stock_history("AAPL", "1mo")  # Apple stock for last month

**Complete Call Example:**
```json
{
  "action": "get_stock_history",
  "parameters": {
    "symbol": "example_value"
  }
}
```

**Parameters:**
- `symbol` (required)
- `period` (optional)
- `reasoning_context` (optional)

**Strengths:**
- you need to:
- See stock price trends over time
- Get historical price data
- Analyze stock performance over a period
- Supports stock ticker symbol (e.g., 'aapl')

**Limitations:**
- See tool documentation for specific constraints

---

### get_stock_price
**Purpose:** get_stock_price(symbol: str) -> Dict[str, Any] - Get current stock price and basic information for a given ticker symbol.

Use this when you need to:
- Find the current price of a stock
- Get basic stock information (company name, market cap, etc.)
- Check today's stock performance

Args:
    symbol: Stock ticker symbol (e.g., 'AAPL' for Apple, 'GOOGL' for Google)

Returns:
    Dictionary with current price, change, volume, and other details

Example:
    get_stock_price("AAPL")  # Get Apple stock price
    get_stock_price("TSLA")  # Get Tesla stock price

**Complete Call Example:**
```json
{
  "action": "get_stock_price",
  "parameters": {
    "symbol": "example_value"
  }
}
```

**Parameters:**
- `symbol` (required)

**Strengths:**
- you need to:
- Find the current price of a stock
- Check today's stock performance
- Get basic stock information (company name
- Supports stock ticker symbol (e.g., 'aapl' for apple, 'googl' for google)

**Limitations:**
- See tool documentation for specific constraints

---

### search_stock_symbol
**Purpose:** search_stock_symbol(query: str, use_web_fallback: bool = True, reasoning_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any] - Search for stock ticker symbols by company name with intelligent web fallback.

This tool provides multi-level ticker resolution:
1. Checks local cache of common tickers
2. Falls back to web search if not found
3. Detects if company is publicly traded or private

Use this when you need to:
- Find the ticker symbol for ANY company
- Determine if a company is publicly traded
- Search for international stock symbols
- Handle ambiguous company names

Args:
    query: Company name or search query (e.g., "Apple", "Bosch", "Microsoft")
    use_web_fallback: Whether to use web search if local lookup fails (default: True)
    reasoning_context: Optional memory context for learning from past attempts

Returns:
    Dictionary with stock symbol, company info, or indication if private company

Example:
    search_stock_symbol("Apple")  # Find AAPL
    search_stock_symbol("Bosch")  # Find BOSCHLTD.NS or detect private
    search_stock_symbol("Tesla")  # Find TSLA

**Complete Call Example:**
```json
{
  "action": "search_stock_symbol",
  "parameters": {
    "query": "example search query"
  }
}
```

**Parameters:**
- `query` (required)
- `use_web_fallback` (optional)
- `reasoning_context` (optional)

**Strengths:**
- you need to:
- Find the ticker symbol for ANY company
- Determine if a company is publicly traded
- Search for international stock symbols
- Handle ambiguous company names

**Limitations:**
- See tool documentation for specific constraints

---

## TWITTER Agent (2 tools)

### summarize_list_activity
**Purpose:** summarize_list_activity(list_name: 'Optional[str]' = None, lookback_hours: 'Optional[int]' = None, max_items: 'Optional[int]' = None) -> 'Dict[str, Any]' - Summarize top tweets/threads from a configured Twitter List.

Args:
    list_name: Logical list key defined in config.yaml -> twitter.lists
        (defaults to twitter.default_list when omitted).
    lookback_hours: Time window to inspect (defaults to twitter.default_lookback_hours or 24).
    max_items: Maximum tweets/threads to highlight (defaults to twitter.max_summary_items or 5, max 10 overall).

**Complete Call Example:**
```json
{
  "action": "summarize_list_activity",
  "parameters": {
  }
}
```

**Parameters:**
- `list_name` (optional)
- `lookback_hours` (optional)
- `max_items` (optional)

**Strengths:**
- Supports logical list key defined in config.yaml -> twitter.lists
- Supports time window to inspect (defaults to twitter.default_lookback_hours or 24).
- Supports maximum tweets/threads to highlight (defaults to twitter.max_summary_items or 5, max 10 overall).

**Limitations:**
- May require API keys or credentials

---

### tweet_message
**Purpose:** tweet_message(message: 'str') -> 'Dict[str, Any]' - Publish a tweet with the provided message (must fit Twitter limits).

**Complete Call Example:**
```json
{
  "action": "tweet_message",
  "parameters": {
    "message": "example_value"
  }
}
```

**Parameters:**
- `message` (required)

**Strengths:**
- Provides functionality for the requested operation

**Limitations:**
- See tool documentation for specific constraints

---

## VOICE Agent (2 tools)

### text_to_speech
**Purpose:** text_to_speech(text: str, voice: str = 'alloy', output_path: Optional[str] = None, speed: float = 1.0) -> Dict[str, Any] - Convert text to speech audio using OpenAI TTS API.

Use this tool when you need to:
- Generate audio from text
- Create voice responses
- Convert text content to speech

This is useful for:
- Generating voice responses for user queries
- Creating audio versions of text content
- Building voice-enabled interactions

Args:
    text: Text to convert to speech (required, max ~4000 characters)
    voice: Voice to use - "alloy", "echo", "fable", "onyx", "nova", "shimmer" (default: "alloy")
    output_path: Optional path to save audio file. If None, saves to data/audio/ directory
    speed: Speech speed multiplier (0.25 to 4.0, default: 1.0)

Returns:
    Dictionary with audio file path and metadata

Examples:
    # Generate speech from text
    text_to_speech(text="Hello, this is a test message")

    # Use specific voice
    text_to_speech(text="Hello world", voice="nova")

    # Save to specific location
    text_to_speech(text="Hello", output_path="/path/to/output.mp3")

**Complete Call Example:**
```json
{
  "action": "text_to_speech",
  "parameters": {
    "text": "example_value"
  }
}
```

**Parameters:**
- `text` (required)
- `voice` (optional)
- `output_path` (optional)
- `speed` (optional)

**Strengths:**
- Supports text to convert to speech (required, max ~4000 characters)
- Supports voice to use - "alloy", "echo", "fable", "onyx", "nova", "shimmer" (default: "alloy")
- Supports optional path to save audio file. if none, saves to data/audio/ directory
- Supports speech speed multiplier (0.25 to 4.0, default: 1.0)
- Returns structured data

**Limitations:**
- May require API keys or credentials

---

### transcribe_audio_file
**Purpose:** transcribe_audio_file(audio_file_path: str, language: Optional[str] = None) -> Dict[str, Any] - Transcribe an audio file to text using OpenAI Whisper API.

Use this tool when you need to:
- Convert speech from audio files to text
- Process voice recordings
- Extract text from audio content

This is useful for:
- Transcribing voice memos or recordings
- Processing audio files for content extraction
- Converting speech to text for further processing

Args:
    audio_file_path: Path to the audio file to transcribe (supports: mp3, mp4, mpeg, mpga, m4a, wav, webm)
    language: Optional language code (e.g., "en", "es", "fr"). If None, auto-detects language.

Returns:
    Dictionary with transcribed text and metadata

Examples:
    # Transcribe an audio file
    transcribe_audio_file(audio_file_path="/path/to/recording.mp3")

    # Transcribe with specific language
    transcribe_audio_file(audio_file_path="/path/to/recording.wav", language="en")

**Complete Call Example:**
```json
{
  "action": "transcribe_audio_file",
  "parameters": {
    "audio_file_path": "/path/to/example"
  }
}
```

**Parameters:**
- `audio_file_path` (required)
- `language` (optional)

**Strengths:**
- Supports path to the audio file to transcribe (supports: mp3, mp4, mpeg, mpga, m4a, wav, webm)
- Supports optional language code (e.g., "en", "es", "fr"). if none, auto-detects language.
- Returns structured data

**Limitations:**
- May require API keys or credentials

---

## WRITING Agent (7 tools)

### compose_professional_email
**Purpose:** compose_professional_email(purpose: str, context: str, recipient: str = 'recipient', writing_brief: Optional[Dict[str, Any]] = None) -> Dict[str, Any] - Compose a professional email with appropriate tone and structure.

WRITING AGENT - LEVEL 5: Email Composition
Use this to draft professional emails, follow-ups, or announcements.

This tool uses LLM to:
- Structure email with proper greeting, body, and closing
- Match appropriate tone for the context
- Include relevant details from context
- Apply writing brief requirements (tone, must-include facts)

Args:
    purpose: The purpose of the email (e.g., "follow-up on meeting", "request information", "share report")
    context: Background information or content to include in the email
    recipient: Name or role of the recipient (e.g., "John Smith", "team", "client")
    writing_brief: Optional writing brief as dictionary

Returns:
    Dictionary with email_subject, email_body, tone, and word_count

Example:
    compose_professional_email(
        purpose="Share quarterly analysis report",
        context="$step2.report_content",
        recipient="Executive Team",
        writing_brief="$step0.writing_brief"
    )

**Complete Call Example:**
```json
{
  "action": "compose_professional_email",
  "parameters": {
    "purpose": "example_value",
    "context": "example_value"
  }
}
```

**Parameters:**
- `purpose` (required)
- `context` (required)
- `recipient` (optional)
- `writing_brief` (optional)

**Strengths:**
- Supports the purpose of the email (e.g., "follow-up on meeting", "request information", "share report")
- Supports background information or content to include in the email
- Supports name or role of the recipient (e.g., "john smith", "team", "client")
- Supports optional writing brief as dictionary
- Returns structured data

**Limitations:**
- See tool documentation for specific constraints

---

### create_detailed_report
**Purpose:** create_detailed_report(content: str, title: str, report_style: str = 'business', include_sections: Optional[List[str]] = None, writing_brief: Optional[Dict[str, Any]] = None) -> Dict[str, Any] - Transform content into a detailed, well-structured report with long-form writing.

WRITING AGENT - LEVEL 3: Report Writing
Use this to create comprehensive reports with detailed analysis and explanations.

⚠️  CRITICAL: This tool returns REPORT TEXT, not a file path!
- If you need to EMAIL the report, you MUST first save it using create_pages_doc
- CORRECT workflow: create_detailed_report → create_pages_doc → compose_email(attachments=["$stepN.pages_path"])
- WRONG: compose_email(attachments=["$stepN.report_content"]) ← report_content is TEXT not a FILE PATH!

This tool uses LLM to:
- Expand and elaborate on key points
- Add context and explanations
- Structure content into logical sections
- Use professional, flowing prose
- Include transitions and narrative flow
- Apply writing brief requirements (tone, audience, must-include facts/data)

Args:
    content: Source content to transform into a report
    title: Report title
    report_style: Writing style for the report:
        - "business": Professional, action-oriented (default)
        - "academic": Formal, analytical, citation-focused
        - "technical": Detailed, precise, specification-focused
        - "executive": High-level, strategic, concise
    include_sections: Optional list of sections to include
        (e.g., ["Executive Summary", "Analysis", "Recommendations"])
        If None, sections are auto-generated based on content
    writing_brief: Optional writing brief as dictionary

Returns:
    Dictionary with report_content (TEXT string), sections (array), word_count (number)
    ⚠️  report_content is TEXT, NOT a file path - use create_pages_doc to save it

Example:
    # With writing brief (recommended)
    create_detailed_report(
        content="$step1.synthesized_content",
        title="NVDA Q4 2024 Analysis",
        report_style="business",
        include_sections=["Executive Summary", "Financial Performance", "Market Position", "Recommendations"],
        writing_brief="$step0.writing_brief"
    )

    # Without brief (legacy mode)
    create_detailed_report(
        content="$step1.synthesized_content",
        title="Annual Security Audit Report",
        report_style="technical",
        include_sections=["Executive Summary", "Findings", "Recommendations"]
    )

**Complete Call Example:**
```json
{
  "action": "create_detailed_report",
  "parameters": {
    "content": "example content",
    "title": "Example Title"
  }
}
```

**Parameters:**
- `content` (required)
- `title` (required)
- `report_style` (optional)
- `include_sections` (optional)
- `writing_brief` (optional)

**Strengths:**
- Supports source content to transform into a report
- Supports report title
- Supports writing style for the report:
- Supports professional, action-oriented (default)
- Supports formal, analytical, citation-focused

**Limitations:**
- May require API keys or credentials

---

### create_meeting_notes
**Purpose:** create_meeting_notes(content: str, meeting_title: str, attendees: Optional[List[str]] = None, include_action_items: bool = True) -> Dict[str, Any] - Transform content into structured meeting notes with action items.

WRITING AGENT - LEVEL 4: Note-Taking
Use this to create organized meeting notes from transcripts or rough notes.

This tool uses LLM to:
- Extract key discussion points
- Identify decisions made
- Extract action items and owners
- Organize chronologically or by topic
- Format in professional note-taking structure

Args:
    content: Source content (meeting transcript, rough notes, etc.)
    meeting_title: Title/topic of the meeting
    attendees: Optional list of attendee names
    include_action_items: Whether to extract and highlight action items (default: True)

Returns:
    Dictionary with formatted_notes, discussion_points, decisions, action_items

Example:
    create_meeting_notes(
        content="$step1.extracted_text",
        meeting_title="Q1 Planning Meeting",
        attendees=["Alice", "Bob", "Charlie"],
        include_action_items=True
    )

**Complete Call Example:**
```json
{
  "action": "create_meeting_notes",
  "parameters": {
    "content": "example content",
    "meeting_title": "Example Title"
  }
}
```

**Parameters:**
- `content` (required)
- `meeting_title` (required)
- `attendees` (optional)
- `include_action_items` (optional)

**Strengths:**
- Supports source content (meeting transcript, rough notes, etc.)
- Supports title/topic of the meeting
- Supports optional list of attendee names
- Supports whether to extract and highlight action items (default: true)
- Returns structured data

**Limitations:**
- May require API keys or credentials

---

### create_quick_summary
**Purpose:** create_quick_summary(content: str, topic: str, max_sentences: int = 3, writing_brief: Optional[Dict[str, Any]] = None) -> Dict[str, Any] - Create a quick, conversational summary for simple/short-answer requests.

WRITING AGENT - LEVEL 0.5: Lightweight Reply Path
Use this for brief, conversational responses when user wants a quick answer.

This tool uses LLM to:
- Extract the most important point(s)
- Format in clear, conversational language
- Keep it brief and to-the-point
- Skip heavy formatting or structure

Args:
    content: Source content to summarize
    topic: Topic to focus on
    max_sentences: Maximum sentences in summary (default: 3)
    writing_brief: Optional writing brief as dictionary

Returns:
    Dictionary with summary, tone, and word_count

Example:
    create_quick_summary(
        content="$step1.extracted_text",
        topic="What is Claude AI?",
        max_sentences=2,
        writing_brief="$step0.writing_brief"
    )

**Complete Call Example:**
```json
{
  "action": "create_quick_summary",
  "parameters": {
    "content": "example content",
    "topic": "example_value"
  }
}
```

**Parameters:**
- `content` (required)
- `topic` (required)
- `max_sentences` (optional)
- `writing_brief` (optional)

**Strengths:**
- Supports source content to summarize
- Supports topic to focus on
- Supports maximum sentences in summary (default: 3)
- Supports optional writing brief as dictionary
- Returns structured data

**Limitations:**
- See tool documentation for specific constraints

---

### create_slide_deck_content
**Purpose:** create_slide_deck_content(content: str, title: str, num_slides: Optional[int] = None, writing_brief: Optional[Dict[str, Any]] = None) -> Dict[str, Any] - Transform content into concise, bullet-point format optimized for slide decks.

WRITING AGENT - LEVEL 2: Slide Deck Writing
Use this to create presentation-ready content with concise bullets.

This tool uses LLM to:
- Extract key messages and talking points
- Format content as concise bullet points
- Organize into logical slides
- Remove verbose language and focus on impact
- Ensure each slide has a clear message
- Apply writing brief requirements (tone, audience, must-include facts/data)

Args:
    content: Source content to transform (can be from synthesis or extraction)
    title: Presentation title/topic
    num_slides: Target number of slides (None = auto-determine based on content, typically 5-10)
    writing_brief: Optional writing brief as dictionary

Returns:
    Dictionary with slides (list of slide objects), total_slides, and formatted_content

Example:
    # With writing brief (recommended)
    create_slide_deck_content(
        content="$step1.synthesized_content",
        title="Q4 Marketing Strategy",
        num_slides=7,
        writing_brief="$step0.writing_brief"
    )

    # Without brief (legacy mode)
    create_slide_deck_content(
        content="$step1.synthesized_content",
        title="Q4 Marketing Strategy",
        num_slides=5
    )

**Complete Call Example:**
```json
{
  "action": "create_slide_deck_content",
  "parameters": {
    "content": "example content",
    "title": "Example Title"
  }
}
```

**Parameters:**
- `content` (required)
- `title` (required)
- `num_slides` (optional)
- `writing_brief` (optional)

**Strengths:**
- Supports source content to transform (can be from synthesis or extraction)
- Supports presentation title/topic
- Supports target number of slides (none = auto-determine based on content, typically 5-10)
- Supports optional writing brief as dictionary
- Returns structured data

**Limitations:**
- May require API keys or credentials

---

### prepare_writing_brief
**Purpose:** prepare_writing_brief(user_request: str, deliverable_type: str = 'general', upstream_artifacts: Optional[Dict[str, Any]] = None, context_hints: Optional[Dict[str, Any]] = None, session_context: Optional[src.memory.session_memory.SessionContext] = None) -> Dict[str, Any] - Analyze user request and context to create a structured writing brief.

WRITING AGENT - LEVEL 0: Brief Preparation
Use this before any writing task to extract intent, tone, audience, and required data.

This tool uses LLM to:
- Parse user intent and extract writing requirements
- Identify tone, audience, and style preferences
- Extract must-include facts and data from context
- Set appropriate constraints based on deliverable type

Args:
    user_request: The original user request or task description
    deliverable_type: Type of deliverable (report, deck, email, summary, narrative)
    upstream_artifacts: Dictionary of results from prior steps (e.g., search results, extracted data)
    context_hints: Additional context (e.g., {"timeframe": "Q4 2024", "project": "Marketing"})
    session_context: Optional SessionContext for auto-populating brief from memory

Returns:
    Dictionary with writing_brief (as dict), analysis, and confidence_score

Example:
    prepare_writing_brief(
        user_request="Create a report on NVDA stock performance with Q4 earnings",
        deliverable_type="report",
        upstream_artifacts={"$step1.stock_data": {...}, "$step2.news": [...]},
        session_context="$step0.session_context"
    )

**Complete Call Example:**
```json
{
  "action": "prepare_writing_brief",
  "parameters": {
    "user_request": "example_value"
  }
}
```

**Parameters:**
- `user_request` (required)
- `deliverable_type` (optional)
- `upstream_artifacts` (optional)
- `context_hints` (optional)
- `session_context` (optional)

**Strengths:**
- Supports the original user request or task description
- Supports type of deliverable (report, deck, email, summary, narrative)
- Supports dictionary of results from prior steps (e.g., search results, extracted data)
- Supports additional context (e.g., {"timeframe": "q4 2024", "project": "marketing"})
- Supports optional sessioncontext for auto-populating brief from memory

**Limitations:**
- See tool documentation for specific constraints

---

### synthesize_content
**Purpose:** synthesize_content(source_contents: List[str], topic: Optional[str] = None, synthesis_style: str = 'comprehensive', writing_brief: Optional[Dict[str, Any]] = None, session_context: Optional[src.memory.session_memory.SessionContext] = None, reasoning_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any] - Synthesize information from multiple sources into cohesive content.

WRITING AGENT - LEVEL 1: Content Synthesis
Use this to combine and analyze information from different sources.

⚠️  CRITICAL: This tool returns SYNTHESIZED TEXT, not a file path!
- If you need to EMAIL the synthesized content, you MUST first save it using create_pages_doc
- CORRECT workflow: synthesize_content → create_pages_doc → compose_email(attachments=["$stepN.pages_path"])
- WRONG: compose_email(attachments=["$stepN.synthesized_content"]) ← This is TEXT not a FILE PATH!

This tool uses LLM to:
- Identify key themes and patterns across sources
- Remove redundancy and contradictions
- Create a unified narrative
- Preserve important details and citations
- Apply writing brief requirements (tone, audience, must-include facts/data)

Args:
    source_contents: List of text contents to synthesize (from documents, web pages, etc.)
    topic: The main topic or focus for synthesis (auto-derived from session_context if not provided)
    synthesis_style: How to synthesize the content:
        - "comprehensive": Include all important details (for reports)
        - "concise": Focus on key points only (for summaries)
        - "comparative": Highlight differences and similarities
        - "chronological": Organize by timeline/sequence
    writing_brief: Optional writing brief as dictionary
        Use prepare_writing_brief first to create this
    session_context: Optional SessionContext for auto-populating topic and context

Returns:
    Dictionary with synthesized_content (TEXT string), key_points, sources_used, word_count
    ⚠️  synthesized_content is TEXT, NOT a file path - use create_pages_doc to save it

Example:
    # With session context (recommended for context-aware synthesis)
    synthesize_content(
        source_contents=["$step1.extracted_text", "$step2.content"],
        session_context="$step0.session_context",
        synthesis_style="comprehensive"
    )

    # Without brief (legacy mode)
    synthesize_content(
        source_contents=["$step1.extracted_text", "$step2.content"],
        topic="AI Safety Research",
        synthesis_style="comprehensive"
    )

**Complete Call Example:**
```json
{
  "action": "synthesize_content",
  "parameters": {
    "source_contents": "example content"
  }
}
```

**Parameters:**
- `source_contents` (required)
- `topic` (optional)
- `synthesis_style` (optional)
- `writing_brief` (optional)
- `session_context` (optional)
- `reasoning_context` (optional)

**Strengths:**
- Supports list of text contents to synthesize (from documents, web pages, etc.)
- Supports the main topic or focus for synthesis (auto-derived from session_context if not provided)
- Supports how to synthesize the content:
- Supports include all important details (for reports)
- Supports focus on key points only (for summaries)

**Limitations:**
- This tool uses LLM to:
- Identify key themes and patterns across sources
- Remove redundancy and contradictions
- Create a unified narrative
- Preserve important details and citations
- Apply writing brief requirements (tone, audience, must-include facts/data)

Args:
    source_contents: List of text contents to synthesize (from documents, web pages, etc.)
    topic: The main topic or focus for synthesis (auto-derived from session_context if not provided)
    synthesis_style: How to synthesize the content:
        - "comprehensive": Include all important details (for reports)
        - "concise": Focus on key points only (for summaries)
        - "comparative": Highlight differences and similarities
        - "chronological": Organize by timeline/sequence
    writing_brief: Optional writing brief as dictionary
        Use prepare_writing_brief first to create this
    session_context: Optional SessionContext for auto-populating topic and context

Returns:
    Dictionary with synthesized_content (TEXT string), key_points, sources_used, word_count
    ⚠️  synthesized_content is TEXT, NOT a file path - use create_pages_doc to save it

Example:
    # With session context (recommended for context-aware synthesis)
    synthesize_content(
        source_contents=["$step1.extracted_text", "$step2.content"],
        session_context="$step0.session_context",
        synthesis_style="comprehensive"
    )

    # Without brief (legacy mode)
    synthesize_content(
        source_contents=["$step1.extracted_text", "$step2.content"],
        topic="AI Safety Research",
        synthesis_style="comprehensive"
    )

---
