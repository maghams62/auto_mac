"""
GitHub Webhook Service - Handle PR events and store metadata.

Receives GitHub webhook events, validates signatures, and stores PR metadata
for the Git agent to query.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class GitHubWebhookError(RuntimeError):
    """Raised when GitHub webhook processing fails."""


class GitHubWebhookService:
    """
    Service for processing GitHub webhook events.

    Handles PR events, validates signatures, and stores metadata.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        github_config = config.get("github", {})

        self.webhook_secret = os.getenv("GITHUB_WEBHOOK_SECRET")
        self.target_repo = github_config.get("repo_name", "auto_mac")
        self.target_branch = github_config.get("base_branch", "main")

        # Storage for PR events
        self.pr_events_file = Path("data/pr_events.json")
        self.pr_events_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize storage if doesn't exist
        if not self.pr_events_file.exists():
            self._save_pr_events([])

        logger.info("[GITHUB WEBHOOK] Initialized webhook service")

    def verify_signature(self, payload_body: bytes, signature_header: str) -> bool:
        """
        Verify GitHub webhook signature.

        Args:
            payload_body: Raw request body bytes
            signature_header: X-Hub-Signature-256 header value

        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            logger.warning("[GITHUB WEBHOOK] No webhook secret configured, skipping signature verification")
            return True  # Allow for development without secret

        if not signature_header:
            logger.error("[GITHUB WEBHOOK] No signature header provided")
            return False

        # GitHub sends signature as "sha256=<hash>"
        try:
            hash_algorithm, signature = signature_header.split("=")
        except ValueError:
            logger.error("[GITHUB WEBHOOK] Invalid signature format")
            return False

        if hash_algorithm != "sha256":
            logger.error(f"[GITHUB WEBHOOK] Unsupported hash algorithm: {hash_algorithm}")
            return False

        # Compute HMAC
        mac = hmac.new(
            self.webhook_secret.encode(),
            msg=payload_body,
            digestmod=hashlib.sha256
        )
        expected_signature = mac.hexdigest()

        # Compare signatures
        if not hmac.compare_digest(expected_signature, signature):
            logger.error("[GITHUB WEBHOOK] Signature verification failed")
            return False

        return True

    def process_pr_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a pull request event.

        Args:
            event_type: GitHub event type (e.g., "pull_request")
            payload: Webhook payload

        Returns:
            Processed PR metadata
        """
        if event_type != "pull_request":
            logger.info(f"[GITHUB WEBHOOK] Ignoring non-PR event: {event_type}")
            return {
                "ignored": True,
                "reason": f"Not a PR event: {event_type}",
            }

        action = payload.get("action")
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})

        # Extract PR metadata
        pr_metadata = {
            "event_type": event_type,
            "action": action,
            "pr_number": pr.get("number"),
            "title": pr.get("title"),
            "state": pr.get("state"),
            "author": pr.get("user", {}).get("login"),
            "repo": repo.get("full_name"),
            "base_branch": pr.get("base", {}).get("ref"),
            "head_branch": pr.get("head", {}).get("ref"),
            "url": pr.get("html_url"),
            "created_at": pr.get("created_at"),
            "updated_at": pr.get("updated_at"),
            "merged_at": pr.get("merged_at"),
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

        # Filter by target repo and branch if configured
        if self.target_repo and pr_metadata["repo"] != self.target_repo:
            logger.info(f"[GITHUB WEBHOOK] Ignoring PR from non-target repo: {pr_metadata['repo']}")
            return {
                "ignored": True,
                "reason": f"Not from target repo: {self.target_repo}",
            }

        if self.target_branch and pr_metadata["base_branch"] != self.target_branch:
            logger.info(f"[GITHUB WEBHOOK] Ignoring PR to non-target branch: {pr_metadata['base_branch']}")
            return {
                "ignored": True,
                "reason": f"Not targeting branch: {self.target_branch}",
            }

        # Store PR event
        self._store_pr_event(pr_metadata)

        logger.info(f"[GITHUB WEBHOOK] Processed PR #{pr_metadata['pr_number']}: {action}")

        return pr_metadata

    def _store_pr_event(self, pr_metadata: Dict[str, Any]) -> None:
        """
        Store PR event in local JSON file.

        Args:
            pr_metadata: PR metadata to store
        """
        try:
            events = self._load_pr_events()

            # Update existing or append new
            pr_number = pr_metadata.get("pr_number")
            existing_index = next(
                (i for i, e in enumerate(events) if e.get("pr_number") == pr_number),
                None
            )

            if existing_index is not None:
                events[existing_index] = pr_metadata
                logger.info(f"[GITHUB WEBHOOK] Updated PR #{pr_number} in storage")
            else:
                events.append(pr_metadata)
                logger.info(f"[GITHUB WEBHOOK] Added PR #{pr_number} to storage")

            # Keep only last 100 PRs
            if len(events) > 100:
                events = events[-100:]

            self._save_pr_events(events)

        except Exception as exc:
            logger.exception(f"[GITHUB WEBHOOK] Failed to store PR event: {exc}")
            raise GitHubWebhookError(f"Failed to store PR event: {exc}")

    def _load_pr_events(self) -> list:
        """Load PR events from storage file."""
        try:
            if not self.pr_events_file.exists():
                return []
            with open(self.pr_events_file, "r") as f:
                return json.load(f)
        except Exception as exc:
            logger.error(f"[GITHUB WEBHOOK] Failed to load PR events: {exc}")
            return []

    def _save_pr_events(self, events: list) -> None:
        """Save PR events to storage file."""
        try:
            with open(self.pr_events_file, "w") as f:
                json.dump(events, f, indent=2)
        except Exception as exc:
            logger.error(f"[GITHUB WEBHOOK] Failed to save PR events: {exc}")

    def get_recent_prs(self, limit: int = 10) -> list:
        """
        Get recent PR events.

        Args:
            limit: Maximum number of PRs to return

        Returns:
            List of recent PR metadata (most recent first)
        """
        events = self._load_pr_events()
        return list(reversed(events[-limit:]))

    def get_pr_by_number(self, pr_number: int) -> Optional[Dict[str, Any]]:
        """
        Get PR metadata by PR number.

        Args:
            pr_number: PR number to lookup

        Returns:
            PR metadata or None if not found
        """
        events = self._load_pr_events()
        return next(
            (e for e in reversed(events) if e.get("pr_number") == pr_number),
            None
        )
