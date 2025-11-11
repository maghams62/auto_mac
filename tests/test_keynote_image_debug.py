"""
Debug Keynote image handling issue.
"""

import sys
from pathlib import Path
import os

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.automation.keynote_composer import KeynoteComposer
from src.utils import load_config

def test_keynote_image():
    """Test Keynote with image."""
    print("=" * 80)
    print("TEST: Keynote with Image Slide")
    print("=" * 80)

    # Get absolute path to screenshot
    screenshot_path = os.path.abspath("data/screenshots/microsoft_stock_today.png")
    print(f"\nImage path: {screenshot_path}")
    print(f"File exists: {os.path.exists(screenshot_path)}")

    if not os.path.exists(screenshot_path):
        print("❌ Screenshot file doesn't exist!")
        return False

    # Create simple presentation with one text slide and one image slide
    config = load_config()
    composer = KeynoteComposer(config)

    slides = [
        {
            "title": "Text Slide",
            "content": "This is a text slide with bullets:\n• Point 1\n• Point 2"
        },
        {
            "title": "Image Slide",
            "image_path": screenshot_path
        }
    ]

    output_path = os.path.expanduser("~/Documents/Keynote_Image_Test.key")

    print(f"\nCreating presentation with {len(slides)} slides...")
    print(f"Output path: {output_path}")

    success = composer.create_presentation(
        title="Image Test",
        slides=slides,
        output_path=output_path
    )

    if success:
        print("✅ TEST PASSED - Presentation created successfully!")
        return True
    else:
        print("❌ TEST FAILED - Failed to create presentation")
        return False


if __name__ == "__main__":
    success = test_keynote_image()
    sys.exit(0 if success else 1)
