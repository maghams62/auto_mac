"""
FINAL TEST: Complete NVIDIA stock analysis workflow with proper screenshot.

This uses the NEW capture_stock_chart tool that:
1. Opens Mac Stocks app
2. Waits for it to be ready
3. Captures ONLY the Stocks app window (not desktop)
4. Combines with data analysis and creates presentation
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("FINAL STOCK WORKFLOW TEST - NVIDIA")
print("=" * 80)
print("\nIMPORTANT: Make sure NVDA is showing in your Stocks app")
print("(The app will be activated and screenshot will be taken)")
print("=" * 80)

# Step 1: Get stock data
print("\n📊 Step 1: Get NVIDIA stock data (yfinance)")
print("-" * 80)

from src.agent.stock_agent import get_stock_price

stock_result = get_stock_price.invoke({"symbol": "NVDA"})

if stock_result.get("error"):
    print(f"❌ Error: {stock_result.get('error_message')}")
    sys.exit(1)

print(f"✅ {stock_result['message']}")
print(f"   Price: ${stock_result['current_price']:.2f}")
print(f"   Change: {stock_result['change_percent']:+.2f}%")

# Step 2: Capture chart from Mac Stocks app (NEW TOOL!)
print("\n📸 Step 2: Capture chart from Mac Stocks app (NEW!)")
print("-" * 80)

from src.agent.stock_agent import capture_stock_chart

chart_result = capture_stock_chart.invoke({"symbol": "NVDA"})

if chart_result.get("error"):
    print(f"❌ Error: {chart_result.get('error_message')}")
    sys.exit(1)

print(f"✅ {chart_result['message']}")
print(f"   Screenshot: {chart_result['screenshot_path']}")
print(f"   This captures ONLY the Stocks app window")

# Step 3: Synthesize content
print("\n📝 Step 3: Synthesize analysis")
print("-" * 80)

from src.agent.writing_agent import synthesize_content

synthesis_result = synthesize_content.invoke({
    "source_contents": [stock_result['message']],
    "topic": "NVIDIA Stock Analysis",
    "synthesis_style": "comprehensive"
})

if synthesis_result.get("error"):
    print(f"❌ Error: {synthesis_result.get('error_message')}")
    sys.exit(1)

print(f"✅ Content synthesized: {synthesis_result['word_count']} words")

# Step 4: Create slide deck content
print("\n📋 Step 4: Create slide deck content")
print("-" * 80)

from src.agent.writing_agent import create_slide_deck_content

slides_result = create_slide_deck_content.invoke({
    "content": synthesis_result['synthesized_content'],
    "title": "NVIDIA Stock Analysis",
    "num_slides": 3
})

if slides_result.get("error"):
    print(f"❌ Error: {slides_result.get('error_message')}")
    sys.exit(1)

print(f"✅ Slide content created: {slides_result['total_slides']} slides")

# Step 5: Create Keynote with content AND chart image
print("\n🎨 Step 5: Create Keynote with data + chart")
print("-" * 80)

from src.agent.presentation_agent import create_keynote_with_images

presentation_result = create_keynote_with_images.invoke({
    "title": "NVIDIA Stock Analysis",
    "content": slides_result['formatted_content'],
    "image_paths": [chart_result['screenshot_path']]
})

if presentation_result.get("error"):
    print(f"❌ Error: {presentation_result.get('error_message')}")
    sys.exit(1)

print(f"✅ Presentation created: {presentation_result['keynote_path']}")
print(f"   Total slides: {presentation_result['slide_count']}")

# Summary
print("\n" + "=" * 80)
print("✅ COMPLETE WORKFLOW TEST PASSED!")
print("=" * 80)
print("\nWorkflow Summary:")
print(f"  1. ✅ Got stock data from yfinance: ${stock_result['current_price']:.2f}")
print(f"  2. ✅ Captured Stocks app chart: {chart_result['screenshot_path']}")
print(f"  3. ✅ Synthesized analysis: {synthesis_result['word_count']} words")
print(f"  4. ✅ Created slide content: {slides_result['total_slides']} slides")
print(f"  5. ✅ Built Keynote presentation: {presentation_result['slide_count']} total slides")
print(f"\n📊 Presentation: {presentation_result['keynote_path']}")
print("\nThis presentation now contains:")
print("  • Stock data analysis slides")
print("  • Chart screenshot from Mac Stocks app")
print("  • Professional formatting")
print("=" * 80)
