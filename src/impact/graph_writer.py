"""
Utilities for emitting ImpactEvent nodes to Neo4j or a JSONL audit log.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from ..graph import DependencyGraph, GraphIngestor
from .models import ImpactReport


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ImpactGraphWriter:
    """
    Writes ImpactEvents to Neo4j when available, falling back to a JSONL log.
    """

    ingestor: GraphIngestor
    log_path: Optional[Path] = None

    def write(
        self,
        report: ImpactReport,
        graph: DependencyGraph,
        doc_issues: Sequence[Dict[str, Any]],
    ) -> None:
        record = self._build_record(report, graph, doc_issues)
        self._write_to_graph(record)
        self._append_log(record)

    # ------------------------------------------------------------------
    # Builders

    def _build_record(
        self,
        report: ImpactReport,
        graph: DependencyGraph,
        doc_issues: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        component_ids = self._collect_component_ids(report)
        service_ids = self._collect_service_ids(component_ids, graph)
        doc_ids = [entity.entity_id for entity in report.impacted_docs]
        slack_thread_ids = [entity.entity_id for entity in report.slack_threads]
        git_event_ids = self._collect_git_event_ids(report.metadata.get("change") or {})
        doc_issue_ids = [issue.get("id") for issue in doc_issues if issue.get("id")]
        properties = {
            "change_id": report.change_id,
            "change_title": report.change_title,
            "change_summary": report.change_summary,
            "impact_level": report.impact_level.value,
            "evidence_mode": report.evidence_mode,
            "source_kind": self._source_kind(report),
            "recorded_at": _utc_now(),
        }
        return {
            "event_id": report.change_id,
            "properties": properties,
            "component_ids": component_ids,
            "service_ids": service_ids,
            "doc_ids": doc_ids,
            "doc_issue_ids": doc_issue_ids,
            "slack_thread_ids": slack_thread_ids,
            "git_event_ids": git_event_ids,
        }

    def _collect_component_ids(self, report: ImpactReport) -> List[str]:
        ids: Set[str] = set()
        for entity in report.changed_components + report.impacted_components:
            if entity.entity_id:
                ids.add(entity.entity_id)
        return sorted(ids)

    def _collect_service_ids(
        self,
        component_ids: Iterable[str],
        graph: DependencyGraph,
    ) -> List[str]:
        services: Set[str] = set()
        for component_id in component_ids:
            service_id = graph.service_for_component(component_id)
            if service_id:
                services.add(service_id)
        return sorted(services)

    @staticmethod
    def _collect_git_event_ids(change_meta: Dict[str, Any]) -> List[str]:
        identifier = change_meta.get("identifier")
        return [identifier] if identifier else []

    @staticmethod
    def _source_kind(report: ImpactReport) -> str:
        if report.metadata.get("slack_context"):
            return "slack"
        return "git"

    # ------------------------------------------------------------------
    # Writers

    def _write_to_graph(self, record: Dict[str, Any]) -> None:
        if not self.ingestor or not self.ingestor.available():
            return
        self.ingestor.upsert_impact_event(
            record["event_id"],
            properties=record["properties"],
            component_ids=record["component_ids"],
            service_ids=record["service_ids"],
            doc_ids=record["doc_ids"],
            slack_thread_ids=record["slack_thread_ids"],
            git_event_ids=record["git_event_ids"],
        )

    def _append_log(self, record: Dict[str, Any]) -> None:
        if not self.log_path:
            return
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
        except Exception:
            # Logging should not block the impact pipeline; failures are noisy elsewhere.
            pass


