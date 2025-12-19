"""
Diagnose WhatsApp UI structure to understand why message reading might fail.
This will help identify if the UI elements need adjustment.
"""

import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils import load_config
from src.automation.whatsapp_controller import WhatsAppController

print("="*80)
print("WhatsApp UI Structure Diagnostic")
print("="*80)

config = load_config()
controller = WhatsAppController(config)

# Ensure session
print("\n[STEP 1] Verifying WhatsApp session...")
session_result = controller.ensure_session()
if not session_result.get('success'):
    print("❌ WhatsApp Desktop not running")
    sys.exit(1)
print("✅ WhatsApp Desktop running")

# Navigate to Dotards
print("\n[STEP 2] Navigating to 'Dotards' group...")
nav_result = controller.navigate_to_chat("Dotards", is_group=True)
if not nav_result.get('success'):
    print(f"❌ Could not navigate: {nav_result.get('error_message')}")
    sys.exit(1)
print("✅ Navigated successfully")

# Raw UI inspection
print("\n[STEP 3] Inspecting WhatsApp UI structure...")
print("-" * 80)

applescript = '''
tell application "System Events"
    tell process "WhatsApp"
        try
            set chatPane to first scroll area of first splitter group of first splitter group of first window

            -- Get all UI elements in the chat pane
            set allElements to entire contents of chatPane

            -- Count elements
            set elementCount to count of allElements

            -- Get info about first few elements
            set elementInfo to ""
            repeat with i from 1 to (elementCount)
                if i > 10 then exit repeat
                try
                    set elem to item i of allElements
                    set elemClass to class of elem as text
                    set elemRole to role of elem
                    set elemDesc to description of elem
                    set elementInfo to elementInfo & "Element " & i & ": " & elemClass & " (role: " & elemRole & ", desc: " & elemDesc & ")\\n"
                end try
            end repeat

            return "Total UI elements: " & elementCount & "\\n\\n" & elementInfo
        on error errMsg
            return "Error inspecting UI: " & errMsg
        end try
    end tell
end tell
'''

try:
    result = subprocess.run(
        ['osascript', '-e', applescript],
        capture_output=True,
        text=True,
        timeout=10
    )

    print("UI Structure:")
    print(result.stdout)

    if result.stderr:
        print("\nErrors:")
        print(result.stderr)

except Exception as e:
    print(f"❌ Failed to inspect UI: {e}")

# Try alternate message detection
print("\n[STEP 4] Testing alternate message detection methods...")
print("-" * 80)

applescript2 = '''
tell application "System Events"
    tell process "WhatsApp"
        try
            -- Method 1: Look for groups in scroll area
            set chatPane to first scroll area of first splitter group of first splitter group of first window
            set groupCount to count of groups of chatPane

            -- Method 2: Look for static text elements
            set textElements to every static text of chatPane
            set textCount to count of textElements

            -- Method 3: Look for UI elements with specific roles
            set allUIElements to every UI element of chatPane
            set uiCount to count of allUIElements

            return "Groups in chat: " & groupCount & "\\nStatic text elements: " & textCount & "\\nTotal UI elements: " & uiCount
        on error errMsg
            return "Error: " & errMsg
        end try
    end tell
end tell
'''

try:
    result = subprocess.run(
        ['osascript', '-e', applescript2],
        capture_output=True,
        text=True,
        timeout=10
    )

    print("Message Detection:")
    print(result.stdout)

except Exception as e:
    print(f"❌ Failed: {e}")

# Check if chat is empty or if it's a UI detection issue
print("\n[STEP 5] Checking if chat appears empty...")
print("-" * 80)

applescript3 = '''
tell application "System Events"
    tell process "WhatsApp"
        try
            -- Check if there's a "no messages" indicator
            set chatPane to first scroll area of first splitter group of first splitter group of first window

            -- Try to find any text content
            set allText to value of every static text of chatPane

            if (count of allText) is 0 then
                return "No text elements found - chat may be empty or UI structure different"
            else
                -- Show first few text values
                set textSample to ""
                repeat with i from 1 to (count of allText)
                    if i > 5 then exit repeat
                    set textSample to textSample & "Text " & i & ": " & (item i of allText) & "\\n"
                end repeat
                return textSample
            end if
        on error errMsg
            return "Error: " & errMsg
        end try
    end tell
end tell
'''

try:
    result = subprocess.run(
        ['osascript', '-e', applescript3],
        capture_output=True,
        text=True,
        timeout=10
    )

    print("Text Content:")
    print(result.stdout)

except Exception as e:
    print(f"❌ Failed: {e}")

print("\n" + "="*80)
print("DIAGNOSTIC SUMMARY")
print("="*80)
print()
print("This diagnostic helps identify why message reading might fail:")
print()
print("Possible Issues:")
print("  1. Chat is genuinely empty (no messages in Dotards group)")
print("  2. WhatsApp UI structure has changed (needs code adjustment)")
print("  3. Messages are collapsed/hidden in the UI")
print("  4. Accessibility permissions insufficient")
print()
print("If UI elements were found above, the chat likely has messages")
print("but the extraction logic may need adjustment for your WhatsApp version.")
print()
