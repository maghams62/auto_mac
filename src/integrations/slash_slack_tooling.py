from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .slack_client import SlackAPIClient, SlackAPIError
from ..services.slack_metadata import SlackMetadataService
from ..utils.slack import normalize_channel_name
from ..utils.slack_links import build_slack_deep_link, build_slack_permalink

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
    deep_link: Optional[str] = None


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
        team_id: Optional[str] = None,
        metadata_service: Optional[SlackMetadataService] = None,
    ):
        self.config = config or {}
        self.client = client or SlackAPIClient()
        self.metadata_service = metadata_service or SlackMetadataService(config=self.config, client=self.client)
        self._user_cache: Dict[str, str] = {}
        self._channel_cache: Dict[str, Dict[str, Any]] = {}
        self.workspace_url = workspace_url or self._derive_workspace_url()
        self.team_id = team_id or self._derive_team_id()

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
        warnings = response.get("warnings", [])

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
            "warnings": warnings,
        }

    def resolve_channel_id(self, channel_name: Optional[str]) -> Optional[str]:
        normalized = self._normalize_channel_name(channel_name)
        if not normalized:
            if channel_name and channel_name.startswith("C"):
                return channel_name
            return None
        if self.metadata_service:
            channel = self.metadata_service.get_channel(normalized)
            if channel:
                return channel.id
        for channel_id, data in self._channel_cache.items():
            if self._normalize_channel_name(data.get("name")) == normalized:
                return channel_id
        try:
            listing = self.client.list_channels(limit=1000)
            for channel in listing.get("channels", []):
                channel_id = channel.get("id")
                self._channel_cache[channel_id] = channel
                if self._normalize_channel_name(channel.get("name")) == normalized:
                    return channel_id
        except SlackAPIError as exc:
            logger.warning("Unable to resolve channel %s: %s", normalized, exc)
        if self.metadata_service:
            refreshed = self.metadata_service.refresh_channels(force=True)
            for channel in refreshed:
                if self._normalize_channel_name(channel.name) == normalized:
                    return channel.id
        return None

    def suggest_channels(self, prefix: str, limit: int = 5) -> List[str]:
        if not prefix:
            prefix = ""
        if self.metadata_service:
            return [channel.name for channel in self.metadata_service.suggest_channels(prefix, limit)]
        return []

    def consume_warnings(self) -> List[str]:
        client = getattr(self, "client", None)
        if client and hasattr(client, "consume_warnings"):
            return client.consume_warnings()
        return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _derive_workspace_url(self) -> Optional[str]:
        def normalize_url(value: Optional[str]) -> Optional[str]:
            if not value:
                return None
            trimmed = value.strip()
            if not trimmed:
                return None
            if not (trimmed.startswith("http://") or trimmed.startswith("https://")):
                trimmed = f"https://{trimmed.lstrip('/')}"
            return trimmed.rstrip("/")

        env_url = normalize_url(os.getenv("SLACK_WORKSPACE_URL") or os.getenv("SLACK_WORKSPACE"))
        if env_url:
            return env_url

        slash_cfg = self.config.get("slash_slack", {}) if self.config else {}
        slash_url = normalize_url(slash_cfg.get("workspace_url"))
        if slash_url:
            return slash_url

        activity_cfg = self.config.get("activity_ingest", {}).get("slack", {}) if self.config else {}
        return normalize_url(activity_cfg.get("workspace_url"))

    def _derive_team_id(self) -> Optional[str]:
        env_team = os.getenv("SLACK_TEAM_ID") or os.getenv("SLACK_WORKSPACE_ID")
        if env_team:
            return env_team.strip()
        slack_cfg = (self.config or {}).get("slack") or {}
        slash_cfg = (self.config or {}).get("slash_slack") or {}
        return (
            slash_cfg.get("workspace_id")
            or slash_cfg.get("team_id")
            or slack_cfg.get("workspace_id")
            or slack_cfg.get("team_id")
        )

    def _get_channel(self, channel_id: str) -> Dict[str, Any]:
        if channel_id in self._channel_cache:
            return self._channel_cache[channel_id]
        if self.metadata_service:
            channel = self.metadata_service.get_channel(channel_id)
            if channel:
                info = {
                    "id": channel.id,
                    "name": channel.name,
                    "is_private": channel.is_private,
                    "is_archived": channel.is_archived,
                    "num_members": channel.num_members,
                }
                self._channel_cache[channel_id] = info
                return info
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
        if self.metadata_service:
            user = self.metadata_service.get_user(user_id)
            if user:
                display = user.real_name or user.display_name or user.name or user_id
                self._user_cache[user_id] = display
                return display
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
        deep_link = build_slack_deep_link(
            channel_id,
            ts,
            team_id=self.team_id,
        )
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
            deep_link=deep_link,
        )

    @staticmethod
    def _message_to_dict(message: NormalizedSlackMessage) -> Dict[str, Any]:
        return asdict(message)

    def _build_permalink(self, channel_id: str, ts: str) -> str:
        permalink = build_slack_permalink(
            channel_id,
            ts,
            workspace_url=self.workspace_url,
            team_id=self.team_id,
        )
        return permalink or ""

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

    @staticmethod
    def _normalize_channel_name(name: Optional[str]) -> Optional[str]:
        return normalize_channel_name(name)


