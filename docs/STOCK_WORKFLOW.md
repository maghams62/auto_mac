# Stock Analysis Workflow Documentation

## Overview

The stock analysis workflow combines multiple agents to create comprehensive stock presentations with both data analysis and visual charts.

## Workflow Components

### 1. Stock Data Collection
- **Tool**: `get_stock_price(symbol="NVDA")`
- **Source**: yfinance library
- **Returns**: Current price, change %, market cap, volume
- **Use**: Get quantitative stock data for analysis

### 2. Stock Chart Capture
- **Tool**: `capture_stock_chart(symbol="NVDA")`
- **Source**: Mac Stocks app
- **Process**:
  1. Opens Mac Stocks app
  2. Activates the app window
  3. Waits for chart to load (3 seconds)
  4. Captures screenshot of Stocks app window
- **Returns**: Screenshot path
- **Use**: Get visual chart/graph for presentations

### 3. Content Synthesis
- **Tool**: `synthesize_content(source_contents=[...], topic="...", synthesis_style="comprehensive")`
- **Purpose**: Convert raw stock data into narrative analysis
- **Styles**: "concise", "comprehensive", "technical", "executive"

### 4. Slide Deck Creation
- **Tool**: `create_slide_deck_content(content="...", title="...", num_slides=3)`
- **Purpose**: Format analysis into presentation-ready bullet points

### 5. Presentation Assembly
- **Tool**: `create_keynote_with_images(title="...", content="...", image_paths=[...])`
- **Purpose**: Create Keynote presentation with both text slides and chart images

## Complete Example Workflow

```python
# Step 1: Get stock data
stock_data = get_stock_price("NVDA")
# Returns: {current_price: 183.82, change_percent: -2.26, ...}

# Step 2: Capture chart from Stocks app
chart = capture_stock_chart("NVDA")
# Returns: {screenshot_path: "data/screenshots/nvda_chart_*.png"}

# Step 3: Synthesize analysis
analysis = synthesize_content(
    source_contents=[stock_data['message']],
    topic="NVIDIA Stock Analysis",
    synthesis_style="comprehensive"
)
# Returns: {synthesized_content: "NVIDIA Corporation...", word_count: 171}

# Step 4: Create slides
slides = create_slide_deck_content(
    content=analysis['synthesized_content'],
    title="NVIDIA Stock Analysis",
    num_slides=3
)
# Returns: {formatted_content: "Slide 1...\n\n\nSlide 2...", total_slides: 3}

# Step 5: Build presentation
presentation = create_keynote_with_images(
    title="NVIDIA Stock Analysis",
    content=slides['formatted_content'],
    image_paths=[chart['screenshot_path']]
)
# Returns: {keynote_path: "~/Documents/NVIDIA Stock Analysis.key", slide_count: 5}
```

## User Request Example

**User**: "Create a presentation about NVIDIA stock with a chart"

**Agent Plan**:
```json
{
  "goal": "Create NVIDIA stock presentation with chart",
  "steps": [
    {"action": "get_stock_price", "parameters": {"symbol": "NVDA"}},
    {"action": "capture_stock_chart", "parameters": {"symbol": "NVDA"}},
    {"action": "synthesize_content", "parameters": {"source_contents": ["$step1.message"]}},
    {"action": "create_slide_deck_content", "parameters": {"content": "$step3.synthesized_content"}},
    {"action": "create_keynote_with_images", "parameters": {
      "title": "NVIDIA Analysis",
      "content": "$step4.formatted_content",
      "image_paths": ["$step2.screenshot_path"]
    }}
  ]
}
```

## Key Points

### ✅ DO:
- Use `capture_stock_chart(symbol="NVDA")` for stock charts
- Synthesize data before creating slides
- Include BOTH content AND image_paths in `create_keynote_with_images`
- Use ticker symbols (NVDA, AAPL, MSFT)

### ❌ DON'T:
- Use `capture_screenshot(app_name="Stocks")` for stock charts (won't navigate to symbol)
- Skip synthesis step (goes from raw data → slides without narrative)
- Forget `content` parameter in `create_keynote_with_images`
- Use company names without converting to ticker (use `search_stock_symbol` first)

## Output

The workflow produces:
- **Keynote presentation** (~5 slides):
  - Title slide
  - 3 content slides with analysis
  - 1 chart image slide from Stocks app
- **Location**: `~/Documents/[Stock] Analysis.key`
- **Contains**: Both quantitative data and visual chart

## Current Limitations

1. **Screenshot Accuracy**: Currently captures whatever is showing in Stocks app
   - **Workaround**: Manually ensure correct stock is displayed before running
   - **Future**: Automate symbol navigation in Stocks app

2. **Window Capture**: Falls back to full screen if window ID not available
   - Usually works fine if Stocks app is in focus

## Testing

Run comprehensive test:
```bash
python test_stock_workflow_final.py
```

Expected output:
```
✅ Got stock data: $183.82
✅ Captured chart: data/screenshots/nvda_chart_*.png
✅ Synthesized analysis: 171 words
✅ Created slides: 3 slides
✅ Built presentation: 5 total slides
📊 Presentation: ~/Documents/NVIDIA Stock Analysis.key
```

## Files Modified

- `src/agent/stock_agent.py` - Added `capture_stock_chart` tool
- `src/automation/stocks_app_automation.py` - Mac Stocks app automation
- `prompts/few_shot_examples.md` - Updated Example 12 with correct pattern
- `config.yaml` - Added browser whitelist for financial sites

## Version

- **Version**: 1.0
- **Date**: 2025-11-07
- **Status**: Production Ready ✅
