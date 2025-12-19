"""
High-level coordinator for optional impact notifications.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from ..config.models import ImpactNotificationSettings
from .models import ImpactLevel, ImpactReport
from .notifications import notify_slack_channel, post_pr_comment

logger = logging.getLogger(__name__)

LevelRank = {
    ImpactLevel.LOW: 0,
    ImpactLevel.MEDIUM: 1,
    ImpactLevel.HIGH: 2,
}


class ImpactNotificationService:
    """
    Applies gating logic + formatting before emitting Slack / PR notifications.
    """

    def __init__(
        self,
        settings: ImpactNotificationSettings,
        *,
        slack_notifier: Optional[Callable[..., None]] = None,
        pr_notifier: Optional[Callable[..., None]] = None,
    ) -> None:
        self.settings = settings
        self._slack_notifier = slack_notifier or notify_slack_channel
        self._pr_notifier = pr_notifier or post_pr_comment
        self._threshold_level = self._coerce_level(settings.min_impact_level) or ImpactLevel.HIGH

    def maybe_notify(
        self,
        report: ImpactReport,
        doc_issues: Sequence[Dict[str, Any]],
    ) -> bool:
        """
        Evaluate feature flags + thresholds and emit notifications when eligible.
        """
        if not self.settings or not self.settings.enabled:
            return False
        if not doc_issues:
            logger.debug("[IMPACT][NOTIFY] No doc issues created; skipping notifications")
            return False

        max_level = self._max_issue_level(doc_issues) or report.impact_level
        if not self._meets_threshold(max_level):
            logger.debug(
                "[IMPACT][NOTIFY] Highest impact level %s below threshold %s",
                max_level,
                self._threshold_level,
            )
            return False

        summary = self._build_summary(report, doc_issues, max_level)
        self._slack_notifier(
            report,
            self.settings,
            message=summary["slack_text"],
            payload=summary,
        )

        pr_number = summary.get("pr_number")
        if pr_number is not None:
            self._pr_notifier(
                pr_number,
                summary["pr_comment"],
                self.settings,
                metadata=summary,
            )
        return True

    # ------------------------------------------------------------------
    # Internal helpers

    def _max_issue_level(self, doc_issues: Sequence[Dict[str, Any]]) -> ImpactLevel:
        captured: List[ImpactLevel] = []
        for issue in doc_issues:
            raw_value = issue.get("impact_level")
            level = self._coerce_level(raw_value)
            if level:
                captured.append(level)
        if not captured:
            return ImpactLevel.MEDIUM
        return max(captured, key=lambda lvl: LevelRank.get(lvl, 0))

    def _meets_threshold(self, observed: ImpactLevel) -> bool:
        return LevelRank[observed] >= LevelRank[self._threshold_level]

    def _coerce_level(self, value: Optional[str]) -> Optional[ImpactLevel]:
        if value is None:
            return None
        if isinstance(value, ImpactLevel):
            return value
        try:
            return ImpactLevel(str(value).lower())
        except ValueError:
            logger.debug("[IMPACT][NOTIFY] Unknown impact level %s", value)
            return None

    def _build_summary(
        self,
        report: ImpactReport,
        doc_issues: Sequence[Dict[str, Any]],
        impact_level: ImpactLevel,
    ) -> Dict[str, Any]:
        components = _collect_unique(doc_issues, "component_ids")
        services = _collect_unique(doc_issues, "service_ids")
        docs = _collect_doc_names(doc_issues)
        doc_links = _collect_doc_links(doc_issues)
        change_links = self._collect_change_links(report)
        links = _dedupe_links(change_links + doc_links)
        pr_number = self._extract_pr_number(report, doc_issues)
        change_label = report.change_title or report.change_id

        summary = {
            "impact_level": impact_level,
            "change_id": report.change_id,
            "change_title": report.change_title,
            "components": components,
            "services": services,
            "docs": docs,
            "links": links,
            "pr_number": pr_number,
        }
        summary["slack_text"] = self._format_slack_text(summary, change_label)
        summary["pr_comment"] = self._format_pr_comment(summary, change_label)
        return summary

    def _collect_change_links(self, report: ImpactReport) -> List[Dict[str, str]]:
        links: List[Dict[str, str]] = []
        change_meta = report.metadata.get("change") or {}
        change_details = change_meta.get("metadata") or {}
        change_url = change_details.get("html_url") or change_details.get("url")
        if change_url:
            links.append(
                {
                    "type": "pr" if change_details.get("pr_number") else "git",
                    "label": change_meta.get("title") or report.change_title or report.change_id,
                    "url": change_url,
                }
            )
        for commit in change_details.get("commits") or []:
            commit_url = commit.get("html_url") or commit.get("url")
            if not commit_url:
                continue
            sha = commit.get("sha") or ""
            label = f"Commit {sha[:7]}" if sha else "Commit"
            links.append({"type": "git", "label": label, "url": commit_url})
        slack_meta = report.metadata.get("slack_context") or {}
        if slack_meta.get("permalink"):
            links.append(
                {
                    "type": "slack",
                    "label": slack_meta.get("channel") or "Slack thread",
                    "url": slack_meta["permalink"],
                }
            )
        return links

    def _extract_pr_number(
        self,
        report: ImpactReport,
        doc_issues: Sequence[Dict[str, Any]],
    ) -> Optional[int]:
        change_meta = report.metadata.get("change") or {}
        change_details = change_meta.get("metadata") or {}
        pr_candidate = change_details.get("pr_number")
        if pr_candidate is not None:
            return _safe_int(pr_candidate)
        for issue in doc_issues:
            change_context = issue.get("change_context") or {}
            candidate = change_context.get("pr_number")
            if candidate is not None:
                converted = _safe_int(candidate)
                if converted is not None:
                    return converted
        return None

    def _format_slack_text(
        self,
        summary: Dict[str, Any],
        change_label: Optional[str],
    ) -> str:
        label = change_label or summary["change_id"]
        level = summary["impact_level"].value.title()
        lines = [f"*{level} doc impact* for {label}"]
        if summary["services"]:
            lines.append(f"• Services: {format_preview(summary['services'])}")
        if summary["components"]:
            lines.append(f"• Components: {format_preview(summary['components'])}")
        if summary["docs"]:
            lines.append(f"• Docs: {format_preview(summary['docs'])}")
        link_markup = format_links(summary["links"])
        if link_markup:
            lines.append(f"• Links: {link_markup}")
        return "\n".join(lines)

    def _format_pr_comment(
        self,
        summary: Dict[str, Any],
        change_label: Optional[str],
    ) -> str:
        label = change_label or summary["change_id"]
        level = summary["impact_level"].value.title()
        parts = [
            f"{level} downstream doc impact detected for {label}."
        ]
        if summary["services"]:
            parts.append(f"Affected services: {format_preview(summary['services'], limit=6)}.")
        if summary["docs"]:
            parts.append(f"Affected docs: {format_preview(summary['docs'], limit=6)}.")
        parts.append("See ImpactAlertsPanel / DocIssues for remediation details.")
        return " ".join(parts)


def _collect_unique(
    doc_issues: Sequence[Dict[str, Any]],
    key: str,
) -> List[str]:
    values: List[str] = []
    for issue in doc_issues:
        entries = issue.get(key) or []
        values.extend([str(entry) for entry in entries if entry])
    return sorted(set(values))


def _collect_doc_names(doc_issues: Sequence[Dict[str, Any]]) -> List[str]:
    names = []
    for issue in doc_issues:
        name = issue.get("doc_title") or issue.get("doc_id")
        if name:
            names.append(str(name))
    return sorted(set(names))


def _collect_doc_links(
    doc_issues: Sequence[Dict[str, Any]],
) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []
    for issue in doc_issues:
        doc_url = issue.get("doc_url")
        doc_title = issue.get("doc_title") or issue.get("doc_id")
        if doc_url:
            links.append({"type": "doc", "label": doc_title or "Doc", "url": doc_url})
        for link in issue.get("links") or []:
            if link.get("url"):
                links.append(
                    {
                        "type": link.get("type") or "link",
                        "label": link.get("label") or link.get("type") or "link",
                        "url": link["url"],
                    }
                )
    return links


def _dedupe_links(links: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: Dict[Tuple[str, str], Dict[str, str]] = {}
    for link in links:
        url = link.get("url")
        label = link.get("label") or url
        if not url:
            continue
        key = (label, url)
        if key not in seen:
            seen[key] = {"label": label, "url": url, "type": link.get("type") or "link"}
    return list(seen.values())


def format_links(links: Sequence[Dict[str, str]]) -> str:
    markup = []
    for link in links:
        label = link.get("label") or link.get("type") or "link"
        url = link.get("url")
        if not url:
            continue
        markup.append(f"<{url}|{label}>")
    return ", ".join(markup)


def format_preview(items: Sequence[str], *, limit: int = 4) -> str:
    unique = [item for item in dict.fromkeys(items) if item]
    if not unique:
        return "n/a"
    if len(unique) <= limit:
        return ", ".join(unique)
    remainder = len(unique) - limit
    return f"{', '.join(unique[:limit])} +{remainder} more"


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

