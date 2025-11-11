"""
Complete test: Create NVIDIA stock analysis presentation with chart screenshot.

This test verifies the entire workflow:
1. Get stock data (yfinance)
2. Take Mac Stocks app screenshot (visual chart)
3. Synthesize analysis
4. Create slide deck content
5. Create Keynote presentation with BOTH content AND image
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("COMPLETE STOCK PRESENTATION TEST - NVIDIA")
print("=" * 80)

# Step 1: Get stock data
print("\n📊 Step 1: Get NVIDIA stock data")
print("-" * 80)

from src.agent.stock_agent import get_stock_price

stock_result = get_stock_price.invoke({"symbol": "NVDA"})

if stock_result.get("error"):
    print(f"❌ Error: {stock_result.get('error_message')}")
    sys.exit(1)

print(f"✅ {stock_result['message']}")
print(f"   Price: ${stock_result['current_price']:.2f}")
print(f"   Change: {stock_result['change_percent']:+.2f}%")

# Step 2: Take screenshot from Mac Stocks app
print("\n📸 Step 2: Capture chart from Mac Stocks app")
print("-" * 80)

from src.agent.screen_agent import capture_screenshot

screenshot_result = capture_screenshot.invoke({
    "app_name": "Stocks",
    "output_name": "nvda_analysis_chart"
})

if screenshot_result.get("error"):
    print(f"❌ Error: {screenshot_result.get('error_message')}")
    sys.exit(1)

print(f"✅ Screenshot captured: {screenshot_result['screenshot_path']}")

# Step 3: Synthesize content
print("\n📝 Step 3: Synthesize analysis content")
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
print(f"   Key points: {len(synthesis_result['key_points'])}")

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

# Step 5: Create Keynote with content AND image
print("\n🎨 Step 5: Create Keynote presentation with chart")
print("-" * 80)

from src.agent.presentation_agent import create_keynote_with_images

presentation_result = create_keynote_with_images.invoke({
    "title": "NVIDIA Stock Analysis",
    "content": slides_result['formatted_content'],
    "image_paths": [screenshot_result['screenshot_path']]
})

if presentation_result.get("error"):
    print(f"❌ Error: {presentation_result.get('error_message')}")
    sys.exit(1)

print(f"✅ Presentation created: {presentation_result['keynote_path']}")
print(f"   Slides: {presentation_result['slide_count']}")

# Summary
print("\n" + "=" * 80)
print("✅ COMPLETE WORKFLOW TEST PASSED!")
print("=" * 80)
print("\nCreated presentation with:")
print(f"  • Stock data from yfinance")
print(f"  • Visual chart from Mac Stocks app")
print(f"  • {slides_result['total_slides']} content slides")
print(f"  • 1 chart image slide")
print(f"\nPresentation saved to: {presentation_result['keynote_path']}")
print("=" * 80)
