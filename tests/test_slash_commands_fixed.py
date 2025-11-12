"""
Test the fixed slash command system with HelpRegistry integration.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ui.slash_commands import SlashCommandParser
from src.utils import load_config
from src.agent.agent_registry import AgentRegistry


def test_standalone_commands():
    """Test that standalone commands (e.g., /email) now show help."""
    print("\n" + "="*60)
    print("TEST 1: Standalone Commands Show Help")
    print("="*60)

    parser = SlashCommandParser()

    test_cases = [
        "/email",
        "/files",
        "/browse",
        "/help",
    ]

    for test_cmd in test_cases:
        result = parser.parse(test_cmd)
        print(f"\nInput: {test_cmd}")
        print(f"Result: {result}")

        if test_cmd == "/help":
            assert result["command"] == "help", f"Expected 'help', got '{result['command']}'"
        else:
            # Standalone commands should redirect to help
            assert result["command"] == "help", f"Standalone {test_cmd} should show help!"
            assert result["agent"] == test_cmd[1:], f"Should set agent to {test_cmd[1:]}"

    print("\n✅ PASS: Standalone commands correctly show help")
    return True


def test_command_with_task():
    """Test that commands with tasks still work normally."""
    print("\n" + "="*60)
    print("TEST 2: Commands With Tasks Work Normally")
    print("="*60)

    parser = SlashCommandParser()

    test_cases = [
        ("/email Read latest 5 emails", "email", "email", "Read latest 5 emails"),
        ("/files Organize PDFs", "files", "file", "Organize PDFs"),
        ("/browse Go to github.com", "browse", "browser", "Go to github.com"),
    ]

    for test_cmd, expected_cmd, expected_agent, expected_task in test_cases:
        result = parser.parse(test_cmd)
        print(f"\nInput: {test_cmd}")
        print(f"Command: {result['command']}, Agent: {result['agent']}, Task: {result.get('task')}")

        assert result["command"] == expected_cmd, f"Expected command '{expected_cmd}'"
        assert result["agent"] == expected_agent, f"Expected agent '{expected_agent}'"
        assert result["task"] == expected_task, f"Expected task '{expected_task}'"

    print("\n✅ PASS: Commands with tasks work correctly")
    return True


def test_typo_suggestions():
    """Test that typos provide suggestions."""
    print("\n" + "="*60)
    print("TEST 3: Typo Suggestions")
    print("="*60)

    parser = SlashCommandParser()

    test_cases = [
        "/fil",       # Should suggest /files
        "/emai",      # Should suggest /email
        "/brows",     # Should suggest /browse
    ]

    for test_cmd in test_cases:
        result = parser.parse(test_cmd)
        print(f"\nInput: {test_cmd}")
        print(f"Result: {result}")

        assert result["command"] == "invalid", "Should be invalid command"
        assert "error" in result, "Should have error message"
        assert "Did you mean" in result["error"] or "suggestions" in result["error"].lower(), "Should provide suggestions"

    print("\n✅ PASS: Typo suggestions work")
    return True


def test_help_search():
    """Test /help search functionality."""
    print("\n" + "="*60)
    print("TEST 4: Help Search")
    print("="*60)

    parser = SlashCommandParser()

    result = parser.parse("/help search email")
    print(f"\nInput: /help search email")
    print(f"Result: {result}")

    assert result["command"] == "help", "Should be help command"
    assert result.get("help_mode") == "search", "Should be search mode"
    assert result.get("search_query") == "email", "Should have search query"

    print("\n✅ PASS: Help search parsing works")
    return True


def test_help_category():
    """Test /help --category functionality."""
    print("\n" + "="*60)
    print("TEST 5: Help Category Filtering")
    print("="*60)

    parser = SlashCommandParser()

    result = parser.parse("/help --category files")
    print(f"\nInput: /help --category files")
    print(f"Result: {result}")

    assert result["command"] == "help", "Should be help command"
    assert result.get("help_mode") == "category", "Should be category mode"
    assert result.get("category") == "files", "Should have category"

    print("\n✅ PASS: Help category parsing works")
    return True


def test_help_integration():
    """Test get_help method with HelpRegistry."""
    print("\n" + "="*60)
    print("TEST 6: Help Method with HelpRegistry")
    print("="*60)

    parser = SlashCommandParser()
    config = load_config()
    agent_registry = AgentRegistry(config)

    # Test general help
    help_text = parser.get_help(agent_registry=agent_registry)
    print(f"\nGeneral help preview (first 500 chars):")
    print(help_text[:500])
    assert "Slash Commands" in help_text, "Should have title"
    assert "email" in help_text.lower(), "Should mention email"

    # Test specific command help
    email_help = parser.get_help(command="email", agent_registry=agent_registry)
    print(f"\nEmail help preview (first 500 chars):")
    print(email_help[:500])
    assert "/email" in email_help, "Should have command name"
    assert "Example" in email_help, "Should have examples"

    # Test search
    search_help = parser.get_help(
        help_mode="search",
        search_query="organize",
        agent_registry=agent_registry
    )
    print(f"\nSearch results preview (first 500 chars):")
    print(search_help[:500])
    assert "Search Results" in search_help, "Should have search title"
    assert "organize" in search_help.lower(), "Should show organize results"

    print("\n✅ PASS: Help method integration works")
    return True


def test_invalid_command_with_suggestions():
    """Test that invalid commands provide suggestions."""
    print("\n" + "="*60)
    print("TEST 7: Invalid Commands With Suggestions")
    print("="*60)

    parser = SlashCommandParser()

    # Test with task
    result = parser.parse("/emailz Read emails")
    print(f"\nInput: /emailz Read emails")
    print(f"Error: {result.get('error', '')[:200]}")

    assert result["command"] == "invalid", "Should be invalid"
    assert "email" in result["error"].lower(), "Should suggest email"

    print("\n✅ PASS: Invalid commands provide suggestions")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("SLASH COMMAND FIX TEST SUITE")
    print("="*60)

    tests = [
        test_standalone_commands,
        test_command_with_task,
        test_typo_suggestions,
        test_help_search,
        test_help_category,
        test_help_integration,
        test_invalid_command_with_suggestions,
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
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nSlash command fixes are working!")
        print("\nKey improvements:")
        print("  • /email alone now shows help (not error)")
        print("  • /help search <query> searches commands")
        print("  • /help --category <cat> filters by category")
        print("  • Typos provide smart suggestions")
        print("  • HelpRegistry integration complete")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
