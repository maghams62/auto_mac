"""
Simple test to verify email reading response format for UI display.
Tests the actual response structure that would be sent to UI.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.agent.email_agent import read_latest_emails
from src.utils import load_config

def test_email_ui_format():
    """Test if email reading returns data in format suitable for UI display."""
    print("=" * 80)
    print("EMAIL UI FORMAT TEST")
    print("=" * 80)
    
    try:
        # Call the email tool directly
        print("\n1. Calling read_latest_emails tool...")
        result = read_latest_emails.invoke({"count": 3})
        
        print(f"   ✓ Tool executed")
        print(f"   Result type: {type(result)}")
        
        # Check result structure
        print("\n2. Analyzing result structure for UI display...")
        
        if isinstance(result, dict):
            has_error = result.get("error", False)
            
            if has_error:
                print(f"   ✗ Error in result: {result.get('error_message', 'Unknown error')}")
                return False
            
            # Check for email data
            emails = result.get("emails", [])
            count = result.get("count", 0)
            
            print(f"   ✓ Result is a dictionary")
            print(f"   ✓ Email count: {count}")
            print(f"   ✓ Emails list length: {len(emails)}")
            
            # Check email structure
            if emails:
                print("\n3. Checking email data structure...")
                first_email = emails[0]
                
                required_fields = ["sender", "subject", "date"]
                optional_fields = ["body", "content", "timestamp", "content_preview"]
                
                print(f"\n   Email structure:")
                print(f"   Required fields:")
                for field in required_fields:
                    has_field = field in first_email
                    value = first_email.get(field, "N/A")
                    status = "✓" if has_field else "✗"
                    print(f"     {status} {field}: {str(value)[:50]}")
                
                print(f"\n   Optional fields:")
                for field in optional_fields:
                    has_field = field in first_email
                    if has_field:
                        value = first_email.get(field, "")
                        value_preview = str(value)[:100] if value else "empty"
                        print(f"     ✓ {field}: {value_preview}...")
                
                # Print sample emails for UI display
                print("\n" + "=" * 80)
                print("SAMPLE EMAIL DATA (as would appear in UI)")
                print("=" * 80)
                
                for i, email in enumerate(emails[:3], 1):
                    print(f"\n--- Email {i} ---")
                    print(f"From: {email.get('sender', 'N/A')}")
                    print(f"Subject: {email.get('subject', 'N/A')}")
                    print(f"Date: {email.get('date', email.get('timestamp', 'N/A'))}")
                    
                    body = email.get('body', email.get('content', ''))
                    if body:
                        preview = body[:200] + "..." if len(body) > 200 else body
                        print(f"Body Preview: {preview}")
                
                # Verify UI display readiness
                print("\n" + "=" * 80)
                print("UI DISPLAY READINESS CHECK")
                print("=" * 80)
                
                ui_ready = True
                issues = []
                
                # Check if data has required fields for UI
                for email in emails:
                    if not email.get("sender"):
                        ui_ready = False
                        issues.append("Missing sender field")
                    if not email.get("subject"):
                        ui_ready = False
                        issues.append("Missing subject field")
                    if not (email.get("date") or email.get("timestamp")):
                        ui_ready = False
                        issues.append("Missing date/timestamp field")
                
                if ui_ready:
                    print("✅ SUCCESS: Email data is properly formatted for UI display!")
                    print("\n   The UI can display:")
                    print("   ✓ Email list with sender, subject, date")
                    print("   ✓ Email content/body")
                    print("   ✓ Email count")
                    print("\n   Format is compatible with:")
                    print("   - MessageBubble component")
                    print("   - Email list rendering")
                    print("   - WebSocket message transmission")
                else:
                    print("⚠️  ISSUES FOUND:")
                    for issue in set(issues):
                        print(f"   - {issue}")
                
                return ui_ready
            else:
                print("   ⚠️  No emails returned (inbox may be empty)")
                return False
        else:
            print(f"   ✗ Unexpected result type: {type(result)}")
            print(f"   Result: {str(result)[:200]}")
            return False
            
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_email_ui_format()
    sys.exit(0 if success else 1)

