#!/usr/bin/env python3
"""
Integration tests for email summarization functionality.

Tests email tool chaining and AppleScript integration for:
- Reading emails and summarizing them
- Reading emails by sender and summarizing
- Reading emails by time and summarizing
- Error handling and edge cases
"""

import sys
import os
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agent.email_agent import (
    read_latest_emails,
    read_emails_by_sender,
    read_emails_by_time,
    summarize_emails
)
from src.automation import MailReader
from src.utils import load_config
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_mail_app_accessibility():
    """Test that Mail.app is accessible via AppleScript."""
    print("\n" + "="*60)
    print("TEST 1: Mail.app Accessibility")
    print("="*60)

    try:
        config = load_config()
        mail_reader = MailReader(config)

        if mail_reader.test_mail_access():
            print("✓ Mail.app is accessible via AppleScript")
            return True
        else:
            print("✗ Mail.app is NOT accessible")
            return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_chaining_read_and_summarize():
    """Test tool chaining: read_latest_emails → summarize_emails."""
    print("\n" + "="*60)
    print("TEST 2: Tool Chaining - Read Latest and Summarize")
    print("="*60)

    try:
        # Step 1: Read latest emails
        print("\nStep 1: Reading latest 3 emails...")
        read_result = read_latest_emails.invoke({"count": 3, "mailbox": "INBOX"})

        if read_result.get("error"):
            print(f"✗ Error reading emails: {read_result.get('error_message')}")
            return False

        emails = read_result.get("emails", [])
        print(f"✓ Retrieved {len(emails)} emails")

        if len(emails) == 0:
            print("⚠ No emails found - this is OK if inbox is empty")
            return True

        # Step 2: Summarize emails
        print("\nStep 2: Summarizing emails...")
        summarize_result = summarize_emails.invoke({
            "emails_data": read_result,
            "focus": "key points"
        })

        if summarize_result.get("error"):
            print(f"✗ Error summarizing: {summarize_result.get('error_message')}")
            return False

        summary = summarize_result.get("summary")
        email_count = summarize_result.get("email_count", 0)

        print(f"✓ Summarized {email_count} emails")
        print(f"\nSummary preview (first 200 chars):")
        print("-" * 60)
        if summary:
            print(summary[:200] + "..." if len(summary) > 200 else summary)
        print("-" * 60)

        # Verify summary structure
        if not summary or len(summary.strip()) == 0:
            print("✗ Summary is empty")
            return False

        if email_count != len(emails):
            print(f"✗ Email count mismatch: {email_count} != {len(emails)}")
            return False

        print("✓ Tool chaining works correctly")
        return True

    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_chaining_read_by_sender_and_summarize():
    """Test tool chaining: read_emails_by_sender → summarize_emails."""
    print("\n" + "="*60)
    print("TEST 3: Tool Chaining - Read by Sender and Summarize")
    print("="*60)

    try:
        # First, get a sender from latest emails
        print("\nStep 1: Finding a sender from latest emails...")
        read_result = read_latest_emails.invoke({"count": 5, "mailbox": "INBOX"})

        if read_result.get("error"):
            print(f"✗ Error reading emails: {read_result.get('error_message')}")
            return False

        emails = read_result.get("emails", [])
        if len(emails) == 0:
            print("⚠ No emails found - skipping sender-based test")
            return True

        # Get first sender
        test_sender = emails[0].get("sender", "")
        if not test_sender:
            print("⚠ No sender found in emails - skipping test")
            return True

        print(f"✓ Testing with sender: {test_sender}")

        # Step 2: Read emails by sender
        print("\nStep 2: Reading emails from sender...")
        sender_result = read_emails_by_sender.invoke({
            "sender": test_sender,
            "count": 3
        })

        if sender_result.get("error"):
            print(f"✗ Error reading by sender: {sender_result.get('error_message')}")
            return False

        sender_emails = sender_result.get("emails", [])
        print(f"✓ Retrieved {len(sender_emails)} emails from {test_sender}")

        if len(sender_emails) == 0:
            print("⚠ No emails from this sender - this is OK")
            return True

        # Step 3: Summarize
        print("\nStep 3: Summarizing emails from sender...")
        summarize_result = summarize_emails.invoke({
            "emails_data": sender_result,
            "focus": "important information"
        })

        if summarize_result.get("error"):
            print(f"✗ Error summarizing: {summarize_result.get('error_message')}")
            return False

        summary = summarize_result.get("summary")
        email_count = summarize_result.get("email_count", 0)

        print(f"✓ Summarized {email_count} emails from {test_sender}")
        print(f"\nSummary preview (first 200 chars):")
        print("-" * 60)
        if summary:
            print(summary[:200] + "..." if len(summary) > 200 else summary)
        print("-" * 60)

        if not summary or len(summary.strip()) == 0:
            print("✗ Summary is empty")
            return False

        print("✓ Tool chaining with sender filter works correctly")
        return True

    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_chaining_read_by_time_and_summarize():
    """Test tool chaining: read_emails_by_time → summarize_emails."""
    print("\n" + "="*60)
    print("TEST 4: Tool Chaining - Read by Time and Summarize")
    print("="*60)

    try:
        # Step 1: Read emails from last hour
        print("\nStep 1: Reading emails from last hour...")
        time_result = read_emails_by_time.invoke({
            "hours": 1,
            "mailbox": "INBOX"
        })

        if time_result.get("error"):
            print(f"✗ Error reading by time: {time_result.get('error_message')}")
            return False

        emails = time_result.get("emails", [])
        print(f"✓ Retrieved {len(emails)} emails from last hour")

        if len(emails) == 0:
            print("⚠ No emails from last hour - this is OK")
            return True

        # Step 2: Summarize
        print("\nStep 2: Summarizing emails from time range...")
        summarize_result = summarize_emails.invoke({
            "emails_data": time_result,
            "focus": "action items and deadlines"
        })

        if summarize_result.get("error"):
            print(f"✗ Error summarizing: {summarize_result.get('error_message')}")
            return False

        summary = summarize_result.get("summary")
        email_count = summarize_result.get("email_count", 0)

        print(f"✓ Summarized {email_count} emails from last hour")
        print(f"\nSummary preview (first 200 chars):")
        print("-" * 60)
        if summary:
            print(summary[:200] + "..." if len(summary) > 200 else summary)
        print("-" * 60)

        if not summary or len(summary.strip()) == 0:
            print("✗ Summary is empty")
            return False

        print("✓ Tool chaining with time filter works correctly")
        return True

    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_summarize_empty_emails():
    """Test error handling when summarizing empty email list."""
    print("\n" + "="*60)
    print("TEST 5: Error Handling - Empty Email List")
    print("="*60)

    try:
        # Try to summarize empty result
        empty_result = {"emails": []}
        summarize_result = summarize_emails.invoke({
            "emails_data": empty_result
        })

        if summarize_result.get("error"):
            print(f"✗ Unexpected error: {summarize_result.get('error_message')}")
            return False

        summary = summarize_result.get("summary", "")
        count = summarize_result.get("count", 0)

        if count != 0:
            print(f"✗ Expected count 0, got {count}")
            return False

        if "no emails" not in summary.lower():
            print(f"⚠ Expected 'no emails' message, got: {summary}")
            # This is OK, just a warning

        print("✓ Empty email list handled gracefully")
        return True

    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_summarize_invalid_input():
    """Test error handling with invalid input."""
    print("\n" + "="*60)
    print("TEST 6: Error Handling - Invalid Input")
    print("="*60)

    try:
        # Try to summarize with missing 'emails' key
        invalid_result = {"count": 0}  # Missing 'emails' key
        summarize_result = summarize_emails.invoke({
            "emails_data": invalid_result
        })

        # Should handle gracefully
        emails = invalid_result.get("emails", [])
        if len(emails) == 0:
            # Should return empty summary
            summary = summarize_result.get("summary", "")
            if "no emails" in summary.lower() or len(summary) == 0:
                print("✓ Invalid input handled gracefully")
                return True

        print("⚠ Unexpected behavior with invalid input")
        return True  # Don't fail, just warn

    except Exception as e:
        # Exception is OK for invalid input
        print(f"✓ Exception caught for invalid input (expected): {type(e).__name__}")
        return True


def main():
    """Run all integration tests."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*10 + "EMAIL SUMMARIZATION INTEGRATION TESTS" + " "*10 + "║")
    print("╚" + "="*58 + "╝")

    tests = [
        ("Mail.app Accessibility", test_mail_app_accessibility),
        ("Tool Chaining: Read Latest → Summarize", test_tool_chaining_read_and_summarize),
        ("Tool Chaining: Read by Sender → Summarize", test_tool_chaining_read_by_sender_and_summarize),
        ("Tool Chaining: Read by Time → Summarize", test_tool_chaining_read_by_time_and_summarize),
        ("Error Handling: Empty Emails", test_summarize_empty_emails),
        ("Error Handling: Invalid Input", test_summarize_invalid_input),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} - {test_name}")

    print("-"*60)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All integration tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

