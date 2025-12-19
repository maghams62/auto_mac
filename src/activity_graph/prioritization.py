from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_WEIGHTS = {
    "git": 3.0,
    "issues": 3.0,
    "support": 4.0,
    "slack": 2.0,
    "docs": 1.0,
}

DOC_SEVERITY_WEIGHTS = {
    "critical": 3.0,
    "high": 2.0,
    "medium": 1.2,
    "low": 0.5,
}


def get_activity_signal_weights(config: Optional[Dict[str, Any]]) -> Dict[str, float]:
    config = config or {}
    weights_cfg = ((config.get("activity_signals") or {}).get("weights") or {})
    weights = {}
    for key, default_value in DEFAULT_WEIGHTS.items():
        try:
            weights[key] = float(weights_cfg.get(key, default_value))
        except (TypeError, ValueError):
            weights[key] = default_value
    return weights


def compute_doc_priorities(
    doc_issues: Optional[Iterable[Dict[str, Any]]],
    component_activity: Optional[Dict[str, Any]],
    weights: Dict[str, float],
    *,
    max_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Rank doc issues for Option 1 answers using config-driven weights.
    """
    if not doc_issues or not component_activity:
        return []

    metrics = {
        "git_events": component_activity.get("git_events", 0),
        "slack_conversations": component_activity.get("slack_conversations", 0),
        "slack_complaints": component_activity.get("slack_complaints", 0),
        "open_doc_issues": component_activity.get("open_doc_issues", 0),
    }

    doc_issue_list = [issue for issue in doc_issues if isinstance(issue, dict)]
    if not doc_issue_list:
        return []

    issue_volume_score = _log_signal(len(doc_issue_list))

    ranked: List[Dict[str, Any]] = []
    for issue in doc_issue_list:
        coverage_gap = _coverage_gap_score(issue)
        reason_parts = []
        git_score = _log_signal(metrics["git_events"])
        if git_score > 0:
            reason_parts.append(f"{metrics['git_events']} Git updates")
        slack_signal = _log_signal(metrics["slack_conversations"])
        if slack_signal > 0:
            reason_parts.append(f"{metrics['slack_conversations']} Slack threads")
        support_signal = _log_signal(metrics["slack_complaints"])
        if support_signal > 0:
            reason_parts.append(f"{metrics['slack_complaints']} complaints")
        if issue_volume_score > 0:
            reason_parts.append(f"{len(doc_issue_list)} doc issues open")
        if coverage_gap > 0:
            severity = issue.get("severity") or issue.get("impact_level")
            if severity:
                reason_parts.append(f"severity {severity}")

        score = (
            weights.get("git", 0.0) * git_score
            + weights.get("slack", 0.0) * slack_signal
            + weights.get("support", 0.0) * support_signal
            + weights.get("issues", 0.0) * issue_volume_score
            + weights.get("docs", 0.0) * coverage_gap
        )

        entry = {
            "doc_id": issue.get("doc_id") or issue.get("id"),
            "doc_title": issue.get("doc_title") or issue.get("summary"),
            "doc_url": issue.get("doc_url"),
            "score": round(score, 3),
            "reason": ", ".join(reason_parts) or "Signal levels are low",
            "severity": issue.get("severity"),
            "impact_level": issue.get("impact_level"),
            "links": issue.get("links"),
        }
        issue_id = issue.get("id")
        if issue_id:
            entry["issue_id"] = issue_id
        severity_score = issue.get("severity_score")
        if severity_score is not None:
            entry["severity_score"] = severity_score
        raw_severity = issue.get("severity_score_100")
        if raw_severity is not None:
            entry["severity_score_100"] = raw_severity
        severity_label = issue.get("severity_label")
        if severity_label:
            entry["severity_label"] = severity_label
        breakdown = issue.get("severity_breakdown")
        if breakdown:
            entry["severity_breakdown"] = breakdown
        details = issue.get("severity_details")
        if details:
            entry["severity_details"] = details
        ranked.append(entry)

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:max_results]


def estimate_doc_issue_pressure(doc_issues: Optional[Iterable[Dict[str, Any]]]) -> float:
    """
    Approximate dissatisfaction contribution from doc issues using the shared severity weights.
    """
    if not doc_issues:
        return 0.0
    total = 0.0
    for issue in doc_issues:
        if not isinstance(issue, dict):
            continue
        severity = (issue.get("severity") or issue.get("impact_level") or "").lower()
        total += DOC_SEVERITY_WEIGHTS.get(severity, DOC_SEVERITY_WEIGHTS["medium"])
    return round(total, 2) if total > 0 else 0.0


def _log_signal(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    if numeric <= 0:
        return 0.0
    return math.log1p(numeric)


def _coverage_gap_score(issue: Dict[str, Any]) -> float:
    severity_map = {
        "critical": 1.0,
        "high": 0.85,
        "medium": 0.6,
        "low": 0.35,
    }
    impact_map = {
        "critical": 1.0,
        "high": 0.85,
        "medium": 0.6,
        "low": 0.35,
    }
    severity = severity_map.get(
        (issue.get("severity") or "").lower(),
        0.5,
    )
    impact = impact_map.get(
        (issue.get("impact_level") or "").lower(),
        0.5,
    )
    confidence = issue.get("confidence")
    if confidence is None:
        confidence = 0.5
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(confidence, 1.0))
    return (severity * 0.4) + (impact * 0.4) + (confidence * 0.2)

