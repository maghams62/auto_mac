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

    def search_tweets(
        self,
        query: str,
        max_results: int = 10,
        start_time_iso: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search recent tweets matching a query.

        Args:
            query: Search query string
            max_results: Maximum tweets to return (10-100)
            start_time_iso: Optional start time filter (ISO 8601 format)

        Returns the raw JSON response with tweets and user data.
        """
        url = f"{self.BASE_URL}/tweets/search/recent"
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

        # Validate parameters
        validated_params = self._validator.validate_params("search_recent", params)

        response = self.read_session.get(url, params=validated_params, timeout=30)
        self._raise_for_status(response, "searching tweets")
        return response.json()

    def get_user_timeline(
        self,
        username: Optional[str] = None,
        user_id: Optional[str] = None,
        max_results: int = 10,
        start_time_iso: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get tweets from a specific user's timeline.

        Args:
            username: Twitter username (e.g., "elonmusk")
            user_id: Twitter user ID (alternative to username)
            max_results: Maximum tweets to return (5-100)
            start_time_iso: Optional start time filter (ISO 8601 format)

        Returns the raw JSON response with tweets.
        """
        # First, get user ID if username provided
        if username and not user_id:
            user_url = f"{self.BASE_URL}/users/by/username/{username}"
            user_response = self.read_session.get(user_url, timeout=30)
            self._raise_for_status(user_response, f"fetching user ID for @{username}")
            user_data = user_response.json()
            user_id = user_data.get("data", {}).get("id")
            if not user_id:
                raise TwitterAPIError(f"Could not find user ID for @{username}")

        if not user_id:
            raise TwitterAPIError("Either username or user_id must be provided")

        url = f"{self.BASE_URL}/users/{user_id}/tweets"
        params = {
            "max_results": max(5, min(max_results, 100)),
            "tweet.fields": "id,text,author_id,created_at,conversation_id,public_metrics,referenced_tweets",
            "expansions": "author_id",
            "user.fields": "id,name,username",
        }
        if start_time_iso:
            params["start_time"] = start_time_iso

        # Validate parameters
        validated_params = self._validator.validate_params("user_timeline", params)

        response = self.read_session.get(url, params=validated_params, timeout=30)
        self._raise_for_status(response, f"fetching user timeline for user {user_id}")
        return response.json()

    def get_authenticated_user_timeline(
        self,
        max_results: int = 10,
        start_time_iso: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get tweets from the authenticated user's timeline (requires OAuth).

        Args:
            max_results: Maximum tweets to return (5-100)
            start_time_iso: Optional start time filter (ISO 8601 format)

        Returns the raw JSON response with tweets.
        """
        if not self._oauth:
            raise TwitterAPIError(
                "OAuth credentials required for authenticated user timeline. "
                "Set TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET."
            )

        # Use Twitter API v2 "me" endpoint to get authenticated user ID
        me_url = f"{self.BASE_URL}/users/me"
        me_response = requests.get(me_url, auth=self._oauth, timeout=30)
        self._raise_for_status(me_response, "fetching authenticated user info")
        me_data = me_response.json()
        user_id = me_data.get("data", {}).get("id")

        if not user_id:
            raise TwitterAPIError("Could not get authenticated user ID")

        # Now fetch the timeline
        return self.get_user_timeline(user_id=user_id, max_results=max_results, start_time_iso=start_time_iso)

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
