#!/usr/bin/env python3
"""
Test script to verify that the Reminders app opens after creating a reminder.
"""

import subprocess
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.automation.reminders_automation import RemindersAutomation

def test_reminders_app_opens():
    """Test that creating a reminder opens the Reminders app."""

    print("🧪 Testing Reminders app opening functionality...")

    # Create automation instance
    automation = RemindersAutomation()

    # Create a test reminder
    print("📝 Creating test reminder...")
    result = automation.create_reminder(
        title="Test Reminder - Verify App Opens",
        due_time="tomorrow at 9am",
        list_name="Test Reminders",
        notes="This is a test to verify the Reminders app opens after creation"
    )

    print("📊 Result:", result)

    if result.get("success"):
        print("✅ Reminder created successfully!")
        print(f"📋 Reminder ID: {result.get('reminder_id')}")
        print(f"📅 Due date: {result.get('due_date')}")
        print(f"📝 Message: {result.get('message')}")

        # Check if the AppleScript contains the activate command
        script = automation._build_create_reminder_applescript(
            "Test Reminder", None, "Test Reminders", "Test notes"
        )

        if "activate" in script:
            print("✅ AppleScript contains 'activate' command - Reminders app should open!")
        else:
            print("❌ AppleScript missing 'activate' command")

        return True
    else:
        print("❌ Failed to create reminder")
        print(f"Error: {result.get('error_message')}")
        return False

if __name__ == "__main__":
    test_reminders_app_opens()
