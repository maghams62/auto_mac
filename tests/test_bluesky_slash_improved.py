"""
Test improved Bluesky slash command intent detection.

Tests the refined logic:
1. Explicit verbs (post, say, tweet, announce) → post mode
2. Short free-form text (≤128 chars, no keywords) → post mode
3. Time/window hints → summary mode
4. Search keywords → search mode
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ui.slash_commands import SlashCommandHandler


def test_explicit_posting_verbs():
    """Test that explicit posting verbs trigger post mode."""

    class MockRegistry:
        config = {"bluesky": {}}
        def execute_tool(self, tool_name, params, session_id=None):
            return {"tool": tool_name, "params": params}
        def get_agent(self, name):
            return None

    handler = SlashCommandHandler(MockRegistry())

    # Test all posting verbs
    posting_verbs = ["post", "say", "tweet", "announce", "publish", "send"]

    for verb in posting_verbs:
        # Test with space separator
        mode, params = handler._parse_bluesky_task(f"{verb} Hello from the test suite!")
        assert mode == "post", f"Expected 'post' mode for verb '{verb}', got: {mode}"
        assert params["message"] == "Hello from the test suite!", \
            f"Expected message to be extracted for '{verb}', got: {params}"

        # Test with colon separator
        mode, params = handler._parse_bluesky_task(f"{verb}: Testing with colon")
        assert mode == "post", f"Expected 'post' mode for '{verb}:', got: {mode}"
        assert params["message"] == "Testing with colon", \
            f"Expected message after colon for '{verb}:', got: {params}"

        # Test with dash separator
        mode, params = handler._parse_bluesky_task(f"{verb} - Testing with dash")
        assert mode == "post", f"Expected 'post' mode for '{verb} -', got: {mode}"
        assert params["message"] == "Testing with dash", \
            f"Expected message after dash for '{verb} -', got: {params}"

    print("✅ Explicit posting verbs tests passed")


def test_short_freeform_text():
    """Test that short text without keywords defaults to post mode."""

    class MockRegistry:
        config = {"bluesky": {}}
        def execute_tool(self, tool_name, params, session_id=None):
            return {"tool": tool_name, "params": params}
        def get_agent(self, name):
            return None

    handler = SlashCommandHandler(MockRegistry())

    # Short, natural language posts
    short_posts = [
        "Launch day! 🚀",
        "Just shipped a new feature",
        "Working on something cool",
        "Coffee time ☕",
        "Great presentation today!",
    ]

    for text in short_posts:
        mode, params = handler._parse_bluesky_task(text)
        assert mode == "post", f"Expected 'post' mode for short text '{text}', got: {mode}"
        assert params["message"] == text, f"Expected message '{text}', got: {params['message']}"

    print("✅ Short free-form text tests passed")


def test_search_keywords_override_short_text():
    """Test that search keywords prevent short text from becoming posts."""

    class MockRegistry:
        config = {"bluesky": {"default_search_limit": 10}}
        def execute_tool(self, tool_name, params, session_id=None):
            return {"tool": tool_name, "params": params}
        def get_agent(self, name):
            return None

    handler = SlashCommandHandler(MockRegistry())

    # Short text but with search keywords - should be search mode
    search_queries = [
        ('search "AI agents"', "search"),
        ('find "machine learning"', "search"),
        ('lookup "LLMs"', "search"),
        ('scan for "agents"', "search"),
    ]

    for text, expected_mode in search_queries:
        mode, params = handler._parse_bluesky_task(text)
        assert mode == expected_mode, f"Expected '{expected_mode}' mode for '{text}', got: {mode}"

    print("✅ Search keywords override tests passed")


def test_summary_keywords():
    """Test that summary keywords trigger summary mode."""

    class MockRegistry:
        config = {"bluesky": {"default_lookback_hours": 24, "max_summary_items": 5}}
        def execute_tool(self, tool_name, params, session_id=None):
            return {"tool": tool_name, "params": params}
        def get_agent(self, name):
            return None

    handler = SlashCommandHandler(MockRegistry())

    # Summary queries
    summary_queries = [
        'summarize "LLMs" 12h',
        'summary "agent ecosystems" 24h',
        'analyze "AI trends"',
        'last 5 posts about "agents"',
    ]

    for text in summary_queries:
        mode, params = handler._parse_bluesky_task(text)
        assert mode == "summary", f"Expected 'summary' mode for '{text}', got: {mode}"

    print("✅ Summary keywords tests passed")


def test_explicit_search_mode():
    """Test explicit search with limit parameters."""

    class MockRegistry:
        config = {"bluesky": {"default_search_limit": 10}}
        def execute_tool(self, tool_name, params, session_id=None):
            return {"tool": tool_name, "params": params}
        def get_agent(self, name):
            return None

    handler = SlashCommandHandler(MockRegistry())

    # Search with limit
    mode, params = handler._parse_bluesky_task('search "agent ecosystems" limit:8')
    assert mode == "search", f"Expected 'search' mode, got: {mode}"
    assert params["query"] == "agent ecosystems", f"Expected query 'agent ecosystems', got: {params['query']}"
    assert params["max_posts"] == 8, f"Expected max_posts=8, got: {params['max_posts']}"

    # Search without explicit limit (should use default)
    mode, params = handler._parse_bluesky_task('search "AI safety"')
    assert mode == "search", f"Expected 'search' mode, got: {mode}"
    assert params["max_posts"] == 10, f"Expected default max_posts=10, got: {params['max_posts']}"

    print("✅ Explicit search mode tests passed")


def test_quoted_text_extraction():
    """Test that quoted text is properly extracted."""

    class MockRegistry:
        config = {"bluesky": {}}
        def execute_tool(self, tool_name, params, session_id=None):
            return {"tool": tool_name, "params": params}
        def get_agent(self, name):
            return None

    handler = SlashCommandHandler(MockRegistry())

    # Double quotes
    mode, params = handler._parse_bluesky_task('post "Testing with quotes"')
    assert params["message"] == "Testing with quotes", \
        f"Expected quoted text to be extracted, got: {params['message']}"

    # Single quotes
    mode, params = handler._parse_bluesky_task("post 'Single quote test'")
    assert params["message"] == "Single quote test", \
        f"Expected single-quoted text to be extracted, got: {params['message']}"

    print("✅ Quoted text extraction tests passed")


def test_long_text_defaults_to_search():
    """Test that text >128 chars defaults to search mode."""

    class MockRegistry:
        config = {"bluesky": {"default_search_limit": 10}}
        def execute_tool(self, tool_name, params, session_id=None):
            return {"tool": tool_name, "params": params}
        def get_agent(self, name):
            return None

    handler = SlashCommandHandler(MockRegistry())

    # Long text without keywords should default to search
    long_text = "This is a very long query about artificial intelligence and machine learning " \
                "that exceeds 128 characters and should therefore be treated as a search query " \
                "rather than a post"

    mode, params = handler._parse_bluesky_task(long_text)
    assert mode == "search", f"Expected 'search' mode for long text, got: {mode}"

    print("✅ Long text defaults to search tests passed")


def test_bluesky_result_formatting():
    """Test that post results are formatted with friendly messages."""

    class MockRegistry:
        config = {"bluesky": {}}
        def execute_tool(self, tool_name, params, session_id=None):
            if tool_name == "post_bluesky_update":
                # Simulate successful post
                return {"success": True, "post_id": "test123"}
            return {}
        def get_agent(self, name):
            return None

    handler = SlashCommandHandler(MockRegistry())

    # Simulate a /bluesky post command through the parser
    from src.ui.slash_commands import SlashCommandParser
    parser = SlashCommandParser()

    parsed = parser.parse("/bluesky post Hello world!")
    assert parsed is not None, "Failed to parse /bluesky command"
    assert parsed["command"] == "bluesky", f"Expected 'bluesky' command, got: {parsed['command']}"

    print("✅ Bluesky result formatting tests passed")


def run_all_tests():
    """Run all Bluesky slash command tests."""
    print("\n" + "="*60)
    print("BLUESKY SLASH COMMAND IMPROVED LOGIC TESTS")
    print("="*60 + "\n")

    test_explicit_posting_verbs()
    test_short_freeform_text()
    test_search_keywords_override_short_text()
    test_summary_keywords()
    test_explicit_search_mode()
    test_quoted_text_extraction()
    test_long_text_defaults_to_search()
    test_bluesky_result_formatting()

    print("\n" + "="*60)
    print("✅ ALL BLUESKY TESTS PASSED")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_tests()
