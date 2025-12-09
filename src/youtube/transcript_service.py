from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
    VideoUnavailable,
)

try:
    from youtube_transcript_api import TooManyRequests  # type: ignore
except ImportError:  # pragma: no cover
    try:
        from youtube_transcript_api._errors import TooManyRequests  # type: ignore
    except ImportError:
        class TooManyRequests(Exception):  # type: ignore
            """Fallback TooManyRequests exception when library version lacks it."""
            pass

logger = logging.getLogger(__name__)


class TranscriptProviderError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class YouTubeTranscriptService:
    """Fetch transcripts using the official YouTube transcript API client."""

    def __init__(self, config: Dict[str, Any]):
        youtube_cfg = (config.get("youtube") or {}).get("transcript") or {}
        self.languages = youtube_cfg.get("preferred_languages") or ["en"]
        self.fallback_languages = youtube_cfg.get("fallback_languages") or []
        self.max_retries = int(youtube_cfg.get("max_retries", 3))
        self.retry_delay = float(youtube_cfg.get("retry_delay_seconds", 2.0))
        self._has_static_helper = hasattr(YouTubeTranscriptApi, "get_transcript")
        self._client: Optional[YouTubeTranscriptApi] = None

    def _ensure_client(self) -> YouTubeTranscriptApi:
        if self._client is None:
            self._client = YouTubeTranscriptApi()
        return self._client

    def fetch_transcript(self, video_id: str) -> Dict[str, Any]:
        attempts = 0
        last_error: Optional[TranscriptProviderError] = None

        while attempts < self.max_retries:
            try:
                transcript = self._fetch_transcript_payload(video_id)
                return {
                    "segments": transcript,
                    "language": transcript[0].get("language", "unknown") if transcript else None,
                }
            except TooManyRequests:
                error = TranscriptProviderError(
                    "TRANSCRIPT_BLOCKED_ANTIBOT",
                    "YouTube rate limited transcript access (possible CAPTCHA).",
                )
                logger.warning("[YOUTUBE] Transcript blocked by anti-bot for %s", video_id)
                raise error
            except TranscriptsDisabled:
                error = TranscriptProviderError(
                    "TRANSCRIPT_DISABLED",
                    "Transcripts are disabled for this video.",
                )
                logger.info("[YOUTUBE] Transcripts disabled for %s", video_id)
                raise error
            except VideoUnavailable:
                error = TranscriptProviderError(
                    "TRANSCRIPT_VIDEO_UNAVAILABLE",
                    "This video is unavailable.",
                )
                raise error
            except NoTranscriptFound:
                error = TranscriptProviderError(
                    "TRANSCRIPT_UNAVAILABLE",
                    "No transcript available for this video.",
                )
                raise error
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("[YOUTUBE] Transcript fetch failed (%s attempt=%s): %s", video_id, attempts, exc)
                last_error = TranscriptProviderError("TRANSCRIPT_UNKNOWN_ERROR", str(exc))
                attempts += 1
                time.sleep(self.retry_delay)
                continue

        raise last_error or TranscriptProviderError(
            "TRANSCRIPT_UNKNOWN_ERROR", "Exhausted retries fetching transcript."
        )

    def _fetch_transcript_payload(self, video_id: str) -> List[Dict[str, Any]]:
        languages = self.languages + self.fallback_languages
        if self._has_static_helper:
            raw_segments = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
            return [self._normalize_segment(segment) for segment in raw_segments]
        client = self._ensure_client()
        transcript_list = client.list(video_id)
        transcript = transcript_list.find_transcript(languages)
        raw_segments = transcript.fetch()
        return [self._normalize_segment(segment) for segment in raw_segments]

    @staticmethod
    def _normalize_segment(segment: Any) -> Dict[str, Any]:
        if isinstance(segment, dict):
            return segment
        data = {}
        for key in ("text", "start", "duration", "offset"):
            if hasattr(segment, key):
                data[key] = getattr(segment, key)
        if not data and hasattr(segment, "__dict__"):
            data = dict(segment.__dict__)
        return data

