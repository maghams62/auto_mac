# Stock Report Generation System

## Overview

The enhanced stock report generation system provides intelligent, automated creation of comprehensive stock analysis reports for **any company** - whether you know the ticker symbol or not.

## Key Features

### 🎯 **Intelligent Ticker Resolution**
- **Local Cache**: Instantly resolves 25+ common tech stocks (Apple → AAPL, Microsoft → MSFT, etc.)
- **Web Fallback**: Automatically searches the web for unknown companies
- **Private Company Detection**: Identifies non-publicly-traded companies
- **International Support**: Handles global stock exchanges (NYSE, NASDAQ, BSE, NSE, etc.)

### 📊 **Multi-Source Chart Capture**
- **Primary**: Mac Stocks app (fast, native, high quality)
- **Fallback**: Yahoo Finance web screenshots (works for all symbols)
- **Automatic Selection**: Intelligently chooses best method

### 📄 **Professional Report Generation**
- **PDF Export**: Clean, professional reports with embedded images
- **AI Analysis**: Optional LLM-generated market analysis and outlook
- **Key Metrics**: Price, change, volume, market cap, 52-week range
- **Historical Data**: 1-month performance trends

## Architecture

```
User Request: "Create a report on Bosch stock"
    ↓
┌─────────────────────────────────────────────────────┐
│  REPORT AGENT (High-Level Orchestrator)             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Step 1: Ticker Resolution                          │
│  ├─ Check local cache (25+ common stocks)           │
│  ├─ Web search if not found                         │
│  └─ Detect if private company                       │
│                                                      │
│  Step 2: Data Fetching                              │
│  ├─ Current price & metrics (yfinance)              │
│  └─ Historical data (1 month)                       │
│                                                      │
│  Step 3: Chart Capture                              │
│  ├─ Try Mac Stocks app                              │
│  └─ Fallback to Yahoo Finance web screenshot        │
│                                                      │
│  Step 4: Content Generation                         │
│  ├─ Format key metrics                              │
│  ├─ Generate AI analysis (optional)                 │
│  └─ Structure into sections                         │
│                                                      │
│  Step 5: Report Creation                            │
│  ├─ Build HTML with embedded chart (base64)         │
│  └─ Convert to PDF via cupsfilter                   │
│                                                      │
└─────────────────────────────────────────────────────┘
    ↓
Output: PDF report + chart screenshot
```

## Usage

### Simple Usage (One Tool)

```python
from agent.report_agent import create_stock_report

# Auto-resolve ticker
result = create_stock_report.invoke({
    "company": "Microsoft"
})

# With explicit ticker
result = create_stock_report.invoke({
    "company": "Apple",
    "ticker": "AAPL",
    "include_analysis": True
})

# Custom output name
result = create_stock_report.invoke({
    "company": "NVIDIA",
    "ticker": "NVDA",
    "output_name": "nvidia_q4_report"
})
```

### Result Structure

```python
{
    "success": True,
    "company": "Microsoft Corporation",
    "ticker": "MSFT",
    "report_path": "data/reports/msft_stock_report_20251107.pdf",
    "chart_path": "data/screenshots/msft_report_chart_20251107.png",
    "report_format": "PDF",
    "ticker_source": "local_cache",  # or "web_search"
    "chart_method": "mac_stocks_app",  # or "yahoo_finance_web"
    "message": "Stock report created for Microsoft Corporation (MSFT)"
}
```

### Error Handling

```python
result = create_stock_report.invoke({"company": "Bosch"})

if result.get("error"):
    if result["error_type"] == "PrivateCompany":
        print(f"{company} is not publicly traded")
    elif result["error_type"] == "TickerNotFound":
        print(f"Could not find ticker for {company}")
    else:
        print(f"Error: {result['error_message']}")
```

## Command-Line Usage

### Run Examples

```bash
# Run comprehensive examples
python examples/stock_report_example.py
```

### Run Tests

```bash
# Test all components
python test_stock_report_system.py
```

## Components

### 1. Stock Agent (`src/agent/stock_agent.py`)

**Enhanced Tools:**

#### `search_stock_symbol(query, use_web_fallback=True)`
- Resolves company names to ticker symbols
- Web fallback for unknown companies
- Detects private companies

**Example:**
```python
from agent.stock_agent import search_stock_symbol

result = search_stock_symbol.invoke({"query": "Bosch"})
# Returns: {"is_private_company": True} or {"found": True, "symbol": "BOSCHLTD.NS"}
```

#### `capture_stock_chart(symbol, output_name, use_web_fallback=True)`
- Multi-source chart capture
- Automatic fallback to web

**Example:**
```python
from agent.stock_agent import capture_stock_chart

result = capture_stock_chart.invoke({
    "symbol": "MSFT",
    "use_web_fallback": True
})
# Returns: {"screenshot_path": "...", "capture_method": "mac_stocks_app"}
```

### 2. Report Agent (`src/agent/report_agent.py`)

**High-Level Tool:**

#### `create_stock_report(company, ticker=None, include_analysis=True)`
- Complete end-to-end report generation
- Orchestrates all sub-agents
- Single-command operation

### 3. Report Generator (`src/automation/report_generator.py`)

**Enhanced Features:**

#### `create_report(title, content, sections, image_paths=None)`
- HTML report generation with base64-embedded images
- PDF conversion via cupsfilter
- Professional styling

**Example:**
```python
from automation.report_generator import ReportGenerator

generator = ReportGenerator(config)
result = generator.create_report(
    title="Stock Analysis",
    sections=[
        {"heading": "Summary", "content": "..."},
        {"heading": "Metrics", "content": "..."}
    ],
    image_paths=["data/screenshots/chart.png"],
    export_pdf=True
)
```

## User Request Examples

The system handles natural language requests:

### Reports (PDF)
- ✅ "Create a report on Microsoft stock price"
- ✅ "Generate a stock analysis report for Apple"
- ✅ "I need a report about Bosch stock with today's price"
- ✅ "Make a PDF report for NVDA with analysis"

### Presentations (Keynote)
- ✅ "Create a slide deck about Tesla stock"
- ✅ "Make a presentation on Apple stock price with charts"
- ✅ "Generate slides for Microsoft stock analysis"

### Automatic Detection
The orchestrator routes requests based on keywords:
- **"report"** → PDF report (Report Agent)
- **"slide deck"** / **"presentation"** → Keynote (Presentation Agent)

## Configuration

### Required Dependencies

Add to `requirements.txt`:
```txt
yfinance>=0.2.28
playwright>=1.40.0
langchain-openai>=0.0.2
```

### Directory Structure
```
auto_mac/
├── data/
│   ├── reports/          # Generated PDF/HTML reports
│   └── screenshots/      # Stock chart screenshots
├── src/
│   ├── agent/
│   │   ├── stock_agent.py      # Enhanced ticker & chart tools
│   │   ├── report_agent.py     # High-level orchestrator
│   │   └── agent_registry.py   # Registration
│   └── automation/
│       └── report_generator.py # PDF generation
└── examples/
    └── stock_report_example.py
```

## Testing

### Test Coverage

1. **Ticker Resolution**
   - Local cache hits
   - Web fallback
   - Private company detection
   - International symbols

2. **Chart Capture**
   - Mac Stocks app
   - Yahoo Finance fallback
   - Error handling

3. **Report Generation**
   - Auto ticker resolution
   - Explicit ticker
   - With/without analysis
   - Image embedding

### Run Tests

```bash
# Full test suite
python test_stock_report_system.py

# Expected output:
# TEST 1: Ticker Resolution ✅
# TEST 2: Chart Capture ✅
# TEST 3: Complete Report Generation ✅
```

## Workflow Comparison

### Before (Manual Steps)

```
User: "Create a report on Bosch"

Step 1: Search for ticker manually
  → "I don't know the Bosch ticker"
  → User provides ticker or gives up

Step 2: Fetch data with known ticker
  → Only works with valid symbols

Step 3: Capture chart
  → Mac Stocks app only
  → Fails for international stocks

Step 4: Create report
  → No image support in PDFs
  → Manual content generation
```

### After (Automated)

```
User: "Create a report on Bosch"

Single Command:
create_stock_report("Bosch")

System:
1. ✅ Searches web for Bosch ticker
2. ✅ Detects if public/private
3. ✅ Fetches data (if public)
4. ✅ Captures chart (web fallback)
5. ✅ Generates AI analysis
6. ✅ Creates PDF with embedded chart

Output: Complete report in seconds
```

## Troubleshooting

### Issue: "Ticker not found"
**Solution:** Enable web fallback
```python
search_stock_symbol.invoke({
    "query": "Company Name",
    "use_web_fallback": True  # Ensure this is True
})
```

### Issue: "Chart capture failed"
**Solution:** System automatically tries web fallback. If both fail:
- Check internet connection
- Verify Mac Stocks app is installed
- Check `data/screenshots/` permissions

### Issue: "PDF conversion failed"
**Solution:** HTML report is still created
- Check cupsfilter installation: `which cupsfilter`
- Open HTML report directly: `open data/reports/report.html`

## Future Enhancements

- [ ] Real-time data feeds (WebSocket)
- [ ] Multi-stock comparison reports
- [ ] Custom date ranges
- [ ] Email delivery
- [ ] Scheduled report generation
- [ ] More chart types (candlestick, volume, etc.)
- [ ] News integration
- [ ] Sentiment analysis

## API Reference

See [API_REFERENCE.md](API_REFERENCE.md) for complete API documentation.

## Examples

See [examples/](../examples/) directory for:
- `stock_report_example.py` - Basic usage
- `advanced_stock_reports.py` - Advanced features (coming soon)
- `batch_report_generation.py` - Bulk processing (coming soon)

## License

Part of the Auto Mac project.
