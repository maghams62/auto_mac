"""
Bluesky API client utilities.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class BlueskyAPIError(RuntimeError):
    """Raised when Bluesky API responses are unsuccessful."""


class BlueskyAPIClient:
    """
    Lightweight wrapper around the Bluesky (AT Protocol) HTTP API.

    Handles session authentication and provides helpers for common feed/search/post
    operations needed by the Bluesky agent tools.
    """

    BASE_URL = "https://bsky.social/xrpc"

    def __init__(self, identifier: Optional[str] = None, password: Optional[str] = None):
        self.identifier = identifier or os.getenv("BLUESKY_USERNAME") or os.getenv("BLUESKY_IDENTIFIER")
        self.password = password or os.getenv("BLUESKY_PASSWORD")

        if not self.identifier or not self.password:
            raise BlueskyAPIError(
                "Bluesky credentials not configured. Set BLUESKY_USERNAME (or BLUESKY_IDENTIFIER) "
                "and BLUESKY_PASSWORD in your environment or .env file."
            )

        self.session = requests.Session()
        self.access_jwt: Optional[str] = None
        self.refresh_jwt: Optional[str] = None
        self.did: Optional[str] = None
        self.handle: Optional[str] = None  # Store the handle from session

        self._authenticate()

    # ------------------------------------------------------------------
    # Public API helpers
    # ------------------------------------------------------------------
    def search_posts(self, query: str, limit: int = 10, cursor: Optional[str] = None) -> Dict[str, Any]:
        """Search public posts containing the provided query string."""
        params = {
            "q": query,
            "limit": max(1, min(limit, 100)),
        }
        if cursor:
            params["cursor"] = cursor

        response = self._get("app.bsky.feed.searchPosts", params=params)
        return response.json()

    def get_author_feed(self, actor: Optional[str] = None, limit: int = 10, cursor: Optional[str] = None) -> Dict[str, Any]:
        """Fetch posts from a specific author/handle. If actor is None, uses authenticated user's handle."""
        if actor is None:
            # Use authenticated user's handle (prefer handle over identifier/email)
            actor = self.handle or self.did or self.identifier
            if not actor:
                raise BlueskyAPIError("Cannot get author feed: no actor specified and no authenticated user handle available.")
        
        params = {
            "actor": actor,
            "limit": max(1, min(limit, 100)),
        }
        if cursor:
            params["cursor"] = cursor

        response = self._get("app.bsky.feed.getAuthorFeed", params=params)
        return response.json()
    
    def get_my_handle(self) -> str:
        """Get the authenticated user's handle."""
        if not self.did:
            raise BlueskyAPIError("Cannot get handle: not authenticated.")
        # Return handle if available, otherwise fall back to DID or identifier
        return self.handle or self.did or self.identifier

    def get_popular(self, limit: int = 10, cursor: Optional[str] = None) -> Dict[str, Any]:
        """Fetch globally popular posts (Bluesky curated)."""
        params = {
            "limit": max(1, min(limit, 100)),
        }
        if cursor:
            params["cursor"] = cursor

        response = self._get("app.bsky.feed.getPopular", params=params)
        return response.json()

    def create_post(self, text: str) -> Dict[str, Any]:
        """Publish a new Bluesky post on behalf of the authenticated user."""
        if not text or not text.strip():
            raise BlueskyAPIError("Cannot create an empty Bluesky post.")

        clean_text = text.strip()
        if len(clean_text) > 300:
            raise BlueskyAPIError("Bluesky posts are limited to 300 characters.")

        record = {
            "$type": "app.bsky.feed.post",
            "text": clean_text,
            "createdAt": self._timestamp(),
        }

        payload = {
            "repo": self.did,
            "collection": "app.bsky.feed.post",
            "record": record,
        }

        response = self._post("com.atproto.repo.createRecord", json=payload)
        return response.json()

    def get_timeline(self, limit: int = 50, cursor: Optional[str] = None) -> Dict[str, Any]:
        """Fetch the authenticated user's timeline (following feed)."""
        params = {
            "limit": max(1, min(limit, 100)),
        }
        if cursor:
            params["cursor"] = cursor

        response = self._get("app.bsky.feed.getTimeline", params=params)
        return response.json()

    def get_list_feed(self, list_uri: str, limit: int = 50, cursor: Optional[str] = None) -> Dict[str, Any]:
        """Fetch posts from a specific Bluesky list."""
        params = {
            "list": list_uri,
            "limit": max(1, min(limit, 100)),
        }
        if cursor:
            params["cursor"] = cursor

        response = self._get("app.bsky.feed.getListFeed", params=params)
        return response.json()

    def list_notifications(self, limit: int = 50, cursor: Optional[str] = None, seen_at: Optional[str] = None) -> Dict[str, Any]:
        """Fetch notifications (mentions, replies, likes, follows, etc.)."""
        params = {
            "limit": max(1, min(limit, 100)),
        }
        if cursor:
            params["cursor"] = cursor
        if seen_at:
            params["seenAt"] = seen_at

        response = self._get("app.bsky.notification.listNotifications", params=params)
        return response.json()

    def get_posts(self, uris: List[str]) -> Dict[str, Any]:
        """Bulk lookup posts by their AT Protocol URIs."""
        if not uris:
            return {"posts": []}

        params = {"uris": uris}
        response = self._get("app.bsky.feed.getPosts", params=params)
        return response.json()

    def reply_to_post(self, text: str, reply_to_uri: str, reply_to_cid: str) -> Dict[str, Any]:
        """Reply to an existing post, creating a threaded conversation."""
        if not text or not text.strip():
            raise BlueskyAPIError("Cannot create an empty Bluesky reply.")

        clean_text = text.strip()
        if len(clean_text) > 300:
            raise BlueskyAPIError("Bluesky posts are limited to 300 characters.")

        record = {
            "$type": "app.bsky.feed.post",
            "text": clean_text,
            "createdAt": self._timestamp(),
            "reply": {
                "root": {
                    "uri": reply_to_uri,
                    "cid": reply_to_cid,
                },
                "parent": {
                    "uri": reply_to_uri,
                    "cid": reply_to_cid,
                },
            },
        }

        payload = {
            "repo": self.did,
            "collection": "app.bsky.feed.post",
            "record": record,
        }

        response = self._post("com.atproto.repo.createRecord", json=payload)
        return response.json()

    def like_post(self, subject_uri: str, subject_cid: str) -> Dict[str, Any]:
        """Like a post."""
        record = {
            "$type": "app.bsky.feed.like",
            "subject": {
                "uri": subject_uri,
                "cid": subject_cid,
            },
            "createdAt": self._timestamp(),
        }

        payload = {
            "repo": self.did,
            "collection": "app.bsky.feed.like",
            "record": record,
        }

        response = self._post("com.atproto.repo.createRecord", json=payload)
        return response.json()

    def repost_post(self, subject_uri: str, subject_cid: str) -> Dict[str, Any]:
        """Repost (boost) a post."""
        record = {
            "$type": "app.bsky.feed.repost",
            "subject": {
                "uri": subject_uri,
                "cid": subject_cid,
            },
            "createdAt": self._timestamp(),
        }

        payload = {
            "repo": self.did,
            "collection": "app.bsky.feed.repost",
            "record": record,
        }

        response = self._post("com.atproto.repo.createRecord", json=payload)
        return response.json()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _authenticate(self) -> None:
        """Obtain access tokens using identifier/password credentials."""
        endpoint = f"{self.BASE_URL}/com.atproto.server.createSession"
        payload = {"identifier": self.identifier, "password": self.password}

        response = requests.post(endpoint, json=payload, timeout=30)
        if response.status_code >= 400:
            detail = _safe_json(response)
            logger.error("Bluesky authentication failed: %s", detail)
            raise BlueskyAPIError(f"Failed to authenticate with Bluesky: {detail}")

        data = response.json()
        self.access_jwt = data.get("accessJwt")
        self.refresh_jwt = data.get("refreshJwt")
        self.did = data.get("did")
        self.handle = data.get("handle")  # Get handle from session response

        if not self.access_jwt or not self.did:
            raise BlueskyAPIError("Bluesky session missing token or DID.")

        self.session.headers.update({
            "Authorization": f"Bearer {self.access_jwt}",
            "Content-Type": "application/json",
            "User-Agent": "MacAutomationAssistant/BlueskyIntegration",
        })

    def _ensure_session(self) -> None:
        """Ensure we have an authenticated session before making API calls."""
        if not self.access_jwt:
            self._authenticate()

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        self._ensure_session()
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, params=params, timeout=30)
        self._raise_for_status(response, f"GET {endpoint}")
        return response

    def _post(self, endpoint: str, json: Optional[Dict[str, Any]] = None) -> requests.Response:
        self._ensure_session()
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.post(url, json=json, timeout=30)
        self._raise_for_status(response, f"POST {endpoint}")
        return response

    @staticmethod
    def _raise_for_status(response: requests.Response, action: str) -> None:
        if response.status_code >= 400:
            detail = _safe_json(response)
            logger.error("Bluesky API error during %s: %s", action, detail)
            raise BlueskyAPIError(f"Bluesky API error ({response.status_code}) during {action}: {detail}")

    @staticmethod
    def _timestamp() -> str:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        return now.isoformat().replace("+00:00", "Z")


def _safe_json(response: requests.Response) -> Any:
    """Attempt to parse a response as JSON, falling back to text."""
    try:
        return response.json()
    except ValueError:
        return response.text
