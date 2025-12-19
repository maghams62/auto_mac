"""
Slack API client utilities.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class SlackAPIError(RuntimeError):
    """Raised when Slack API responses are unsuccessful."""


class SlackAPIClient:
    """
    Lightweight wrapper around the Slack Web API.

    Handles authentication and provides helpers for common channel/message
    operations needed by the Slack agent tools.
    """

    BASE_URL = "https://slack.com/api"

    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = (
            bot_token
            or os.getenv("SLACK_TOKEN")
            or os.getenv("SLACK_BOT_TOKEN")
        )
        self.user_token = os.getenv("SLACK_USER_TOKEN")
        self.default_channel_id = os.getenv("SLACK_CHANNEL_ID")

        if not self.bot_token:
            config = self._load_config_fallback()
            slack_cfg = config.get("slack", {}) if config else {}
            self.bot_token = slack_cfg.get("bot_token")
            self.default_channel_id = self.default_channel_id or slack_cfg.get("default_channel_id")

        if not self.bot_token:
            raise SlackAPIError(
                "Slack credentials not configured. Set SLACK_TOKEN (or legacy "
                "SLACK_BOT_TOKEN) in your environment or slack.bot_token in config.yaml."
            )

        self.session = self._build_session(self.bot_token)
        self.user_session = self._build_session(self.user_token) if self.user_token else self.session
        self._warning_log: List[str] = []

    @staticmethod
    def _build_session(token: Optional[str]) -> requests.Session:
        session = requests.Session()
        if token:
            session.headers.update({
                "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "MacAutomationAssistant/SlackIntegration",
        })
        return session

    @staticmethod
    def _load_config_fallback() -> Optional[Dict[str, Any]]:
        """
        Attempt to read config via ConfigManager or raw loader so we can
        pick up slack.bot_token/default_channel_id if env vars are missing.
        """
        try:
            from ..config_manager import get_global_config_manager
            return get_global_config_manager().get_config()
        except Exception:
            try:
                from ..utils import load_config
                return load_config()
            except Exception:
                logger.warning("SlackAPIClient could not load config fallback", exc_info=True)
                return None

    # ------------------------------------------------------------------
    # Public API helpers
    # ------------------------------------------------------------------
    def fetch_messages(
        self,
        channel: str,
        limit: int = 100,
        oldest: Optional[str] = None,
        latest: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch messages from a Slack channel.

        Args:
            channel: Channel ID (e.g., "C0123456789")
            limit: Maximum number of messages to return (1-1000)
            oldest: Return messages after this timestamp (exclusive)
            latest: Return messages before this timestamp (inclusive)

        Returns:
            Dictionary containing messages and channel info
        """
        params = {
            "channel": channel,
            "limit": max(1, min(limit, 1000)),
        }
        if oldest:
            params["oldest"] = oldest
        if latest:
            params["latest"] = latest

        response = self._get("conversations.history", params=params)
        data = response.json()
        self._raise_for_error(data, "fetch_messages")
        return data

    def fetch_thread(
        self,
        channel: str,
        thread_ts: str,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """
        Fetch a Slack thread (parent message + replies).

        Args:
            channel: Channel ID housing the thread.
            thread_ts: Timestamp of root message.
            limit: Maximum replies to return.
        """
        params = {
            "channel": channel,
            "ts": thread_ts,
            "limit": max(1, min(limit, 1000)),
        }
        response = self._get("conversations.replies", params=params)
        data = response.json()
        self._raise_for_error(data, "fetch_thread")
        return data

    def get_channel_info(self, channel: str) -> Dict[str, Any]:
        """
        Get information about a Slack channel.

        Args:
            channel: Channel ID (e.g., "C0123456789")

        Returns:
            Dictionary containing channel information
        """
        params = {"channel": channel}
        response = self._get("conversations.info", params=params)
        data = response.json()
        self._raise_for_error(data, "get_channel_info")
        return data

    def list_channels(
        self,
        limit: int = 100,
        exclude_archived: bool = True,
        types: str = "public_channel,private_channel",
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List channels in the workspace.

        Args:
            limit: Maximum number of channels to return
            exclude_archived: Exclude archived channels
            types: Comma-separated channel types to include

        Returns:
            Dictionary containing list of channels
        """
        params = {
            "limit": max(1, min(limit, 1000)),
            "exclude_archived": exclude_archived,
            "types": types,
        }
        if cursor:
            params["cursor"] = cursor
        response = self._get("conversations.list", params=params)
        data = response.json()
        self._raise_for_error(data, "list_channels")
        return data

    def list_users(
        self,
        limit: int = 200,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List users in the workspace for autocomplete use cases.

        Args:
            limit: Maximum number of users to return
            cursor: Pagination cursor from previous response
        """
        params = {
            "limit": max(1, min(limit, 200)),
        }
        if cursor:
            params["cursor"] = cursor
        response = self._get("users.list", params=params)
        data = response.json()
        self._raise_for_error(data, "list_users")
        return data

    def get_user_info(self, user: str) -> Dict[str, Any]:
        """
        Get information about a Slack user.

        Args:
            user: User ID (e.g., "U0123456789")

        Returns:
            Dictionary containing user information
        """
        params = {"user": user}
        response = self._get("users.info", params=params)
        data = response.json()
        self._raise_for_error(data, "get_user_info")
        return data

    def auth_test(self, *, use_user_token: bool = False) -> Dict[str, Any]:
        """
        Retrieve identity details (team/workspace, user) for the current token.

        Args:
            use_user_token: When True and a user token is configured, issue the request
                as the user token instead of the bot token.
        """
        session = self.user_session if (use_user_token and self.user_session is not None) else self.session
        response = self._post("auth.test", session=session)
        data = response.json()
        self._raise_for_error(data, "auth_test")
        return data

    def search_messages(
        self,
        query: str,
        channel: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Search for messages using Slack's search.messages API.

        Args:
            query: Search query (supports Slack search syntax)
            channel: Optional channel ID to restrict search
            limit: Max results to return (default 20, max 100)

        Returns:
            Dictionary containing search results:
            {
                "matches": [
                    {
                        "text": str,
                        "user": str,
                        "username": str,
                        "channel": {"id": str, "name": str},
                        "timestamp": str,
                        "permalink": str,
                    }
                ],
                "total": int,
            }
        """
        # Build search query
        search_query = query
        if channel:
            # Add channel filter to query
            search_query = f"{query} in:{channel}"

        params = {
            "query": search_query,
            "count": max(1, min(limit, 100)),
            "sort": "timestamp",
            "sort_dir": "desc",
        }

        try:
            response = self._get("search.messages", params=params, session=self.user_session)
            data = response.json()
            self._raise_for_error(data, "search_messages")

            # Normalize results
            messages = data.get("messages", {})
            matches = []

            for match in messages.get("matches", []):
                # Extract channel info
                channel_info = match.get("channel", {})
                if isinstance(channel_info, dict):
                    channel_data = {"id": channel_info.get("id", ""), "name": channel_info.get("name", "")}
                else:
                    # Sometimes channel is just an ID string
                    channel_data = {"id": str(channel_info), "name": ""}

                # Get username if available
                username = match.get("username", "")
                if not username and "user" in match:
                    # Try to fetch user info for username
                    try:
                        user_info = self.get_user_info(match["user"])
                        username = user_info.get("user", {}).get("name", "")
                    except Exception:
                        username = match.get("user", "")

                normalized_match = {
                    "text": match.get("text", ""),
                    "user": match.get("user", ""),
                    "username": username,
                    "channel": channel_data,
                    "timestamp": match.get("ts", ""),
                    "permalink": match.get("permalink", ""),
                }
                matches.append(normalized_match)

            return {
                "matches": matches,
                "total": messages.get("total", 0),
            }

        except SlackAPIError as e:
            # If search.messages fails (permission issue), try fallback
            logger.warning(f"search.messages failed: {e}, attempting fallback to conversations.history")
            fallback = self._search_fallback(query, channel, limit)
            warnings = fallback.setdefault("warnings", [])
            warnings.append(f"search.messages error: {e}")
            self._warning_log.append(f"search.messages error: {e}")
            return fallback

    def _search_fallback(
        self,
        query: str,
        channel: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Fallback search implementation using conversations.history + in-code filtering.

        Used when search.messages API is unavailable or fails (permission issues).

        Args:
            query: Search query (simple text match)
            channel: Channel ID to search in
            limit: Max results to return

        Returns:
            Dictionary with same format as search_messages
        """
        if not channel:
            logger.error("Fallback search requires a channel ID")
            warning = "fallback search missing channel"
            self._warning_log.append(warning)
            return {"matches": [], "total": 0, "warnings": [warning]}

        # Fetch recent messages from the channel
        try:
            history = self.fetch_messages(channel, limit=200)  # Fetch more to filter
            messages = history.get("messages", [])

            # Simple keyword matching (case-insensitive)
            query_lower = query.lower()
            matches = []

            for msg in messages:
                text = msg.get("text", "")
                if query_lower in text.lower():
                    # Normalize to match search.messages format
                    matches.append({
                        "text": text,
                        "user": msg.get("user", ""),
                        "username": "",  # Not available in conversations.history
                        "channel": {"id": channel, "name": ""},
                        "timestamp": msg.get("ts", ""),
                        "permalink": "",  # Not available without additional API call
                    })

                    if len(matches) >= limit:
                        break

            return {
                "matches": matches,
                "total": len(matches),
                "warnings": [],
            }

        except Exception as e:
            warning = f"fallback search failed: {e}"
            logger.error(warning)
            self._warning_log.append(warning)
            return {"matches": [], "total": 0, "warnings": [warning]}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, *, session: Optional[requests.Session] = None) -> requests.Response:
        """Make a GET request to the Slack API."""
        url = f"{self.BASE_URL}/{endpoint}"
        session = session or self.session
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response

    def _post(self, endpoint: str, json: Optional[Dict[str, Any]] = None, *, session: Optional[requests.Session] = None) -> requests.Response:
        """Make a POST request to the Slack API."""
        url = f"{self.BASE_URL}/{endpoint}"
        session = session or self.session
        response = session.post(url, json=json, timeout=30)
        response.raise_for_status()
        return response

    @staticmethod
    def _raise_for_error(data: Dict[str, Any], action: str) -> None:
        """
        Raise SlackAPIError if the response indicates an error.

        Slack API returns ok: false when there's an error.
        """
        if not data.get("ok", False):
            error_msg = data.get("error", "unknown_error")
            logger.error("Slack API error during %s: %s", action, error_msg)
            raise SlackAPIError(f"Slack API error during {action}: {error_msg}")

    def consume_warnings(self) -> List[str]:
        warnings = self._warning_log[:]
        self._warning_log.clear()
        return warnings
