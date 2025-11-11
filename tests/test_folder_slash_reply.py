import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.slash_commands import SlashCommandHandler


class DummyRegistry:
    def __init__(self, listing):
        self.calls = []
        self.listing = listing
        self.config = {}

    def get_agent(self, agent_name):
        return SimpleNamespace()

    def execute_tool(self, tool_name, inputs, session_id=None):
        self.calls.append((tool_name, inputs))
        if tool_name == "folder_list":
            return self.listing
        if tool_name == "reply_to_user":
            return {
                "type": "reply",
                "message": inputs.get("message"),
                "details": inputs.get("details"),
                "artifacts": inputs.get("artifacts"),
                "status": inputs.get("status", "success"),
                "error": False,
            }
        return {"success": True}


FOLDER_LISTING = {
    "items": [
        {"name": "Report.pdf", "type": "file", "extension": ".pdf"},
        {"name": "Images", "type": "dir"},
        {"name": "Notes.txt", "type": "file", "extension": ".txt"},
        {"name": "todo", "type": "file", "extension": ""},
    ],
    "total_count": 4,
    "folder_path": "/tmp/test-folder",
    "relative_path": "test-folder",
}


def test_folder_summary_shortcut(monkeypatch):
    registry = DummyRegistry(FOLDER_LISTING)
    handler = SlashCommandHandler(registry)

    is_command, payload = handler.handle('/folder summarise my files')

    assert is_command
    assert payload["agent"] == "folder"
    assert payload["result"]["type"] == "reply"
    assert "Files:" in payload["result"]["details"]
    assert ("folder_list", {}) in registry.calls
    assert any(name == "reply_to_user" for name, _ in registry.calls)


def test_folder_listing_via_llm(monkeypatch):
    registry = DummyRegistry(FOLDER_LISTING)
    handler = SlashCommandHandler(registry)

    monkeypatch.setattr(
        SlashCommandHandler,
        "_execute_agent_task",
        lambda self, agent, agent_name, task: FOLDER_LISTING,
    )

    is_command, payload = handler.handle('/folder show everything')

    assert is_command
    assert payload["agent"] in {"folder", "file"}
    assert payload["result"]["type"] == "reply"
    assert "Files:" in payload["result"]["details"]
    assert any(name == "reply_to_user" for name, _ in registry.calls)
