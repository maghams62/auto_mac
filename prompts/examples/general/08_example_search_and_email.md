## Example: SEARCH AND EMAIL PATTERN

**Reasoning (chain of thought):**
1. User wants information searched AND emailed
2. Must include both google_search AND compose_email steps
3. Reply should acknowledge task completion, not repeat the info (it's in the email)
4. The original query context guides reply tone: "search X and email it" → "Searched and emailed"

**User Request:** "search what's arsenal's score and email it to me"

```json
{
  "goal": "Search for Arsenal's latest score and email the results to user",
  "steps": [
    {
      "id": 1,
      "action": "google_search",
      "parameters": {
        "query": "Arsenal latest score today",
        "num_results": 3
      },
      "dependencies": [],
      "reasoning": "Search for Arsenal's most recent match score",
      "expected_output": "results array with titles, snippets, links"
    },
    {
      "id": 2,
      "action": "compose_email",
      "parameters": {
        "subject": "Arsenal Latest Score",
        "body": "Here are the latest Arsenal scores:\n\n$step1.results[0].title\n$step1.results[0].snippet\n$step1.results[0].link\n\n$step1.results[1].title\n$step1.results[1].snippet\n$step1.results[1].link",
        "send": true
      },
      "dependencies": [1],
      "reasoning": "Email the search results to user with formatted content",
      "expected_output": "Email sent confirmation"
    },
    {
      "id": 3,
      "action": "reply_to_user",
      "parameters": {
        "message": "Searched for Arsenal's latest score and emailed the results to you.",
        "details": "Top result: $step1.results[0].title - $step1.results[0].snippet",
        "status": "success"
      },
      "dependencies": [2],
      "reasoning": "Confirm task completion with context-aware acknowledgement",
      "expected_output": "User confirmation"
    }
  ],
  "complexity": "simple"
}
```

**CRITICAL PATTERNS FOR SEARCH + EMAIL:**

### ✅ Complete Workflow
```
google_search → compose_email → reply_to_user
```

### ✅ Email Must Include Search Results
```json
{
  "action": "compose_email",
  "parameters": {
    "body": "Results:\n\n$step1.results[0].title\n$step1.results[0].snippet"
  }
}
```

### ✅ Reply is Context-Aware Acknowledgement
The original query said "search X and email it" so the reply:
- ✅ Acknowledges what was done: "Searched and emailed"
- ✅ Provides brief preview in details
- ❌ Does NOT repeat full results (they're in the email)

**Context-Aware Reply Pattern:**
- **Query says "email it"** → Reply confirms email sent
- **Query says "what is X"** → Reply provides the answer
- **Query says "create and email"** → Reply confirms both actions

### ❌ ANTI-PATTERNS (WRONG!)

**❌ Search without Email:**
```json
// WRONG: User said "email it" but plan only searches
{
  "steps": [
    {"action": "google_search"},
    {"action": "reply_to_user"}  // ❌ Missing compose_email!
  ]
}
```

**❌ Reply Repeats Email Content:**
```json
// WRONG: Reply duplicates what's in the email
{
  "action": "reply_to_user",
  "parameters": {
    "message": "Here are the results: [full search results]"  // ❌ Already in email!
  }
}
```

**❌ Reply Ignores Query Context:**
```json
// WRONG: Generic reply doesn't match query intent
{
  "action": "reply_to_user",
  "parameters": {
    "message": "Task completed"  // ❌ Too generic! Should say "Searched and emailed"
  }
}
```

### Reply Message Crafting Guidelines

**Original Query Context Guides Reply:**

1. **"Search X and email it"** → "Searched for X and emailed the results"
2. **"What is X"** → "X is [answer from search]"
3. **"Find X and send it"** → "Found X and sent to you"
4. **"Create X and email it"** → "Created X and emailed to you"

**Template:**
```
[Past tense of action from query] + [what was done] + [where it is if applicable]
```

**Examples:**
- Query: "search arsenal score and email it" → Reply: "Searched for Arsenal's score and emailed the results"
- Query: "find tesla stock price and send it" → Reply: "Found Tesla's stock price and sent to you"
- Query: "get weather forecast and email" → Reply: "Retrieved weather forecast and emailed to you"

---
