#!/usr/bin/env python3
"""
Test script for email reading and summarization functionality.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

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


def test_mail_access():
    """Test if Mail.app is accessible."""
    print("\n" + "="*60)
    print("TEST 1: Mail.app Access")
    print("="*60)

    config = load_config()
    mail_reader = MailReader(config)

    if mail_reader.test_mail_access():
        print("✓ Mail.app is accessible")
        return True
    else:
        print("✗ Mail.app is NOT accessible")
        return False


def test_read_latest_emails():
    """Test reading latest emails."""
    print("\n" + "="*60)
    print("TEST 2: Read Latest Emails")
    print("="*60)

    try:
        result = read_latest_emails.invoke({"count": 5, "mailbox": "INBOX"})

        if result.get("error"):
            print(f"✗ Error: {result.get('error_message')}")
            return False

        emails = result.get("emails", [])
        print(f"✓ Retrieved {len(emails)} emails")

        for i, email in enumerate(emails, 1):
            print(f"\n  Email #{i}:")
            print(f"    From: {email.get('sender', 'Unknown')}")
            print(f"    Subject: {email.get('subject', 'No subject')}")
            print(f"    Date: {email.get('date', 'Unknown')}")
            preview = email.get('content_preview', '')[:100]
            print(f"    Preview: {preview}...")

        return True

    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_read_by_time():
    """Test reading emails by time range."""
    print("\n" + "="*60)
    print("TEST 3: Read Emails from Last Hour")
    print("="*60)

    try:
        result = read_emails_by_time.invoke({"hours": 1, "mailbox": "INBOX"})

        if result.get("error"):
            print(f"✗ Error: {result.get('error_message')}")
            return False

        emails = result.get("emails", [])
        print(f"✓ Retrieved {len(emails)} emails from the last hour")

        for i, email in enumerate(emails, 1):
            print(f"\n  Email #{i}:")
            print(f"    From: {email.get('sender', 'Unknown')}")
            print(f"    Subject: {email.get('subject', 'No subject')}")
            print(f"    Date: {email.get('date', 'Unknown')}")

        return True

    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_summarize():
    """Test email summarization."""
    print("\n" + "="*60)
    print("TEST 4: Email Summarization")
    print("="*60)

    try:
        # First read some emails
        read_result = read_latest_emails.invoke({"count": 3, "mailbox": "INBOX"})

        if read_result.get("error"):
            print(f"✗ Error reading emails: {read_result.get('error_message')}")
            return False

        # Then summarize them
        summarize_result = summarize_emails.invoke({
            "emails_data": read_result,
            "focus": "key points and action items"
        })

        if summarize_result.get("error"):
            print(f"✗ Error summarizing: {summarize_result.get('error_message')}")
            return False

        print(f"✓ Summarized {summarize_result.get('email_count')} emails")
        print("\nSummary:")
        print("-" * 60)
        print(summarize_result.get('summary', 'No summary generated'))
        print("-" * 60)

        return True

    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """Test complete integration with agent registry."""
    print("\n" + "="*60)
    print("TEST 5: Agent Registry Integration")
    print("="*60)

    try:
        from src.agent.agent_registry import AgentRegistry

        config = load_config()
        registry = AgentRegistry(config)

        # Get email agent
        email_agent = registry.get_agent("email")
        if not email_agent:
            print("✗ Could not get email agent from registry")
            return False

        print(f"✓ Email agent loaded")

        # Check tools
        tools = email_agent.get_tools()
        print(f"✓ Email agent has {len(tools)} tools:")
        for tool in tools:
            print(f"    - {tool.name}")

        # Test execution through registry
        result = registry.execute_tool(
            tool_name="read_latest_emails",
            inputs={"count": 2, "mailbox": "INBOX"}
        )

        if result.get("error"):
            print(f"✗ Registry execution error: {result.get('error_message')}")
            return False

        print(f"✓ Registry execution successful, got {result.get('count')} emails")

        return True

    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "EMAIL READING TEST SUITE" + " "*19 + "║")
    print("╚" + "="*58 + "╝")

    tests = [
        ("Mail.app Access", test_mail_access),
        ("Read Latest Emails", test_read_latest_emails),
        ("Read by Time Range", test_read_by_time),
        ("Email Summarization", test_summarize),
        ("Agent Integration", test_integration),
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
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
