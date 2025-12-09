from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BaseModalityHandler
from ...impact.doc_issues import DocIssueService

logger = logging.getLogger(__name__)


class DocIssuesModalityHandler(BaseModalityHandler):
    """
    Modality handler that surfaces persisted DocIssues for universal search.
    """

    _SEVERITY_WEIGHTS = {
        "critical": 3.0,
        "high": 2.0,
        "medium": 1.2,
        "low": 0.5,
    }

    def __init__(
        self,
        modality_config,
        app_config: Dict[str, Any],
        *,
        doc_issue_service: Optional[DocIssueService] = None,
    ):
        super().__init__(modality_config)
        self.app_config = app_config
        path_value = self._resolve_doc_issue_path(app_config, modality_config.scope or {})
        self.doc_issue_path = Path(path_value) if path_value else None
        self.doc_issue_service = doc_issue_service or (
            DocIssueService(path=self.doc_issue_path) if self.doc_issue_path else None
        )

    def can_query(self) -> bool:
        return bool(self.doc_issue_service and self.doc_issue_path)

    def ingest(self, *, scope_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        issues = self._load_doc_issues()
        return {
            "doc_issues": len(issues),
            "path": str(self.doc_issue_path) if self.doc_issue_path else None,
        }

    def query(self, query_text: str, *, limit: int | None = None) -> List[Dict[str, Any]]:
        issues = self._load_doc_issues()
        if not issues:
            return []

        component_hint = self._extract_component_token(query_text)
        ranked = sorted(
            issues,
            key=lambda issue: self._score_issue(issue, query_text, component_hint),
            reverse=True,
        )
        max_results = limit or self.modality_config.max_results
        weight = self.modality_config.weight

        results: List[Dict[str, Any]] = []
        for issue in ranked[: max(1, max_results)]:
            raw_score = self._score_issue(issue, query_text, component_hint)
            results.append(
                {
                    "modality": self.modality_id,
                    "source_type": "doc_issue",
                    "entity_id": issue.get("id"),
                    "title": issue.get("doc_title") or issue.get("doc_path") or issue.get("id"),
                    "text": issue.get("summary"),
                    "score": raw_score * weight,
                    "raw_score": raw_score,
                    "url": issue.get("doc_url") or self._first_link(issue) or issue.get("doc_path"),
                    "metadata": {
                        "severity": issue.get("severity"),
                        "component_ids": issue.get("component_ids") or [],
                        "service_ids": issue.get("service_ids") or [],
                        "doc_path": issue.get("doc_path"),
                        "doc_issue_id": issue.get("id"),
                        "state": issue.get("state"),
                        "source": issue.get("source"),
                        "updated_at": issue.get("updated_at"),
                    },
                }
            )

        return results

    def _load_doc_issues(self) -> List[Dict[str, Any]]:
        if not self.doc_issue_service:
            return []
        try:
            return self.doc_issue_service.list()
        except Exception as exc:
            logger.warning("[SEARCH][DOC_ISSUES] Unable to read doc issues: %s", exc)
            return []

    @staticmethod
    def _resolve_doc_issue_path(app_config: Dict[str, Any], scope: Dict[str, Any]) -> Optional[str]:
        if scope.get("path"):
            return scope["path"]

        ag_cfg = app_config.get("activity_graph") or {}
        if ag_cfg.get("doc_issues_path"):
            return ag_cfg["doc_issues_path"]

        ingest_cfg = (app_config.get("activity_ingest") or {}).get("doc_issues") or {}
        if ingest_cfg.get("path"):
            return ingest_cfg["path"]

        return "data/live/doc_issues.json"

    @classmethod
    def _score_issue(cls, issue: Dict[str, Any], query: str, component_hint: Optional[str]) -> float:
        severity = str(issue.get("severity") or "medium").lower()
        severity_score = cls._SEVERITY_WEIGHTS.get(severity, 1.0)

        timestamp = issue.get("updated_at") or issue.get("detected_at")
        recency_multiplier = 1.0
        if timestamp:
            parsed = cls._parse_timestamp(timestamp)
            if parsed:
                age_hours = (datetime.now(tz=parsed.tzinfo or timezone.utc) - parsed).total_seconds() / 3600.0
                if age_hours <= 24:
                    recency_multiplier = 1.0
                elif age_hours <= 24 * 7:
                    recency_multiplier = 0.7
                else:
                    recency_multiplier = 0.4

        query_bonus = 0.0
        normalized_query = (query or "").lower()
        if normalized_query:
            haystack = " ".join(
                str(issue.get(field) or "").lower()
                for field in ("summary", "doc_title", "doc_path")
            )
            if normalized_query in haystack:
                query_bonus += 0.5
        if component_hint and component_hint in (issue.get("component_ids") or []):
            query_bonus += 0.5

        return severity_score * recency_multiplier + query_bonus

    @staticmethod
    def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            if value.endswith("Z"):
                value = value.replace("Z", "+00:00")
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _extract_component_token(query: str) -> Optional[str]:
        if not query:
            return None
        for token in query.replace(",", " ").split():
            token = token.strip()
            if token.startswith("comp:"):
                return token
        return None

    @staticmethod
    def _first_link(issue: Dict[str, Any]) -> Optional[str]:
        links = issue.get("links") or []
        for link in links:
            if isinstance(link, dict) and link.get("url"):
                return link["url"]
        return None

