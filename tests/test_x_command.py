#!/usr/bin/env python3
"""
Test /x slash command for Twitter summaries.

This test verifies that:
1. /x command maps to twitter agent
2. Examples are properly configured
3. Tooltip is available
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ui.slash_commands import SlashCommandParser


def test_x_command_mapping():
    """Test that /x maps to twitter agent."""
    parser = SlashCommandParser()

    # Check command map
    assert "x" in parser.COMMAND_MAP, "/x command not in COMMAND_MAP"
    assert parser.COMMAND_MAP["x"] == "twitter", "/x should map to twitter agent"

    print("✓ /x command correctly maps to twitter agent")


def test_x_command_examples():
    """Test that /x has proper examples."""
    parser = SlashCommandParser()

    # Check examples
    assert "x" in parser.EXAMPLES, "/x command has no examples"
    examples = parser.EXAMPLES["x"]

    assert len(examples) >= 2, "Should have at least 2 examples"
    assert any("1h" in ex for ex in examples), "Should have 1 hour example"

    print("✓ /x command has proper examples:")
    for example in examples:
        print(f"  - {example}")


def test_x_command_tooltip():
    """Test that /x has a tooltip."""
    parser = SlashCommandParser()

    # Check tooltips
    x_tooltips = [t for t in parser.COMMAND_TOOLTIPS if t["command"] == "/x"]

    assert len(x_tooltips) > 0, "/x command has no tooltip"
    tooltip = x_tooltips[0]

    assert "label" in tooltip, "Tooltip missing label"
    assert "description" in tooltip, "Tooltip missing description"

    print(f"✓ /x command has tooltip: {tooltip['label']} - {tooltip['description']}")


def test_x_command_parsing():
    """Test that /x commands parse correctly."""
    parser = SlashCommandParser()

    test_cases = [
        "/x summarize last 1h",
        "/x what happened on Twitter in the past hour",
    ]

    for command in test_cases:
        result = parser.parse(command)

        assert result is not None, f"Failed to parse: {command}"
        assert result["agent"] == "twitter", f"Wrong agent for: {command}"
        assert "task" in result, f"Missing task for: {command}"

        print(f"✓ Parsed: {command}")
        print(f"  → Agent: {result['agent']}, Task: {result['task']}")


if __name__ == "__main__":
    print("Testing /x slash command implementation...\n")

    try:
        test_x_command_mapping()
        test_x_command_examples()
        test_x_command_tooltip()
        test_x_command_parsing()

        print("\n✅ All /x command tests passed!")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
