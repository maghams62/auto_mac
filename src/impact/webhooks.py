"""
Stateless helpers that translate external webhooks into ImpactReports.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .service import ImpactService, SlackComplaintInput

logger = logging.getLogger(__name__)


class ImpactWebhookHandlers:
    def __init__(self, impact_service: ImpactService):
        self.impact_service = impact_service

    def handle_github_event(self, event_type: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if event_type == "pull_request":
            return self._handle_pull_request(payload)
        if event_type == "push":
            return self._handle_push(payload)
        return None

    def _handle_pull_request(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        action = payload.get("action")
        if action not in {"opened", "synchronize", "reopened", "ready_for_review"}:
            return None
        pr_payload = payload.get("pull_request") or {}
        repo_full = (payload.get("repository") or {}).get("full_name")
        pr_number = pr_payload.get("number") or payload.get("number")
        if not repo_full or not pr_number:
            logger.warning("[WEBHOOK] Missing repo/pr for pull_request event")
            return None
        logger.info("[WEBHOOK] Triggering impact analysis for PR %s#%s", repo_full, pr_number)
        report = self.impact_service.analyze_git_pr(repo_full, int(pr_number))
        return report.to_dict()

    def _handle_push(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        repo_full = (payload.get("repository") or {}).get("full_name")
        commits = [commit.get("id") for commit in payload.get("commits", []) if commit.get("id")]
        if not repo_full or not commits:
            return None
        branch = payload.get("ref", "").split("/", 2)[-1]
        title = f"Push to {branch}" if branch else "Git push"
        description = (payload.get("head_commit") or {}).get("message")
        logger.info("[WEBHOOK] Triggering impact analysis for push %s (%s commits)", repo_full, len(commits))
        report = self.impact_service.analyze_git_change(
            repo_full,
            commits=commits[:10],
            title=title,
            description=description,
        )
        return report.to_dict()

    def handle_slack_complaint(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map a Slack analyzer event to the Slack complaint impact flow.
        """
        channel = event.get("channel")
        message = event.get("text") or ""
        ts = event.get("ts") or event.get("timestamp")
        if not channel or not ts or not message:
            return None
        context = event.get("context", {})
        complaint_input = SlackComplaintInput(
            channel=channel,
            message=message,
            timestamp=str(ts),
            component_ids=context.get("component_ids"),
            api_ids=context.get("api_ids"),
            repo=context.get("repo"),
            commit_shas=context.get("commit_shas"),
            permalink=context.get("permalink") or event.get("permalink"),
        )
        report = self.impact_service.analyze_slack_complaint(complaint_input)
        return report.to_dict()

