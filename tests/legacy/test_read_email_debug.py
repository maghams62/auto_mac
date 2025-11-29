"""
Debug test to read emails with detailed logging.
Success criteria: Can print out the email content.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from src.automation import MailReader
from src.utils import load_config

def test_read_email_debug():
    """Test reading emails with debug output."""
    print("=" * 80)
    print("EMAIL READING DEBUG TEST")
    print("=" * 80)
    
    try:
        # Load config
        print("\n1. Loading configuration...")
        config = load_config()
        email_config = config.get("email", {})
        account_email = email_config.get("account_email")
        print(f"   Account email: {account_email or 'Not configured'}")
        
        # Initialize MailReader
        print("\n2. Initializing MailReader...")
        mail_reader = MailReader(config)
        
        # Test Mail.app accessibility
        print("\n3. Testing Mail.app accessibility...")
        if not mail_reader.test_mail_access():
            print("   ✗ Mail.app is not accessible")
            return False
        print("   ✓ Mail.app is accessible")
        
        # Try reading with different parameters
        print("\n4. Attempting to read emails...")
        
        # Try with account name
        if account_email:
            print(f"   Trying with account: {account_email}")
            emails = mail_reader.read_latest_emails(count=5, account_name=account_email)
            if emails:
                print(f"   ✓ Found {len(emails)} email(s) with account name")
                print_emails(emails)
                return True
        
        # Try without account name
        print("   Trying without account name...")
        emails = mail_reader.read_latest_emails(count=5)
        if emails:
            print(f"   ✓ Found {len(emails)} email(s) without account name")
            print_emails(emails)
            return True
        
        # Try with different mailbox
        print("   Trying with different mailboxes...")
        for mailbox in ["INBOX", "Inbox", "inbox"]:
            print(f"   Trying mailbox: {mailbox}")
            emails = mail_reader.read_latest_emails(count=5, mailbox_name=mailbox)
            if emails:
                print(f"   ✓ Found {len(emails)} email(s) in {mailbox}")
                print_emails(emails)
                return True
        
        print("   ✗ No emails found with any configuration")
        print("\n   Possible reasons:")
        print("   - Inbox is empty")
        print("   - Account configuration mismatch")
        print("   - AppleScript execution issue")
        return False
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def print_emails(emails):
    """Print email content."""
    print("\n" + "=" * 80)
    print("EMAIL CONTENT")
    print("=" * 80)
    
    for i, email in enumerate(emails, 1):
        print(f"\n--- Email {i} of {len(emails)} ---")
        print(f"From: {email.get('sender', 'N/A')}")
        print(f"Subject: {email.get('subject', 'N/A')}")
        print(f"Date: {email.get('date', email.get('timestamp', 'N/A'))}")
        
        # Print body content
        body = email.get('body', email.get('content', ''))
        if body:
            print(f"\nBody:")
            print("-" * 40)
            print(body)
            print("-" * 40)
        else:
            print("\nBody: (empty or not available)")
        
        # Print all keys for debugging
        print(f"\nAvailable keys: {list(email.keys())}")

if __name__ == "__main__":
    success = test_read_email_debug()
    sys.exit(0 if success else 1)

