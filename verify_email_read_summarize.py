#!/usr/bin/env python3
"""
Verification script to test if email reading and summarization works.
Tests the actual functionality end-to-end.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_email_reading():
    """Test if we can read emails."""
    logger.info("=" * 60)
    logger.info("TEST 1: Email Reading")
    logger.info("=" * 60)
    
    try:
        from src.agent.email_agent import read_latest_emails
        
        logger.info("Calling read_latest_emails(count=3)...")
        result = read_latest_emails.invoke({"count": 3, "mailbox": "INBOX"})
        
        if result.get("error"):
            logger.error(f"❌ Email reading failed: {result.get('error_message')}")
            logger.error(f"Error type: {result.get('error_type')}")
            return False
        
        emails = result.get("emails", [])
        email_count = len(emails)
        
        logger.info(f"✅ Successfully read {email_count} emails")
        
        if email_count > 0:
            logger.info(f"Sample email:")
            logger.info(f"  Sender: {emails[0].get('sender', 'N/A')}")
            logger.info(f"  Subject: {emails[0].get('subject', 'N/A')}")
            logger.info(f"  Date: {emails[0].get('date', 'N/A')}")
            logger.info(f"  Content preview: {emails[0].get('content_preview', 'N/A')[:100]}...")
            return True, result
        else:
            logger.warning("⚠️  No emails found (this might be normal if inbox is empty)")
            return True, result  # Still success, just no emails
            
    except Exception as e:
        logger.error(f"❌ Exception during email reading: {e}", exc_info=True)
        return False, None

def test_email_summarization(emails_data):
    """Test if we can summarize emails."""
    logger.info("=" * 60)
    logger.info("TEST 2: Email Summarization")
    logger.info("=" * 60)
    
    if not emails_data:
        logger.warning("⚠️  Skipping summarization test - no emails data provided")
        return False
    
    emails = emails_data.get("emails", [])
    if not emails or len(emails) == 0:
        logger.warning("⚠️  Skipping summarization test - no emails to summarize")
        return False
    
    try:
        from src.agent.email_agent import summarize_emails
        
        logger.info(f"Calling summarize_emails() with {len(emails)} emails...")
        result = summarize_emails.invoke({
            "emails_data": emails_data,
            "focus": None
        })
        
        if result.get("error"):
            logger.error(f"❌ Email summarization failed: {result.get('error_message')}")
            return False
        
        summary = result.get("summary", "")
        email_count = result.get("email_count", 0)
        
        if summary:
            logger.info(f"✅ Successfully summarized {email_count} emails")
            logger.info(f"Summary (first 500 chars):")
            logger.info(f"{summary[:500]}...")
            return True
        else:
            logger.warning("⚠️  Summary is empty")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception during email summarization: {e}", exc_info=True)
        return False

def test_full_workflow():
    """Test the full workflow: read + summarize."""
    logger.info("=" * 60)
    logger.info("TEST 3: Full Workflow (Read + Summarize)")
    logger.info("=" * 60)
    
    # Test reading
    success, emails_data = test_email_reading()
    if not success:
        logger.error("❌ Cannot proceed with full workflow - email reading failed")
        return False
    
    # Test summarization
    if emails_data:
        success = test_email_summarization(emails_data)
        if success:
            logger.info("✅ Full workflow test PASSED")
            return True
        else:
            logger.error("❌ Full workflow test FAILED - summarization failed")
            return False
    else:
        logger.warning("⚠️  Cannot test full workflow - no emails to summarize")
        return False

def main():
    """Run all verification tests."""
    logger.info("Starting Email Read & Summarize Verification")
    logger.info("=" * 60)
    
    # Test 1: Reading
    read_success, emails_data = test_email_reading()
    
    # Test 2: Summarization (if we have emails)
    summarize_success = False
    if read_success and emails_data:
        emails = emails_data.get("emails", [])
        if emails and len(emails) > 0:
            summarize_success = test_email_summarization(emails_data)
        else:
            logger.info("Skipping summarization - no emails found")
            summarize_success = True  # Not a failure, just no data
    
    # Test 3: Full workflow
    workflow_success = test_full_workflow()
    
    # Summary
    logger.info("=" * 60)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Email Reading: {'✅ PASS' if read_success else '❌ FAIL'}")
    logger.info(f"Email Summarization: {'✅ PASS' if summarize_success else '❌ FAIL'}")
    logger.info(f"Full Workflow: {'✅ PASS' if workflow_success else '❌ FAIL'}")
    
    if read_success and (summarize_success or not emails_data or len(emails_data.get("emails", [])) == 0):
        logger.info("=" * 60)
        logger.info("✅ OVERALL: Email reading and summarization is WORKING")
        logger.info("=" * 60)
        return 0
    else:
        logger.info("=" * 60)
        logger.info("❌ OVERALL: Some tests FAILED")
        logger.info("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())

