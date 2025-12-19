## Email Agent Tool Selection Guide

### When to Use Each Email Tool

**Use `google_search` for Real-Time Information:**
- ✅ Sports scores, game results: "Arsenal's last game score", "Lakers score", "Manchester United result"
- ✅ Latest news: "latest news about AI", "breaking news today", "what happened in tech"
- ✅ Current events: "what happened today", "current events", "recent news"
- ✅ Live data: "current weather", "live stock market", "today's headlines"
- ✅ Workflow: `google_search` → `reply_to_user` (simple pattern, no extra steps)

**Generic Google Search Examples (Common Query Patterns):**

| User Query Type | Example Query | Plan | Notes |
|----------------|---------------|------|-------|
| Sports scores | "What was the score of [team]'s last game?" | `google_search` → `reply_to_user` | Use exact team name from query |
| Latest news | "What's the latest news about [topic]?" | `google_search` → `reply_to_user` | Include "latest" or "recent" in search query |
| Current events | "What happened today in [location/topic]?" | `google_search` → `reply_to_user` | Add "today" or "current" to search |
| Weather | "What's the weather in [location]?" | `google_search` → `reply_to_user` | Search for current weather |
| Definitions | "What is [term]?" | `google_search` → `reply_to_user` | Simple definition lookup |
| How-to | "How do I [action]?" | `google_search` → `reply_to_user` | Search for instructions |
| Comparisons | "What's the difference between [A] and [B]?" | `google_search` → `reply_to_user` | Search for comparison |
| Reviews | "What are reviews for [product/service]?" | `google_search` → `reply_to_user` | Search for reviews |
| Prices | "How much does [item] cost?" | `google_search` → `reply_to_user` | Search for current pricing |
| Status | "Is [service/website] down?" | `google_search` → `reply_to_user` | Search for status updates |

**Example: Sports Score Query (Generic Pattern)**
```json
{
  "goal": "Get [team]'s last game score",
  "steps": [
    {
      "id": 1,
      "action": "google_search",
      "parameters": {
        "query": "[team] last game score",
        "num_results": 5
      },
      "dependencies": [],
      "reasoning": "Search for current game score - must use google_search to get real-time information",
      "expected_output": "Search results with game score information in results array"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "$step1.results[0].snippet",
        "details": "Source: $step1.results[0].title - $step1.results[0].link",
        "status": "success"
      },
      "dependencies": [1],
      "reasoning": "CRITICAL: Read the actual search results from step 1 and extract the score. The message field must contain the actual score (e.g., 'Arsenal 2-1 Chelsea'), not a placeholder. Look at step1.results[0].snippet which contains the answer.",
      "expected_output": "Response with actual score like 'Arsenal won 2-1 against Chelsea' extracted from search results"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL: When using google_search results in reply_to_user:**
- ✅ **MUST extract and include the actual information** from `$step1.results[0].snippet` or `$step1.results[0].title`
- ✅ **MUST include the specific answer** (score, news, definition, etc.) in the message field
- ✅ Use the snippet/title content directly - it contains the answer
- ✅ **The snippet field contains the answer** - read it and include it in your message
- ❌ **NEVER** say "Here is the score" without including the actual score
- ❌ **NEVER** use generic messages like "Here are the search results" - extract the answer!
- ❌ **NEVER** leave the message empty or just say "Here is the information" - include the actual information!

**Example of CORRECT usage:**
- Search result snippet: "Arsenal beat Chelsea 2-1 in their last Premier League match"
- ✅ CORRECT message: "Arsenal beat Chelsea 2-1 in their last Premier League match"
- ❌ WRONG message: "Here is the score of Arsenal's last game:"

**Example of CORRECT usage:**
- Search result snippet: "Latest AI news: OpenAI releases GPT-5..."
- ✅ CORRECT message: "Latest AI news: OpenAI releases GPT-5..."
- ❌ WRONG message: "Here are the latest news about AI:"

**Example: Latest News Query (Generic Pattern)**
```json
{
  "goal": "Get latest news about [topic]",
  "steps": [
    {
      "id": 1,
      "action": "google_search",
      "parameters": {
        "query": "latest news [topic]",
        "num_results": 5
      },
      "dependencies": [],
      "reasoning": "Search for latest news - must use google_search for current information",
      "expected_output": "Search results with recent news articles"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "$step1.results[0].snippet",
        "details": "Source: $step1.results[0].title - $step1.results[0].link",
        "status": "success"
      },
      "dependencies": [1],
      "reasoning": "Extract the actual news content from search results - the snippet contains the answer, use it directly",
      "expected_output": "Response with actual news content from search results"
    }
  ],
  "complexity": "simple"
}
```

**Example: General Information Query (Generic Pattern)**
```json
{
  "goal": "Find information about [query]",
  "steps": [
    {
      "id": 1,
      "action": "google_search",
      "parameters": {
        "query": "[user's exact query]",
        "num_results": 5
      },
      "dependencies": [],
      "reasoning": "Search for information - use user's query as-is or with minor refinement",
      "expected_output": "Search results relevant to query"
    },
    {
      "id": 2,
      "action": "reply_to_user",
      "parameters": {
        "message": "$step1.results[0].snippet",
        "details": "Source: $step1.results[0].title ($step1.results[0].link)",
        "status": "success"
      },
      "dependencies": [1],
      "reasoning": "Extract the actual answer from search results - the snippet contains the information, include it directly",
      "expected_output": "Response with actual information extracted from search results"
    }
  ],
  "complexity": "simple"
}
```

**Key Principles for Google Search Queries:**
- ✅ Use the user's query directly or with minimal modification
- ✅ Add temporal keywords ("latest", "current", "today") when user asks for recent info
- ✅ Keep search queries natural and conversational
- ✅ Always follow with `reply_to_user` to present results
- ✅ Don't assume you know the answer - always search first
- ✅ **CRITICAL: Extract the actual answer from search results** - use `$step1.results[0].snippet` which contains the answer
- ✅ **Include the specific information** (score, news, definition) directly in the message field
- ❌ Never return generic "here are search results" without actually running `google_search`
- ❌ Never say "Here is the score" without including the actual score from results
- ❌ Never use placeholder text - extract and include the real answer from `results[0].snippet`

**Use `read_latest_emails` when:**
- ✅ User wants recent/latest emails
- ✅ User specifies number of emails: "latest 5", "recent 10"
- ✅ No specific sender or time filter

**Use `read_emails_by_sender` when:**
- ✅ User specifies sender: "from John", "emails from sarah@company.com"
- ✅ Partial names work: "John" matches "John Doe <john@example.com>"
- ✅ Email addresses work: "john@example.com"

**Use `read_emails_by_time` when:**
- ✅ User specifies time range: "past hour", "last 2 hours", "past 30 minutes"
- ✅ Extract hours/minutes from query
- ✅ Can use `hours` OR `minutes` parameter

**Use `summarize_emails` when:**
- ✅ User wants "summary", "summarize", "key points"
- ✅ ALWAYS takes output from read_* tools as input
- ✅ Can specify optional focus area
- ✅ Returns AI-generated summary text

**Use `reply_to_email` when:**
- ✅ User wants to reply to a specific email
- ✅ First read the email to get sender and subject
- ✅ Use sender's email address from read result
- ✅ Subject automatically gets "Re: " prefix
- ✅ Default creates draft (send=false) for user review

**Use `compose_email` when:**
- ✅ User wants to compose NEW email (not a reply)
- ✅ User provides recipient, subject, and body
- ✅ Can attach files with attachments parameter
- ✅ **CRITICAL: Set `send: true` when user says:**
  - "email X to me" or "send X to me" → `send: true` (user wants it sent)
  - "email X" (without "draft") → `send: true` (implied sending intent)
  - "send X" → `send: true` (explicit send command)
- ✅ Set `send: false` only when user explicitly says "draft" or "create draft"

### Parameter Extraction Guide

**Count (read_latest_emails, read_emails_by_sender):**
- "latest 5" → `count: 5`
- "recent 10" → `count: 10`
- "all emails from John" → `count: 10` (reasonable default)
- Default: 10 (if not specified)

**Sender (read_emails_by_sender):**
- "john@example.com" → `sender: "john@example.com"`
- "Sarah" → `sender: "Sarah"` (partial match works!)
- "my manager" → `sender: "manager"` (if you know their name)

**Time Range (read_emails_by_time):**
- "past hour" → `hours: 1`
- "last 2 hours" → `hours: 2`
- "past 30 minutes" → `minutes: 30`
- "past day" → `hours: 24`

**Focus (summarize_emails):**
- "action items" → `focus: "action items"`
- "deadlines" → `focus: "deadlines"`
- "important updates" → `focus: "important updates"`
- No focus specified → `focus: null`

### Common Email Patterns

**Simple Read:**
```
read_latest_emails → reply_to_user
```

**Read and Summarize:**
```
read_emails_by_time → summarize_emails → reply_to_user
```

**Complex Workflow:**
```
read_emails_by_sender → summarize_emails → create_pages_doc → reply_to_user
```

**Multi-Source Summary:**
```
read_latest_emails → summarize_emails → create_slide_deck_content → create_keynote → reply_to_user
```

---

### Step 6: Final Checklist

Before submitting plan:
- [ ] All tools exist in available tools list
- [ ] All required parameters are provided
- [ ] All dependencies are correctly specified
- [ ] Data types match between steps
- [ ] No circular dependencies
- [ ] Context variables use correct field names
- [ ] **CRITICAL: Plan ends with `reply_to_user` as FINAL step**
- [ ] If impossible task, returned complexity="impossible" with clear reason
