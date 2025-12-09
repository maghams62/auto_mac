"""
Slack metadata provider with lightweight TTL caching for autocomplete flows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..integrations.slack_client import SlackAPIClient, SlackAPIError
from ..utils.slack import normalize_channel_name
from .ttl_cache import TTLCache, CacheStats

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SlackChannel:
    id: str
    name: str
    is_private: bool
    is_archived: bool
    num_members: Optional[int] = None


@dataclass(frozen=True)
class SlackUser:
    id: str
    name: str
    real_name: Optional[str]
    display_name: Optional[str]


class SlackMetadataService:
    """
    Fetch Slack channel/user metadata from the Web API and cache the results.
    """

    CHANNEL_CACHE_KEY = "channels"
    USER_CACHE_KEY = "users"

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        client: Optional[SlackAPIClient] = None,
    ):
        self.config = config or {}
        metadata_cfg = (self.config.get("metadata_cache") or {}).get("slack") or {}
        ttl_seconds = int(metadata_cfg.get("ttl_seconds", 600))
        self.max_items = int(metadata_cfg.get("max_items", 2000))
        self.log_metrics = bool(metadata_cfg.get("log_metrics", False))
        self._client = client
        self.default_channel_id = (self.config.get("slash_slack") or {}).get(
            "default_channel_id"
        ) or (self.config.get("slack") or {}).get("default_channel_id")
        self.channel_cache = TTLCache(ttl_seconds, label="slack_channels")
        self.user_cache = TTLCache(ttl_seconds, label="slack_users")

    # ------------------------------------------------------------------ #
    # Channel helpers
    # ------------------------------------------------------------------ #
    def get_channel(self, identifier: Optional[str]) -> Optional[SlackChannel]:
        if not identifier:
            return None
        payload = self._ensure_channels()
        normalized = normalize_channel_name(identifier)
        alias_key = normalized or identifier
        return payload["aliases"].get(alias_key) or payload["aliases"].get(identifier)

    def suggest_channels(self, prefix: str = "", limit: int = 10) -> List[SlackChannel]:
        payload = self._ensure_channels()
        channels: List[SlackChannel] = payload["items"]
        if not prefix:
            return channels[: limit or len(channels)]

        prefix_norm = normalize_channel_name(prefix) or prefix.lower()
        prefix_lower = prefix.lower()
        results: List[SlackChannel] = []
        seen: set[str] = set()
        for channel in channels:
            if len(results) >= limit:
                break
            if channel.id in seen:
                continue
            normalized = normalize_channel_name(channel.name) or ""
            if (
                channel.id.startswith(prefix)
                or channel.name.lower().startswith(prefix_lower)
                or (normalized and normalized.startswith(prefix_norm))
            ):
                results.append(channel)
                seen.add(channel.id)
        return results

    def refresh_channels(self, *, force: bool = False) -> List[SlackChannel]:
        if force:
            self.channel_cache.invalidate(self.CHANNEL_CACHE_KEY)
        payload = self._ensure_channels()
        return payload["items"]

    # ------------------------------------------------------------------ #
    # User helpers
    # ------------------------------------------------------------------ #
    def get_user(self, identifier: Optional[str]) -> Optional[SlackUser]:
        if not identifier:
            return None
        payload = self._ensure_users()
        normalized = identifier.lower()
        aliases = payload["aliases"]
        return aliases.get(identifier) or aliases.get(normalized)

    def suggest_users(self, prefix: str = "", limit: int = 10) -> List[SlackUser]:
        payload = self._ensure_users()
        users: List[SlackUser] = payload["items"]
        if not prefix:
            return users[: limit or len(users)]
        prefix_lower = prefix.lower()
        results: List[SlackUser] = []
        seen: set[str] = set()
        for user in users:
            if len(results) >= limit:
                break
            if user.id in seen:
                continue
            if any(
                value and value.lower().startswith(prefix_lower)
                for value in (user.name, user.real_name, user.display_name)
            ):
                results.append(user)
                seen.add(user.id)
        return results

    def refresh_users(self, *, force: bool = False) -> List[SlackUser]:
        if force:
            self.user_cache.invalidate(self.USER_CACHE_KEY)
        payload = self._ensure_users()
        return payload["items"]

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #
    def describe(self) -> Dict[str, Any]:
        return {
            "channels": self.channel_cache.describe().__dict__,
            "users": self.user_cache.describe().__dict__,
            "default_channel_id": self.default_channel_id,
        }

    def get_default_channel_id(self) -> Optional[str]:
        if self.default_channel_id:
            return self.default_channel_id
        payload = self._ensure_channels()
        if payload["items"]:
            return payload["items"][0].id
        return None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _ensure_channels(self) -> Dict[str, any]:
        payload = self.channel_cache.get(self.CHANNEL_CACHE_KEY)
        if payload:
            self._log_cache_stats("slack_channels", self.channel_cache.describe())
            return payload
        channels = self._fetch_channels_live()
        alias_map: Dict[str, SlackChannel] = {}
        for channel in channels:
            alias_map[channel.id] = channel
            normalized = normalize_channel_name(channel.name)
            if normalized:
                alias_map.setdefault(normalized, channel)
        payload = {"items": channels, "aliases": alias_map}
        self.channel_cache.set(self.CHANNEL_CACHE_KEY, payload)
        self._log_cache_stats("slack_channels", self.channel_cache.describe())
        return payload

    def _ensure_users(self) -> Dict[str, any]:
        payload = self.user_cache.get(self.USER_CACHE_KEY)
        if payload:
            self._log_cache_stats("slack_users", self.user_cache.describe())
            return payload
        users = self._fetch_users_live()
        alias_map: Dict[str, SlackUser] = {}
        for user in users:
            alias_map[user.id] = user
            if user.name:
                alias_map.setdefault(user.name.lower(), user)
            if user.real_name:
                alias_map.setdefault(user.real_name.lower(), user)
            if user.display_name:
                alias_map.setdefault(user.display_name.lower(), user)
        payload = {"items": users, "aliases": alias_map}
        self.user_cache.set(self.USER_CACHE_KEY, payload)
        self._log_cache_stats("slack_users", self.user_cache.describe())
        return payload

    def _fetch_channels_live(self) -> List[SlackChannel]:
        cursor: Optional[str] = None
        channels: List[SlackChannel] = []
        try:
            while True:
                response = self._client_ref().list_channels(limit=200, cursor=cursor)
                for raw in response.get("channels", []):
                    channel = SlackChannel(
                        id=raw.get("id"),
                        name=raw.get("name") or raw.get("id", ""),
                        is_private=raw.get("is_private", False),
                        is_archived=raw.get("is_archived", False),
                        num_members=raw.get("num_members"),
                    )
                    channels.append(channel)
                    if self.max_items and len(channels) >= self.max_items:
                        break
                if self.max_items and len(channels) >= self.max_items:
                    break
                cursor = (
                    (response.get("response_metadata") or {}).get("next_cursor") or None
                )
                if not cursor:
                    break
        except SlackAPIError as exc:
            logger.warning("Failed to refresh Slack channels: %s", exc)
        return channels

    def _fetch_users_live(self) -> List[SlackUser]:
        cursor: Optional[str] = None
        users: List[SlackUser] = []
        try:
            while True:
                response = self._client_ref().list_users(limit=200, cursor=cursor)
                for raw in response.get("members", []):
                    profile = raw.get("profile") or {}
                    users.append(
                        SlackUser(
                            id=raw.get("id"),
                            name=raw.get("name"),
                            real_name=profile.get("real_name") or raw.get("real_name"),
                            display_name=profile.get("display_name")
                            or raw.get("profile", {}).get("display_name"),
                        )
                    )
                    if self.max_items and len(users) >= self.max_items:
                        break
                if self.max_items and len(users) >= self.max_items:
                    break
                cursor = (
                    (response.get("response_metadata") or {}).get("next_cursor") or None
                )
                if not cursor:
                    break
        except SlackAPIError as exc:
            logger.warning("Failed to refresh Slack users: %s", exc)
        return users

    def _log_cache_stats(self, label: str, stats: CacheStats) -> None:
        if not self.log_metrics:
            return
        logger.info(
            "[METADATA] %s cache hits=%s misses=%s size=%s ttl=%ss",
            label,
            stats.hits,
            stats.misses,
            stats.size,
            stats.ttl_seconds,
        )

    def _client_ref(self) -> SlackAPIClient:
        if self._client is None:
            self._client = SlackAPIClient()
        return self._client


