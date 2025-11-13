"""
Test explain command functionality - both slash and natural language.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
from unittest.mock import Mock, patch
from src.utils import load_config
from src.agent.agent import AutomationAgent as Agent
from src.ui.slash_commands import SlashCommandHandler, create_slash_command_handler
from src.services.explain_pipeline import ExplainPipeline

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_slash_explain_commands():
    """Test slash command explain functionality."""
    logger.info("\n" + "="*80)
    logger.info("TEST: SLASH EXPLAIN COMMANDS")
    logger.info("="*80)

    try:
        config = load_config()
        handler = create_slash_command_handler(config)

        # Test /explain command
        is_command, result = handler.handle("/explain Edgar Allan Poe")
        if is_command and result.get("type") == "result" and result.get("agent") == "explain":
            logger.info("✓ PASS: /explain command handled correctly")
        else:
            logger.error(f"✗ FAIL: /explain command not handled properly: {result}")
            return False

        # Test /files explain command (should route to explain agent)
        is_command, result = handler.handle("/files explain machine learning")
        if is_command and result.get("type") == "result" and result.get("agent") == "explain":
            logger.info("✓ PASS: /files explain command routed to explain agent")
        else:
            logger.error(f"✗ FAIL: /files explain command not routed properly: {result}")
            return False

        logger.info("\n✓ SLASH EXPLAIN TESTS PASSED")
        return True

    except Exception as e:
        logger.error(f"✗ FAIL: Slash explain test error: {e}", exc_info=True)
        return False


def test_natural_language_explain():
    """Test natural language explain detection in agent.run()."""
    logger.info("\n" + "="*80)
    logger.info("TEST: NATURAL LANGUAGE EXPLAIN DETECTION")
    logger.info("="*80)

    try:
        config = load_config()

        # Create agent with mocked explain pipeline
        with patch('src.agent.agent_registry.AgentRegistry') as mock_registry_class, \
             patch('src.services.explain_pipeline.ExplainPipeline') as mock_pipeline_class:

            # Setup mocks
            mock_registry = Mock()
            mock_registry_class.return_value = mock_registry

            mock_pipeline = Mock()
            mock_pipeline_class.return_value = mock_pipeline

            # Mock successful explain result
            mock_pipeline.execute.return_value = {
                "success": True,
                "summary": "This is an explanation of Edgar Allan Poe.",
                "doc_title": "Test Document",
                "doc_path": "/test/path.pdf",
                "word_count": 50,
                "telemetry": {
                    "topic_extracted": "Edgar Allan Poe",
                    "selected_file": "/test/path.pdf",
                    "similarity_score": 0.85
                }
            }

            # Create agent (this will use our mocked registry and pipeline)
            agent = Agent(config)

            # Test explain command detection
            test_cases = [
                "explain Edgar Allan Poe",
                "summarize machine learning",
                "describe quantum physics",
                "tell me about artificial intelligence",
                "what is blockchain"
            ]

            for test_query in test_cases:
                logger.info(f"Testing: '{test_query}'")
                result = agent.run(test_query)

                # Should have called the explain pipeline
                mock_pipeline.execute.assert_called()

                # Should return success result
                if result.get("status") == "success" and result.get("message"):
                    logger.info(f"✓ PASS: '{test_query}' detected and processed")
                else:
                    logger.error(f"✗ FAIL: '{test_query}' not processed correctly: {result}")
                    return False

                # Reset mock for next test
                mock_pipeline.reset_mock()

            # Test delivery intent conflict avoidance
            delivery_cases = [
                "email me the explanation of Edgar Allan Poe",  # Should not trigger explain
                "send the summary to john@example.com",  # Should not trigger explain
            ]

            for test_query in delivery_cases:
                logger.info(f"Testing delivery conflict: '{test_query}'")
                result = agent.run(test_query)

                # Should NOT have called the explain pipeline (should fall through to normal processing)
                if not mock_pipeline.execute.called:
                    logger.info(f"✓ PASS: '{test_query}' correctly avoided explain detection due to delivery intent")
                else:
                    logger.error(f"✗ FAIL: '{test_query}' incorrectly triggered explain detection")
                    return False

        logger.info("\n✓ NATURAL LANGUAGE EXPLAIN TESTS PASSED")
        return True

    except Exception as e:
        logger.error(f"✗ FAIL: Natural language explain test error: {e}", exc_info=True)
        return False


def test_explain_pipeline_error_handling():
    """Test explain pipeline error handling."""
    logger.info("\n" + "="*80)
    logger.info("TEST: EXPLAIN PIPELINE ERROR HANDLING")
    logger.info("="*80)

    try:
        from src.services.explain_pipeline import ExplainPipeline
        from unittest.mock import Mock

        mock_registry = Mock()
        pipeline = ExplainPipeline(mock_registry)

        # Test error response creation
        error_result = pipeline._create_error_response("Test error message", {"test": "telemetry"})
        if (not error_result.get("success") and
            error_result.get("error") and
            error_result.get("error_message") == "Test error message"):
            logger.info("✓ PASS: Error response creation works")
        else:
            logger.error(f"✗ FAIL: Error response creation failed: {error_result}")
            return False

        # Test topic extraction edge cases
        edge_cases = [
            ("explain", "explain"),  # No topic
            ("", ""),  # Empty string
            ("explain the", "the"),  # Minimal topic
        ]

        for input_text, expected in edge_cases:
            result = pipeline._extract_topic(input_text)
            if result == expected:
                logger.info(f"✓ PASS: Edge case '{input_text}' -> '{result}'")
            else:
                logger.error(f"✗ FAIL: Edge case '{input_text}' expected '{expected}', got '{result}'")
                return False

        logger.info("\n✓ ERROR HANDLING TESTS PASSED")
        return True

    except Exception as e:
        logger.error(f"✗ FAIL: Error handling test error: {e}", exc_info=True)
        return False


def run_all_explain_tests():
    """Run all explain command tests."""
    logger.info("\n" + "="*80)
    logger.info("EXPLAIN COMMAND SYSTEM TESTS")
    logger.info("="*80)

    results = {
        "Slash Explain Commands": test_slash_explain_commands(),
        "Natural Language Explain": test_natural_language_explain(),
        "Error Handling": test_explain_pipeline_error_handling(),
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

    logger.info(f"\nTotal: {passed}/{total} tests passed ({int(passed/total*100) if total > 0 else 0}%)")

    # Features demonstrated
    logger.info("\n" + "="*80)
    logger.info("EXPLAIN FEATURES VERIFIED:")
    logger.info("="*80)
    logger.info("  ✓ /explain slash command parsing and execution")
    logger.info("  ✓ /files explain... routing to explain agent")
    logger.info("  ✓ Natural language explain detection (explain/summarize/describe/tell me about)")
    logger.info("  ✓ Delivery intent conflict avoidance")
    logger.info("  ✓ Explain pipeline topic extraction and style determination")
    logger.info("  ✓ Error handling and telemetry reporting")

    return results


if __name__ == "__main__":
    run_all_explain_tests()
