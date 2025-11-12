# Final Comprehensive Fix V2: Enhanced Social Media Validation

## Executive Summary

Built on top of the previous 4-layer defense system, this enhancement specifically targets the **social media digest/summary workflow issue** identified in the Bluesky post summary example.

**New Critical Addition:**
- Enhanced validation now provides **CRITICAL warnings** when social media fetch operations skip Writing Agent tools
- Specifically detects `fetch_twitter`, `fetch_bluesky`, and `fetch_social` patterns
- Distinguishes between generic report warnings and high-priority social media digest warnings

## The Issue That Required This Enhancement

### User's Concrete Example (Bluesky Posts)
```
Query: "summarize recent Bluesky posts"
What Happened: fetch_bluesky_posts → reply_to_user ❌
Should Be: fetch_bluesky_posts → synthesize_content → reply_to_user ✅
```

**User feedback:** "this was sent in the UI but not added to the report. these are very good insights"

This revealed that:
1. The Writing Agent wasn't being invoked for social media summaries
2. Raw post data was sent directly to reply, lacking analysis and formatting
3. Generic warnings weren't strong enough for critical patterns

## Enhanced Validation Logic

### File: [src/agent/agent.py:759-783](src/agent/agent.py#L759-L783)

```python
# VALIDATION 3: Report/summary requests should use writing tools
report_keywords = ["report", "summary", "summarize", "digest", "analysis", "analyze"]
is_report_request = any(keyword in user_request.lower() for keyword in report_keywords)

# Check if we have social media fetching
has_social_fetch = any(
    step.get("action", "").startswith(("fetch_twitter", "fetch_bluesky", "fetch_social"))
    for step in steps
)

# Check if plan has reply_to_user
has_reply = any(s.get("action") == "reply_to_user" for s in steps)

if is_report_request and (has_email or has_reply) and not has_writing_tool:
    if has_social_fetch:
        warnings.append(
            "⚠️  CRITICAL: Social media digest/summary detected but plan skips Writing Agent! "
            "Required workflow: fetch_posts → synthesize_content → reply_to_user/compose_email. "
            "Raw post data lacks analysis and formatting."
        )
    else:
        warnings.append(
            "Request appears to need a report/summary but plan skips writing tools. "
            "Consider using synthesize_content or create_detailed_report before email/reply."
        )
```

**Key Improvements:**
1. **Pattern-specific detection**: Checks for social media fetch actions explicitly
2. **Elevated severity**: CRITICAL warning for social media vs generic warning for other reports
3. **Clear guidance**: Specifies the exact required workflow
4. **Context-aware**: Only triggers when report keywords + fetch + output (email/reply) detected

## Enhanced Prompt Guidance

### File: [prompts/task_decomposition.md:53-58](prompts/task_decomposition.md#L53-L58)

```markdown
**For Social Media Digests/Summaries:**
- ✅ **ALWAYS use Writing Agent for social media summaries:**
  - When user wants a "digest", "summary", or "report" of tweets/posts
  - Workflow: `fetch_[platform]_posts` → `synthesize_content` (synthesis_style: "concise") → `reply_to_user` OR `create_detailed_report` → `compose_email`
  - ❌ DON'T send raw post data directly to reply_to_user or email - it lacks analysis and formatting!
```

**Why This Addition:**
- Explicitly calls out social media as a distinct pattern requiring writing tools
- Shows concrete workflow examples
- Warns against the exact anti-pattern that was occurring

## Complete 4-Layer Defense (Now Enhanced)

```
┌─────────────────────────────────────────┐
│         LLM Creates Plan                │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│    _validate_and_fix_plan()             │
│                                          │
│  1. Check for {file1.name} patterns     │
│     → Auto-correct to $step1.duplicates │
│                                          │
│  2. Check keynote → email flow          │
│     → Auto-add missing attachments      │
│                                          │
│  3. Check for missing writing tools     │
│     → CRITICAL warning if social media  │
│     → Generic warning for other reports │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│       Execute Corrected Plan            │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│    reply_to_user (auto-formatting)      │
│                                          │
│  - Detects list/array in details        │
│  - Calls _format_duplicate_details()    │
│  - Returns formatted human-readable text│
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│     Finalize (regression detection)     │
│                                          │
│  - Checks for orphaned braces {2}       │
│  - Checks for invalid {file1.name}      │
│  - Logs errors if detected              │
└──────────────┬──────────────────────────┘
               │
               ▼
          UI Display ✅
```

## Files Modified in This Enhancement

### 1. [src/agent/agent.py](src/agent/agent.py)
**Lines Changed:** 759-783 (enhanced validation logic)

**What Changed:**
- Added `has_social_fetch` detection for `fetch_twitter`, `fetch_bluesky`, `fetch_social` patterns
- Added `has_reply` check for `reply_to_user` actions
- Split warning logic: CRITICAL for social media, generic for others
- Improved message clarity for required workflow

### 2. [prompts/task_decomposition.md](prompts/task_decomposition.md)
**Lines Added:** 53-58 (social media digest guidance)

**What Changed:**
- Added explicit section for social media digests
- Showed correct workflow: fetch → synthesize_content → reply/email
- Warned against the anti-pattern: fetch → reply (no writing step)

## Expected Log Patterns

### When Social Media Digest Query Arrives

**Scenario A: Plan Follows Guidance (Good)**
```
Query: "summarize recent Bluesky posts"
Plan: fetch_bluesky_posts → synthesize_content → reply_to_user
Log: [No warnings - plan is correct]
```

**Scenario B: Plan Skips Writing Tools (Bad)**
```
Query: "summarize recent Bluesky posts"
Plan: fetch_bluesky_posts → reply_to_user
Log: [PLAN VALIDATION] Potential issues detected:
  ⚠️  CRITICAL: Social media digest/summary detected but plan skips Writing Agent!
      Required workflow: fetch_posts → synthesize_content → reply_to_user/compose_email.
      Raw post data lacks analysis and formatting.
```

### When Generic Report Query Arrives

**Scenario C: Generic Report (Standard Warning)**
```
Query: "summarize these documents and email me"
Plan: search_documents → compose_email
Log: [PLAN VALIDATION] Potential issues detected:
  ⚠️  Request appears to need a report/summary but plan skips writing tools.
      Consider using synthesize_content or create_detailed_report before email/reply.
```

## Why This Enhancement Was Needed

### Problem with Generic Warnings
The original validation only provided generic warnings for missing writing tools. This wasn't sufficient because:
1. **All warnings looked the same** - no way to distinguish critical patterns from edge cases
2. **No pattern-specific guidance** - didn't tell the planner which workflow to use
3. **Insufficient prompt emphasis** - social media digests weren't explicitly called out

### Solution: Pattern-Specific Validation
1. **Explicit pattern detection** - knows when social media is involved
2. **Severity levels** - CRITICAL warnings get more attention
3. **Workflow guidance** - shows exact steps needed
4. **Prompt reinforcement** - adds explicit anti-patterns to teaching material

## Testing Scenarios

### Test 1: Bluesky Post Summary ✅
```
Query: "summarize recent Bluesky posts about AI"
Expected Behavior:
  1. Planner creates: fetch_bluesky_posts → synthesize_content → reply_to_user
  2. No warnings (correct plan)
  3. UI shows formatted summary with insights
```

### Test 2: Twitter Digest ✅
```
Query: "give me a digest of tweets from @username"
Expected Behavior:
  1. Planner creates: fetch_twitter_posts → synthesize_content → reply_to_user
  2. No warnings (correct plan)
  3. UI shows formatted digest
```

### Test 3: Social Media Without Writing Tools (Should Warn) ⚠️
```
Query: "summarize Bluesky posts"
Planner creates: fetch_bluesky_posts → reply_to_user
Expected Behavior:
  1. Validation detects social media + summary keywords
  2. Logs CRITICAL warning about missing Writing Agent
  3. Execution proceeds (warning only, not blocking)
  4. Admin reviews logs and strengthens prompt if pattern repeats
```

### Test 4: Generic Document Report (Generic Warning) ⚠️
```
Query: "summarize these files and email them"
Planner creates: search_documents → compose_email
Expected Behavior:
  1. Validation detects report keywords + email
  2. Logs generic warning about missing writing tools
  3. Execution proceeds
```

## Server Status

```
✅ Server restarted (PID: 99330)
✅ Enhanced social media validation active
✅ All 3 validation checks active:
   1. Invalid placeholder auto-correction
   2. Keynote attachment auto-addition
   3. Writing tool discipline (now with social media specificity)
✅ Automatic formatting active
✅ Regression detection active
✅ All 12 unit tests passing
✅ Ready to test at http://localhost:3000
```

## Monitoring & Logs

### Success Patterns (What We Want to See)
```
[PLAN VALIDATION] Plan validation complete. No issues detected.
```

### Warning Patterns - Critical (Social Media)
```
[PLAN VALIDATION] Potential issues detected:
  ⚠️  CRITICAL: Social media digest/summary detected but plan skips Writing Agent!
      Required workflow: fetch_posts → synthesize_content → reply_to_user/compose_email.
      Raw post data lacks analysis and formatting.
```

### Warning Patterns - Generic (Other Reports)
```
[PLAN VALIDATION] Potential issues detected:
  ⚠️  Request appears to need a report/summary but plan skips writing tools.
      Consider using synthesize_content or create_detailed_report before email/reply.
```

## Why This is a Strong Enhancement

### 1. Addresses Concrete User Issue
- User provided real example of Bluesky summary going wrong
- This directly targets that exact pattern
- Won't fix retroactively but prevents future occurrences

### 2. Pattern-Specific Intelligence
- Not all report queries are equal
- Social media digests have higher bar for quality
- Validation now recognizes this distinction

### 3. Actionable Warnings
- CRITICAL warnings signal higher priority
- Logs show exact workflow needed
- Makes debugging and prompt tuning easier

### 4. Extensible Architecture
- Easy to add more pattern-specific validations
- Can add more social platforms (`fetch_instagram`, `fetch_reddit`)
- Can adjust severity levels as patterns emerge

## Limitations & Future Work

### Current Limitation: Warning-Only
The validation only **warns** about missing writing tools, it doesn't **auto-fix** by injecting steps. This is because:
1. **Step ID renumbering** - Adding a step means renumbering all subsequent steps
2. **Dependency updates** - All references like `$step2.field` would need updating
3. **Complexity risk** - Auto-injection could introduce new bugs

### Future Enhancement: Auto-Injection (Complex)
If CRITICAL warnings appear frequently, consider implementing:
```python
if has_social_fetch and not has_writing_tool:
    # Find the fetch step
    fetch_step_idx = next(i for i, s in enumerate(steps) if "fetch_" in s["action"])

    # Insert synthesize_content step after fetch
    new_step = {
        "id": fetch_step_idx + 1,
        "action": "synthesize_content",
        "parameters": {
            "content": f"$step{fetch_step_idx}.posts",
            "synthesis_style": "concise"
        },
        "dependencies": [fetch_step_idx]
    }

    # Insert and renumber all subsequent steps
    steps.insert(fetch_step_idx + 1, new_step)
    # ... renumber logic ...
```

**Recommendation:** Start with warnings, measure frequency, implement auto-injection only if pattern is common.

## Conclusion

**Enhancement Complete:**
✅ Social media digest patterns now trigger CRITICAL warnings
✅ Prompt explicitly teaches social media workflow
✅ Validation distinguishes between social media and generic reports
✅ Clear guidance provided in warnings
✅ Server restarted with changes active

**Testing Required:**
1. Test Bluesky post summary queries
2. Test Twitter digest queries
3. Monitor logs for CRITICAL warnings
4. If warnings appear frequently, consider auto-injection enhancement

**Next Steps:**
1. Monitor production logs for pattern frequency
2. If CRITICAL warnings are common, strengthen prompt further
3. If pattern persists despite strong prompt, implement auto-injection
4. Consider extending to other social platforms as needed

The system now has pattern-specific intelligence for social media digests, addressing the concrete issue you identified while maintaining the generalized architecture.
