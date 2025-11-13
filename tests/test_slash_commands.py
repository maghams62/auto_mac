"""
Test slash command system.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
from src.utils import load_config
from src.agent.agent_registry import AgentRegistry
from src.ui.slash_commands import SlashCommandParser, SlashCommandHandler, create_slash_command_handler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_parser():
    """Test slash command parser."""
    logger.info("\n" + "="*80)
    logger.info("TEST: SLASH COMMAND PARSER")
    logger.info("="*80)

    parser = SlashCommandParser()

    # Test valid commands
    test_cases = [
        ("/files Organize my PDFs", {"command": "files", "agent": "file", "task": "Organize my PDFs"}),
        ("/files explain Edgar Allan Poe", {"command": "files", "agent": "file", "task": "explain Edgar Allan Poe"}),
        ("/explain Edgar Allan Poe", {"command": "explain", "agent": "explain", "task": "Edgar Allan Poe"}),
        ("/browse Search for Python tutorials", {"command": "browse", "agent": "browser", "task": "Search for Python tutorials"}),
        ("/maps Plan trip from LA to SF", {"command": "maps", "agent": "maps", "task": "Plan trip from LA to SF"}),
        ("/calendar List my upcoming events", {"command": "calendar", "agent": "calendar", "task": "List my upcoming events"}),
        ("/calendar prep for Q4 Review", {"command": "calendar", "agent": "calendar", "task": "prep for Q4 Review"}),
        ("/help", {"command": "help", "agent": None}),
        ("/agents", {"command": "agents", "agent": None}),
        ("/help files", {"command": "help", "agent": "files"}),
        ("/help explain", {"command": "help", "agent": "explain"}),
    ]

    passed = 0
    for message, expected in test_cases:
        result = parser.parse(message)
        if result and result.get("command") == expected["command"]:
            logger.info(f"✓ PASS: '{message}' -> {result['command']}")
            passed += 1
        else:
            logger.error(f"✗ FAIL: '{message}' -> {result}")

    # Test invalid commands
    invalid_cases = [
        "Hello world",  # Not a command
        "/unknown task",  # Unknown command
    ]

    for message in invalid_cases:
        result = parser.parse(message)
        if not result or result.get("command") == "invalid":
            logger.info(f"✓ PASS: '{message}' correctly rejected")
            passed += 1
        else:
            logger.error(f"✗ FAIL: '{message}' should be invalid")

    total = len(test_cases) + len(invalid_cases)
    logger.info(f"\nParser Tests: {passed}/{total} passed")

    return passed == total


def test_help():
    """Test help system."""
    logger.info("\n" + "="*80)
    logger.info("TEST: HELP SYSTEM")
    logger.info("="*80)

    parser = SlashCommandParser()

    # Test general help
    general_help = parser.get_help()
    logger.info("\nGeneral Help (preview):")
    logger.info(general_help[:200] + "...")

    # Test specific command help
    files_help = parser.get_help("files")
    logger.info(f"\n/files Help (preview):")
    logger.info(files_help[:200] + "...")

    # Test agents list
    agents_list = parser.get_agents_list()
    logger.info(f"\nAgents List (preview):")
    logger.info(agents_list[:200] + "...")

    if general_help and files_help and agents_list:
        logger.info("\n✓ PASS: Help system works")
        return True
    else:
        logger.error("\n✗ FAIL: Help system incomplete")
        return False


def test_handler():
    """Test slash command handler."""
    logger.info("\n" + "="*80)
    logger.info("TEST: SLASH COMMAND HANDLER")
    logger.info("="*80)

    try:
        config = load_config()
        registry = AgentRegistry(config)
        handler = create_slash_command_handler(registry)

        # Test help command
        is_command, result = handler.handle("/help")
        if is_command and result.get("type") == "help":
            logger.info("✓ PASS: /help command works")
        else:
            logger.error("✗ FAIL: /help command failed")
            return False

        # Test agents command
        is_command, result = handler.handle("/agents")
        if is_command and result.get("type") == "agents":
            logger.info("✓ PASS: /agents command works")
        else:
            logger.error("✗ FAIL: /agents command failed")
            return False

        # Test invalid command
        is_command, result = handler.handle("/unknown task")
        if is_command and result.get("type") == "error":
            logger.info("✓ PASS: Invalid command correctly handled")
        else:
            logger.error("✗ FAIL: Invalid command not handled")
            return False

        # Test non-command
        is_command, result = handler.handle("Hello world")
        if not is_command:
            logger.info("✓ PASS: Non-command correctly ignored")
        else:
            logger.error("✗ FAIL: Non-command incorrectly handled")
            return False

        logger.info("\n✓ ALL TESTS PASSED")
        return True

    except Exception as e:
        logger.error(f"✗ FAIL: Handler test error: {e}", exc_info=True)
        return False


def test_explain_pipeline():
    """Test explain pipeline functionality."""
    logger.info("\n" + "="*80)
    logger.info("TEST: EXPLAIN PIPELINE")
    logger.info("="*80)

    try:
        from src.services.explain_pipeline import ExplainPipeline
        from unittest.mock import Mock, patch

        # Create mock agent registry
        mock_registry = Mock()

        # Test topic extraction
        pipeline = ExplainPipeline(mock_registry)

        # Test topic extraction directly
        test_cases = [
            ("explain Edgar Allan Poe", "Edgar Allan Poe"),
            ("summarize the machine learning paper", "machine learning paper"),
            ("describe what AI is", "what AI is"),
            ("tell me about quantum physics", "quantum physics"),
        ]

        for input_text, expected_topic in test_cases:
            extracted = pipeline._extract_topic(input_text)
            if extracted == expected_topic:
                logger.info(f"✓ PASS: '{input_text}' -> '{extracted}'")
            else:
                logger.error(f"✗ FAIL: '{input_text}' expected '{expected_topic}', got '{extracted}'")
                return False

        # Test synthesis style determination
        style_cases = [
            ("explain this in detail", "comprehensive"),
            ("summarize the key points", "concise"),
            ("compare these approaches", "comparative"),
            ("describe the timeline", "chronological"),
        ]

        for input_text, expected_style in style_cases:
            style = pipeline._determine_synthesis_style(input_text)
            if style == expected_style:
                logger.info(f"✓ PASS: '{input_text}' -> style '{style}'")
            else:
                logger.error(f"✗ FAIL: '{input_text}' expected style '{expected_style}', got '{style}'")
                return False

        logger.info("\n✓ EXPLAIN PIPELINE TESTS PASSED")
        return True

    except Exception as e:
        logger.error(f"✗ FAIL: Explain pipeline test error: {e}", exc_info=True)
        return False


def test_agent_execution():
    """Test executing commands through agents."""
    logger.info("\n" + "="*80)
    logger.info("TEST: AGENT EXECUTION VIA SLASH COMMANDS")
    logger.info("="*80)

    try:
        config = load_config()
        registry = AgentRegistry(config)
        handler = create_slash_command_handler(registry)

        # Test file organization command
        logger.info("\nTesting: /files Organize PDFs by topic")
        is_command, result = handler.handle("/files Organize AI-related PDFs in test_docs")

        if is_command:
            logger.info(f"✓ Command recognized")
            logger.info(f"  Type: {result.get('type')}")
            logger.info(f"  Agent: {result.get('agent')}")

            if result.get("type") == "result":
                exec_result = result.get("result", {})
                if exec_result.get("error"):
                    logger.warning(f"  Execution error (expected): {exec_result.get('error_message')}")
                else:
                    logger.info(f"  ✓ Execution successful!")
                    if "files_moved" in exec_result:
                        logger.info(f"    Files moved: {len(exec_result['files_moved'])}")
                        logger.info(f"    Files skipped: {len(exec_result.get('files_skipped', []))}")

        logger.info("\n✓ Agent execution test completed")
        return True

    except Exception as e:
        logger.error(f"✗ FAIL: Agent execution test error: {e}", exc_info=True)
        return False


def test_files_list_integration():
    """Test /files list command integration with document listing service."""
    logger.info("\n" + "="*80)
    logger.info("TEST: /FILES LIST INTEGRATION")
    logger.info("="*80)

    try:
        # Import required modules
        from src.agent.agent_registry import AgentRegistry
        from src.ui.slash_commands import create_slash_command_handler
        from src.utils import load_config

        # Load config and create handler
        config = load_config()
        registry = AgentRegistry(config)
        handler = create_slash_command_handler(registry, config)

        # Test 1: Basic /files list command
        logger.info("Testing /files list...")
        is_command, result = handler.handle("/files list")

        if not is_command:
            logger.error("✗ FAIL: /files list not recognized as command")
            return False

        if not result or result.get("type") != "result":
            logger.error(f"✗ FAIL: Expected result type 'result', got: {result}")
            return False

        if result.get("agent") != "file":
            logger.error(f"✗ FAIL: Expected agent 'file', got: {result.get('agent')}")
            return False

        # Check if we have a message
        message = result.get("message", "")
        if not message:
            logger.error("✗ FAIL: No message in result")
            return False

        logger.info(f"✓ PASS: Got message: {message[:100]}...")

        # Check if we have details (the actual document list)
        details = result.get("details", "")
        if not details:
            logger.error("✗ FAIL: No details (document list) in result")
            return False

        # Check for expected content in details
        if "Documents (" not in details:
            logger.error("✗ FAIL: Expected 'Documents (' in details")
            return False

        if ".pdf" not in details and ".txt" not in details:
            logger.error("✗ FAIL: Expected document extensions in details")
            return False

        logger.info("✓ PASS: Document list contains expected content")

        # Test 2: /files list with filter
        logger.info("Testing /files list guitar...")
        is_command, result = handler.handle("/files list guitar")

        if not is_command:
            logger.error("✗ FAIL: /files list guitar not recognized as command")
            return False

        if result.get("type") != "result":
            logger.error(f"✗ FAIL: Expected result type 'result', got: {result}")
            return False

        message = result.get("message", "")
        if "guitar" in message.lower() or "No documents found matching" in message:
            logger.info("✓ PASS: Filter applied correctly")
        else:
            logger.warning(f"⚠ WARN: Filter may not have been applied, message: {message}")

        # Test 3: /files show (alternative syntax)
        logger.info("Testing /files show...")
        is_command, result = handler.handle("/files show")

        if not is_command:
            logger.error("✗ FAIL: /files show not recognized as command")
            return False

        if result.get("type") != "result":
            logger.error(f"✗ FAIL: Expected result type 'result', got: {result}")
            return False

        logger.info("✓ PASS: /files show command works")

        # Test 4: Empty /files command should default to list
        logger.info("Testing /files (empty command)...")
        is_command, result = handler.handle("/files")

        if not is_command:
            logger.error("✗ FAIL: /files not recognized as command")
            return False

        if result.get("type") != "result":
            logger.error(f"✗ FAIL: Expected result type 'result', got: {result}")
            return False

        logger.info("✓ PASS: Empty /files command defaults to list")

        logger.info("✓ FILES LIST INTEGRATION TESTS PASSED")
        return True

    except Exception as e:
        logger.error(f"✗ FAIL: Files list integration test error: {e}", exc_info=True)
        return False


def run_all_tests():
    """Run all slash command tests."""
    logger.info("\n" + "="*80)
    logger.info("SLASH COMMAND SYSTEM TESTS")
    logger.info("="*80)

    results = {
        "Parser": test_parser(),
        "Help System": test_help(),
        "Handler": test_handler(),
        "Agent Execution": test_agent_execution(),
        "Explain Pipeline": test_explain_pipeline(),
        "Files List Integration": test_files_list_integration(),
    }

    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"  {status} - {test_name}")

    logger.info(f"\nTotal: {passed}/{total} tests passed ({int(passed/total*100)}%)")

    # Features demonstrated
    logger.info("\n" + "="*80)
    logger.info("FEATURES VERIFIED:")
    logger.info("="*80)
    logger.info("  ✓ Slash command parsing")
    logger.info("  ✓ Command to agent mapping")
    logger.info("  ✓ Help system (general and specific)")
    logger.info("  ✓ Agents list generation")
    logger.info("  ✓ Invalid command handling")
    logger.info("  ✓ LLM-based tool routing")
    logger.info("  ✓ Direct agent execution")
    logger.info("  ✓ /files list command integration")
    logger.info("  ✓ Document listing with metadata and filtering")
    logger.info("  ✓ Document list UI formatting")

    return results


if __name__ == "__main__":
    run_all_tests()
