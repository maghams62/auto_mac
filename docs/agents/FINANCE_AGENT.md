# Google Finance Implementation

## Overview

Completely redesigned stock report system to use **Google Finance** as the primary data source instead of the Mac Stocks app. This provides:

1. **AI-Generated Research** - Extract Google's AI-powered stock research
2. **Reliable Screenshots** - Browser-based chart capture that works consistently
3. **Rich Data** - Price, statistics, company info, and research in one place
4. **Universal Access** - Works for any publicly traded company

## What Changed

### ❌ OLD System (Mac Stocks App)
**Problems:**
- Screenshot capture was unreliable (captured desktop instead of app window)
- Limited to stocks supported by Mac Stocks app
- No research/analysis data available
- Blocking operations

### ✅ NEW System (Google Finance)
**Solutions:**
- Playwright-based screenshot capture (reliable, non-blocking)
- Works for all publicly traded companies
- Extracts AI-generated research from Google Finance
- Rich data extraction (price, stats, research, about)

## New Architecture

```
User: "Create a report on Palantir stock"
    ↓
┌─────────────────────────────────────────────────────────┐
│  GOOGLE FINANCE AGENT                                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Step 1: Search Google Finance                          │
│  ├─ Search "Palantir stock google finance"              │
│  ├─ Find Google Finance page link                       │
│  └─ Extract URL: /finance/quote/PLTR:NASDAQ             │
│                                                          │
│  Step 2: Navigate to Stock Page                         │
│  ├─ Open https://www.google.com/finance/quote/PLTR:NASDAQ│
│  └─ Wait for page to load                               │
│                                                          │
│  Step 3: Extract Data                                   │
│  ├─ Price & Change (from price elements)                │
│  ├─ AI Research (from research section)                 │
│  ├─ Statistics (P/E, Market Cap, etc.)                  │
│  └─ About (company description)                         │
│                                                          │
│  Step 4: Capture Chart Screenshot                       │
│  ├─ Take full-page screenshot via Playwright            │
│  └─ Save to data/screenshots/                           │
│                                                          │
│  Step 5: Compile Report/Presentation                    │
│  ├─ Format extracted data into sections                 │
│  ├─ Embed chart screenshot                              │
│  └─ Generate PDF or Keynote                             │
│                                                          │
└─────────────────────────────────────────────────────────┘
    ↓
Output: PDF/Presentation with Google Finance data + chart
```

## New Files

### 1. Google Finance Agent ([src/agent/google_finance_agent.py](src/agent/google_finance_agent.py))

**Tools:**

#### `search_google_finance_stock(company)`
- Searches Google Finance for company
- Returns stock page URL and ticker
- Example: `"Palantir"` → `"https://www.google.com/finance/quote/PLTR:NASDAQ"`

#### `extract_google_finance_data(url)`
- Extracts from Google Finance page:
  - Current price & change
  - AI-generated research summary
  - Key statistics (P/E, Market Cap, etc.)
  - Company description
- Returns structured data dictionary

#### `capture_google_finance_chart(url, output_name)`
- Takes screenshot of Google Finance page
- Captures chart and price info
- Saves to `data/screenshots/`

#### `create_stock_report_from_google_finance(company, output_format)`
- **HIGH-LEVEL TOOL** - Does everything in one command
- Supports: `output_format="pdf"` or `output_format="presentation"`
- Orchestrates all steps automatically

### 2. Test Suite ([test_google_finance.py](test_google_finance.py))

Comprehensive tests for:
- Searching Google Finance
- Extracting data
- Capturing charts
- Creating complete reports

## Usage

### Simple Usage (One Command)

```python
from src.agent.google_finance_agent import create_stock_report_from_google_finance

# Create PDF report
result = create_stock_report_from_google_finance.invoke({
    "company": "Palantir",
    "output_format": "pdf"
})

print(f"Report: {result['report_path']}")
print(f"Chart: {result['chart_path']}")
print(f"Research: {result['data_extracted']['research']}")
```

### Step-by-Step Usage

```python
from src.agent.google_finance_agent import (
    search_google_finance_stock,
    extract_google_finance_data,
    capture_google_finance_chart
)

# Step 1: Find the stock
search = search_google_finance_stock.invoke({"company": "Palantir"})
url = search["url"]  # https://www.google.com/finance/quote/PLTR:NASDAQ

# Step 2: Extract data
data = extract_google_finance_data.invoke({"url": url})
print(f"Price: {data['price_data']['price']}")
print(f"Research: {data['research']}")

# Step 3: Capture chart
chart = capture_google_finance_chart.invoke({"url": url})
print(f"Chart saved: {chart['screenshot_path']}")
```

## Example Output

### For Palantir (PLTR):

**Extracted Data:**
```python
{
    "price_data": {
        "price": "$78.45",
        "change": "+$2.35 (3.09%)"
    },
    "research": "Palantir Technologies Inc. is a software company that builds
data analytics platforms for government and commercial clients. The company's
platforms enable organizations to integrate, manage, and analyze vast amounts
of data...",
    "statistics": {
        "P/E ratio": "245.67",
        "Market cap": "$165.2B",
        "Dividend yield": "—",
        "52-week high": "$80.12",
        "52-week low": "$15.66"
    },
    "about": "Palantir Technologies Inc. builds and deploys software platforms
for the intelligence community..."
}
```

**Generated Report Structure:**
```
PALANTIR TECHNOLOGIES INC. (PLTR) STOCK REPORT
==============================================

Executive Summary
-----------------
Current Price: $78.45
Change: +$2.35 (3.09%)

Research & Analysis
-------------------
[AI-generated research from Google Finance]

Key Statistics
--------------
P/E ratio: 245.67
Market cap: $165.2B
...

Charts & Visualizations
-----------------------
[Embedded screenshot of Google Finance chart]
```

## Testing

### Run Complete Test Suite:
```bash
python test_google_finance.py
```

**Tests:**
1. ✅ Search Google Finance for multiple companies
2. ✅ Extract price data and AI research
3. ✅ Capture chart screenshots
4. ✅ Generate complete PDF reports

### Quick Test (Single Company):
```bash
python -c "from src.agent.google_finance_agent import create_stock_report_from_google_finance; print(create_stock_report_from_google_finance.invoke({'company': 'Palantir', 'output_format': 'pdf'}))"
```

## Integration with Orchestrator

The orchestrator automatically routes requests to Google Finance Agent:

```python
# User requests:
"Create a report on Palantir stock"
"Generate stock analysis for PLTR"
"Make a presentation about Microsoft stock"

# Orchestrator routes to:
create_stock_report_from_google_finance(company, output_format)
```

## Advantages Over Mac Stocks App

| Feature | Mac Stocks App (OLD) | Google Finance (NEW) |
|---------|---------------------|----------------------|
| Screenshot Reliability | ❌ Often captured desktop | ✅ Reliable browser capture |
| Data Available | ❌ Just chart | ✅ Price + Research + Stats |
| AI Research | ❌ None | ✅ Google's AI summaries |
| Coverage | ❌ Limited stocks | ✅ All public companies |
| Performance | ❌ Blocking | ✅ Non-blocking |
| Consistency | ❌ App-dependent | ✅ Web-based, consistent |

## Anti-CAPTCHA Strategies

The agent implements multiple strategies to avoid Google CAPTCHAs:

### ✅ **Strategy 1: Direct URL Access**
- Uses ticker symbols to construct direct Google Finance URLs
- **No search queries = No CAPTCHA triggers**
- Example: `PLTR` → `https://www.google.com/finance/quote/PLTR:NASDAQ`

### ✅ **Strategy 2: Google Finance Internal Search**
- Falls back to Google Finance's own search (not main Google Search)
- Less monitored than main search, lower CAPTCHA risk

### ✅ **Strategy 3: CAPTCHA Detection**
- Detects CAPTCHAs early and provides helpful error messages
- Suggests using ticker symbols for direct access

### ✅ **Best Practices:**
```python
# ✅ RECOMMENDED: Use ticker symbols (no CAPTCHA risk)
create_stock_report_from_google_finance("PLTR", "pdf")
create_stock_report_from_google_finance("MSFT", "pdf")

# ⚠️  CAUTION: Company names may trigger search (CAPTCHA possible)
create_stock_report_from_google_finance("Palantir Technologies", "pdf")

# ✅ GOOD: Add delays between requests
import time
for ticker in ["PLTR", "MSFT", "NVDA"]:
    result = create_stock_report_from_google_finance(ticker, "pdf")
    time.sleep(10)  # Wait 10 seconds between requests
```

**Full anti-CAPTCHA guide:** [docs/ANTI_CAPTCHA_STRATEGIES.md](docs/ANTI_CAPTCHA_STRATEGIES.md)

## Configuration

No additional configuration needed! The agent uses existing Playwright setup.

**Requirements:**
- `playwright` (already in requirements.txt)
- Internet connection
- Playwright chromium browser: `playwright install chromium`

## Output Locations

```
auto_mac/
├── data/
│   ├── reports/                    # PDF reports
│   │   └── pltr_gfinance_report_20251107.pdf
│   └── screenshots/                # Chart screenshots
│       └── pltr_gfinance_20251107.png
```

## Error Handling

### Common Scenarios:

**1. Company Not Found:**
```python
{
    "error": True,
    "error_type": "StockNotFound",
    "error_message": "Could not find Google Finance page for: Unknown Corp",
    "suggestion": "Try using the exact ticker symbol"
}
```

**2. Private Company:**
Google Finance typically doesn't have pages for private companies, so the search will fail gracefully.

**3. Page Structure Changed:**
```python
{
    "warning": "Limited data extracted - page structure may have changed"
}
```

The agent will still capture screenshots and create reports with available data.

## Future Enhancements

- [ ] Extract financial statements (Income, Balance Sheet, Cash Flow)
- [ ] Historical price charts with custom date ranges
- [ ] News sentiment analysis
- [ ] Analyst recommendations
- [ ] Peer comparison tables
- [ ] Real-time data updates (websocket)

## Migration Guide

### From Old System to New System:

**OLD:**
```python
from agent.report_agent import create_stock_report

# Had issues with Mac Stocks app screenshots
result = create_stock_report.invoke({"company": "Palantir"})
```

**NEW:**
```python
from agent.google_finance_agent import create_stock_report_from_google_finance

# Reliable, with AI research included
result = create_stock_report_from_google_finance.invoke({
    "company": "Palantir",
    "output_format": "pdf"
})

# Access AI research:
print(result['data_extracted']['research'])
```

## Example: Complete Workflow

```python
#!/usr/bin/env python3
"""Example: Create stock reports for multiple companies."""

from src.agent.google_finance_agent import create_stock_report_from_google_finance

companies = ["Palantir", "Microsoft", "NVIDIA", "Apple"]

for company in companies:
    print(f"\nCreating report for {company}...")

    result = create_stock_report_from_google_finance.invoke({
        "company": company,
        "output_format": "pdf"
    })

    if result.get("error"):
        print(f"  ❌ {result['error_message']}")
    else:
        print(f"  ✅ Report: {result['report_path']}")
        print(f"     Ticker: {result['ticker']}")
        print(f"     Price: {result['data_extracted']['price_data']}")

print("\n✅ All reports generated in data/reports/")
```

## Summary

The new Google Finance Agent provides:
- ✅ **Reliable screenshot capture** (no more desktop captures)
- ✅ **AI-generated research** from Google Finance
- ✅ **Rich data extraction** (price, stats, research, about)
- ✅ **Universal coverage** (all publicly traded companies)
- ✅ **PDF or Keynote output** (flexible formats)
- ✅ **Single-command operation** (fully automated)

**One command creates a complete report with AI research and charts!**

```python
create_stock_report_from_google_finance("Palantir", "pdf")
```
