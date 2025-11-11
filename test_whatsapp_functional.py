#!/usr/bin/env python3
"""
Functional test for WhatsApp - test actual WhatsApp operations.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils import load_config
from src.agent.agent import AutomationAgent
from src.memory import SessionManager

def test_whatsapp_functional():
    """Test WhatsApp functionality end-to-end."""
    
    print("=" * 80)
    print("WhatsApp Functional Test")
    print("=" * 80)
    print("\n⚠️  Note: This test requires WhatsApp Desktop to be running and logged in.")
    print("⚠️  Make sure you have granted accessibility permissions.\n")
    
    config = load_config()
    session_manager = SessionManager(storage_dir="data/sessions")
    agent = AutomationAgent(config, session_manager=session_manager)
    
    # Test 1: Ensure session
    print("\n1. Testing: whatsapp_ensure_session")
    print("-" * 80)
    try:
        result = agent.run("ensure whatsapp session is active", session_id="test_whatsapp")
        print(f"   Status: {result.get('status')}")
        print(f"   Message: {result.get('message', 'N/A')[:200]}")
        if result.get('status') == 'success':
            print("   ✅ Session check completed")
        else:
            print("   ⚠️  Session check may have issues (check if WhatsApp is running)")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: List chats
    print("\n2. Testing: /whatsapp list chats")
    print("-" * 80)
    try:
        result = agent.run("/whatsapp list chats", session_id="test_whatsapp")
        print(f"   Status: {result.get('status')}")
        print(f"   Message: {result.get('message', 'N/A')[:300]}")
        if result.get('status') == 'success':
            print("   ✅ List chats command executed")
        else:
            print("   ⚠️  List chats may have issues")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: Natural language - read messages
    print("\n3. Testing: 'read whatsapp messages' (natural language)")
    print("-" * 80)
    print("   Note: This will try to read from a chat. You may need to specify a contact name.")
    try:
        result = agent.run("read whatsapp messages", session_id="test_whatsapp")
        print(f"   Status: {result.get('status')}")
        print(f"   Message: {result.get('message', 'N/A')[:300]}")
        if result.get('status') == 'success':
            print("   ✅ Natural language command executed")
        else:
            print("   ⚠️  Command may need a specific contact name")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 4: Detect unread
    print("\n4. Testing: 'detect unread whatsapp messages'")
    print("-" * 80)
    try:
        result = agent.run("detect unread whatsapp messages", session_id="test_whatsapp")
        print(f"   Status: {result.get('status')}")
        print(f"   Message: {result.get('message', 'N/A')[:300]}")
        if result.get('status') == 'success':
            print("   ✅ Unread detection executed")
        else:
            print("   ⚠️  Unread detection may have issues")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 80)
    print("Functional test completed!")
    print("=" * 80)
    print("\nNote: Some tests may fail if:")
    print("  1. WhatsApp Desktop is not running")
    print("  2. WhatsApp is not logged in")
    print("  3. Accessibility permissions are not granted")
    print("  4. No chats are available")
    print("=" * 80)

if __name__ == "__main__":
    test_whatsapp_functional()

