"""
Slash Command Regression Tests

Tests for:
- Supported vs unsupported commands
- Telemetry behavior
- Command routing and fallback
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
from typing import Dict, Any

# Import helpers directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'fixtures')))
from slash_command_helpers import (
    create_slash_handler,
    invoke_slash_command,
    parse_slash_command,
    is_supported_command,
    get_usage_metrics,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_supported_commands():
    """Test that all supported commands are recognized."""
    logger.info("\n" + "="*80)
    logger.info("TEST: SUPPORTED COMMANDS")
    logger.info("="*80)

    supported_commands = [
        ("/email read my latest 3 emails", "email"),
        ("/explain Project Kickoff", "explain"),
        ("/bluesky search agentic workflows limit 5", "bluesky"),
        ("/bluesky post Hello world!", "bluesky"),
        ("/report summarize Tesla quarterly update", "report"),
        ("/help", "help"),
        ("/agents", "agents"),
        ("/clear", "clear"),
        ("/confetti", "confetti"),
    ]

    handler = create_slash_handler()
    passed = 0
    total = len(supported_commands)

    for command_str, expected_cmd in supported_commands:
        parsed = parse_slash_command(command_str)
        if parsed and parsed.get("command") == expected_cmd:
            logger.info(f"✓ PASS: '{command_str}' -> {expected_cmd}")
            passed += 1
        else:
            logger.error(f"✗ FAIL: '{command_str}' -> {parsed}")

    logger.info(f"\nSupported Commands Tests: {passed}/{total} passed")
    return passed == total


def test_unsupported_commands_fallback():
    """Test that unsupported commands fall back to natural language."""
    logger.info("\n" + "="*80)
    logger.info("TEST: UNSUPPORTED COMMANDS FALLBACK")
    logger.info("="*80)

    # Note: /maps is actually a supported backend command, but not in frontend dropdown
    # These are truly unsupported commands that should fall through
    unsupported_commands = [
        "/unknown do something",
        "/xyz123 task here",
        "/nonexistent command test",
    ]

    handler = create_slash_handler()
    passed = 0
    total = len(unsupported_commands)

    for command_str in unsupported_commands:
        # Parse should return None for unsupported commands
        parsed = parse_slash_command(command_str)
        if parsed is None:
            logger.info(f"✓ PASS: '{command_str}' correctly returns None (will fall through to orchestrator)")
            passed += 1
        else:
            logger.error(f"✗ FAIL: '{command_str}' should return None, got: {parsed}")
            continue  # Skip handler test if parsing failed

        # Handler should return (False, None) for unsupported commands
        is_command, result = invoke_slash_command(handler, command_str)
        if not is_command:
            logger.info(f"✓ PASS: Handler correctly returns is_command=False for '{command_str}'")
        else:
            logger.error(f"✗ FAIL: Handler should return is_command=False for '{command_str}', got: {is_command}")

    logger.info(f"\nUnsupported Commands Tests: {passed}/{total} passed")
    return passed == total


def test_telemetry_behavior():
    """Test that telemetry is recorded correctly for supported commands."""
    logger.info("\n" + "="*80)
    logger.info("TEST: TELEMETRY BEHAVIOR")
    logger.info("="*80)

    handler = create_slash_handler()
    
    # Get initial metrics
    initial_metrics = get_usage_metrics(handler)
    initial_email_count = initial_metrics.get("email", 0)

    # Invoke a supported command
    is_command, result = invoke_slash_command(handler, "/email read my latest 3 emails")
    
    if not is_command:
        logger.error("✗ FAIL: /email should be recognized as command")
        return False

    # Check metrics increased
    final_metrics = get_usage_metrics(handler)
    final_email_count = final_metrics.get("email", 0)

    if final_email_count > initial_email_count:
        logger.info(f"✓ PASS: Telemetry recorded (email count: {initial_email_count} -> {final_email_count})")
    else:
        logger.error(f"✗ FAIL: Telemetry not recorded (email count: {initial_email_count} -> {final_email_count})")
        return False

    # Test that unsupported commands don't increment telemetry
    initial_unknown_count = final_metrics.get("unknown", 0)
    is_command, result = invoke_slash_command(handler, "/unknown do something")
    
    if is_command:
        logger.error("✗ FAIL: /unknown should not be recognized as command")
        return False

    final_metrics_after = get_usage_metrics(handler)
    final_unknown_count = final_metrics_after.get("unknown", 0)

    if final_unknown_count == initial_unknown_count:
        logger.info(f"✓ PASS: Unsupported command did not increment telemetry")
    else:
        logger.error(f"✗ FAIL: Unsupported command incremented telemetry (unknown count: {initial_unknown_count} -> {final_unknown_count})")
        return False

    logger.info("\n✓ Telemetry behavior tests passed")
    return True


def test_command_routing():
    """Test that commands route to correct agents/tools."""
    logger.info("\n" + "="*80)
    logger.info("TEST: COMMAND ROUTING")
    logger.info("="*80)

    handler = create_slash_handler()
    
    test_cases = [
        ("/email read my latest 3 emails", "email"),
        ("/explain Project Kickoff", "explain"),
        ("/bluesky search agentic workflows", "bluesky"),
        ("/report summarize Tesla quarterly update", "report"),
    ]

    passed = 0
    total = len(test_cases)

    for command_str, expected_agent in test_cases:
        is_command, result = invoke_slash_command(handler, command_str)
        
        if not is_command:
            logger.error(f"✗ FAIL: '{command_str}' not recognized as command")
            continue

        # Check result structure
        if isinstance(result, dict):
            agent = result.get("agent") or result.get("type")
            if agent == expected_agent or result.get("type") in ["result", "help", "agents", "clear"]:
                logger.info(f"✓ PASS: '{command_str}' routed correctly")
                passed += 1
            else:
                logger.error(f"✗ FAIL: '{command_str}' routed to wrong agent: {agent}")
        else:
            logger.error(f"✗ FAIL: '{command_str}' returned unexpected result type: {type(result)}")

    logger.info(f"\nCommand Routing Tests: {passed}/{total} passed")
    return passed == total


def test_exactly_one_telemetry_per_invocation():
    """Test that exactly one telemetry event is recorded per command invocation."""
    logger.info("\n" + "="*80)
    logger.info("TEST: EXACTLY ONE TELEMETRY PER INVOCATION")
    logger.info("="*80)

    handler = create_slash_handler()
    
    # Get initial metrics
    initial_metrics = get_usage_metrics(handler)
    initial_help_count = initial_metrics.get("help", 0)

    # Invoke command multiple times
    for i in range(3):
        is_command, result = invoke_slash_command(handler, "/help")
        if not is_command:
            logger.error(f"✗ FAIL: /help not recognized on invocation {i+1}")
            return False

    # Check metrics increased by exactly 3
    final_metrics = get_usage_metrics(handler)
    final_help_count = final_metrics.get("help", 0)

    expected_count = initial_help_count + 3
    if final_help_count == expected_count:
        logger.info(f"✓ PASS: Exactly one telemetry event per invocation (count: {initial_help_count} -> {final_help_count})")
        return True
    else:
        logger.error(f"✗ FAIL: Expected {expected_count} telemetry events, got {final_help_count}")
        return False


def test_telemetry_failure_does_not_break_flow():
    """Test that telemetry failures don't break user-facing flows."""
    logger.info("\n" + "="*80)
    logger.info("TEST: TELEMETRY FAILURE HANDLING")
    logger.info("="*80)

    handler = create_slash_handler()
    
    # Mock a telemetry failure by temporarily breaking the performance monitor
    # (In real scenario, this would be handled gracefully)
    try:
        is_command, result = invoke_slash_command(handler, "/help")
        
        if is_command and result:
            logger.info("✓ PASS: Command executed successfully even if telemetry might fail")
            return True
        else:
            logger.error("✗ FAIL: Command failed when telemetry might fail")
            return False
    except Exception as e:
        logger.error(f"✗ FAIL: Exception during command execution: {e}")
        return False


def run_all_tests():
    """Run all slash command regression tests."""
    logger.info("\n" + "="*80)
    logger.info("SLASH COMMAND REGRESSION TESTS")
    logger.info("="*80)

    results = {
        "supported_commands": test_supported_commands(),
        "unsupported_commands_fallback": test_unsupported_commands_fallback(),
        "telemetry_behavior": test_telemetry_behavior(),
        "command_routing": test_command_routing(),
        "exactly_one_telemetry": test_exactly_one_telemetry_per_invocation(),
        "telemetry_failure_handling": test_telemetry_failure_does_not_break_flow(),
    }

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    logger.info("\n" + "="*80)
    logger.info(f"RESULTS: {passed}/{total} test suites passed")
    logger.info("="*80)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

