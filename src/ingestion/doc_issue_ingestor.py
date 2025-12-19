"""
Doc issue ingestion pipeline for syncing Impact-generated issues into Neo4j.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..graph import GraphIngestor, GraphService
from ..utils.component_ids import normalize_component_ids

logger = logging.getLogger(__name__)


class DocIssueIngestor:
    """
    Loads persisted doc issues (produced by the impact pipeline) and upserts them
    into the activity graph so downstream analytics/visualizations can treat them
    like first-class "ticket" nodes.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        *,
        graph_service: Optional[GraphService] = None,
    ):
        activity_cfg = config.get("activity_ingest") or {}
        doc_cfg = activity_cfg.get("doc_issues") or {}
        self.enabled: bool = bool(doc_cfg.get("enabled", False))
        self.path = Path(doc_cfg.get("path", "data/live/doc_issues.json"))
        self.graph_service = graph_service or GraphService(config)
        self.graph_ingestor = GraphIngestor(self.graph_service)
        self._default_component: str | None = doc_cfg.get("default_component")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def ingest(self) -> Dict[str, int]:
        if not self.enabled:
            logger.info("[DOC ISSUES] Ingestion disabled via config.")
            return {"issues": 0}

        if not self.path.exists():
            logger.warning("[DOC ISSUES] Doc issue file not found: %s", self.path)
            return {"issues": 0}

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8")) or []
        except json.JSONDecodeError as exc:
            logger.error("[DOC ISSUES] Failed to parse %s: %s", self.path, exc)
            return {"issues": 0}

        if not isinstance(payload, list):
            logger.error("[DOC ISSUES] Expected a list in %s, got %s", self.path, type(payload))
            return {"issues": 0}

        processed = 0
        for record in payload:
            if not isinstance(record, dict):
                logger.debug("[DOC ISSUES] Skipping non-dict record: %s", record)
                continue
            try:
                self._upsert_issue(record)
                processed += 1
            except Exception:
                logger.exception("[DOC ISSUES] Failed to ingest record %s", record.get("id"))

        logger.info("[DOC ISSUES] Upserted %s issues from %s", processed, self.path)
        return {"issues": processed}

    def close(self) -> None:
        if self.graph_service:
            self.graph_service.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _upsert_issue(self, issue: Dict[str, Any]) -> None:
        if not self.graph_ingestor.available():
            return

        issue_id = issue.get("id") or issue.get("issue_id")
        if not issue_id:
            logger.debug("[DOC ISSUES] Skipping record without id: %s", issue)
            return

        component_ids = self._coerce_ids(issue.get("component_ids"))
        if not component_ids and self._default_component:
            component_ids = [self._default_component]
        if not component_ids:
            logger.debug("[DOC ISSUES] Skipping issue %s without component mapping", issue_id)
            return

        endpoint_ids = self._coerce_ids(issue.get("api_ids") or issue.get("endpoint_ids"))
        doc_id = issue.get("doc_id")
        doc_ids = [doc_id] if doc_id else []

        props = {
            "title": issue.get("doc_title") or issue.get("change_title"),
            "summary": issue.get("summary") or issue.get("change_summary"),
            "severity": (issue.get("severity") or "medium").lower(),
            "state": issue.get("state") or issue.get("status") or "open",
            "source": issue.get("source") or "impact-report",
            "linked_change": issue.get("linked_change") or (issue.get("change_context") or {}).get("identifier"),
            "doc_id": doc_id,
            "doc_path": issue.get("doc_path"),
            "doc_url": issue.get("doc_url"),
            "repo_id": issue.get("repo_id"),
            "impact_level": issue.get("impact_level"),
            "confidence": issue.get("confidence"),
            "updated_at": issue.get("updated_at"),
            "created_at": issue.get("created_at"),
            "detected_at": issue.get("detected_at"),
            "evidence_mode": issue.get("evidence_mode"),
        }
        props = {key: value for key, value in props.items() if value is not None}

        tags = issue.get("labels") or issue.get("tags") or []
        if tags:
            props["labels"] = list(sorted({str(tag) for tag in tags}))

        self.graph_ingestor.upsert_issue(
            issue_id=str(issue_id),
            component_ids=component_ids,
            endpoint_ids=endpoint_ids,
            doc_ids=doc_ids,
            properties=props,
        )

        # Mirror doc issues as lightweight support cases so dissatisfaction metrics can weight them.
        sentiment_weight = self._severity_weight(props.get("severity"))
        case_id = f"support:doc_issue:{issue_id}"
        self.graph_ingestor.upsert_support_case(
            case_id=case_id,
            component_ids=component_ids,
            endpoint_ids=endpoint_ids,
            properties={
                "source": "doc_issue",
                "issue_id": issue_id,
                "title": props.get("title"),
                "severity": props.get("severity"),
            },
            sentiment_weight=sentiment_weight,
            last_seen=props.get("updated_at"),
        )

    @staticmethod
    def _coerce_ids(value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, str):
            return normalize_component_ids([value])
        if isinstance(value, Iterable):
            ids: List[str] = []
            for item in value:
                if not item:
                    continue
                ids.append(str(item))
            return normalize_component_ids(ids)
        return []

    @staticmethod
    def _severity_weight(severity: Optional[str]) -> float:
        normalized = (severity or "medium").lower()
        if normalized == "critical":
            return 4.0
        if normalized == "high":
            return 3.0
        if normalized == "medium":
            return 2.0
        return 1.0


__all__ = ["DocIssueIngestor"]

