"""
Test slash command routing and parser hardening.

This test suite ensures:
1. Natural queries with /Users paths fall through to orchestrator
2. /files commands route to test_docs
3. /folder commands work correctly
4. Unknown commands return None instead of errors
5. Path escaping with // works
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ui.slash_commands import SlashCommandParser, SlashCommandHandler, get_demo_documents_root


def test_parser_path_escaping():
    """Test that paths starting with / are not treated as commands."""
    parser = SlashCommandParser()

    # Test 1: /Users path should NOT be treated as a command
    result = parser.parse("/Users/john/Documents/myfile.txt")
    assert result is None, f"Expected None for /Users path, got: {result}"

    # Test 2: // escaping should work
    result = parser.parse("//Users/john/Documents/myfile.txt")
    assert result is None, f"Expected None for // escaped path, got: {result}"

    # Test 3: Unknown command should return None (not error)
    result = parser.parse("/unknown_command do something")
    assert result is None, f"Expected None for unknown command, got: {result}"

    # Test 4: Known command should work
    result = parser.parse("/files organize PDFs")
    assert result is not None, "Expected result for /files command"
    assert result["command"] == "files", f"Expected 'files' command, got: {result['command']}"
    assert result["agent"] == "file", f"Expected 'file' agent, got: {result['agent']}"

    print("✅ Parser path escaping tests passed")


def test_parser_known_commands():
    """Test that only known commands are recognized."""
    parser = SlashCommandParser()

    known_commands = ["files", "folder", "email", "maps", "stock", "browse"]
    unknown_commands = ["foo", "bar", "xyz123"]

    # Test known commands
    for cmd in known_commands:
        result = parser.parse(f"/{cmd} some task")
        assert result is not None, f"Expected result for known command /{cmd}"
        assert result["command"] == cmd, f"Expected command '{cmd}', got: {result['command']}"

    # Test unknown commands
    for cmd in unknown_commands:
        result = parser.parse(f"/{cmd} some task")
        assert result is None, f"Expected None for unknown command /{cmd}, got: {result}"

    print("✅ Parser known commands tests passed")


def test_demo_documents_root():
    """Test demo documents root utility."""
    config = {
        "documents": {
            "folders": ["/Users/test/tests/data/test_docs"]
        }
    }

    demo_root = get_demo_documents_root(config)
    assert demo_root == "/Users/test/tests/data/test_docs", f"Expected test_docs path, got: {demo_root}"

    # Test fallback to document_directory
    config2 = {
        "document_directory": "/Users/test/legacy/docs"
    }
    demo_root2 = get_demo_documents_root(config2)
    assert demo_root2 == "/Users/test/legacy/docs", f"Expected legacy path, got: {demo_root2}"

    # Test empty config
    demo_root3 = get_demo_documents_root({})
    assert demo_root3 is None, f"Expected None for empty config, got: {demo_root3}"

    print("✅ Demo documents root tests passed")


def test_files_command_routing():
    """Test that /files commands route deterministically to demo folder."""
    from src.ui.slash_commands import SlashCommandHandler

    config = {
        "documents": {
            "folders": ["/Users/test/tests/data/test_docs"]
        }
    }

    # Create a mock handler (we just need the routing method)
    class MockRegistry:
        def execute_tool(self, tool_name, params, session_id=None):
            return {"tool": tool_name, "params": params}

    handler = SlashCommandHandler(MockRegistry(), config=config)

    # Test 1: Summarize should route to search_documents with demo root
    tool, params, msg = handler._route_files_command("summarize Edgar Allan Poe")
    assert tool == "search_documents", f"Expected search_documents, got: {tool}"
    assert params.get("source_path") == "/Users/test/tests/data/test_docs", \
        f"Expected demo root in params, got: {params}"
    assert msg is not None, "Expected demo root message"

    # Test 2: Organize should include demo root
    tool, params, msg = handler._route_files_command("organize my PDFs")
    assert tool == "organize_files", f"Expected organize_files, got: {tool}"
    assert params.get("folder_path") == "/Users/test/tests/data/test_docs", \
        f"Expected demo root in params, got: {params}"
    assert msg is not None, "Expected demo root message"

    # Test 3: ZIP should include demo root
    tool, params, msg = handler._route_files_command("zip all images")
    assert tool == "create_zip_archive", f"Expected create_zip_archive, got: {tool}"
    assert params.get("source_path") == "/Users/test/tests/data/test_docs", \
        f"Expected demo root in params, got: {params}"
    assert msg is not None, "Expected demo root message"

    # Test 4: List all files (should route to list_related_documents)
    tool, params, msg = handler._route_files_command("show all guitar tabs")
    assert tool == "list_related_documents", f"Expected list_related_documents, got: {tool}"
    assert "guitar tabs" in params.get("query", ""), \
        f"Expected query to contain 'guitar tabs', got: {params}"
    assert params.get("max_results") == 10, \
        f"Expected max_results=10, got: {params.get('max_results')}"

    # Test 5: List all with different keywords
    tool, params, msg = handler._route_files_command("list all PDF documents")
    assert tool == "list_related_documents", f"Expected list_related_documents, got: {tool}"
    assert "PDF" in params.get("query", ""), \
        f"Expected query to contain 'PDF', got: {params}"

    # Test 6: Pull up all
    tool, params, msg = handler._route_files_command("pull up all meeting notes")
    assert tool == "list_related_documents", f"Expected list_related_documents, got: {tool}"

    # Test 7: Find all
    tool, params, msg = handler._route_files_command("find all reports")
    assert tool == "list_related_documents", f"Expected list_related_documents, got: {tool}"

    # Test 8: Default search (no listing keywords)
    tool, params, msg = handler._route_files_command("find documents about AI")
    assert tool == "search_documents", f"Expected search_documents, got: {tool}"
    assert params.get("source_path") == "/Users/test/tests/data/test_docs", \
        f"Expected demo root in params, got: {params}"
    assert msg is not None, "Expected demo root message"

    print("✅ Files command routing tests passed")


def test_folder_command_routing():
    """Test that /folder commands route deterministically."""
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

    # Test 1: List should use demo root
    tool, params, msg = handler._route_folder_command("list files")
    assert tool == "folder_list", f"Expected folder_list, got: {tool}"
    assert params.get("folder_path") == "/Users/test/tests/data/test_docs", \
        f"Expected demo root, got: {params}"
    assert msg is not None, "Expected demo root message"

    # Test 2: Organize
    tool, params, msg = handler._route_folder_command("organize by type")
    assert tool == "folder_organize_by_type", f"Expected folder_organize_by_type, got: {tool}"
    assert params.get("dry_run") is True, f"Expected dry_run=True, got: {params}"
    assert msg is not None, "Expected demo root message"

    # Test 3: Normalize/rename
    tool, params, msg = handler._route_folder_command("rename alpha")
    assert tool == "folder_normalize_names", f"Expected folder_normalize_names, got: {tool}"
    assert msg is not None, "Expected demo root message"

    # Test 4: Default list (empty task)
    tool, params, msg = handler._route_folder_command("")
    assert tool == "folder_list", f"Expected folder_list, got: {tool}"
    assert msg is not None, "Expected demo root message"

    print("✅ Folder command routing tests passed")


def test_natural_language_with_paths():
    """Test that natural language queries with paths fall through."""
    parser = SlashCommandParser()

    test_cases = [
        "Please organize the files in /Users/john/Documents",
        "Can you search /Users/john/Desktop for PDFs?",
        "Look at the folder /Users/john/Downloads and tell me what's inside",
        "/Users/john/Documents/report.pdf",
        "//Users/john/path with spaces/file.txt",
    ]

    for query in test_cases:
        result = parser.parse(query)
        assert result is None, f"Expected None for natural query '{query}', got: {result}"

    print("✅ Natural language with paths tests passed")


def test_slash_commands_work():
    """Test that valid slash commands still work."""
    parser = SlashCommandParser()

    test_cases = [
        ("/files organize PDFs", "files", "organize PDFs"),
        ("/folder list", "folder", "list"),
        ("/email read latest 5", "email", "read latest 5"),
        ("/maps plan trip from LA to SF", "maps", "plan trip from LA to SF"),
        ("/stock get AAPL price", "stock", "get AAPL price"),
    ]

    for command_str, expected_cmd, expected_task in test_cases:
        result = parser.parse(command_str)
        assert result is not None, f"Expected result for '{command_str}'"
        assert result["command"] == expected_cmd, \
            f"Expected command '{expected_cmd}', got: {result['command']}"
        assert result["task"] == expected_task, \
            f"Expected task '{expected_task}', got: {result['task']}"

    print("✅ Slash commands work tests passed")


def run_all_tests():
    """Run all slash command tests."""
    print("\n" + "="*60)
    print("SLASH COMMAND ROUTING TESTS")
    print("="*60 + "\n")

    test_parser_path_escaping()
    test_parser_known_commands()
    test_demo_documents_root()
    test_files_command_routing()
    test_folder_command_routing()
    test_natural_language_with_paths()
    test_slash_commands_work()

    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_tests()
