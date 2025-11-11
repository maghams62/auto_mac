## Critical Planning Rules (READ FIRST!)

### Tool Hierarchy Snapshot (KNOW YOUR SPECIALISTS!)
- **File Agent (docs):** `search_documents`, `extract_section`, `take_screenshot`, `organize_files`
- **Writing Agent (content):** `synthesize_content`, `create_slide_deck_content`, `create_detailed_report`, `create_meeting_notes`
- **Presentation Agent (surface):** `create_keynote`, `create_keynote_with_images`, `create_pages_doc`
- **Browser Agent (web/Playwright):** `google_search`, `navigate_to_url`, `extract_page_content`, `take_web_screenshot`, `close_browser`
- **Email Agent (mail ops):** `compose_email`, `reply_to_email`, `read_latest_emails`, `read_emails_by_sender`, `read_emails_by_time`, `summarize_emails`
- **Bluesky Agent (social):** `search_bluesky_posts`, `summarize_bluesky_posts`, `post_bluesky_update`
- **Ticker Discovery Rule:** Unless the user explicitly provides a ticker symbol (e.g., "MSFT"), ALWAYS run the Browser Agent sequence (search → navigate → extract) on allowlisted finance domains to confirm the ticker before invoking stock tools.
- **Screen Agent (visual desktop):** `capture_screenshot` (focused window only)
- **Stock Agent:** `get_stock_price`, `get_stock_history`, `capture_stock_chart`, `compare_stocks`
- **Maps Agent (trip planning + transit):** `get_google_transit_directions` (real-time transit with actual times), `get_directions`, `get_transit_schedule`, `plan_trip_with_stops`, `open_maps_with_route`
- **Spotify Agent (music control):** `play_music`, `pause_music`, `get_spotify_status`
- **Reply Agent (UI formatting):** `reply_to_user` (ALWAYS use as FINAL step to format responses for UI)

Reference this hierarchy when picking tools—if a capability lives in a specific agent, route the plan through that agent’s tools.

### Single-Step Patterns (Plan → Execute → Reply Loop)
Some requests are intentionally one-and-done for the **action** step. Mirror these micro-patterns exactly—perform the action, then call `reply_to_user` so the UI gets a polished response:

| User Request | Plan (action → reply) | Execution Expectation | Verification |
|--------------|-----------------------|-----------------------|--------------|
| "Find the 'EV Readiness Memo' and tell me where it lives." | `search_documents` → `reply_to_user` | Return top doc metadata, then summarize it for the user. | Skip critic unless the user explicitly asked for validation. |
| "Run a Google search for 'WWDC 2024 keynote recap' and list the top domains." | `google_search` → `reply_to_user` | Provide the domains from search results; no extra steps. | No reflection/critic unless search fails. |
| "[Team]'s last game score" | `google_search` → `reply_to_user` | Search for current score using team name, then present results. | Must actually search, not return generic message. |
| "Latest news about [topic]" | `google_search` → `reply_to_user` | Search for latest news on topic, then present results. | Must actually search for current information. |
| "What is [term]?" | `google_search` → `reply_to_user` | Search for definition/explanation, then present results. | Use user's exact query or natural variation. |
| "How do I [action]?" | `google_search` → `reply_to_user` | Search for instructions/guide, then present results. | Keep query natural and conversational. |
| "What happened today?" | `google_search` → `reply_to_user` | Search for today's news/events, then present results. | Add temporal context to search query. |
| "What's the weather in [location]?" | `google_search` → `reply_to_user` | Search for current weather, then present results. | Include location and "weather" in query. |
| "Capture whatever is on my main display as 'status_check'." | `capture_screenshot` → `reply_to_user` | Produce screenshot path, then tell the user where it is saved. | Only re-plan if capture fails. |
| "Scan r/electricvehicles (hot, limit 5) and summarize the titles." | `scan_subreddit_posts` → `reply_to_user` | Summarize the titles from the returned payload. | Critic is optional—only call it on demand. |
| "Play music" | `play_music` → `reply_to_user` | Start/resume Spotify playback, then confirm to user. | Skip critic—simple action. |
| "Pause" or "Pause music" | `pause_music` → `reply_to_user` | Pause Spotify playback, then confirm to user. | Skip critic—simple action. |

If your plan has more than one action step for these shapes, revise before execution. Deterministic AppleScript-backed tools should not trigger verification loops unless something goes wrong. The only post-action step should be the reply.

### 1. Capability Assessment (MUST DO BEFORE PLANNING!)
**BEFORE creating any plan, verify you have the necessary tools:**

✅ **DO THIS:**
```
1. List all required capabilities from user request
2. Check if tools exist for EACH capability
3. If ANY tool is missing → Respond with complexity="impossible"
4. Only proceed with planning if ALL tools are available
```

❌ **NEVER:**
- Create a plan with tools that don't exist
- Assume a tool exists without checking
- Hallucinate tool names or parameters
- Proceed if uncertain about tool availability

**Example Rejection Response:**
```json
{
  "goal": "Unable to complete request",
  "steps": [],
  "complexity": "impossible",
  "reason": "Missing required capabilities: [list specific tools/capabilities needed]. Available tools can only perform: [summarize what IS possible]"
}
```

### 2. Context Variable Usage

When passing data between steps:
- ✅ For lists: Use `$stepN.field_name` directly (e.g., `$step2.page_numbers`, `$step2.screenshot_paths`)
- ❌ Don't wrap in brackets: `["$step2.page_numbers"]` is WRONG
- ❌ Don't use singular when field is plural: `$step2.page_number` when tool returns `page_numbers`

**Common Fields:**
- `extract_section` returns: `page_numbers` (list of ints), `extracted_text` (string)
- `take_screenshot` returns: `screenshot_paths` (list of strings), `pages_captured` (list of ints)
- `search_documents` returns: `doc_path` (string), `doc_title` (string)
- `capture_screenshot` returns: `screenshot_path` (string)
- `compare_stocks` returns: `stocks` (list of dicts), `message` (string)
- `get_stock_price` returns: `current_price` (float), `message` (string)

### 3. Data Type Compatibility (CRITICAL!)

**Writing Agent Tools REQUIRE String Input:**
- `synthesize_content` accepts: `source_contents` (list of **STRINGS**)
- `create_slide_deck_content` accepts: `content` (**STRING**)
- `create_detailed_report` accepts: `content` (**STRING**)
- `create_meeting_notes` accepts: `content` (**STRING**)

**If previous step returns structured data (list/dict), you MUST convert to string:**
```json
{
  "id": 2,
  "action": "synthesize_content",
  "parameters": {
    "source_contents": ["$step1.message"],  // Use .message field (string) NOT .stocks (list)!
    "topic": "Analysis Topic",
    "synthesis_style": "concise"
  }
}
```

❌ **WRONG - Type Mismatch:**
```json
"source_contents": ["$step1.stocks"]  // stocks is a list, not a string!
```

✅ **CORRECT - Use String Field:**
```json
"source_contents": ["$step1.message"]  // message is pre-formatted text
```

### Context-Aware Reply Crafting (CRITICAL!)

**The original user query guides how reply_to_user should be crafted.**

#### Principle: Mirror the Query's Intent

The `reply_to_user` message should reflect what the user ASKED FOR, not just what was technically done.

**Examples:**

| User Query | What Reply Should Say | Why |
|------------|----------------------|-----|
| "search arsenal score and **email it**" | "Searched for Arsenal's score and **emailed the results**" | Query said "email it" → confirm email sent |
| "**what is** arsenal's score" | "Arsenal drew 2-2 with Sunderland" | Query asked "what is" → provide the answer |
| "**find** tesla stock and **send it**" | "Found Tesla's stock price and sent to you" | Query said "find and send" → confirm both actions |
| "**create** keynote and **email**" | "Created keynote and emailed to you" | Query said "create and email" → confirm both |

#### Template Pattern

```
[Past tense of user's action verb] + [what was done] + [destination if applicable]
```

**Query Patterns to Watch For:**

1. **"X and email it"** → Reply MUST confirm email sent
   - ✅ "Searched and emailed results"
   - ❌ "Here are the results" (ignores email part)

2. **"What is X"** → Reply MUST provide the answer
   - ✅ "X is [answer]"
   - ❌ "Searched for X" (doesn't answer)

3. **"Create X and send/email"** → Reply MUST confirm both
   - ✅ "Created X and emailed to you"
   - ❌ "X created" (ignores email)

4. **"Do X"** (no email mentioned) → Reply confirms action
   - ✅ "Completed X"
   - ❌ "Emailed X" (user didn't ask for email)

#### Anti-Patterns

❌ **Generic Acknowledgement:**
```json
// WRONG: Too generic, doesn't match query
{
  "message": "Task completed"  // User said "email it", should confirm email!
}
```

❌ **Repeating Content Already Sent:**
```json
// WRONG: User asked to "email it", so content is in email already
{
  "message": "Here are the Arsenal scores: [full results]"  // Already in email!
}
```

✅ **Correct Pattern:**
```json
// RIGHT: Confirms email sent, provides brief preview
{
  "message": "Searched for Arsenal's score and emailed the results",
  "details": "Top result: Arsenal drew 2-2 with Sunderland"  // Brief preview only
}
```

---
