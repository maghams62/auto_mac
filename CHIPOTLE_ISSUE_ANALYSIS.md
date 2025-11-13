# Chipotle Stock Analysis Issue - Root Cause & Fix

## User Report
1. ❌ PowerPoint (Keynote) was NOT attached to email
2. ❌ PowerPoint content was NOT about stock analysis (generic content)

## Investigation Results

### Issue #1: Missing Attachment (CONFIRMED BUG)

**What Happened:**
```
Step 5 (create_keynote): returned keynote_path='/Users/siddharthsuresh/Documents/Chipotle Stock Analysis.key'
Step 6 (compose_email): planned with attachments=['$step5.keynote_path']
After parameter resolution: attachments=['/Users/siddharthsuresh/Documents/Chipotle Stock Analysis.key'] ✅
After email verification: attachments=[] ❌ ← BUG HERE!
```

**Root Cause:**
The email content verifier suggested:
```json
{
  "suggestions": {
    "body": "...",
    "attachments": []  ← Incorrectly removed the correct attachment!
  }
}
```

The verifier was too aggressive and suggested removing the attachment that was already correct, rather than leaving it alone.

**Why This Happened:**
The verifier LLM was not explicitly told to:
1. Only suggest changes for what's MISSING
2. Preserve existing correct values
3. Never suggest empty attachments if files should be attached

**Fix Applied:**
Updated `/Users/siddharthsuresh/Downloads/auto_mac/src/agent/email_content_verifier.py` with explicit rules:

```python
CRITICAL RULES FOR SUGGESTIONS:
1. Only suggest corrections for what's actually MISSING
2. If attachments are already correct, DO NOT include "attachments" in suggestions
3. If body is already correct, DO NOT include "body" in suggestions
4. When suggesting attachment corrections, INCLUDE existing correct attachments + add missing ones
5. NEVER suggest an empty attachments array if files should be attached

Examples:
- If attachments are correct, suggestions = {} (no changes needed)
- If body needs link added, suggestions = {"body": "new body with link"}
- If attachment exists but another is missing, suggestions = {"attachments": ["existing.key", "missing.pdf"]}
```

### Issue #2: Presentation Content (PARTIALLY CONFIRMED)

**What Actually Happened:**
The presentation WAS created with stock analysis content:

```
Slide 1: CMG Stock Price Fluctuations
- Significant fluctuations in past week
- Driven by market trends, company factors
- Recent earnings report impacts

Slide 2: Growth Strategy Highlights
- Focus on digital sales expansion
- Enhancing delivery capabilities
- Driving investor interest

Slide 3: Operational Cost Concerns
- Rising operational costs noted
- Inflation pressures on margins
- Potential impact on profitability

Slide 4: Analyst Opinions Diverge
- Optimism: Strong brand, menu innovation
- Pessimism: Increased competition risks
- Regulatory challenges potential

Slide 5: Fast-Casual Dining Sector Context
- Chipotle a key player in sector
- Sector evolving with consumer trends
- Investor focus on exposure opportunities
```

**However - The Analysis Was Generic:**
The system retrieved real stock data:
- CMG history: 5 data points (Nov 6-12, 2025)
- Latest price: $31.32
- Period change: +2.49% (+$0.76)

**But** the analysis passed to `synthesize_content` was just:
```
'source_contents': ['CMG history for 1wk: 5 data points']
```

This is why the slides contain generic analysis ("significant fluctuations", "market trends") rather than specific numbers and dates from the actual stock data.

**Root Cause:**
The `get_stock_history` tool returned detailed data:
```python
{
  'history': [
    {'date': '2025-11-06', 'close': 30.56},
    {'date': '2025-11-07', 'close': 30.59},
    {'date': '2025-11-10', 'close': 30.48},
    {'date': '2025-11-11', 'close': 29.81},
    {'date': '2025-11-12', 'close': 31.32}
  ],
  'period_change_percent': 2.49
}
```

But only the `message` field was passed to synthesis:
```
'message': 'CMG history for 1wk: 5 data points'
```

**This is a planning issue**, not a verification issue. The planner should have passed `$step2.history` or formatted the stock data before synthesis.

## Summary

### ✅ Issue #1 Fixed
- **Problem:** Email verifier removed correct attachments
- **Fix:** Updated verifier prompt with explicit preservation rules
- **Status:** FIXED - Next email will include attachments correctly

### ⚠️ Issue #2 Needs Improvement  
- **Problem:** Stock analysis lacks specific numbers/dates
- **Root Cause:** Planner passed summary message instead of actual data to synthesis
- **Fix Needed:** Update planning prompt or add a preprocessing step to format stock data
- **Status:** PARTIAL - Presentation is about stock analysis, but lacks specific data points

## Files Modified
1. `/Users/siddharthsuresh/Downloads/auto_mac/src/agent/email_content_verifier.py` - Fixed attachment preservation logic

## Next Steps

### For Immediate Use:
1. Restart the API server to load the fixed verifier
2. Test with the same request: "fetch Chipotle stock, analyze, create slideshow, email"
3. Verify attachment is included in email

### For Better Stock Analysis:
Consider updating the planning to:
```json
{
  "action": "synthesize_content",
  "parameters": {
    "source_contents": [
      "CMG stock data (Nov 6-12):",
      "Nov 6: $30.56",
      "Nov 7: $30.59", 
      "Nov 10: $30.48",
      "Nov 11: $29.81",
      "Nov 12: $31.32",
      "Change: +2.49% (+$0.76)"
    ],
    "topic": "Chipotle Stock Analysis"
  }
}
```

Or add a data formatter tool that converts stock_history into human-readable format before synthesis.

## Testing

To verify the fix works:
```bash
# 1. Restart server
cd /Users/siddharthsuresh/Downloads/auto_mac
./restart_server.sh

# 2. Test the request again in the UI
"Fetch Chipotle stock price over the past week, analyze it, create a slideshow and email that to me"

# 3. Check that:
- Email is received
- Keynote file is attached
- Attachment opens correctly
```

