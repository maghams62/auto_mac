"""
Oqoqo Agent - Query and analyze activity across Slack + GitHub.

This agent orchestrates activity signals from multiple sources to answer
questions about recent work, discussions, and code changes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from .multi_source_reasoner import MultiSourceReasoner

logger = logging.getLogger(__name__)


@tool
def get_git_activity(
    limit: int = 10,
    state: str = "all",
    branch: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get recent GitHub PR activity.

    Args:
        limit: Maximum number of PRs to return (default 10, max 50)
        state: "open", "closed", or "all" (default "all")
        branch: Filter by base branch (e.g., "main")

    Returns:
        Dictionary with PR list and metadata
    """
    try:
        from .git_agent import list_recent_prs

        result = list_recent_prs(
            limit=limit,
            state=state,
            branch=branch,
            use_live_api=True  # Prefer live API over webhook cache
        )

        logger.info(f"[OQOQO AGENT] Fetched {result.get('count', 0)} PRs")
        return result

    except Exception as exc:
        logger.exception("Error fetching Git activity")
        return {
            "error": True,
            "error_type": "GitActivityError",
            "error_message": str(exc),
            "retry_possible": True,
        }


@tool
def get_slack_activity(
    query: str,
    channel: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Search Slack for discussions and activity.

    Args:
        query: Search query (keywords, phrases)
        channel: Optional channel ID to restrict search
        limit: Maximum results to return (default 20, max 100)

    Returns:
        Dictionary with search results
    """
    try:
        from .slack_agent import search_slack_messages

        result = search_slack_messages(
            query=query,
            channel=channel,
            limit=limit
        )

        total = result.get("total", 0)
        logger.info(f"[OQOQO AGENT] Found {total} Slack messages matching '{query}'")

        return result

    except Exception as exc:
        logger.exception("Error fetching Slack activity")
        return {
            "error": True,
            "error_type": "SlackActivityError",
            "error_message": str(exc),
            "retry_possible": True,
        }


@tool
def get_combined_activity(
    query: str,
    git_limit: int = 5,
    slack_limit: int = 10,
    git_state: str = "all",
    branch: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get combined activity from both Git and Slack.

    This is a convenience tool that fetches activity from both sources
    and returns a unified view.

    Args:
        query: Search query for Slack (keywords related to the topic)
        git_limit: Max PRs to return (default 5)
        slack_limit: Max Slack messages to return (default 10)
        git_state: PR state filter ("open", "closed", "all")
        branch: Optional Git branch filter

    Returns:
        Dictionary with both Git and Slack activity
    """
    try:
        # Fetch Git activity
        git_result = get_git_activity(
            limit=git_limit,
            state=git_state,
            branch=branch
        )

        # Fetch Slack activity
        slack_result = get_slack_activity(
            query=query,
            limit=slack_limit
        )

        # Combine results
        combined = {
            "git_activity": {
                "count": git_result.get("count", 0),
                "source": git_result.get("source", "unknown"),
                "prs": git_result.get("prs", []),
                "error": git_result.get("error", False),
            },
            "slack_activity": {
                "total": slack_result.get("total", 0),
                "matches": slack_result.get("matches", []),
                "error": slack_result.get("error", False),
            },
            "query": query,
        }

        logger.info(
            f"[OQOQO AGENT] Combined activity: "
            f"{combined['git_activity']['count']} PRs, "
            f"{combined['slack_activity']['total']} Slack messages"
        )

        return combined

    except Exception as exc:
        logger.exception("Error fetching combined activity")
        return {
            "error": True,
            "error_type": "CombinedActivityError",
            "error_message": str(exc),
            "retry_possible": True,
        }


@tool
def query_with_reasoning(
    query: str,
    sources: Optional[str] = None,
    git_limit: int = 10,
    slack_limit: int = 20
) -> Dict[str, Any]:
    """
    Query activity across multiple sources with intelligent reasoning.

    This is the enhanced version that:
    - Infers relevant sources from your question
    - Gathers evidence from Git, Slack, docs, issues
    - Detects conflicts between sources
    - Identifies information gaps
    - Generates comprehensive summary with source attribution

    Use this for questions like:
    - "What changed in the auth feature?"
    - "Did we discuss the performance issue?"
    - "What's the status of the calendar refactor?"

    Args:
        query: Your question or search query
        sources: Optional comma-separated list of sources ("git,slack,docs,issues")
                If not provided, sources will be inferred from the query.
        git_limit: Max PRs to retrieve (default 10)
        slack_limit: Max Slack messages to retrieve (default 20)

    Returns:
        Dictionary with evidence, conflicts, gaps, and summary
    """
    try:
        from ..utils import load_config

        config = load_config()

        # Parse sources if provided
        source_list = None
        if sources:
            source_list = [s.strip() for s in sources.split(",")]

        # Initialize reasoner
        reasoner = MultiSourceReasoner(config)

        # Execute multi-source query
        result = reasoner.query(
            query=query,
            sources=source_list,
            git_limit=git_limit,
            slack_limit=slack_limit,
        )

        logger.info(
            f"[OQOQO AGENT] Reasoning complete: "
            f"{result['evidence_count']} evidence, "
            f"{len(result.get('conflicts', []))} conflicts, "
            f"{len(result.get('gaps', []))} gaps"
        )

        return result

    except Exception as exc:
        logger.exception("Error in query_with_reasoning")
        return {
            "error": True,
            "error_type": "ReasoningError",
            "error_message": str(exc),
            "retry_possible": True,
        }


OQOQO_AGENT_TOOLS = [
    get_git_activity,
    get_slack_activity,
    get_combined_activity,
    query_with_reasoning,  # Enhanced multi-source reasoning
]

OQOQO_AGENT_HIERARCHY = """
Oqoqo Agent Hierarchy:
=====================

LEVEL 1: Simple Activity Query (Legacy)
└─ get_git_activity(limit=10, state="all", branch=None)
   → Get recent GitHub PR activity

└─ get_slack_activity(query, channel=None, limit=20)
   → Search Slack messages and discussions

└─ get_combined_activity(query, git_limit=5, slack_limit=10, git_state="all", branch=None)
   → Get unified view of Git + Slack activity

LEVEL 2: Multi-Source Reasoning (Recommended)
└─ query_with_reasoning(query, sources=None, git_limit=10, slack_limit=20)
   → Enhanced multi-source query with:
     • Automatic source inference from query
     • Evidence normalization across sources
     • Conflict detection between sources
     • Gap detection (missing information)
     • Comprehensive summary with source attribution

PURPOSE: Query recent activity across code and communication channels
RECOMMENDED USE CASES (use query_with_reasoning):
- "What changed in the auth feature?"
- "Did we discuss the performance issue?"
- "What's the status of the calendar refactor?"
- "Recent work on the payments API"

LEGACY USE CASES (use simple tools):
- "List the last 10 PRs"
- "Search Slack for 'bug'"
"""


class OqoqoAgent:
    """
    Orchestrates activity queries across Git and Slack.

    This agent provides a unified interface to query recent work activity,
    combining code changes (GitHub PRs) with team discussions (Slack messages).
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in OQOQO_AGENT_TOOLS}
        logger.info(f"[OQOQO AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get list of available tools."""
        return OQOQO_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get agent hierarchy documentation."""
        return OQOQO_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool.

        Args:
            tool_name: Name of tool to execute
            inputs: Tool input parameters

        Returns:
            Tool execution result
        """
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Oqoqo agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys()),
            }

        tool = self.tools[tool_name]
        try:
            result = tool.invoke(inputs)
            logger.info(f"[OQOQO AGENT] Executed {tool_name}")
            return result
        except Exception as exc:
            logger.exception(f"Oqoqo agent execution error: {tool_name}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(exc),
                "retry_possible": False,
            }
