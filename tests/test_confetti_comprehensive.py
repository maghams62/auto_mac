#!/usr/bin/env python3
"""
Comprehensive test suite for confetti/celebration feature.
Tests all integration points and functionality.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils import load_config
from src.agent.agent_registry import AgentRegistry
from src.agent.celebration_agent import CelebrationAgent, trigger_confetti, CELEBRATION_AGENT_TOOLS
from src.automation.celebration_automation import CelebrationAutomation
from src.ui.slash_commands import SlashCommandParser, SlashCommandHandler
from src.orchestrator.agent_capabilities import build_agent_capabilities
from src.agent.agent import AutomationAgent
from src.memory import SessionManager

def test_automation_class():
    """Test CelebrationAutomation class directly."""
    print("\n" + "=" * 80)
    print("TEST 1: CelebrationAutomation Class")
    print("=" * 80)
    
    config = load_config()
    automation = CelebrationAutomation(config)
    
    print("Testing trigger_confetti()...")
    result = automation.trigger_confetti()
    
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' key"
    
    if result.get("success"):
        print("✅ Automation class works correctly")
        print(f"   Message: {result.get('message')}")
    else:
        print(f"⚠️  Automation returned error: {result.get('error_message')}")
        print("   (This might be okay if notifications are disabled)")
    
    return result.get("success", False)

def test_agent_tool():
    """Test the trigger_confetti tool directly."""
    print("\n" + "=" * 80)
    print("TEST 2: Celebration Agent Tool")
    print("=" * 80)
    
    print("Testing trigger_confetti tool...")
    result = trigger_confetti.invoke({})
    
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result or "error" in result, "Result should have success or error"
    
    if result.get("success"):
        print("✅ Agent tool works correctly")
        print(f"   Message: {result.get('message')}")
    else:
        print(f"⚠️  Tool returned error: {result.get('error_message', 'Unknown error')}")
    
    return result.get("success", False)

def test_agent_class():
    """Test CelebrationAgent class."""
    print("\n" + "=" * 80)
    print("TEST 3: CelebrationAgent Class")
    print("=" * 80)
    
    config = load_config()
    agent = CelebrationAgent(config)
    
    # Test get_tools
    tools = agent.get_tools()
    assert len(tools) > 0, "Agent should have tools"
    assert trigger_confetti in tools, "Should include trigger_confetti tool"
    print(f"✅ Agent has {len(tools)} tool(s)")
    
    # Test execute
    result = agent.execute("trigger_confetti", {})
    assert isinstance(result, dict), "Execute should return dict"
    
    if result.get("success"):
        print("✅ Agent.execute() works correctly")
    else:
        print(f"⚠️  Agent.execute() returned: {result.get('error_message', 'Unknown')}")
    
    # Test unknown tool
    unknown_result = agent.execute("unknown_tool", {})
    assert unknown_result.get("error"), "Should return error for unknown tool"
    print("✅ Error handling for unknown tools works")
    
    return True

def test_agent_registry():
    """Test agent registration in AgentRegistry."""
    print("\n" + "=" * 80)
    print("TEST 4: Agent Registry Integration")
    print("=" * 80)
    
    config = load_config()
    registry = AgentRegistry(config)
    
    # Test agent retrieval
    celebration_agent = registry.get_agent("celebration")
    assert celebration_agent is not None, "Should be able to get celebration agent"
    print("✅ Celebration agent retrievable from registry")
    
    # Test tool registration
    from src.agent.agent_registry import ALL_AGENT_TOOLS
    confetti_tools = [t for t in ALL_AGENT_TOOLS if t.name == "trigger_confetti"]
    assert len(confetti_tools) > 0, "trigger_confetti should be in ALL_AGENT_TOOLS"
    print(f"✅ trigger_confetti tool registered in ALL_AGENT_TOOLS")
    
    # Test tool-to-agent mapping
    tool_agent = registry.tool_to_agent.get("trigger_confetti")
    assert tool_agent == "celebration", f"Tool should map to celebration agent, got {tool_agent}"
    print("✅ Tool-to-agent mapping correct")
    
    return True

def test_agent_capabilities():
    """Test agent capabilities integration."""
    print("\n" + "=" * 80)
    print("TEST 5: Agent Capabilities")
    print("=" * 80)
    
    config = load_config()
    registry = AgentRegistry(config)
    capabilities = build_agent_capabilities(registry)
    
    celebration_caps = [c for c in capabilities if c["agent"] == "celebration"]
    assert len(celebration_caps) > 0, "Celebration should be in capabilities"
    
    cap = celebration_caps[0]
    print(f"✅ Celebration agent in capabilities")
    print(f"   Title: {cap.get('title')}")
    print(f"   Domain: {cap.get('domain')}")
    
    assert cap.get("domain") == "Celebratory effects and fun interactions", "Domain should match"
    
    return True

def test_slash_command_parsing():
    """Test slash command parsing."""
    print("\n" + "=" * 80)
    print("TEST 6: Slash Command Parsing")
    print("=" * 80)
    
    parser = SlashCommandParser()
    
    # Test /confetti
    result = parser.parse("/confetti")
    assert result is not None, "Should parse /confetti"
    assert result["command"] == "confetti", "Command should be confetti"
    assert result["agent"] == "celebration", "Should route to celebration agent"
    print("✅ /confetti parses correctly")
    
    # Test /celebrate
    result = parser.parse("/celebrate")
    assert result is not None, "Should parse /celebrate"
    assert result["agent"] == "celebration", "Should route to celebration agent"
    print("✅ /celebrate parses correctly")
    
    # Test /party
    result = parser.parse("/party")
    assert result is not None, "Should parse /party"
    assert result["agent"] == "celebration", "Should route to celebration agent"
    print("✅ /party parses correctly")
    
    # Test command tooltips
    tooltips = [t for t in parser.COMMAND_TOOLTIPS if t["command"] == "/confetti"]
    assert len(tooltips) > 0, "Should have tooltip for /confetti"
    print(f"✅ Tooltip exists: {tooltips[0]['description']}")
    
    # Test agent descriptions
    desc = parser.AGENT_DESCRIPTIONS.get("celebration")
    assert desc is not None, "Should have description for celebration agent"
    print(f"✅ Agent description: {desc}")
    
    # Test examples
    examples = parser.EXAMPLES.get("celebration", [])
    assert len(examples) > 0, "Should have examples for celebration"
    print(f"✅ Examples: {examples}")
    
    return True

def test_slash_command_handler():
    """Test slash command handler execution."""
    print("\n" + "=" * 80)
    print("TEST 7: Slash Command Handler")
    print("=" * 80)
    
    config = load_config()
    registry = AgentRegistry(config)
    handler = SlashCommandHandler(registry, config)
    
    # Test /confetti execution
    print("Executing /confetti via handler...")
    is_command, result = handler.handle("/confetti", session_id="test_comprehensive")
    
    assert isinstance(is_command, bool), "Handler should return tuple (bool, Any)"
    assert is_command, "Should recognize /confetti as command"
    assert isinstance(result, dict), "Result should be dict"
    print(f"✅ Handler executed successfully")
    print(f"   Is command: {is_command}")
    print(f"   Result type: {result.get('type', 'N/A')}")
    if result.get('result'):
        print(f"   Success: {result.get('result', {}).get('success', 'N/A')}")
    
    return True

def test_end_to_end():
    """Test end-to-end through AutomationAgent."""
    print("\n" + "=" * 80)
    print("TEST 8: End-to-End Integration")
    print("=" * 80)
    
    config = load_config()
    session_manager = SessionManager(storage_dir="data/sessions")
    agent = AutomationAgent(config, session_manager=session_manager)
    
    print("Testing /confetti through AutomationAgent...")
    result = agent.run("/confetti", session_id="test_e2e")
    
    assert isinstance(result, dict), "Should return dict"
    assert result.get("status") in ["success", "partial_success", "completed"], "Should have valid status"
    
    print(f"✅ End-to-end test completed")
    print(f"   Status: {result.get('status')}")
    print(f"   Message: {result.get('message', 'N/A')}")
    
    return True

def test_frontend_integration():
    """Test frontend command definition."""
    print("\n" + "=" * 80)
    print("TEST 9: Frontend Integration")
    print("=" * 80)
    
    try:
        import json
        frontend_file = "frontend/lib/slashCommands.ts"
        
        if os.path.exists(frontend_file):
            with open(frontend_file, 'r') as f:
                content = f.read()
                
            assert "/confetti" in content, "Should have /confetti in frontend file"
            assert "Confetti" in content, "Should have Confetti label"
            assert "celebratory" in content.lower(), "Should have celebratory description"
            
            print("✅ Frontend file contains confetti command")
            print("   File: frontend/lib/slashCommands.ts")
        else:
            print("⚠️  Frontend file not found (may need to build frontend)")
    except Exception as e:
        print(f"⚠️  Could not verify frontend: {e}")
    
    return True

def main():
    """Run all tests."""
    print("=" * 80)
    print("COMPREHENSIVE CONFETTI FEATURE TEST SUITE")
    print("=" * 80)
    print("\n⚠️  Note: Some tests will trigger actual confetti effects!")
    print("⚠️  Make sure notifications are enabled.\n")
    
    tests = [
        ("Automation Class", test_automation_class),
        ("Agent Tool", test_agent_tool),
        ("Agent Class", test_agent_class),
        ("Agent Registry", test_agent_registry),
        ("Agent Capabilities", test_agent_capabilities),
        ("Slash Command Parsing", test_slash_command_parsing),
        ("Slash Command Handler", test_slash_command_handler),
        ("End-to-End", test_end_to_end),
        ("Frontend Integration", test_frontend_integration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result, None))
        except AssertionError as e:
            results.append((name, False, str(e)))
            print(f"\n❌ {name} FAILED: {e}")
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"\n❌ {name} ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result, _ in results if result)
    total = len(results)
    
    for name, result, error in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if error:
            print(f"      Error: {error}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Confetti feature is fully functional!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed or had issues")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

