# Anti-CAPTCHA Strategies for Google Finance Agent

## Overview

Google may show CAPTCHAs when detecting automated traffic. This document explains the strategies implemented to avoid and handle CAPTCHAs.

## Implemented Strategies

### 1. **Direct URL Access (Highest Priority)**

**Strategy:** Bypass Google Search entirely by constructing direct Google Finance URLs.

**How it works:**
```python
# Instead of searching, we go directly to the stock page
direct_url = f"https://www.google.com/finance/quote/{ticker}:{exchange}"
# Example: https://www.google.com/finance/quote/PLTR:NASDAQ
```

**Advantages:**
- ✅ No search queries = no CAPTCHA triggers
- ✅ Fastest method (one request)
- ✅ Works for all ticker symbols

**When it's used:**
- When user provides a ticker-like input (1-5 letters)
- Tries common exchanges: NASDAQ, NYSE, NSE, BSE

**Example:**
```python
search_google_finance_stock("PLTR")
# → Tries direct URLs first
# → Returns immediately if found
```

### 2. **Google Finance Internal Search (Fallback)**

**Strategy:** Use Google Finance's own search instead of main Google Search.

**How it works:**
```python
# Use Google Finance search endpoint (less monitored)
finance_search_url = f"https://www.google.com/finance/search?q={company}"
# Example: https://www.google.com/finance/search?q=Palantir
```

**Advantages:**
- ✅ Avoids main Google Search CAPTCHA systems
- ✅ Works for company names
- ✅ Returns structured results

**When it's used:**
- When direct URL doesn't work
- When user provides company name instead of ticker

### 3. **CAPTCHA Detection**

**Strategy:** Detect CAPTCHAs early and fail gracefully with helpful messages.

**Detection method:**
```python
page_content = page.content()
if "captcha" in page_content.lower() or "unusual traffic" in page_content.lower():
    return {
        "error": True,
        "error_type": "CAPTCHADetected",
        "error_message": "Google detected unusual traffic...",
        "suggestion": "Try using exact ticker symbol (e.g., PLTR)"
    }
```

**User experience:**
```
❌ Google detected unusual traffic and showed a CAPTCHA.
💡 Suggestion: Try using the exact ticker symbol (e.g., PLTR, MSFT) for direct access
```

### 4. **Non-Headless Browser**

**Strategy:** Use visible browser mode to appear more like a human.

**Implementation:**
```python
browser = SyncWebBrowser(config, headless=False)
```

**Advantages:**
- ✅ Looks more like real user
- ✅ Can see what's happening (debugging)
- ✅ Lower CAPTCHA probability

### 5. **Realistic Delays**

**Strategy:** Add natural delays between requests.

**Implementation:**
```python
time.sleep(2)  # Wait for page load
time.sleep(3)  # Wait for dynamic content
```

**Advantages:**
- ✅ Mimics human behavior
- ✅ Allows content to fully load
- ✅ Reduces rate-limiting triggers

## Priority Flow

```
User Request: "Find Palantir stock"
    ↓
┌─────────────────────────────────────────────────────┐
│  STRATEGY 1: Direct URL (No Search)                 │
├─────────────────────────────────────────────────────┤
│  IF ticker-like (PLTR):                             │
│    Try: https://www.google.com/finance/quote/       │
│         PLTR:NASDAQ                                  │
│         PLTR:NYSE                                    │
│         PLTR:NSE                                     │
│    ✅ Success → Return immediately                   │
│    ❌ 404 → Continue to Strategy 2                   │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│  STRATEGY 2: Google Finance Search                  │
├─────────────────────────────────────────────────────┤
│  Try: https://www.google.com/finance/search?        │
│       q=Palantir                                     │
│    ↓                                                 │
│  Check for CAPTCHA:                                  │
│    IF CAPTCHA detected:                              │
│      ❌ Return error with suggestion                 │
│    ELSE:                                             │
│      ✅ Parse search results                         │
│      ✅ Extract first match                          │
│      ✅ Return stock page URL                        │
└─────────────────────────────────────────────────────┘
```

## Best Practices for Users

### ✅ DO: Use Ticker Symbols When Known

**Good:**
```python
create_stock_report_from_google_finance("PLTR", "pdf")
create_stock_report_from_google_finance("MSFT", "pdf")
create_stock_report_from_google_finance("NVDA", "pdf")
```

**Why:** Direct URL access, no search needed, no CAPTCHA risk.

### ✅ DO: Wait Between Requests

**Good:**
```python
for ticker in ["PLTR", "MSFT", "NVDA"]:
    result = create_stock_report_from_google_finance(ticker, "pdf")
    time.sleep(5)  # Wait 5 seconds between requests
```

**Why:** Reduces rate-limiting and CAPTCHA triggers.

### ⚠️ CAUTION: Company Names May Trigger Search

**May trigger CAPTCHA:**
```python
create_stock_report_from_google_finance("Palantir Technologies", "pdf")
```

**Better:**
```python
create_stock_report_from_google_finance("PLTR", "pdf")
```

### ❌ DON'T: Make Rapid Sequential Requests

**Bad:**
```python
# Making 50 requests in a loop without delays
for ticker in long_list:
    result = create_stock_report_from_google_finance(ticker, "pdf")
```

**Good:**
```python
import time
for ticker in long_list:
    result = create_stock_report_from_google_finance(ticker, "pdf")
    time.sleep(10)  # Wait 10 seconds between requests
```

## Error Handling

### When CAPTCHA is Detected

```python
result = create_stock_report_from_google_finance("Palantir", "pdf")

if result.get("error") and result.get("error_type") == "CAPTCHADetected":
    print("❌ CAPTCHA detected!")
    print(f"💡 {result['suggestion']}")

    # Retry with ticker symbol
    result = create_stock_report_from_google_finance("PLTR", "pdf")
```

### Complete Error Handling Example

```python
def safe_create_report(company, max_retries=3):
    """Create report with CAPTCHA handling."""

    for attempt in range(max_retries):
        result = create_stock_report_from_google_finance(company, "pdf")

        if not result.get("error"):
            return result  # Success!

        error_type = result.get("error_type")

        if error_type == "CAPTCHADetected":
            print(f"⚠️  CAPTCHA detected on attempt {attempt + 1}")

            if attempt < max_retries - 1:
                # Wait longer and try direct URL
                print("Waiting 60 seconds before retry...")
                time.sleep(60)

                # Try with ticker if we used company name
                if len(company) > 5:
                    print(f"💡 Suggestion: Use ticker symbol instead")
                    return {"error": True, "suggestion": "Use ticker symbol"}
            else:
                print("❌ Max retries reached")
                return result

        else:
            # Other error
            return result

    return {"error": True, "error_message": "Failed after all retries"}
```

## Rate Limiting Recommendations

### For Individual Use

```python
# Good: One request at a time with delays
tickers = ["PLTR", "MSFT", "NVDA"]

for ticker in tickers:
    result = create_stock_report_from_google_finance(ticker, "pdf")
    print(f"✅ Created report for {ticker}")
    time.sleep(10)  # Wait 10 seconds
```

### For Batch Processing

```python
import time
from datetime import datetime

def batch_create_reports(tickers, batch_size=5, batch_delay=300):
    """Create reports in batches with delays."""

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]

        print(f"\n📊 Processing batch {i//batch_size + 1}")
        print(f"Tickers: {', '.join(batch)}")

        for ticker in batch:
            result = create_stock_report_from_google_finance(ticker, "pdf")

            if result.get("error"):
                print(f"  ❌ {ticker}: {result['error_message']}")
            else:
                print(f"  ✅ {ticker}: {result['report_path']}")

            time.sleep(10)  # Wait between each ticker

        # Wait between batches
        if i + batch_size < len(tickers):
            print(f"\n⏸️  Waiting {batch_delay} seconds before next batch...")
            time.sleep(batch_delay)

# Usage
all_tickers = ["PLTR", "MSFT", "NVDA", "AAPL", "GOOGL", "META", "TSLA"]
batch_create_reports(all_tickers, batch_size=3, batch_delay=300)
```

## Advanced: Rotating User Agents (Future Enhancement)

**Not currently implemented, but possible:**

```python
# Potential future enhancement
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36...",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
    # etc.
]

# Rotate user agents between requests
browser = SyncWebBrowser(config, headless=False, user_agent=random.choice(USER_AGENTS))
```

## Monitoring CAPTCHA Rates

### Log CAPTCHA Occurrences

```python
import json
from datetime import datetime

def log_captcha(company, method):
    """Log CAPTCHA occurrences for monitoring."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "company": company,
        "method": method,
        "type": "CAPTCHA"
    }

    with open("captcha_log.json", "a") as f:
        f.write(json.dumps(log_entry) + "\n")

# Usage in error handling
if result.get("error_type") == "CAPTCHADetected":
    log_captcha(company, "finance_search")
```

## Troubleshooting

### Issue: Getting CAPTCHAs Frequently

**Solutions:**
1. ✅ Use ticker symbols instead of company names
2. ✅ Increase delays between requests (minimum 10 seconds)
3. ✅ Reduce batch size (max 5 stocks at a time)
4. ✅ Wait 5-10 minutes between batches

### Issue: Direct URLs Not Working

**Possible causes:**
- Incorrect ticker symbol
- Ticker listed on different exchange
- Company not publicly traded

**Solution:**
```python
# Try multiple exchanges
exchanges = ["NASDAQ", "NYSE", "NSE", "BSE", "LSE"]
for exchange in exchanges:
    result = create_stock_report_from_google_finance(f"{ticker}:{exchange}", "pdf")
    if not result.get("error"):
        break
```

### Issue: CAPTCHA Even with Ticker Symbols

**Cause:** Rate limiting from too many requests

**Solution:**
```python
# Wait longer between requests
import time
time.sleep(30)  # Wait 30 seconds

# Or wait until next day
```

## Summary

**CAPTCHA Avoidance Priority:**

1. 🥇 **Direct URL** - Use ticker symbols when possible
2. 🥈 **Google Finance Search** - Fallback for company names
3. 🥉 **Error Handling** - Graceful degradation with suggestions

**Key Takeaways:**
- ✅ Ticker symbols are fastest and safest
- ✅ Add delays between requests (10+ seconds)
- ✅ Batch processing with longer waits between batches
- ✅ Monitor and log CAPTCHA occurrences
- ✅ Provide fallback suggestions to users

**Remember:** Google's CAPTCHA systems are designed to detect bots. The best strategy is to make requests look as human as possible: use direct URLs, add realistic delays, and don't make too many requests in a short time.
