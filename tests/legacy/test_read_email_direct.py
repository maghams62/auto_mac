"""
Direct test to read emails and print them out.
Success criteria: Can print out the email content.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.automation import MailReader
from src.utils import load_config

def test_read_email():
    """Test reading emails and print them out."""
    print("=" * 80)
    print("EMAIL READING TEST")
    print("=" * 80)
    
    try:
        # Load config
        print("\n1. Loading configuration...")
        config = load_config()
        print("   ✓ Configuration loaded")
        
        # Initialize MailReader
        print("\n2. Initializing MailReader...")
        mail_reader = MailReader(config)
        print("   ✓ MailReader initialized")
        
        # Test Mail.app accessibility
        print("\n3. Testing Mail.app accessibility...")
        if not mail_reader.test_mail_access():
            print("   ✗ Mail.app is not accessible")
            print("   Please ensure:")
            print("   - Mail.app is running")
            print("   - Automation permissions are granted in System Settings")
            return False
        print("   ✓ Mail.app is accessible")
        
        # Read latest emails
        print("\n4. Reading latest 5 emails...")
        emails = mail_reader.read_latest_emails(count=5)
        
        if not emails:
            print("   ✗ No emails found")
            return False
        
        print(f"   ✓ Found {len(emails)} email(s)")
        
        # Print out each email
        print("\n" + "=" * 80)
        print("EMAIL CONTENT")
        print("=" * 80)
        
        for i, email in enumerate(emails, 1):
            print(f"\n--- Email {i} of {len(emails)} ---")
            print(f"From: {email.get('sender', 'N/A')}")
            print(f"Subject: {email.get('subject', 'N/A')}")
            print(f"Date: {email.get('date', 'N/A')}")
            print(f"Timestamp: {email.get('timestamp', 'N/A')}")
            
            # Print body content
            body = email.get('body', email.get('content', ''))
            if body:
                print(f"\nBody:")
                print("-" * 40)
                # Print first 500 chars, or full body if shorter
                body_preview = body[:500] if len(body) > 500 else body
                print(body_preview)
                if len(body) > 500:
                    print(f"\n... (truncated, total {len(body)} characters)")
                print("-" * 40)
            else:
                print("\nBody: (empty or not available)")
            
            # Print content preview if available
            content_preview = email.get('content_preview', '')
            if content_preview and content_preview != body:
                print(f"\nPreview: {content_preview[:200]}")
        
        print("\n" + "=" * 80)
        print("SUCCESS: Emails read and printed successfully!")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_read_email()
    sys.exit(0 if success else 1)

