"""
Bluesky Notification Service - Real-time monitoring and notifications for Bluesky activity.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from ..integrations.bluesky_client import BlueskyAPIClient, BlueskyAPIError

logger = logging.getLogger(__name__)


class BlueskyNotificationService:
    """
    Background service that polls Bluesky for notifications and timeline updates,
    broadcasting real-time notifications to connected WebSocket clients.
    """

    def __init__(self, connection_manager, config: Dict[str, any]):
        self.connection_manager = connection_manager
        self.config = config
        self.bluesky_config = config.get("bluesky", {})

        # Service state
        self.running = False
        self.poll_interval = self.bluesky_config.get("notification_poll_interval_seconds", 60)
        self.max_retries = 3
        self.backoff_factor = 2.0

        # Deduplication state - in-memory cache of seen notification URIs
        self.seen_notifications: Set[str] = set()
        self.seen_timeline_posts: Set[str] = set()

        # Persistence file for state recovery
        self.state_file = os.path.join("data", "bluesky_state.json")

        # Bluesky client (created lazily to avoid auth issues during init)
        self.client: Optional[BlueskyAPIClient] = None

        # Background task
        self.poll_task: Optional[asyncio.Task] = None

        logger.info(f"[BLUESKY NOTIFICATIONS] Initialized with {self.poll_interval}s poll interval")

    def _ensure_client(self) -> Optional[BlueskyAPIClient]:
        """Ensure we have an authenticated Bluesky client."""
        if self.client is None:
            try:
                self.client = BlueskyAPIClient()
                logger.info("[BLUESKY NOTIFICATIONS] Authenticated with Bluesky")
            except BlueskyAPIError as e:
                logger.error(f"[BLUESKY NOTIFICATIONS] Failed to authenticate: {e}")
                return None
        return self.client

    def _load_persistent_state(self) -> None:
        """Load deduplication state from persistent storage."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)

                # Load seen URIs (limit to prevent memory bloat)
                seen_notifications = state.get("seen_notifications", [])
                seen_timeline = state.get("seen_timeline_posts", [])

                # Keep only recent entries (last 1000)
                self.seen_notifications = set(seen_notifications[-1000:])
                self.seen_timeline_posts = set(seen_timeline[-1000:])

                logger.info(f"[BLUESKY NOTIFICATIONS] Loaded state: {len(self.seen_notifications)} notifications, {len(self.seen_timeline_posts)} timeline posts")
        except Exception as e:
            logger.warning(f"[BLUESKY NOTIFICATIONS] Failed to load persistent state: {e}")

    def _save_persistent_state(self) -> None:
        """Save deduplication state to persistent storage."""
        try:
            state = {
                "seen_notifications": list(self.seen_notifications),
                "seen_timeline_posts": list(self.seen_timeline_posts),
                "last_updated": datetime.now(timezone.utc).isoformat()
            }

            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            logger.warning(f"[BLUESKY NOTIFICATIONS] Failed to save persistent state: {e}")

    async def _poll_notifications(self) -> None:
        """Poll for new notifications and broadcast them."""
        client = self._ensure_client()
        if not client:
            return

        try:
            # Get recent notifications
            raw_notifications = client.list_notifications(limit=20)
            notifications = raw_notifications.get("notifications", [])

            new_notifications = []
            for notification in notifications:
                uri = notification.get("uri")
                if uri and uri not in self.seen_notifications:
                    self.seen_notifications.add(uri)
                    new_notifications.append(notification)

            # Broadcast new notifications
            for notification in new_notifications:
                await self._broadcast_notification(notification, "notification")

        except BlueskyAPIError as e:
            logger.warning(f"[BLUESKY NOTIFICATIONS] Failed to poll notifications: {e}")
        except Exception as e:
            logger.exception("[BLUESKY NOTIFICATIONS] Unexpected error polling notifications")

    async def _poll_timeline(self) -> None:
        """Poll for new timeline posts and broadcast mentions/replies."""
        client = self._ensure_client()
        if not client:
            return

        try:
            # Get recent timeline posts
            raw_timeline = client.get_timeline(limit=20)
            feed_items = raw_timeline.get("feed", [])

            new_posts = []
            for feed_item in feed_items:
                post = feed_item.get("post", {})
                uri = post.get("uri")

                if uri and uri not in self.seen_timeline_posts:
                    self.seen_timeline_posts.add(uri)

                    # Check if this post mentions us or is a reply to our posts
                    author = post.get("author", {})
                    record = post.get("record", {})

                    # Simple mention detection (could be enhanced)
                    text = record.get("text", "").lower()
                    handle = client.handle or ""

                    if handle and ("@" + handle.lower() in text or handle.lower() in text):
                        new_posts.append(post)

            # Broadcast new mentions/replies
            for post in new_posts:
                await self._broadcast_notification(post, "timeline_mention")

        except BlueskyAPIError as e:
            logger.warning(f"[BLUESKY NOTIFICATIONS] Failed to poll timeline: {e}")
        except Exception as e:
            logger.exception("[BLUESKY NOTIFICATIONS] Unexpected error polling timeline")

    async def _broadcast_notification(self, item: Dict, source: str) -> None:
        """Broadcast a notification to all connected WebSocket clients."""
        try:
            # Normalize the notification/post data
            if source == "notification":
                # Handle notification format
                record = item.get("record", {})
                author = item.get("author", {})

                # Add post context if available (needed for URI and subject_post)
                subject_post_data = None
                if item.get("reasonSubject"):
                    try:
                        client = self._ensure_client()
                        if client:
                            post_raw = client.get_posts([item["reasonSubject"]])
                            if post_raw.get("posts"):
                                from ..agent.bluesky_agent import _normalize_post
                                subject_post_data = _normalize_post(post_raw["posts"][0])
                    except Exception:
                        pass

                notification_payload = {
                    "type": "bluesky_notification",
                    "source": "notification",
                    "notification_type": record.get("$type", "").replace("app.bsky.notification.", ""),
                    "reason": item.get("reason"),
                    "author_handle": author.get("handle", ""),
                    "author_name": author.get("displayName") or author.get("handle", ""),
                    "timestamp": item.get("indexedAt"),
                    "uri": subject_post_data.get("uri") if subject_post_data else None,  # Use post URI for actions
                    "reason_subject": item.get("reasonSubject"),
                }

                # Add subject post data if available
                if subject_post_data:
                    notification_payload["subject_post"] = subject_post_data

            else:  # timeline_mention
                from ..agent.bluesky_agent import _normalize_post
                post_data = _normalize_post(item)
                notification_payload = {
                    "type": "bluesky_notification",
                    "source": "timeline_mention",
                    "author_handle": post_data.get("author_handle"),
                    "author_name": post_data.get("author_name"),
                    "uri": post_data.get("uri"),  # Use post URI for actions
                    "post": post_data,
                    "timestamp": post_data.get("created_at"),
                }

            # Broadcast to all connected clients
            await self.connection_manager.broadcast({
                "type": "bluesky_notification",
                "data": notification_payload,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            logger.info(f"[BLUESKY NOTIFICATIONS] Broadcast {source} notification from @{notification_payload.get('author_handle', 'unknown')}")

        except Exception as e:
            logger.exception(f"[BLUESKY NOTIFICATIONS] Failed to broadcast notification: {e}")

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        logger.info(f"[BLUESKY NOTIFICATIONS] Starting poll loop (interval: {self.poll_interval}s)")

        consecutive_failures = 0
        max_consecutive_failures = 5

        while self.running:
            try:
                # Poll both notifications and timeline
                await self._poll_notifications()
                await self._poll_timeline()

                # Save state periodically (every 10 polls)
                if consecutive_failures == 0:
                    self._save_persistent_state()

                consecutive_failures = 0

            except Exception as e:
                consecutive_failures += 1
                logger.exception(f"[BLUESKY NOTIFICATIONS] Poll cycle failed ({consecutive_failures}/{max_consecutive_failures})")

                if consecutive_failures >= max_consecutive_failures:
                    logger.error("[BLUESKY NOTIFICATIONS] Too many consecutive failures, stopping service")
                    self.running = False
                    break

            # Wait for next poll cycle
            await asyncio.sleep(self.poll_interval)

        logger.info("[BLUESKY NOTIFICATIONS] Poll loop stopped")

    async def start(self) -> None:
        """Start the notification service."""
        if self.running:
            logger.warning("[BLUESKY NOTIFICATIONS] Service already running")
            return

        # Load persistent state
        self._load_persistent_state()

        # Check if notifications are enabled
        if not self.bluesky_config.get("notifications_enabled", True):
            logger.info("[BLUESKY NOTIFICATIONS] Notifications disabled in config")
            return

        self.running = True

        # Start the polling task
        self.poll_task = asyncio.create_task(self._poll_loop())

        logger.info("[BLUESKY NOTIFICATIONS] Service started")

    async def stop(self) -> None:
        """Stop the notification service."""
        if not self.running:
            return

        logger.info("[BLUESKY NOTIFICATIONS] Stopping service...")
        self.running = False

        if self.poll_task:
            self.poll_task.cancel()
            try:
                await self.poll_task
            except asyncio.CancelledError:
                pass

        # Final state save
        self._save_persistent_state()

        logger.info("[BLUESKY NOTIFICATIONS] Service stopped")

    def is_running(self) -> bool:
        """Check if the service is currently running."""
        return self.running and self.poll_task and not self.poll_task.done()
