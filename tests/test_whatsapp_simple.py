"""
Simple WhatsApp integration test - tests controller directly without agent dependencies.
"""

import sys
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import load_config
from src.automation.whatsapp_controller import WhatsAppController


def test_whatsapp_functionality():
    """Test WhatsApp functionality step by step."""
    print("\n" + "="*70)
    print("WHATSAPP INTEGRATION TEST")
    print("="*70)
    print("\nThis test will verify WhatsApp Desktop integration.")
    print("Make sure WhatsApp Desktop is running and you're logged in.\n")
    
    try:
        config = load_config()
        controller = WhatsAppController(config)
        
        # Test 1: Session verification
        print("1️⃣  Testing session verification...")
        session_result = controller.ensure_session()
        print(f"   Result: {json.dumps(session_result, indent=6)}")
        
        if session_result.get("error"):
            print(f"\n❌ Session check failed: {session_result.get('error_message')}")
            print("\nPlease ensure:")
            print("  - WhatsApp Desktop is installed")
            print("  - WhatsApp Desktop is running")
            print("  - You are logged in to WhatsApp")
            return False
        
        print("   ✅ Session verified\n")
        
        # Test 2: List chats
        print("2️⃣  Testing chat list retrieval...")
        chats_result = controller.get_chat_list()
        print(f"   Found {chats_result.get('total', 0)} chats/groups")
        
        if chats_result.get("error"):
            print(f"   ⚠️  Warning: {chats_result.get('error_message')}")
        else:
            chats = chats_result.get("chats", [])
            if chats:
                print(f"   Sample chats: {', '.join(chats[:5])}")
            print("   ✅ Chat list retrieved\n")
        
        # Test 3: Detect unread
        print("3️⃣  Testing unread detection...")
        unread_result = controller.detect_unread_chats()
        unread_count = len(unread_result.get("unread_chats", []))
        print(f"   Found {unread_count} unread chats")
        if unread_result.get("error"):
            print(f"   ⚠️  Warning: {unread_result.get('error_message')}")
        else:
            print("   ✅ Unread detection working\n")
        
        # Test 4: Interactive navigation and reading
        print("4️⃣  Testing navigation and message reading...")
        print("   Enter a contact name or group name to test:")
        print("   (Press Enter to skip this test)")
        contact_name = input("   Contact/Group: ").strip()
        
        if contact_name:
            is_group_input = input("   Is this a group? (y/n): ").strip().lower()
            is_group = is_group_input == 'y'
            
            print(f"\n   Navigating to '{contact_name}'...")
            nav_result = controller.navigate_to_chat(contact_name, is_group)
            
            if nav_result.get("error"):
                print(f"   ❌ Navigation failed: {nav_result.get('error_message')}")
                print("\n   Troubleshooting:")
                print("   - Make sure the contact/group name matches exactly")
                print("   - Try using the exact name as shown in WhatsApp")
                print("   - For groups, make sure is_group=True")
            else:
                print(f"   ✅ Successfully navigated to {contact_name}\n")
                
                # Read messages
                print(f"   Reading messages from '{contact_name}'...")
                read_result = controller.read_messages(contact_name, limit=10, is_group=is_group, skip_navigation=True)
                
                if read_result.get("error"):
                    print(f"   ❌ Reading failed: {read_result.get('error_message')}")
                    print("\n   Note: This might be due to:")
                    print("   - WhatsApp UI structure differences")
                    print("   - Accessibility permissions not granted")
                    print("   - No messages in the chat")
                else:
                    messages = read_result.get("messages", [])
                    print(f"   ✅ Read {len(messages)} messages")
                    
                    if messages:
                        print("\n   Sample messages:")
                        for i, msg in enumerate(messages[:3], 1):
                            preview = msg[:80] + "..." if len(msg) > 80 else msg
                            print(f"      {i}. {preview}")
                    
                    # Test summarization if we have messages
                    if messages and len(messages) > 0:
                        print("\n   Testing AI summarization...")
                        try:
                            from src.agent.whatsapp_agent import _summarize_messages_with_llm
                            summary = _summarize_messages_with_llm(
                                config, 
                                messages, 
                                contact_name, 
                                is_group
                            )
                            print(f"   ✅ Summary generated ({len(summary)} chars)")
                            print(f"\n   Summary:\n   {summary[:300]}...")
                        except Exception as e:
                            print(f"   ⚠️  Summarization skipped: {e}")
                    
                    # Test sender filtering if group
                    if is_group and messages:
                        print("\n   Testing sender filtering...")
                        sender_name = input("   Enter a sender name to filter: ").strip()
                        if sender_name:
                            filter_result = controller.read_messages_from_sender(
                                contact_name, 
                                sender_name, 
                                limit=5
                            )
                            if filter_result.get("error"):
                                print(f"   ⚠️  Filtering warning: {filter_result.get('error_message')}")
                            else:
                                filtered = filter_result.get("messages", [])
                                print(f"   ✅ Found {len(filtered)} messages from {sender_name}")
                                if filtered:
                                    print("   Sample filtered messages:")
                                    for i, msg in enumerate(filtered[:2], 1):
                                        print(f"      {i}. {msg[:60]}...")
        else:
            print("   ⏭️  Skipped (no contact name provided)\n")
        
        print("\n" + "="*70)
        print("TEST COMPLETE")
        print("="*70)
        print("\n✅ Basic WhatsApp integration is working!")
        print("\nNext steps:")
        print("  - Test with actual WhatsApp contacts/groups")
        print("  - Verify UI element extraction works correctly")
        print("  - Test summarization with longer conversations")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
        return False
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_whatsapp_functionality()

