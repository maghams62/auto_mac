"""
Twitter API client utilities.
"""

from __future__ import annotations

import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

import requests
from requests_oauthlib import OAuth1

from ..utils.api_validator import create_twitter_validator


logger = logging.getLogger(__name__)


class TwitterAPIError(RuntimeError):
    """Raised when Twitter API responses are unsuccessful."""


class TwitterAPIClient:
    """
    Lightweight wrapper around the Twitter v2 REST API.

    Uses bearer-token (app-only) authentication for read-only endpoints.
    """

    BASE_URL = "https://api.twitter.com/2"

    def __init__(self):
        token = os.getenv("TWITTER_BEARER_TOKEN")
        if not token:
            raise TwitterAPIError("TWITTER_BEARER_TOKEN not configured in environment")

        self.read_session = requests.Session()
        self.read_session.headers.update({
            "Authorization": f"Bearer {token}",
            "User-Agent": "MacMCP-TwitterSummarizer/1.0",
        })

        api_key = os.getenv("TWITTER_API_KEY")
        api_secret = os.getenv("TWITTER_API_SECRET")
        access_token = os.getenv("TWITTER_ACCESS_TOKEN")
        access_secret = os.getenv("TWITTER_ACCESS_SECRET")

        if all([api_key, api_secret, access_token, access_secret]):
            self._oauth = OAuth1(api_key, api_secret, access_token, access_secret)
        else:
            self._oauth = None

        # API parameter validator - prevents sending unsupported parameters
        self._validator = create_twitter_validator()

    def fetch_list_tweets(
        self,
        list_id: str,
        start_time_iso: Optional[str] = None,
        max_results: int = 100,
    ) -> Dict[str, Any]:
        """
        Fetch tweets from a Twitter List.

        NOTE: The Lists API endpoint does NOT support start_time parameter.
        Time filtering must be done client-side after fetching.

        Args:
            list_id: Twitter List ID
            start_time_iso: IGNORED - kept for API compatibility, but Lists endpoint doesn't support it
            max_results: Maximum tweets to fetch (10-100)

        Returns the raw JSON response.
        """
        url = f"{self.BASE_URL}/lists/{list_id}/tweets"
        params = {
            "max_results": max(10, min(max_results, 100)),
            "tweet.fields": "id,text,author_id,created_at,conversation_id,public_metrics,referenced_tweets",
            "expansions": "author_id",
            "user.fields": "id,name,username",
        }

        # DEFENSIVE: Validate parameters against API capabilities
        # This prevents sending unsupported params like 'start_time' which cause 400 errors
        validated_params = self._validator.validate_params("lists_tweets", params)

        response = self.read_session.get(url, params=validated_params, timeout=30)
        self._raise_for_status(response, "fetching list tweets")
        return response.json()

    def fetch_conversation(
        self,
        conversation_id: str,
        start_time_iso: Optional[str],
        max_results: int = 100,
    ) -> Dict[str, Any]:
        """
        Fetch tweets belonging to a conversation/thread.
        """
        url = f"{self.BASE_URL}/tweets/search/recent"
        query = f"conversation_id:{conversation_id}"
        params = {
            "query": query,
            "max_results": max(10, min(max_results, 100)),
            "tweet.fields": "id,text,author_id,created_at,conversation_id,public_metrics,referenced_tweets",
            "expansions": "author_id",
            "user.fields": "id,name,username",
            "sort_order": "recency",
        }
        if start_time_iso:
            params["start_time"] = start_time_iso

        # DEFENSIVE: Validate parameters (search endpoint DOES support start_time)
        validated_params = self._validator.validate_params("search_recent", params)

        response = self.read_session.get(url, params=validated_params, timeout=30)
        self._raise_for_status(response, "fetching conversation")
        return response.json()

    def post_tweet(self, text: str) -> Dict[str, Any]:
        """
        Publish a tweet using user-context OAuth credentials.
        """
        if not text or not text.strip():
            raise TwitterAPIError("Cannot post empty tweet text")

        if not self._oauth:
            raise TwitterAPIError(
                "Twitter API/Access tokens not configured. "
                "Set TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET."
            )

        url = f"{self.BASE_URL}/tweets"
        payload = {"text": text.strip()}
        response = requests.post(url, json=payload, auth=self._oauth, timeout=30)
        self._raise_for_status(response, "posting tweet")
        return response.json()

    @staticmethod
    def _raise_for_status(response: requests.Response, action: str):
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            logger.error("Twitter API error while %s: %s", action, detail)
            raise TwitterAPIError(f"Twitter API error ({response.status_code}) while {action}: {detail}")


def isoformat(dt: datetime) -> str:
    """Format datetime as RFC3339 / ISO8601 string."""
    iso = dt.replace(microsecond=0).isoformat()
    if not iso.endswith("Z"):
        if dt.tzinfo is None:
            return f"{iso}Z"
        return iso.replace("+00:00", "Z")
    return iso
