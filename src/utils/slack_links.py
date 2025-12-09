from __future__ import annotations

from typing import Optional


def _normalize_channel_id(channel_id: Optional[str]) -> Optional[str]:
    if not channel_id:
        return None
    channel = str(channel_id).strip()
    if not channel:
        return None
    if channel.startswith("#"):
        channel = channel.lstrip("#")
    return channel or None


def _normalize_timestamp(ts: Optional[str]) -> Optional[str]:
    if ts is None:
        return None
    ts_str = str(ts).strip()
    if not ts_str:
        return None
    return ts_str.replace(".", "")


def build_slack_permalink(
    channel_id: Optional[str],
    ts: Optional[str],
    *,
    workspace_url: Optional[str] = None,
    team_id: Optional[str] = None,
) -> Optional[str]:
    """
    Build a web-friendly Slack permalink.
    """
    channel = _normalize_channel_id(channel_id)
    if not channel:
        return None
    ts_compact = _normalize_timestamp(ts)
    if workspace_url:
        base = workspace_url.rstrip("/")
        if ts_compact:
            return f"{base}/archives/{channel}/p{ts_compact}"
        return f"{base}/archives/{channel}"
    team = str(team_id).strip() if team_id else ""
    if team:
        query = f"channel={channel}&team={team}"
        if ts_compact:
            query += f"&message={ts_compact}"
        return f"https://slack.com/app_redirect?{query}"
    return None


def build_slack_deep_link(
    channel_id: Optional[str],
    ts: Optional[str],
    *,
    team_id: Optional[str] = None,
) -> Optional[str]:
    """
    Build a slack:// deep link that prefers opening the native Slack client.
    """
    channel = _normalize_channel_id(channel_id)
    team = str(team_id).strip() if team_id else ""
    if not channel or not team:
        return None
    base = f"slack://channel?team={team}&id={channel}"
    ts_str = _normalize_timestamp(ts)
    if ts_str:
        return f"{base}&message={ts_str}"
    return base

