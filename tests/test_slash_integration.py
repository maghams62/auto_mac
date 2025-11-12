"""
Integration test for slash command system.

Tests the full flow from parsing to execution with demo constraints.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_natural_query_with_path_falls_through():
    """
    Test that natural language queries with /Users paths fall through
    to the orchestrator instead of being treated as slash commands.
    """
    from src.ui.slash_commands import SlashCommandParser

    parser = SlashCommandParser()

    # These should all return None (not a slash command)
    test_cases = [
        "Please organize the files in /Users/john/Documents",
        "Search /Users/john/Desktop for PDFs about machine learning",
        "Look at /Users/john/Downloads and tell me what's inside",
        "/Users/john/Documents/report.pdf",  # Just a path
        "Can you help me with /Users/john/some/path?",
    ]

    for query in test_cases:
        result = parser.parse(query)
        assert result is None, f"Natural query '{query}' should not be treated as slash command, got: {result}"

    print("✅ Natural queries with /Users paths correctly fall through to orchestrator")


def test_path_escaping():
    """Test that // at the start escapes the slash command system."""
    from src.ui.slash_commands import SlashCommandParser

    parser = SlashCommandParser()

    # Double slash should escape
    result = parser.parse("//Users/john/Documents/file.txt")
    assert result is None, "// prefix should escape slash command parsing"

    result = parser.parse("//some/other/path")
    assert result is None, "// prefix should escape slash command parsing"

    print("✅ Path escaping with // works correctly")


def test_files_command_with_demo_constraint():
    """
    Test that /files commands use demo folder by default.
    """
    from src.ui.slash_commands import SlashCommandHandler

    config = {
        "documents": {
            "folders": ["/Users/test/tests/data/test_docs"]
        }
    }

    class MockRegistry:
        def execute_tool(self, tool_name, params, session_id=None):
            return {"tool": tool_name, "params": params}

    handler = SlashCommandHandler(MockRegistry(), config=config)

    # Test various /files commands
    test_cases = [
        ("summarize Edgar Allan Poe", "search_documents"),
        ("organize PDFs", "organize_files"),
        ("zip all documents", "create_zip_archive"),
        ("find AI papers", "search_documents"),
    ]

    for task, expected_tool in test_cases:
        tool_name, params, msg = handler._route_files_command(task)
        assert tool_name == expected_tool, f"Expected {expected_tool} for '{task}', got {tool_name}"

        # Check that demo folder is used (for tools that support it)
        if "path" in params:
            for key in params:
                if "path" in key and params[key]:
                    assert "/test_docs" in params[key], \
                        f"Expected demo folder in params for '{task}', got: {params}"

        # Check that demo root message is present
        assert msg is not None, f"Expected demo root message for '{task}'"

    print("✅ /files commands correctly use demo folder constraint")


def test_folder_command_with_demo_constraint():
    """
    Test that /folder commands use demo folder by default.
    """
    from src.ui.slash_commands import SlashCommandHandler

    config = {
        "documents": {
            "folders": ["/Users/test/tests/data/test_docs"]
        }
    }

    class MockRegistry:
        def execute_tool(self, tool_name, params, session_id=None):
            return {"tool": tool_name, "params": params}

    handler = SlashCommandHandler(MockRegistry(), config=config)

    # Test various /folder commands
    test_cases = [
        ("list", "folder_list"),
        ("organize", "folder_organize_by_type"),
        ("rename alpha", "folder_normalize_names"),
        ("", "folder_list"),  # Empty task defaults to list
    ]

    for task, expected_tool in test_cases:
        tool_name, params, msg = handler._route_folder_command(task)
        assert tool_name == expected_tool, f"Expected {expected_tool} for '{task}', got {tool_name}"

        # All folder commands should have folder_path
        if "folder_path" in params:
            assert "/test_docs" in params["folder_path"], \
                f"Expected demo folder for '{task}', got: {params}"

        # Check that demo root message is present
        assert msg is not None, f"Expected demo root message for '{task}'"

    print("✅ /folder commands correctly use demo folder constraint")


def test_stock_command():
    """Test that /stock commands work correctly."""
    from src.ui.slash_commands import SlashCommandParser

    parser = SlashCommandParser()

    result = parser.parse("/stock Get META price")
    assert result is not None, "Expected valid result for /stock command"
    assert result["command"] == "stock"
    assert result["agent"] == "google_finance"
    assert result["task"] == "Get META price"

    print("✅ /stock command routing works")


def test_unknown_command_returns_none():
    """Test that unknown commands return None instead of error."""
    from src.ui.slash_commands import SlashCommandParser

    parser = SlashCommandParser()

    # These should return None (fall through to orchestrator)
    unknown_commands = [
        "/foo do something",
        "/unknown command here",
        "/xyz123 test",
    ]

    for cmd in unknown_commands:
        result = parser.parse(cmd)
        assert result is None, f"Unknown command '{cmd}' should return None, got: {result}"

    print("✅ Unknown commands correctly return None")


def test_known_commands_still_work():
    """Test that all known commands are recognized."""
    from src.ui.slash_commands import SlashCommandParser

    parser = SlashCommandParser()

    known_commands = [
        ("/files organize", "file"),
        ("/folder list", "folder"),
        ("/email read latest", "email"),
        ("/browse search python", "browser"),
        ("/maps plan trip", "maps"),
        ("/stock get AAPL", "google_finance"),
        ("/report create", "report"),
        ("/spotify play", "spotify"),
        ("/whatsapp read", "whatsapp"),
    ]

    for cmd, expected_agent in known_commands:
        result = parser.parse(cmd)
        assert result is not None, f"Known command '{cmd}' should be recognized"
        assert result["agent"] == expected_agent, \
            f"Expected agent '{expected_agent}' for '{cmd}', got: {result['agent']}"

    print("✅ All known commands are correctly recognized")


def test_help_commands():
    """Test that help commands work correctly."""
    from src.ui.slash_commands import SlashCommandParser

    parser = SlashCommandParser()

    # General help
    result = parser.parse("/help")
    assert result is not None
    assert result["command"] == "help"

    # Specific command help
    result = parser.parse("/help files")
    assert result is not None
    assert result["command"] == "help"
    assert result["agent"] == "files"

    print("✅ Help commands work correctly")


def run_integration_tests():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("SLASH COMMAND INTEGRATION TESTS")
    print("="*60 + "\n")

    test_natural_query_with_path_falls_through()
    test_path_escaping()
    test_files_command_with_demo_constraint()
    test_folder_command_with_demo_constraint()
    test_stock_command()
    test_unknown_command_returns_none()
    test_known_commands_still_work()
    test_help_commands()

    print("\n" + "="*60)
    print("✅ ALL INTEGRATION TESTS PASSED")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_integration_tests()
