"""
Traceability -> Neo4j ingestion helpers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.graph.service import GraphService

logger = logging.getLogger(__name__)


class TraceabilityNeo4jIngestor:
    """
    Writes investigations, evidence, and DocIssue links into Neo4j.
    """

    def __init__(self, graph_service: GraphService, enabled: bool):
        self.graph_service = graph_service
        self.enabled = bool(enabled and graph_service and graph_service.is_available())

    def upsert_investigation(self, record: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        investigation_id = record.get("id")
        if not investigation_id:
            return
        component_ids: List[str] = [str(cid) for cid in record.get("component_ids", []) if cid]
        params = {
            "id": investigation_id,
            "question": record.get("question"),
            "answer": record.get("answer"),
            "goal": record.get("goal"),
            "status": record.get("status"),
            "plan_id": record.get("plan_id"),
            "session_id": record.get("session_id"),
            "created_at": record.get("created_at"),
            "component_ids": component_ids,
        }
        try:
            self.graph_service.run_write(
                """
                MERGE (i:Investigation {id: $id})
                SET i.question = COALESCE($question, i.question),
                    i.answer = COALESCE($answer, i.answer),
                    i.goal = COALESCE($goal, i.goal),
                    i.status = COALESCE($status, i.status),
                    i.plan_id = COALESCE($plan_id, i.plan_id),
                    i.session_id = COALESCE($session_id, i.session_id),
                    i.created_at = COALESCE($created_at, i.created_at)
                WITH i, $component_ids AS component_ids
                UNWIND component_ids AS component_id
                MERGE (c:Component {id: component_id})
                ON CREATE SET c.name = component_id
                MERGE (i)-[:TOUCHES_COMPONENT]->(c)
                """,
                params,
            )
        except Exception as exc:
            logger.warning("[TRACEABILITY][NEO4J] Failed to upsert investigation %s: %s", investigation_id, exc)
            return

        evidence_entries: List[Dict[str, Any]] = record.get("evidence") or []
        if evidence_entries:
            self._upsert_evidence(investigation_id, evidence_entries, component_ids)

    def _upsert_evidence(
        self,
        investigation_id: str,
        evidence_entries: List[Dict[str, Any]],
        component_ids: List[str],
    ) -> None:
        evidence_payload = [
            {
                "id": entry.get("evidence_id") or entry.get("id"),
                "source": entry.get("source"),
                "title": entry.get("title"),
                "url": entry.get("url"),
            }
            for entry in evidence_entries
            if entry.get("evidence_id") or entry.get("id")
        ]
        if not evidence_payload:
            return
        try:
            self.graph_service.run_write(
                """
                MATCH (i:Investigation {id: $investigation_id})
                WITH i, $evidence AS evidence, $component_ids AS component_ids
                UNWIND evidence AS ev
                MERGE (e:Evidence {id: ev.id})
                SET e.source = COALESCE(ev.source, e.source),
                    e.title = COALESCE(ev.title, e.title),
                    e.url = COALESCE(ev.url, e.url)
                MERGE (i)-[:EMITTED]->(e)
                WITH e, component_ids
                UNWIND component_ids AS component_id
                MERGE (c:Component {id: component_id})
                MERGE (e)-[:REFERENCES_COMPONENT]->(c)
                """,
                {
                    "investigation_id": investigation_id,
                    "evidence": evidence_payload,
                    "component_ids": component_ids,
                },
            )
        except Exception as exc:
            logger.warning("[TRACEABILITY][NEO4J] Failed to upsert evidence for %s: %s", investigation_id, exc)

    def link_doc_issue(self, issue_record: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        investigation_id = issue_record.get("origin_investigation_id")
        if not investigation_id:
            return
        component_ids: List[str] = [str(cid) for cid in issue_record.get("component_ids", []) if cid]
        evidence_ids: List[str] = [str(eid) for eid in issue_record.get("evidence_ids", []) if eid]
        params = {
            "issue_id": issue_record.get("id"),
            "title": issue_record.get("doc_title") or issue_record.get("summary"),
            "summary": issue_record.get("summary"),
            "severity": issue_record.get("severity"),
            "state": issue_record.get("state"),
            "component_ids": component_ids,
            "evidence_ids": evidence_ids,
            "investigation_id": investigation_id,
        }
        if not params["issue_id"]:
            return
        try:
            self.graph_service.run_write(
                """
                MERGE (issue:DocIssue {id: $issue_id})
                SET issue.title = COALESCE($title, issue.title),
                    issue.summary = COALESCE($summary, issue.summary),
                    issue.severity = COALESCE($severity, issue.severity),
                    issue.state = COALESCE($state, issue.state)
                WITH issue, $component_ids AS component_ids
                UNWIND component_ids AS component_id
                MERGE (c:Component {id: component_id})
                MERGE (issue)-[:AFFECTS_COMPONENT]->(c)
                WITH issue
                MATCH (i:Investigation {id: $investigation_id})
                MERGE (i)-[:SUPPORTS]->(issue)
                WITH issue
                UNWIND $evidence_ids AS evidence_id
                MATCH (e:Evidence {id: evidence_id})
                MERGE (e)-[:CITED_IN]->(issue)
                """,
                params,
            )
        except Exception as exc:
            logger.warning("[TRACEABILITY][NEO4J] Failed to link doc issue %s: %s", params["issue_id"], exc)

