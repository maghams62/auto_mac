#!/usr/bin/env python3
"""
Tests for /bluesky slash command routing and parsing.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.slash_commands import SlashCommandParser, SlashCommandHandler


def test_bluesky_command_mapping():
    parser = SlashCommandParser()
    assert "bluesky" in parser.COMMAND_MAP
    assert parser.COMMAND_MAP["bluesky"] == "bluesky"
    assert parser.COMMAND_MAP["sky"] == "bluesky"


def test_bluesky_examples_and_tooltip():
    parser = SlashCommandParser()
    assert "bluesky" in parser.EXAMPLES
    assert any("search" in ex for ex in parser.EXAMPLES["bluesky"])
    tooltips = [tip for tip in parser.COMMAND_TOOLTIPS if tip["command"] == "/bluesky"]
    assert tooltips, "/bluesky command should have tooltip"
    tooltip = tooltips[0]
    assert "Bluesky" in tooltip["label"]


class DummyRegistry:
    def __init__(self):
        self.calls = []
        self.config = {
            "bluesky": {
                "default_lookback_hours": 24,
                "max_summary_items": 5,
                "default_search_limit": 10,
            }
        }

    def execute_tool(self, tool_name, params, session_id=None):
        self.calls.append((tool_name, params))
        return {"success": True, "tool": tool_name, "params": params}


def test_bluesky_search_routing():
    handler = SlashCommandHandler(DummyRegistry())
    is_cmd, result = handler.handle('/bluesky search "agent ecosystems" limit:8')

    assert is_cmd is True
    assert result["agent"] == "bluesky"
    assert result["mode"] == "search"
    tool_name, params = handler.registry.calls[-1]
    assert tool_name == "search_bluesky_posts"
    assert params["max_posts"] == 8
    assert params["query"] == "agent ecosystems"


def test_bluesky_summary_routing():
    handler = SlashCommandHandler(DummyRegistry())
    is_cmd, result = handler.handle('/bluesky summarize "agent ecosystems" 12h max:3')

    assert is_cmd is True
    assert result["mode"] == "summary"
    tool_name, params = handler.registry.calls[-1]
    assert tool_name == "summarize_bluesky_posts"
    assert params["lookback_hours"] == 12
    assert params["max_items"] == 3
    assert params["query"] == "agent ecosystems"


def test_bluesky_post_routing():
    handler = SlashCommandHandler(DummyRegistry())
    is_cmd, result = handler.handle('/bluesky post "Hello Bluesky!"')

    assert is_cmd is True
    assert result["mode"] == "post"
    tool_name, params = handler.registry.calls[-1]
    assert tool_name == "post_bluesky_update"
    assert params["message"] == "Hello Bluesky!"


if __name__ == "__main__":
    print("Testing /bluesky slash command implementation...\n")
    try:
        test_bluesky_command_mapping()
        test_bluesky_examples_and_tooltip()
        test_bluesky_search_routing()
        test_bluesky_summary_routing()
        test_bluesky_post_routing()
        print("\n✅ All /bluesky command tests passed!")
    except AssertionError as exc:
        print(f"\n❌ Test failed: {exc}")
        sys.exit(1)
