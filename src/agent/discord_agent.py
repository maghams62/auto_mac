"""
Discord Agent - Bridges MacMCP automation with the Discord desktop client.

Responsibilities:
- Guarantee the Discord session is authenticated (using .env credentials)
- Navigate to specific servers/channels
- Read, post, and verify chat messages
- Detect unread activity and capture screenshots for auditing
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List
from langchain_core.tools import tool
import logging

from src.utils import load_config
from src.automation.discord_controller import DiscordController

logger = logging.getLogger(__name__)


def _get_controller() -> DiscordController:
    config = load_config()
    return DiscordController(config)


@tool
def ensure_discord_session() -> Dict[str, Any]:
    """
    Bring Discord to the foreground and log in if needed (uses DISCORD_EMAIL/DISCORD_PASSWORD from .env).

    Use this before any other Discord actions if you're unsure whether the desktop client
    is authenticated. Returns details about whether a login was performed or skipped.
    """
    logger.info("[DISCORD AGENT] Tool: ensure_discord_session()")
    controller = _get_controller()
    return controller.ensure_session()


@tool
def navigate_discord_channel(
    channel_name: str,
    server_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Navigate to a Discord channel using the Cmd+K quick switcher.

    Args:
        channel_name: Channel to open (e.g., "general")
        server_name: Optional server/guild name to disambiguate
    """
    logger.info(f"[DISCORD AGENT] Tool: navigate_discord_channel(channel='{channel_name}', server='{server_name}')")
    controller = _get_controller()
    return controller.navigate_to_channel(channel_name, server_name)


@tool
def discord_send_message(
    channel_name: str,
    message: str,
    server_name: Optional[str] = None,
    confirm_delivery: bool = True
) -> Dict[str, Any]:
    """
    Post a message to a Discord channel via the desktop app.

    Args:
        channel_name: Channel to post to
        message: Text body (newlines supported)
        server_name: Optional server/guild
        confirm_delivery: When true, re-read the channel afterward to confirm the text appears
    """
    logger.info(f"[DISCORD AGENT] Tool: discord_send_message(channel='{channel_name}', server='{server_name}')")
    controller = _get_controller()
    return controller.send_message(channel_name, message, server_name=server_name, confirm_delivery=confirm_delivery)


@tool
def discord_read_channel_messages(
    channel_name: str,
    limit: int = 10,
    server_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Read recent messages from a Discord channel using macOS accessibility text scraping.

    Args:
        channel_name: Channel to read from
        limit: Maximum number of messages to return (most recent)
        server_name: Optional server/guild
    """
    logger.info(f"[DISCORD AGENT] Tool: discord_read_channel_messages(channel='{channel_name}', limit={limit})")
    controller = _get_controller()
    return controller.read_messages(channel_name, limit=limit, server_name=server_name)


@tool
def discord_detect_unread_channels(
    server_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Inspect the server/channel list for unread indicators (bold text, dot badges).

    Args:
        server_name: Optional substring filter for the server/guild
    """
    logger.info("[DISCORD AGENT] Tool: discord_detect_unread_channels()")
    controller = _get_controller()
    return controller.detect_unread_channels(server_name=server_name)


@tool
def discord_capture_recent_messages(
    channel_name: str,
    server_name: Optional[str] = None,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Take a screenshot of the active Discord channel for auditing or sharing.

    Args:
        channel_name: Channel to capture
        server_name: Optional server/guild
        output_path: Optional custom screenshot path
    """
    logger.info("[DISCORD AGENT] Tool: discord_capture_recent_messages()")
    controller = _get_controller()
    return controller.screenshot_recent_messages(channel_name, server_name=server_name, output_path=output_path)


@tool
def verify_discord_channel(
    channel_name: str,
    server_name: Optional[str] = None,
    send_test_message: bool = False,
    test_message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verify the agent can log in, locate, and interact with a channel.

    Args:
        channel_name: Target channel
        server_name: Optional server/guild
        send_test_message: When true, posts a probe message (may remain in channel history)
        test_message: Optional override for the probe text
    """
    logger.info("[DISCORD AGENT] Tool: verify_discord_channel()")
    controller = _get_controller()
    return controller.verify_channel_interaction(
        channel_name,
        server_name=server_name,
        send_test_message=send_test_message,
        test_message=test_message
    )


DISCORD_AGENT_TOOLS = [
    ensure_discord_session,
    navigate_discord_channel,
    discord_send_message,
    discord_read_channel_messages,
    discord_detect_unread_channels,
    discord_capture_recent_messages,
    verify_discord_channel,
]


DISCORD_AGENT_HIERARCHY = """
Discord Agent Hierarchy:
=======================

LEVEL 1: Session + Navigation
└─ ensure_discord_session() → Activate/login using .env credentials
└─ navigate_discord_channel(channel_name, server_name?) → Jump to channel via quick switcher

LEVEL 2: Channel Interaction
└─ discord_send_message(channel_name, message, server_name?, confirm_delivery?) → Post chat messages
└─ discord_read_channel_messages(channel_name, limit, server_name?) → Read recent messages
└─ discord_detect_unread_channels(server_name?) → Find unread indicators
└─ discord_capture_recent_messages(channel_name, server_name?, output_path?) → Screenshot Discord UI

LEVEL 3: Verification
└─ verify_discord_channel(channel_name, server_name?, send_test_message?, test_message?) → End-to-end capability check
"""


class DiscordAgent:
    """Mini-orchestrator that exposes Discord UI automation as LangChain tools."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in DISCORD_AGENT_TOOLS}
        logger.info(f"[DISCORD AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        return DISCORD_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        return DISCORD_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Discord agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[DISCORD AGENT] Executing tool: {tool_name}")

        try:
            return tool.invoke(inputs)
        except Exception as exc:
            logger.error(f"[DISCORD AGENT] Execution error: {exc}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(exc),
                "retry_possible": False
            }
