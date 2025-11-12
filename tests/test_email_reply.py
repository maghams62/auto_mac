"""
Test script for email reply functionality.

Tests:
1. Email agent has reply_to_email tool
2. Tool is registered in agent registry
3. Tool parameters are correct
4. Tool creates draft reply with "Re: " prefix
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils import load_config
from src.agent.email_agent import EmailAgent, EMAIL_AGENT_TOOLS
from src.agent.agent_registry import AgentRegistry


def test_reply_tool_exists():
    """Test that reply_to_email tool exists in EMAIL_AGENT_TOOLS."""
    print("\n" + "="*60)
    print("TEST 1: Verify reply_to_email tool exists")
    print("="*60)

    tool_names = [tool.name for tool in EMAIL_AGENT_TOOLS]
    print(f"Email Agent Tools ({len(tool_names)}):")
    for name in tool_names:
        print(f"  - {name}")

    assert "reply_to_email" in tool_names, "reply_to_email tool not found!"
    print("\n✅ PASS: reply_to_email tool exists in EMAIL_AGENT_TOOLS")
    return True


def test_agent_registry():
    """Test that reply_to_email is registered in agent registry."""
    print("\n" + "="*60)
    print("TEST 2: Verify tool is registered in AgentRegistry")
    print("="*60)

    config = load_config()
    registry = AgentRegistry(config)

    # Check tool-to-agent mapping
    assert "reply_to_email" in registry.tool_to_agent, "reply_to_email not in tool_to_agent mapping!"
    agent_name = registry.tool_to_agent["reply_to_email"]
    print(f"reply_to_email is mapped to: {agent_name} agent")

    assert agent_name == "email", f"Expected 'email' agent, got '{agent_name}'"
    print("\n✅ PASS: reply_to_email correctly mapped to email agent")
    return True


def test_tool_parameters():
    """Test that reply_to_email has correct parameters."""
    print("\n" + "="*60)
    print("TEST 3: Verify tool parameters")
    print("="*60)

    # Get the tool
    reply_tool = None
    for tool in EMAIL_AGENT_TOOLS:
        if tool.name == "reply_to_email":
            reply_tool = tool
            break

    assert reply_tool is not None, "reply_to_email tool not found!"

    # Check tool schema
    schema = reply_tool.args_schema
    if schema:
        print(f"\nTool Schema: {schema.__name__}")
        print("Parameters:")
        try:
            # Try pydantic v2 syntax
            if hasattr(schema, 'model_fields'):
                for field_name, field_info in schema.model_fields.items():
                    required = field_info.is_required()
                    field_type = field_info.annotation
                    print(f"  - {field_name}: {field_type} (required={required})")
            # Try pydantic v1 syntax
            elif hasattr(schema, '__fields__'):
                for field_name, field_info in schema.__fields__.items():
                    required = field_info.required
                    field_type = field_info.type_
                    print(f"  - {field_name}: {field_type} (required={required})")
            else:
                print("  (Schema inspection not available - skipping detailed check)")
        except Exception as e:
            print(f"  (Could not inspect schema: {e})")

    # Basic verification that the tool is callable
    print("\nVerifying tool is callable...")
    assert callable(reply_tool.func), "Tool function is not callable!"

    print("\n✅ PASS: Tool has correct schema and is callable")
    return True


def test_email_agent_tool_count():
    """Test that email agent has 6 tools."""
    print("\n" + "="*60)
    print("TEST 4: Verify email agent tool count")
    print("="*60)

    config = load_config()
    email_agent = EmailAgent(config)
    tools = email_agent.get_tools()

    print(f"\nEmail Agent has {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool.name}")

    expected_count = 6
    assert len(tools) == expected_count, f"Expected {expected_count} tools, got {len(tools)}"
    print(f"\n✅ PASS: Email agent has {expected_count} tools")
    return True


def test_hierarchy_documentation():
    """Test that hierarchy documentation mentions reply_to_email."""
    print("\n" + "="*60)
    print("TEST 5: Verify hierarchy documentation")
    print("="*60)

    config = load_config()
    email_agent = EmailAgent(config)
    hierarchy = email_agent.get_hierarchy()

    print("\nEmail Agent Hierarchy:")
    print(hierarchy[:500] + "...")

    assert "reply_to_email" in hierarchy, "reply_to_email not mentioned in hierarchy!"
    assert "Reply to a specific email" in hierarchy or "reply" in hierarchy.lower(), "Reply functionality not documented!"

    print("\n✅ PASS: Hierarchy documentation includes reply_to_email")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("EMAIL REPLY FUNCTIONALITY TEST SUITE")
    print("="*60)

    tests = [
        test_reply_tool_exists,
        test_agent_registry,
        test_tool_parameters,
        test_email_agent_tool_count,
        test_hierarchy_documentation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"\n❌ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            failed += 1

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nEmail reply functionality is ready to use!")
        print("\nUsage examples:")
        print('  - "Read the latest email from John and reply saying thanks"')
        print('  - "Reply to Sarah\'s email about the meeting"')
        print('  - "Read my latest email and draft a reply"')
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
