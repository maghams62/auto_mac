"""
Test script for WhatsApp integration functionality.

Tests:
1. Session verification
2. Navigation to chats/groups
3. Reading messages
4. Summarization
5. Sender filtering
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import load_config
from src.automation.whatsapp_controller import WhatsAppController
from src.agent.whatsapp_agent import WhatsAppAgent
import json


def test_session_verification():
    """Test WhatsApp session verification."""
    print("\n" + "="*60)
    print("TEST 1: Session Verification")
    print("="*60)
    
    config = load_config()
    controller = WhatsAppController(config)
    
    result = controller.ensure_session()
    print(f"Result: {json.dumps(result, indent=2)}")
    
    if result.get("error"):
        print(f"❌ Session verification failed: {result.get('error_message')}")
        return False
    
    print("✅ Session verification successful")
    return True


def test_navigation(contact_name: str, is_group: bool = False):
    """Test navigation to a chat/group."""
    print("\n" + "="*60)
    print(f"TEST 2: Navigation to {'Group' if is_group else 'Chat'}")
    print(f"Target: {contact_name}")
    print("="*60)
    
    config = load_config()
    controller = WhatsAppController(config)
    
    result = controller.navigate_to_chat(contact_name, is_group)
    print(f"Result: {json.dumps(result, indent=2)}")
    
    if result.get("error"):
        print(f"❌ Navigation failed: {result.get('error_message')}")
        return False
    
    print(f"✅ Successfully navigated to {contact_name}")
    return True


def test_read_messages(contact_name: str, limit: int = 10, is_group: bool = False):
    """Test reading messages from a chat/group."""
    print("\n" + "="*60)
    print(f"TEST 3: Reading Messages")
    print(f"Contact: {contact_name} (Group: {is_group})")
    print(f"Limit: {limit}")
    print("="*60)
    
    config = load_config()
    controller = WhatsAppController(config)
    
    result = controller.read_messages(contact_name, limit=limit, is_group=is_group)
    print(f"Result: {json.dumps(result, indent=2)}")
    
    if result.get("error"):
        print(f"❌ Reading messages failed: {result.get('error_message')}")
        return False
    
    messages = result.get("messages", [])
    print(f"\n✅ Successfully read {len(messages)} messages")
    
    if messages:
        print("\nSample messages:")
        for i, msg in enumerate(messages[:3], 1):
            print(f"  {i}. {msg[:100]}...")
    
    return True


def test_summarization(contact_name: str, is_group: bool = False):
    """Test AI-powered message summarization."""
    print("\n" + "="*60)
    print(f"TEST 4: Message Summarization")
    print(f"Contact: {contact_name} (Group: {is_group})")
    print("="*60)
    
    config = load_config()
    agent = WhatsAppAgent(config)
    
    result = agent.execute("whatsapp_summarize_messages", {
        "contact_name": contact_name,
        "is_group": is_group,
        "limit": 30
    })
    
    print(f"Result: {json.dumps(result, indent=2)}")
    
    if result.get("error"):
        print(f"❌ Summarization failed: {result.get('error_message')}")
        return False
    
    summary = result.get("summary", "")
    if summary:
        print(f"\n✅ Summary generated ({len(summary)} characters)")
        print(f"\nSummary:\n{summary}")
    else:
        print("⚠️  No summary generated (may be no messages)")
    
    return True


def test_sender_filtering(group_name: str, sender_name: str):
    """Test filtering messages by sender in a group."""
    print("\n" + "="*60)
    print(f"TEST 5: Sender Filtering")
    print(f"Group: {group_name}")
    print(f"Sender: {sender_name}")
    print("="*60)
    
    config = load_config()
    agent = WhatsAppAgent(config)
    
    result = agent.execute("whatsapp_read_messages_from_sender", {
        "contact_name": group_name,
        "sender_name": sender_name,
        "limit": 10
    })
    
    print(f"Result: {json.dumps(result, indent=2)}")
    
    if result.get("error"):
        print(f"❌ Sender filtering failed: {result.get('error_message')}")
        return False
    
    messages = result.get("messages", [])
    print(f"\n✅ Found {len(messages)} messages from {sender_name}")
    
    if messages:
        print("\nSample messages:")
        for i, msg in enumerate(messages[:3], 1):
            print(f"  {i}. {msg[:100]}...")
    
    return True


def test_list_chats():
    """Test listing all available chats."""
    print("\n" + "="*60)
    print("TEST 6: List All Chats")
    print("="*60)
    
    config = load_config()
    controller = WhatsAppController(config)
    
    result = controller.get_chat_list()
    print(f"Result: {json.dumps(result, indent=2)}")
    
    if result.get("error"):
        print(f"❌ Listing chats failed: {result.get('error_message')}")
        return False
    
    chats = result.get("chats", [])
    print(f"\n✅ Found {len(chats)} chats/groups")
    
    if chats:
        print("\nAvailable chats/groups:")
        for i, chat in enumerate(chats[:10], 1):  # Show first 10
            print(f"  {i}. {chat}")
        if len(chats) > 10:
            print(f"  ... and {len(chats) - 10} more")
    
    return True


def test_detect_unread():
    """Test detecting unread chats."""
    print("\n" + "="*60)
    print("TEST 7: Detect Unread Chats")
    print("="*60)
    
    config = load_config()
    controller = WhatsAppController(config)
    
    result = controller.detect_unread_chats()
    print(f"Result: {json.dumps(result, indent=2)}")
    
    if result.get("error"):
        print(f"❌ Unread detection failed: {result.get('error_message')}")
        return False
    
    unread_chats = result.get("unread_chats", [])
    print(f"\n✅ Found {len(unread_chats)} unread chats")
    
    if unread_chats:
        print("\nUnread chats:")
        for i, chat in enumerate(unread_chats, 1):
            print(f"  {i}. {chat}")
    else:
        print("  No unread chats detected")
    
    return True


def main():
    """Run all WhatsApp integration tests."""
    print("\n" + "="*60)
    print("WHATSAPP INTEGRATION TEST SUITE")
    print("="*60)
    print("\nThis will test WhatsApp Desktop integration.")
    print("Make sure WhatsApp Desktop is running and you're logged in.")
    print("\nPress Enter to continue or Ctrl+C to cancel...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n\nTest cancelled.")
        return
    
    results = []
    
    # Test 1: Session verification
    results.append(("Session Verification", test_session_verification()))
    
    if not results[-1][1]:
        print("\n❌ Session verification failed. Cannot continue tests.")
        print("Please ensure WhatsApp Desktop is running and logged in.")
        return
    
    # Test 2: List chats (to discover available chats)
    results.append(("List Chats", test_list_chats()))
    
    # Test 3: Detect unread
    results.append(("Detect Unread", test_detect_unread()))
    
    # Test 4: Navigation (using a test contact - user should provide)
    print("\n" + "="*60)
    print("INTERACTIVE TEST: Navigation and Reading")
    print("="*60)
    print("\nEnter a contact name or group name to test:")
    print("(Or press Enter to skip navigation/reading tests)")
    contact_name = input("Contact/Group name: ").strip()
    
    if contact_name:
        is_group_input = input("Is this a group? (y/n, default: n): ").strip().lower()
        is_group = is_group_input == 'y'
        
        results.append(("Navigation", test_navigation(contact_name, is_group)))
        results.append(("Read Messages", test_read_messages(contact_name, limit=10, is_group=is_group)))
        results.append(("Summarization", test_summarization(contact_name, is_group=is_group)))
        
        # Test sender filtering if it's a group
        if is_group:
            print("\n" + "="*60)
            print("INTERACTIVE TEST: Sender Filtering")
            print("="*60)
            sender_name = input(f"Enter a sender name to filter messages from in '{contact_name}': ").strip()
            if sender_name:
                results.append(("Sender Filtering", test_sender_filtering(contact_name, sender_name)))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")


if __name__ == "__main__":
    main()

