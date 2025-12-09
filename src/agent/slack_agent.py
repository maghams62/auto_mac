"""
Slack Agent - Fetch and analyze messages from Slack channels.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from ..integrations.slack_client import SlackAPIClient, SlackAPIError
from ..services.slack_metadata import SlackMetadataService
from ..utils.slack import normalize_channel_name
_metadata_service: Optional[SlackMetadataService] = None


def _get_slack_metadata_service(config: Dict[str, Any]) -> SlackMetadataService:
    global _metadata_service
    if _metadata_service is None:
        _metadata_service = SlackMetadataService(config=config)
    return _metadata_service


logger = logging.getLogger(__name__)


def _format_timestamp(ts: str) -> str:
    """Convert Slack timestamp to human-readable format."""
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError):
        return ts


def _normalize_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a Slack message to a consistent format."""
    return {
        "type": msg.get("type", "message"),
        "user": msg.get("user", "unknown"),
        "text": msg.get("text", ""),
        "timestamp": msg.get("ts", ""),
        "formatted_time": _format_timestamp(msg.get("ts", "")),
        "thread_ts": msg.get("thread_ts"),
        "reply_count": msg.get("reply_count", 0),
        "reactions": msg.get("reactions", []),
        "files": msg.get("files", []),
        "attachments": msg.get("attachments", []),
    }


@tool
def fetch_slack_messages(channel_id: str, limit: int = 100) -> Dict[str, Any]:
    """
    Fetch recent messages from a Slack channel.

    Args:
        channel_id: Slack channel ID (e.g., "C0123456789")
        limit: Maximum number of messages to return (default 100, max 1000)
    """
    if not channel_id or not channel_id.strip():
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "Channel ID cannot be empty.",
            "retry_possible": False,
        }

    limit = max(1, min(limit, 1000))

    try:
        client = SlackAPIClient()
        response = client.fetch_messages(channel_id.strip(), limit=limit)
    except SlackAPIError as exc:
        return {
            "error": True,
            "error_type": "SlackAPIError",
            "error_message": str(exc),
            "retry_possible": True,
        }
    except Exception as exc:
        logger.exception("Unexpected Slack fetch error")
        return {
            "error": True,
            "error_type": "SlackClientError",
            "error_message": str(exc),
            "retry_possible": False,
        }

    messages = [_normalize_message(msg) for msg in response.get("messages", [])]

    return {
        "channel_id": channel_id.strip(),
        "count": len(messages),
        "messages": messages,
        "has_more": response.get("has_more", False),
    }


@tool
def get_slack_channel_info(channel_id: str) -> Dict[str, Any]:
    """
    Get information about a Slack channel.

    Args:
        channel_id: Slack channel ID (e.g., "C0123456789")
    """
    if not channel_id or not channel_id.strip():
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "Channel ID cannot be empty.",
            "retry_possible": False,
        }

    try:
        client = SlackAPIClient()
        response = client.get_channel_info(channel_id.strip())
    except SlackAPIError as exc:
        return {
            "error": True,
            "error_type": "SlackAPIError",
            "error_message": str(exc),
            "retry_possible": True,
        }
    except Exception as exc:
        logger.exception("Unexpected Slack channel info error")
        return {
            "error": True,
            "error_type": "SlackClientError",
            "error_message": str(exc),
            "retry_possible": False,
        }

    channel = response.get("channel", {})

    return {
        "id": channel.get("id"),
        "name": channel.get("name"),
        "is_channel": channel.get("is_channel", False),
        "is_private": channel.get("is_private", False),
        "is_archived": channel.get("is_archived", False),
        "topic": channel.get("topic", {}).get("value", ""),
        "purpose": channel.get("purpose", {}).get("value", ""),
        "num_members": channel.get("num_members", 0),
        "created": _format_timestamp(str(channel.get("created", 0))),
    }


@tool
def list_slack_channels(limit: int = 100) -> Dict[str, Any]:
    """
    List channels in the Slack workspace.

    Args:
        limit: Maximum number of channels to return (default 100, max 1000)
    """
    limit = max(1, min(limit, 1000))

    try:
        client = SlackAPIClient()
        response = client.list_channels(limit=limit)
    except SlackAPIError as exc:
        return {
            "error": True,
            "error_type": "SlackAPIError",
            "error_message": str(exc),
            "retry_possible": True,
        }
    except Exception as exc:
        logger.exception("Unexpected Slack list channels error")
        return {
            "error": True,
            "error_type": "SlackClientError",
            "error_message": str(exc),
            "retry_possible": False,
        }

    channels = []
    for channel in response.get("channels", []):
        channels.append({
            "id": channel.get("id"),
            "name": channel.get("name"),
            "is_channel": channel.get("is_channel", False),
            "is_private": channel.get("is_private", False),
            "is_archived": channel.get("is_archived", False),
            "num_members": channel.get("num_members", 0),
        })

    return {
        "count": len(channels),
        "channels": channels,
    }


@tool
def search_slack_messages(
    query: str,
    channel: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Search Slack messages and find relevant discussions.

    Use this when user asks questions like:
    - "Did we discuss the payments API change?"
    - "What did the team say about the 500 errors?"
    - "Check Slack for mentions of the auth bug"
    - "Search Slack for discussions about X"

    Args:
        query: Search query or question (e.g., "payments API", "500 errors")
        channel: Optional channel name or ID (e.g., "#payments-demo", "C0123456789")
        limit: Max messages to retrieve (default 20, max 100)

    Returns:
        Dictionary with search results and message details
    """
    if not query or not query.strip():
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "Search query cannot be empty.",
            "retry_possible": False,
        }

    limit = max(1, min(limit, 100))

    try:
        from ..integrations.slack_client import SlackAPIClient
        from ..utils import load_config

        config = load_config()
        client = SlackAPIClient()
        metadata_service = _get_slack_metadata_service(config)

        # Determine which channel to scope the search to (optional)
        search_channel = channel
        channels_searched: List[str] = []

        if search_channel:
            normalized = normalize_channel_name(search_channel)
            match = metadata_service.get_channel(search_channel) or (
                metadata_service.get_channel(normalized) if normalized else None
            )
            if match:
                search_channel = match.id
                channels_searched = [match.name]
        if not search_channel:
            search_channel = metadata_service.get_default_channel_id()
            if search_channel:
                resolved = metadata_service.get_channel(search_channel)
                channels_searched = [resolved.name if resolved else search_channel]

        # Perform search
        results = client.search_messages(query, channel=search_channel, limit=limit)

        # Extract unique channels from results
        if not channels_searched and results.get("matches"):
            channels_searched = list(
                {
                    match.get("channel", {}).get("name", match.get("channel", {}).get("id", ""))
                    for match in results["matches"]
                    if match.get("channel")
                }
            )

        return {
            "query": query,
            "channels_searched": channels_searched or (["workspace default"] if search_channel else []),
            "messages_found": results.get("total", 0),
            "messages": results.get("matches", []),
        }

    except Exception as exc:
        logger.exception("Error searching Slack messages")
        return {
            "error": True,
            "error_type": "SlackSearchError",
            "error_message": str(exc),
            "retry_possible": True,
        }


SLACK_AGENT_TOOLS = [
    fetch_slack_messages,
    get_slack_channel_info,
    list_slack_channels,
    search_slack_messages,
]

SLACK_AGENT_HIERARCHY = """
Slack Agent Hierarchy:
=====================

LEVEL 1: Channel Information
└─ list_slack_channels(limit=100) → List channels in workspace
└─ get_slack_channel_info(channel_id) → Get channel metadata

LEVEL 2: Message Retrieval
└─ fetch_slack_messages(channel_id, limit=100) → Fetch recent messages from channel
└─ search_slack_messages(query, channel, limit) → Search and find relevant discussions
"""


class SlackAgent:
    """
    Orchestrates Slack channel and message operations.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in SLACK_AGENT_TOOLS}
        logger.info(f"[SLACK AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        return SLACK_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        return SLACK_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Slack agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys()),
            }

        tool = self.tools[tool_name]
        try:
            return tool.invoke(inputs)
        except Exception as exc:
            logger.exception("Slack agent execution error")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(exc),
                "retry_possible": False,
            }
