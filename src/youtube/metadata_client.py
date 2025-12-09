from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from .utils import extract_playlist_id, extract_timestamp_seconds, normalize_video_url

logger = logging.getLogger(__name__)


def _parse_iso8601_duration(duration: str) -> Optional[int]:
    if not duration:
        return None

    hours = minutes = seconds = 0
    number = ""
    duration = duration.upper()

    for char in duration:
        if char.isdigit():
            number += char
            continue

        if char == "H" and number:
            hours = int(number)
            number = ""
        elif char == "M" and number:
            minutes = int(number)
            number = ""
        elif char == "S" and number:
            seconds = int(number)
            number = ""

    total = hours * 3600 + minutes * 60 + seconds
    return total or None


class YouTubeMetadataClient:
    """Fetch YouTube metadata via Data API or oEmbed fallback."""

    OEMBED_URL = "https://www.youtube.com/oembed"
    DATA_API_URL = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, config: Dict[str, Any]):
        youtube_cfg = (config.get("youtube") or {}).get("metadata") or {}
        self.api_key = youtube_cfg.get("api_key") or None
        self.timeout = float(youtube_cfg.get("oembed_timeout_seconds", 4.0))
        self._client = httpx.Client(timeout=self.timeout)

    def fetch_metadata(self, video_id: str, url: Optional[str]) -> Dict[str, Any]:
        if self.api_key:
            metadata = self._fetch_via_data_api(video_id)
            if metadata:
                final = metadata
            else:
                final = None
        else:
            final = None
        if url:
            metadata = self._fetch_via_oembed(url)
            if metadata:
                final = metadata if final is None else {**metadata, **final}
        if not final:
            final = {
                "video_id": video_id,
                "title": None,
                "channel_title": None,
                "duration_seconds": None,
            }

        final["video_id"] = video_id
        playlist_id = final.get("playlist_id") or extract_playlist_id(url)
        timestamp_seconds = final.get("timestamp_seconds") or extract_timestamp_seconds(url)
        final["playlist_id"] = playlist_id
        final["timestamp_seconds"] = timestamp_seconds
        final["canonical_url"] = final.get("canonical_url") or normalize_video_url(
            video_id,
            playlist_id=playlist_id,
            timestamp=None,
        )
        if playlist_id and not final.get("playlist_url"):
            final["playlist_url"] = f"https://www.youtube.com/playlist?list={playlist_id}"
        final.setdefault("url", url or final["canonical_url"])
        return final

    def _fetch_via_data_api(self, video_id: str) -> Optional[Dict[str, Any]]:
        params = {
            "id": video_id,
            "part": "snippet,contentDetails",
            "key": self.api_key,
        }
        try:
            response = self._client.get(self.DATA_API_URL, params=params)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.warning("[YOUTUBE] Data API metadata fetch failed: %s", exc)
            return None

        items = data.get("items") or []
        if not items:
            return None

        snippet = items[0].get("snippet") or {}
        details = items[0].get("contentDetails") or {}
        duration = _parse_iso8601_duration(details.get("duration", ""))
        tags = snippet.get("tags") or []
        channel_id = snippet.get("channelId")
        return {
            "video_id": video_id,
            "title": snippet.get("title"),
            "channel_title": snippet.get("channelTitle"),
            "description": snippet.get("description"),
            "duration_seconds": duration,
            "thumbnail_url": (snippet.get("thumbnails") or {}).get("high", {}).get("url"),
            "tags": tags,
            "channel_id": channel_id,
            "channel_url": f"https://www.youtube.com/channel/{channel_id}" if channel_id else None,
            "published_at": snippet.get("publishedAt"),
        }

    def _fetch_via_oembed(self, url: str) -> Optional[Dict[str, Any]]:
        params = {"url": url, "format": "json"}
        try:
            response = self._client.get(self.OEMBED_URL, params=params)
            response.raise_for_status()
            data = response.json()
            return {
                "title": data.get("title"),
                "channel_title": data.get("author_name"),
                "description": None,
                "thumbnail_url": data.get("thumbnail_url"),
                "duration_seconds": None,
                "tags": [],
                "channel_id": None,
                "channel_url": None,
                "published_at": None,
            }
        except Exception as exc:
            logger.debug("[YOUTUBE] oEmbed metadata fetch failed: %s", exc)
            return None

