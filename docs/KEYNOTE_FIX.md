# Keynote Presentation with Screenshots - Fix Documentation

## Issue

When the agent was asked to "create a slide deck with screenshots," it failed with:

```
Error: create_presentation() got an unexpected keyword argument 'content'
```

**Root Cause:** The agent planned to use `create_keynote` tool but passed parameters that didn't match the underlying `KeynoteComposer.create_presentation()` method signature.

## What Was Fixed

### 1. Fixed `create_keynote` Tool Wrapper
**File:** `src/agent/tools.py`

- Added logic to convert `content` string into proper `slides` format
- Now properly calls `keynote_composer.create_presentation(title, slides, output_path)`
- Handles both short and long content by splitting into multiple slides

### 2. Enhanced `KeynoteComposer` to Support Images
**File:** `src/automation/keynote_composer.py`

- Updated `_build_applescript()` to accept slides with `image_path` field
- Slides can now have either `content` (text) or `image_path` (image)
- Generates AppleScript to insert images into Keynote slides

### 3. Added New Tool: `create_keynote_with_images`
**File:** `src/agent/tools.py`

**Purpose:** Specifically for creating presentations from screenshots/images

**Parameters:**
```python
{
    "title": str,
    "image_paths": List[str],  # List of screenshot paths
    "output_path": Optional[str]
}
```

**Usage Pattern:**
```
search_documents → extract_section → take_screenshot → create_keynote_with_images → compose_email
```

This tool:
- Accepts a list of image paths (like screenshots)
- Creates one slide per image
- Returns the presentation path

### 4. Updated Tool Documentation
**File:** `prompts/tool_definitions.md`

- Added complete documentation for `create_keynote_with_images`
- Added new chaining pattern: Screenshot → Presentation → Email
- Clarified when to use each tool

## How It Works Now

### Original Request:
```
"Take a screenshot of the chorus page of The Night We Met and create a slide deck with just that and email it"
```

### Agent's Plan (Now Fixed):
```
Step 1: search_documents(query="The Night We Met")
  → doc_path: /path/to/The Night We Met.pdf

Step 2: extract_section(doc_path=$step1.doc_path, section="chorus")
  → page_numbers: [2, 4, 3]

Step 3: take_screenshot(doc_path=$step1.doc_path, pages=[2, 4, 3])
  → screenshot_paths: ["/tmp/page2.png", "/tmp/page4.png", "/tmp/page3.png"]

Step 4: create_keynote_with_images(
    title="The Night We Met - Chorus",
    image_paths=$step3.screenshot_paths
)
  → keynote_path: ~/Documents/The Night We Met - Chorus.key
  → slide_count: 4 (1 title slide + 3 image slides)

Step 5: compose_email(
    subject="Chorus from The Night We Met",
    body="Attached is the slide deck...",
    recipient="user@example.com",
    attachments=[$step4.keynote_path],
    send=true
)
  → status: "sent"
```

## Tools Comparison

### `create_keynote` (Text-based)
**Use when:**
- Creating presentation from document text
- Generating slides from written content
- Converting text to structured slides

**Input:** `content` (string)
**Output:** Keynote file with text slides

### `create_keynote_with_images` (Image-based)
**Use when:**
- Creating presentation from screenshots
- Displaying images as slides
- Visual content (charts, diagrams, photos)

**Input:** `image_paths` (list of file paths)
**Output:** Keynote file with image slides

## Testing

Run the test script:
```bash
python test_keynote_fix.py
```

This will execute the exact request that previously failed and verify:
1. ✓ Screenshots are captured
2. ✓ Keynote presentation is created WITH images
3. ✓ Email is sent with presentation attached
4. ✓ All steps succeed

## Examples

### Example 1: Screenshot → Presentation → Email
```python
from src.agent.agent import AutomationAgent
from src.utils import load_config

agent = AutomationAgent(load_config())

result = agent.run(
    "Take a screenshot of page 5 of my report and create a slide deck"
)
```

### Example 2: Direct Tool Usage
```python
from src.agent.tools import take_screenshot, create_keynote_with_images

# Take screenshots
screenshots = take_screenshot(
    doc_path="/path/to/doc.pdf",
    pages=[3, 5, 7]
)

# Create presentation with those screenshots
presentation = create_keynote_with_images(
    title="My Presentation",
    image_paths=screenshots["screenshot_paths"]
)

print(f"Created: {presentation['keynote_path']}")
```

## What Changed in the Codebase

### Modified Files
1. ✏️ `src/agent/tools.py` - Fixed `create_keynote`, added `create_keynote_with_images`
2. ✏️ `src/automation/keynote_composer.py` - Enhanced to support images in slides
3. ✏️ `prompts/tool_definitions.md` - Added documentation for new tool

### New Files
1. 🆕 `test_keynote_fix.py` - Test script to verify fix
2. 🆕 `KEYNOTE_FIX.md` - This documentation

### No Breaking Changes
- All existing functionality preserved
- Old code continues to work
- New tool is additive (doesn't replace anything)

## Summary

The issue was that the agent couldn't create Keynote presentations with screenshots because:

1. ❌ Tool signature mismatch (`content` vs `slides`)
2. ❌ No support for images in slides
3. ❌ No dedicated tool for image-based presentations

Now fixed:

1. ✅ `create_keynote` properly converts content to slides
2. ✅ `KeynoteComposer` supports images via AppleScript
3. ✅ New `create_keynote_with_images` tool for screenshot presentations
4. ✅ Complete documentation and examples
5. ✅ Test script to verify functionality

**The agent can now successfully create Keynote presentations with screenshots and email them!** 🎉
