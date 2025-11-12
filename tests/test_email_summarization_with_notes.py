#!/usr/bin/env python3
"""
Test Email Summarization Feature

This test verifies:
1. Email reading tools work correctly
2. Email summarization tools work correctly
3. Notes creation tools work correctly
4. The workflow for "summarize emails and add to notes" is functional
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent.email_agent import read_latest_emails, summarize_emails
from src.agent.notes_agent import create_note
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def test_read_emails():
    """Test 1: Reading latest emails"""
    print_section("TEST 1: Reading Latest Emails")

    print("Testing: read_latest_emails(count=5)\n")

    try:
        result = read_latest_emails.invoke({"count": 5, "mailbox": "INBOX"})

        if result.get('error'):
            print(f"⚠️  Error reading emails: {result.get('error_message')}")
            print(f"   Error type: {result.get('error_type')}")
            print(f"\n   This is expected if Mail.app is not configured or permissions not granted.")
            return None
        else:
            emails = result.get('emails', [])
            count = result.get('count', 0)
            account = result.get('account')

            print(f"✅ Successfully read {count} emails from account: {account}")

            if count > 0:
                print(f"\n📧 Sample Emails:")
                for i, email in enumerate(emails[:5], 1):
                    print(f"\n   {i}. From: {email.get('sender')}")
                    print(f"      Subject: {email.get('subject')}")
                    print(f"      Date: {email.get('date')}")
                    preview = email.get('content_preview', '')
                    if preview:
                        print(f"      Preview: {preview[:100]}...")

            return result

    except Exception as e:
        print(f"❌ Exception reading emails: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_summarize_emails(emails_data):
    """Test 2: Summarizing emails"""
    print_section("TEST 2: Summarizing Emails")

    if emails_data is None:
        print("⚠️  Skipping test - no emails data available from previous test")
        return None

    emails = emails_data.get('emails', [])
    if len(emails) == 0:
        print("⚠️  No emails to summarize")
        return None

    print(f"Testing: summarize_emails() with {len(emails)} emails\n")

    try:
        result = summarize_emails.invoke({
            "emails_data": emails_data,
            "focus": None
        })

        if result.get('error'):
            print(f"❌ Error summarizing emails: {result.get('error_message')}")
            print(f"   Error type: {result.get('error_type')}")
            return None
        else:
            summary = result.get('summary', '')
            email_count = result.get('email_count', 0)

            print(f"✅ Successfully summarized {email_count} emails")
            print(f"\n📊 Summary:\n")
            print("-" * 80)
            print(summary)
            print("-" * 80)

            return result

    except Exception as e:
        print(f"❌ Exception summarizing emails: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_create_note_with_summary(summary_data):
    """Test 3: Creating note with email summary"""
    print_section("TEST 3: Creating Note with Summary")

    if summary_data is None:
        print("⚠️  Skipping test - no summary data available from previous test")
        return None

    summary = summary_data.get('summary', '')
    if not summary:
        print("⚠️  No summary content to save")
        return None

    print(f"Testing: create_note() with email summary\n")

    try:
        result = create_note.invoke({
            "title": "Email Summary Test",
            "body": summary,
            "folder": "Notes"
        })

        if result.get('success'):
            print(f"✅ Successfully created note")
            print(f"   Title: {result.get('note_title')}")
            print(f"   Folder: {result.get('folder')}")
            print(f"   Note ID: {result.get('note_id')}")
            print(f"   Created At: {result.get('created_at')}")
            return result
        else:
            print(f"⚠️  Error creating note: {result.get('error_message')}")
            print(f"   Error type: {result.get('error_type')}")
            print(f"\n   This is expected if Notes.app permissions are not granted.")
            return None

    except Exception as e:
        print(f"❌ Exception creating note: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_workflow_integration():
    """Test 4: Complete workflow integration"""
    print_section("TEST 4: Complete Workflow Integration")

    print("Simulating workflow: 'summarize my last 3 emails and add it to notes'\n")
    print("Expected steps:")
    print("  1. read_latest_emails(count=3)")
    print("  2. summarize_emails(emails_data=$step1)")
    print("  3. create_note(title='Email Summary', body=$step2.summary)")
    print("\nExecuting workflow...\n")

    # Step 1: Read emails
    print("--- Step 1: Reading 3 latest emails ---")
    emails_result = read_latest_emails.invoke({"count": 3, "mailbox": "INBOX"})

    if emails_result.get('error'):
        print(f"⚠️  Step 1 failed: {emails_result.get('error_message')}")
        print("   Cannot continue with workflow")
        return False

    email_count = emails_result.get('count', 0)
    print(f"✅ Step 1 complete: Read {email_count} emails")

    if email_count == 0:
        print("⚠️  No emails to process. Workflow cannot continue.")
        return False

    # Step 2: Summarize emails
    print("\n--- Step 2: Summarizing emails ---")
    summary_result = summarize_emails.invoke({
        "emails_data": emails_result,
        "focus": None
    })

    if summary_result.get('error'):
        print(f"⚠️  Step 2 failed: {summary_result.get('error_message')}")
        return False

    print(f"✅ Step 2 complete: Generated summary for {summary_result.get('email_count')} emails")

    # Step 3: Create note
    print("\n--- Step 3: Creating note with summary ---")
    note_result = create_note.invoke({
        "title": "Email Summary - Integration Test",
        "body": summary_result.get('summary'),
        "folder": "Notes"
    })

    if note_result.get('success'):
        print(f"✅ Step 3 complete: Note created successfully")
        print(f"\n🎉 WORKFLOW COMPLETE")
        print(f"   - Read {email_count} emails")
        print(f"   - Generated summary")
        print(f"   - Saved to Notes app")
        return True
    else:
        print(f"⚠️  Step 3 failed: {note_result.get('error_message')}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("  EMAIL SUMMARIZATION & NOTES INTEGRATION TESTS")
    print("=" * 80)
    print("\nThis test suite verifies:")
    print("  1. Email reading functionality")
    print("  2. Email summarization functionality")
    print("  3. Notes creation functionality")
    print("  4. Complete workflow integration")
    print("\nNote: Some tests may show warnings if Mail.app or Notes.app are not")
    print("configured or if permissions have not been granted. This is expected.")

    try:
        # Test 1: Read emails
        emails_data = test_read_emails()

        # Test 2: Summarize emails
        summary_data = test_summarize_emails(emails_data)

        # Test 3: Create note
        note_data = test_create_note_with_summary(summary_data)

        # Test 4: Complete workflow
        workflow_success = test_workflow_integration()

        # Final summary
        print_section("FINAL SUMMARY")

        print("Test Results:")
        print(f"  1. Email Reading:       {'✅ PASS' if emails_data else '⚠️  SKIP/FAIL'}")
        print(f"  2. Email Summarization: {'✅ PASS' if summary_data else '⚠️  SKIP/FAIL'}")
        print(f"  3. Note Creation:       {'✅ PASS' if note_data else '⚠️  SKIP/FAIL'}")
        print(f"  4. Workflow Integration: {'✅ PASS' if workflow_success else '⚠️  SKIP/FAIL'}")

        print("\n" + "=" * 80)

        if all([emails_data, summary_data, note_data, workflow_success]):
            print("  ALL TESTS PASSED ✅")
            print("=" * 80)
            print("\n✅ The feature is working correctly!")
            print("\nYou can now use:")
            print("  • 'summarize my last 5 emails'")
            print("  • 'summarize the last 3 emails and add it to notes'")
        else:
            print("  SOME TESTS FAILED OR SKIPPED")
            print("=" * 80)
            print("\n⚠️  Some functionality may not be working.")
            print("\nPossible reasons:")
            print("  • Mail.app is not configured")
            print("  • Notes.app permissions not granted")
            print("  • No emails in inbox")
            print("\nPlease check the output above for details.")

        print("\n📝 Next Steps:")
        print("  1. Ensure Mail.app is configured with your email account")
        print("  2. Grant necessary permissions to Terminal/Python for Mail.app and Notes.app")
        print("  3. Try the feature in the main UI")

    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
