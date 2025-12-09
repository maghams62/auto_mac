"""
Notification stubs for ImpactReports.

These helpers stay behind a feature flag until Step 3 finishes wiring DocIssues
and ImpactEvents into live notification channels.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..config.models import ImpactNotificationSettings
from .models import ImpactReport

logger = logging.getLogger(__name__)


def notify_slack_channel(
    report: ImpactReport,
    settings: ImpactNotificationSettings,
    *,
    message: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log a placeholder Slack notification for the given report.

    When `settings.enabled` is False no action is taken. Once Step 3 is ready,
    this helper can be extended to call the actual Slack client.
    """

    if not settings.enabled:
        logger.debug("[IMPACT][NOTIFY] Slack notifications disabled; skipping %s", report.change_id)
        return

    channel = settings.slack_channel or "#docs-impact"
    headline = report.change_title or report.change_id
    summary = message or report.evidence_summary or report.change_summary or "No summary provided."
    log_payload = f" payload={payload}" if payload else ""
    logger.info(
        "[IMPACT][NOTIFY] Would notify Slack channel %s about %s%s",
        channel,
        summary or headline,
        log_payload,
    )


def post_pr_comment(
    pr_number: int,
    impact_summary: str,
    settings: ImpactNotificationSettings,
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log a placeholder GitHub PR comment for downstream wiring.

    When notifications are disabled nothing happens. If enabled but no GitHub App
    is configured we emit a warning so operators know why the notifier skipped.
    """

    if not settings.enabled:
        logger.debug("[IMPACT][NOTIFY] PR comment disabled; skipping #%s", pr_number)
        return

    if not settings.github_app_id:
        logger.warning(
            "[IMPACT][NOTIFY] GitHub App ID missing; cannot post comment for PR #%s", pr_number
        )
        return

    details = f" metadata={metadata}" if metadata else ""
    logger.info(
        "[IMPACT][NOTIFY] Would post PR comment via GitHub App %s on #%s: %s%s",
        settings.github_app_id,
        pr_number,
        impact_summary,
        details,
    )

