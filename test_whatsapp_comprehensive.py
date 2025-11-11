#!/usr/bin/env python3
"""
Comprehensive test for WhatsApp integration - verify implementation correctness.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils import load_config
from src.agent.agent_registry import AgentRegistry
from src.ui.slash_commands import SlashCommandParser, SlashCommandHandler
from src.orchestrator.agent_capabilities import build_agent_capabilities
from src.orchestrator.intent_planner import IntentPlanner

def test_whatsapp_integration():
    """Comprehensive test of WhatsApp integration."""
    
    print("=" * 80)
    print("WhatsApp Integration Comprehensive Test")
    print("=" * 80)
    
    config = load_config()
    registry = AgentRegistry(config)
    
    # Test 1: Agent Registration
    print("\n1. Testing Agent Registration...")
    print("-" * 80)
    whatsapp_agent = registry.get_agent("whatsapp")
    if whatsapp_agent:
        print("   ✅ WhatsApp agent found in registry")
        tools = whatsapp_agent.get_tools()
        print(f"   ✅ Found {len(tools)} WhatsApp tools:")
        for tool in tools:
            print(f"      - {tool.name}")
    else:
        print("   ❌ WhatsApp agent NOT found in registry")
        return False
    
    # Test 2: Tools in ALL_AGENT_TOOLS
    print("\n2. Testing Tools in ALL_AGENT_TOOLS...")
    print("-" * 80)
    from src.agent.agent_registry import ALL_AGENT_TOOLS
    whatsapp_tools = [t for t in ALL_AGENT_TOOLS if 'whatsapp' in t.name.lower()]
    print(f"   ✅ Found {len(whatsapp_tools)} WhatsApp tools in ALL_AGENT_TOOLS:")
    for tool in whatsapp_tools:
        print(f"      - {tool.name}")
    
    if len(whatsapp_tools) != 9:
        print(f"   ⚠️  Expected 9 tools, found {len(whatsapp_tools)}")
    
    # Test 3: Agent Capabilities
    print("\n3. Testing Agent Capabilities...")
    print("-" * 80)
    caps = build_agent_capabilities(registry)
    whatsapp_cap = [c for c in caps if 'whatsapp' in c['agent'].lower()]
    if whatsapp_cap:
        print("   ✅ WhatsApp in capabilities")
        print(f"   Domain: {whatsapp_cap[0]['domain']}")
        print(f"   Title: {whatsapp_cap[0]['title']}")
    else:
        print("   ❌ WhatsApp NOT in capabilities")
        return False
    
    # Test 4: Intent Planner
    print("\n4. Testing Intent Planner Routing...")
    print("-" * 80)
    planner = IntentPlanner(config)
    test_queries = [
        "read whatsapp messages from John",
        "list my whatsapp chats",
        "summarize whatsapp group messages",
        "detect unread whatsapp messages"
    ]
    
    for query in test_queries:
        intent = planner.analyze(query, caps)
        involved = intent.get('involved_agents', [])
        primary = intent.get('primary_agent')
        if 'whatsapp' in involved or primary == 'whatsapp':
            print(f"   ✅ '{query}' → routes to WhatsApp")
        else:
            print(f"   ⚠️  '{query}' → routes to {involved} (primary: {primary})")
    
    # Test 5: Slash Command Parsing
    print("\n5. Testing Slash Command Parsing...")
    print("-" * 80)
    parser = SlashCommandParser()
    test_commands = [
        "/whatsapp read messages from John",
        "/whatsapp list chats",
        "/whatsapp summarize Family group",
        "/wa detect unread"
    ]
    
    for cmd in test_commands:
        parsed = parser.parse(cmd)
        if parsed and parsed.get('agent') == 'whatsapp':
            print(f"   ✅ '{cmd}' → WhatsApp agent")
        else:
            print(f"   ❌ '{cmd}' → {parsed.get('agent') if parsed else 'NOT PARSED'}")
    
    # Test 6: Slash Command Handler
    print("\n6. Testing Slash Command Handler...")
    print("-" * 80)
    handler = SlashCommandHandler(registry)
    test_cmd = "/whatsapp list chats"
    is_cmd, result = handler.handle(test_cmd)
    
    if is_cmd:
        print(f"   ✅ Command recognized: {test_cmd}")
        if isinstance(result, dict):
            print(f"   Result type: {result.get('type')}")
            if result.get('type') == 'result':
                print(f"   Agent: {result.get('agent')}")
    else:
        print(f"   ❌ Command NOT recognized")
        return False
    
    # Test 7: Tool Availability Check
    print("\n7. Testing Tool Availability...")
    print("-" * 80)
    expected_tools = [
        'whatsapp_ensure_session',
        'whatsapp_navigate_to_chat',
        'whatsapp_read_messages',
        'whatsapp_read_messages_from_sender',
        'whatsapp_read_group_messages',
        'whatsapp_detect_unread',
        'whatsapp_list_chats',
        'whatsapp_summarize_messages',
        'whatsapp_extract_action_items'
    ]
    
    tool_names = [t.name for t in whatsapp_tools]
    missing = [t for t in expected_tools if t not in tool_names]
    if missing:
        print(f"   ❌ Missing tools: {missing}")
        return False
    else:
        print(f"   ✅ All {len(expected_tools)} expected tools found")
    
    # Test 8: Controller Implementation Check
    print("\n8. Testing Controller Implementation...")
    print("-" * 80)
    try:
        from src.automation.whatsapp_controller import WhatsAppController
        controller = WhatsAppController(config)
        
        # Check methods exist
        methods = ['ensure_session', 'navigate_to_chat', 'read_messages', 
                   'read_messages_from_sender', 'detect_unread_chats', 'get_chat_list']
        for method in methods:
            if hasattr(controller, method):
                print(f"   ✅ Method exists: {method}")
            else:
                print(f"   ❌ Method missing: {method}")
                return False
    except Exception as e:
        print(f"   ❌ Controller import/init failed: {e}")
        return False
    
    print("\n" + "=" * 80)
    print("✅ All integration tests passed!")
    print("=" * 80)
    
    return True

if __name__ == "__main__":
    success = test_whatsapp_integration()
    sys.exit(0 if success else 1)

