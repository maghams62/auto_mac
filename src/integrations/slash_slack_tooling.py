from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .slack_client import SlackAPIClient, SlackAPIError

logger = logging.getLogger(__name__)


@dataclass
class NormalizedSlackMessage:
    id: str
    channel_id: str
    channel_name: str
    text: str
    ts: str
    iso_time: str
    user_id: Optional[str]
    user_name: Optional[str]
    thread_ts: Optional[str]
    reply_count: int
    permalink: str
    mentions: List[Dict[str, str]]
    references: List[Dict[str, str]]
    reactions: List[Dict[str, Any]]
    files: List[Dict[str, Any]]


class SlashSlackToolingAdapter:
    """
    High-level, read-only helper around SlackAPIClient for slash-slack workflows.

    Responsibilities:
        * Normalize channel/thread/search responses into consistent structures.
        * Resolve user and channel metadata with caching.
        * Provide best-effort permalinks/mentions/references for graph awareness.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[SlackAPIClient] = None,
        workspace_url: Optional[str] = None,
    ):
        self.config = config or {}
        self.client = client or SlackAPIClient()
        self._user_cache: Dict[str, str] = {}
        self._channel_cache: Dict[str, Dict[str, Any]] = {}
        self.workspace_url = workspace_url or self._derive_workspace_url()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_channel_messages(
        self,
        channel_id: str,
        limit: int = 200,
        oldest: Optional[str] = None,
        latest: Optional[str] = None,
    ) -> Dict[str, Any]:
        response = self.client.fetch_messages(channel_id, limit=limit, oldest=oldest, latest=latest)
        channel_info = self._get_channel(channel_id)

        normalized = [
            self._message_to_dict(self._normalize_message(msg, channel_id, channel_info.get("name", channel_id)))
            for msg in response.get("messages", [])
        ]

        return {
            "channel_id": channel_id,
            "channel_name": channel_info.get("name", channel_id),
            "messages": normalized,
            "has_more": response.get("has_more", False),
        }

    def fetch_thread(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 200,
    ) -> Dict[str, Any]:
        response = self.client.fetch_thread(channel_id, thread_ts, limit=limit)
        channel_info = self._get_channel(channel_id)
        normalized = [
            self._message_to_dict(self._normalize_message(msg, channel_id, channel_info.get("name", channel_id)))
            for msg in response.get("messages", [])
        ]
        return {
            "channel_id": channel_id,
            "channel_name": channel_info.get("name", channel_id),
            "messages": normalized,
        }

    def search_messages(
        self,
        query: str,
        channel: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        response = self.client.search_messages(query, channel=channel, limit=limit)
        matches = response.get("matches", [])

        normalized: List[Dict[str, Any]] = []
        for match in matches:
            channel_id = match.get("channel", {}).get("id") or match.get("channel", {}).get("name") or channel
            channel_name = match.get("channel", {}).get("name") or channel_id or ""
            if channel_id:
                channel_info = self._get_channel(channel_id)
                channel_name = channel_info.get("name", channel_name or channel_id)
            normalized.append(
                self._message_to_dict(
                    self._normalize_message(
                        {
                            "text": match.get("text", ""),
                            "user": match.get("user"),
                            "username": match.get("username"),
                            "ts": match.get("timestamp") or match.get("ts"),
                            "permalink": match.get("permalink", ""),
                        },
                        channel_id or "unknown",
                        channel_name or (channel_id or "unknown"),
                    )
                )
            )

        return {
            "query": query,
            "channel": channel,
            "messages": normalized,
            "total": response.get("total", len(normalized)),
        }

    def resolve_channel_id(self, channel_name: Optional[str]) -> Optional[str]:
        if not channel_name:
            return None
        normalized = channel_name.lstrip("#")
        for channel_id, data in self._channel_cache.items():
            if data.get("name") == normalized:
                return channel_id
        try:
            listing = self.client.list_channels(limit=1000)
            for channel in listing.get("channels", []):
                self._channel_cache[channel.get("id")] = channel
                if channel.get("name") == normalized:
                    return channel.get("id")
        except SlackAPIError as exc:
            logger.warning("Unable to resolve channel %s: %s", normalized, exc)
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _derive_workspace_url(self) -> Optional[str]:
        env_url = os.getenv("SLACK_WORKSPACE_URL")
        if env_url:
            return env_url.rstrip("/")
        activity_cfg = self.config.get("activity_ingest", {}).get("slack", {}) if self.config else {}
        return activity_cfg.get("workspace_url", "").rstrip("/") or None

    def _get_channel(self, channel_id: str) -> Dict[str, Any]:
        if channel_id in self._channel_cache:
            return self._channel_cache[channel_id]
        try:
            info = self.client.get_channel_info(channel_id).get("channel", {})  # type: ignore[assignment]
            self._channel_cache[channel_id] = info
            return info
        except SlackAPIError as exc:
            logger.warning("Unable to fetch channel info for %s: %s", channel_id, exc)
            return {"id": channel_id, "name": channel_id}

    def _get_user_display(self, user_id: Optional[str]) -> Optional[str]:
        if not user_id:
            return None
        if user_id in self._user_cache:
            return self._user_cache[user_id]
        try:
            info = self.client.get_user_info(user_id)
            display = info.get("user", {}).get("real_name") or info.get("user", {}).get("name") or user_id
            self._user_cache[user_id] = display
            return display
        except SlackAPIError as exc:
            logger.debug("Unable to fetch user info for %s: %s", user_id, exc)
            self._user_cache[user_id] = user_id
            return user_id

    def _normalize_message(
        self,
        msg: Dict[str, Any],
        channel_id: str,
        channel_name: str,
    ) -> NormalizedSlackMessage:
        ts = msg.get("ts") or msg.get("timestamp")
        if not ts:
            ts = f"{datetime.now(tz=timezone.utc).timestamp():.6f}"
        permalink = msg.get("permalink") or self._build_permalink(channel_id, ts)
        user_id = msg.get("user")
        user_name = msg.get("username") or self._get_user_display(user_id)

        mentions = self._extract_mentions(msg.get("text", ""))
        references = self._extract_references(msg.get("text", ""))
        iso_time = self._ts_to_iso(ts)

        return NormalizedSlackMessage(
            id=self._stable_id(channel_id, ts),
            channel_id=channel_id,
            channel_name=channel_name,
            text=msg.get("text", ""),
            ts=ts,
            iso_time=iso_time,
            user_id=user_id,
            user_name=user_name,
            thread_ts=msg.get("thread_ts"),
            reply_count=msg.get("reply_count", 0),
            permalink=permalink,
            mentions=mentions,
            references=references,
            reactions=msg.get("reactions", []),
            files=msg.get("files", []),
        )

    @staticmethod
    def _message_to_dict(message: NormalizedSlackMessage) -> Dict[str, Any]:
        return asdict(message)

    def _build_permalink(self, channel_id: str, ts: str) -> str:
        suffix = f"/archives/{channel_id}/p{ts.replace('.', '')}"
        if self.workspace_url:
            return f"{self.workspace_url}{suffix}"
        return f"https://slack.com{suffix}"

    @staticmethod
    def _stable_id(*parts: Optional[str]) -> str:
        data = "|".join([p for p in parts if p])
        if not data:
            data = "slack"
        return hashlib.sha1(data.encode("utf-8")).hexdigest()[:20]

    @staticmethod
    def _ts_to_iso(ts: str) -> str:
        try:
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            return dt.isoformat()
        except (ValueError, OSError):
            return ts

    def _extract_mentions(self, text: str) -> List[Dict[str, str]]:
        mentions: List[Dict[str, str]] = []
        for match in re.finditer(r"<@([A-Z0-9]+)>", text):
            user_id = match.group(1)
            mentions.append({
                "user_id": user_id,
                "display": self._get_user_display(user_id) or user_id,
            })
        return mentions

    @staticmethod
    def _extract_references(text: str) -> List[Dict[str, str]]:
        references: List[Dict[str, str]] = []
        for match in re.findall(r'(https?://[^\s>]+)', text):
            kind = "link"
            lower = match.lower()
            if "figma.com" in lower:
                kind = "figma"
            elif "github.com" in lower:
                kind = "github"
            elif "notion.so" in lower or "notion.site" in lower:
                kind = "notion"
            elif lower.endswith(".pdf"):
                kind = "document"
            references.append({"kind": kind, "url": match})
        return references


