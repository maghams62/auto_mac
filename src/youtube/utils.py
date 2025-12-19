from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable, Optional, Tuple
from urllib.parse import parse_qs, urlparse

if False:  # pragma: no cover
    from .models import VideoContext

_YOUTUBE_HOST_KEYWORDS = ("youtube.com", "youtu.be")
_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CLEAN_ALIAS_PATTERN = re.compile(r"[^a-z0-9]+")
_TS_COMPONENT_PATTERN = re.compile(
    r"^(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)(?:s)?)?$",
    flags=re.IGNORECASE,
)


def is_youtube_url(value: str) -> bool:
    if not value:
        return False
    parsed = urlparse(value.strip())
    netloc = parsed.netloc.lower()
    return any(keyword in netloc for keyword in _YOUTUBE_HOST_KEYWORDS)


def extract_video_id(value: str) -> Optional[str]:
    """
    Extract a YouTube video ID from a URL or bare ID.
    """
    if not value:
        return None

    cleaned = value.strip()
    if _VIDEO_ID_PATTERN.match(cleaned):
        return cleaned

    parsed = urlparse(cleaned)
    if not parsed.scheme:
        return None

    host = parsed.netloc.lower()
    path = parsed.path.strip("/")

    if "youtu.be" in host and path:
        return path.split("/")[0]

    if "youtube.com" in host:
        if path == "watch" or not path:
            query = parse_qs(parsed.query)
            candidates = query.get("v")
            if candidates:
                candidate = candidates[0]
                if _VIDEO_ID_PATTERN.match(candidate):
                    return candidate
        else:
            parts = path.split("/")
            if parts and parts[0] in {"shorts", "live", "embed"} and len(parts) > 1:
                candidate = parts[1]
                if _VIDEO_ID_PATTERN.match(candidate):
                    return candidate

    return None


def slugify_text(value: str) -> str:
    value = value.lower().strip()
    value = _CLEAN_ALIAS_PATTERN.sub("-", value)
    value = value.strip("-")
    return value or "video"


def build_video_alias(title: Optional[str], video_id: str, channel_title: Optional[str] = None) -> str:
    base = title or channel_title or video_id
    slug = slugify_text(base)
    return slug[:40] or video_id[:8]


def match_video_context(
    selector: str,
    contexts: Iterable["VideoContext"],
) -> Tuple[Optional["VideoContext"], Optional[float]]:
    """
    Attempt to find the best matching VideoContext given a selector.

    Returns (context, score).
    """

    normalized = (selector or "").strip()
    if not normalized:
        return None, None

    target_alias = normalized[1:].lower() if normalized.startswith("@") else normalized.lower()
    best_ctx = None
    best_score = 0.0

    for ctx in contexts:
        alias = ctx.alias.lower()
        title = (ctx.title or "").lower()
        channel = (ctx.channel_title or "").lower()

        if normalized.startswith("@") and alias == target_alias:
            return ctx, 1.0

        if normalized == ctx.video_id:
            return ctx, 1.0

        score = max(
            SequenceMatcher(None, target_alias, alias).ratio(),
            SequenceMatcher(None, normalized, title).ratio() if title else 0.0,
            SequenceMatcher(None, normalized, channel).ratio() if channel else 0.0,
        )
        if score > best_score:
            best_ctx = ctx
            best_score = score

    return best_ctx, best_score if best_ctx else None


def extract_playlist_id(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    parsed = urlparse(value.strip())
    query = parse_qs(parsed.query)
    candidate = (query.get("list") or [None])[0]
    return candidate


def extract_timestamp_seconds(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    parsed = urlparse(value.strip())
    query = parse_qs(parsed.query)
    token = (query.get("t") or query.get("start") or query.get("time_continue") or [None])[0]
    if not token and parsed.fragment.startswith("t="):
        token = parsed.fragment[2:]
    if not token:
        return None
    token = token.strip()
    if token.isdigit():
        return int(token)
    match = _TS_COMPONENT_PATTERN.match(token)
    if not match:
        return None
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    total = hours * 3600 + minutes * 60 + seconds
    return total or None


def normalize_video_url(
    video_id: str,
    *,
    playlist_id: Optional[str] = None,
    timestamp: Optional[int] = None,
) -> str:
    params = [f"v={video_id}"]
    if playlist_id:
        params.append(f"list={playlist_id}")
    if timestamp and timestamp > 0:
        params.append(f"t={int(timestamp)}")
    query = "&".join(params)
    return f"https://www.youtube.com/watch?{query}"


def canonical_channel_identifier(channel_id: Optional[str], channel_title: Optional[str]) -> Optional[str]:
    if channel_id:
        return channel_id
    if channel_title:
        return f"channel:{slugify_text(channel_title)}"
    return None


def canonical_playlist_identifier(playlist_id: Optional[str], channel_title: Optional[str]) -> Optional[str]:
    if playlist_id:
        return playlist_id
    if channel_title:
        return f"playlist:{slugify_text(channel_title)}"
    return None

