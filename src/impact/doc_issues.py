"""
Helpers that persist ImpactReports into DocIssue records for downstream consumers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import uuid4

from ..graph.dependency_graph import DependencyGraph
from ..utils.component_ids import normalize_component_ids
from .models import ImpactLevel, ImpactReport, ImpactedEntity

SOURCE_KIND = "impact-report"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _severity_from_level(level: ImpactLevel) -> str:
    if level == ImpactLevel.HIGH:
        return "high"
    if level == ImpactLevel.LOW:
        return "low"
    return "medium"


@dataclass
class DocIssueService:
    """
    Creates or updates DocIssue records produced by cross-system impact analysis.
    """

    path: Path

    def list(self) -> List[Dict[str, Any]]:
        return self._load()

    def create_from_impact(
        self,
        report: ImpactReport,
        graph: DependencyGraph,
    ) -> List[Dict[str, Any]]:
        """
        Create/update DocIssues for each impacted doc in the supplied report.
        """
        if not self.path:
            return []

        existing = self._load()
        issues_by_id = {issue["id"]: issue for issue in existing if issue.get("id")}
        indexed = {self._issue_key(issue): issue for issue in existing if self._issue_key(issue)}

        change_context = self._build_change_context(report)
        links = self._build_links(report)
        updated_records: List[Dict[str, Any]] = []
        dirty = False

        for doc in report.impacted_docs:
            issue_payload, key = self._build_issue_payload(
                doc,
                report,
                graph,
                change_context,
                links,
            )
            if not key:
                continue
            now = _utc_now()
            existing_issue = indexed.get(key)
            if existing_issue:
                merged = existing_issue.copy()
                merged.update(issue_payload)
                merged["id"] = existing_issue.get("id") or issue_payload["id"]
                merged["state"] = existing_issue.get("state", "open")
                merged["created_at"] = existing_issue.get("created_at", merged["detected_at"])
                merged["detected_at"] = existing_issue.get("detected_at", merged["created_at"])
                merged["updated_at"] = now
                indexed[key] = merged
                issues_by_id[merged["id"]] = merged
                updated_records.append(merged)
                dirty = True
                continue

            issue_payload["created_at"] = now
            issue_payload["detected_at"] = now
            issue_payload["updated_at"] = now
            issue_payload["state"] = "open"
            indexed[key] = issue_payload
            issues_by_id[issue_payload["id"]] = issue_payload
            updated_records.append(issue_payload)
            dirty = True

        if dirty:
            payload = sorted(issues_by_id.values(), key=lambda issue: issue.get("updated_at", ""))
            self._save(payload)
        return updated_records

    def create_manual_issue(
        self,
        *,
        title: str,
        summary: str,
        severity: str,
        status: str,
        doc_path: str,
        component_ids: List[str],
        service_ids: Optional[List[str]] = None,
        repo_id: Optional[str] = None,
        doc_url: Optional[str] = None,
        doc_id: Optional[str] = None,
        source: str = "traceability",
        origin_investigation_id: Optional[str] = None,
        evidence_ids: Optional[List[str]] = None,
        links: Optional[List[Dict[str, str]]] = None,
        change_context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.path:
            raise ValueError("DocIssue store is not configured.")
        if not component_ids:
            raise ValueError("component_ids must contain at least one entry.")

        normalized_severity = (severity or "medium").lower()
        normalized_status = (status or "open").lower()
        now = _utc_now()
        canonical_components = normalize_component_ids(component_ids)
        record = {
            "id": f"traceability:{uuid4()}",
            "doc_id": doc_id or f"doc:{doc_path}",
            "doc_title": title,
            "doc_path": doc_path,
            "doc_url": doc_url,
            "repo_id": repo_id,
            "component_ids": canonical_components,
            "service_ids": service_ids or [],
            "impact_level": None,
            "severity": normalized_severity,
            "source": source,
            "linked_change": None,
            "change_context": change_context or {},
            "change_title": title,
            "change_summary": summary,
            "summary": summary,
            "confidence": None,
            "evidence_mode": "manual",
            "evidence_summary": None,
            "links": links or [],
            "metadata": metadata or {},
            "origin_investigation_id": origin_investigation_id,
            "evidence_ids": evidence_ids or [],
            "created_at": now,
            "detected_at": now,
            "updated_at": now,
            "state": normalized_status,
        }

        records = self._load()
        records.append(record)
        self._save(records)
        return record

    # ------------------------------------------------------------------
    # Internal helpers

    def _build_issue_payload(
        self,
        doc: ImpactedEntity,
        report: ImpactReport,
        graph: DependencyGraph,
        change_context: Dict[str, Any],
        links: List[Dict[str, str]],
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        doc_props = graph.docs.get(doc.entity_id, {})
        component_ids = normalize_component_ids(self._resolve_component_ids(doc, graph))
        service_ids = self._resolve_service_ids(component_ids, graph)
        repo_id = self._resolve_repo_id(doc_props, component_ids, graph, report)
        doc_path = self._resolve_doc_path(doc_props, doc.entity_id)
        doc_title = doc_props.get("title") or doc.entity_id
        doc_url = self._build_doc_url(doc_props, doc_path, repo_id)
        linked_change = change_context.get("identifier") or report.change_id
        key = self._make_issue_key(repo_id, doc_path, linked_change)
        if key is None:
            return {}, None

        severity = self._classify_severity(doc)
        issue_id = f"impact:{doc.entity_id}:{linked_change}"
        doc_update_hint = self._build_doc_update_hint(doc, report)
        payload = {
            "id": issue_id,
            "doc_id": doc.entity_id,
            "doc_title": doc_title,
            "doc_path": doc_path,
            "doc_url": doc_url,
            "repo_id": repo_id,
            "component_ids": component_ids,
            "service_ids": service_ids,
            "impact_level": doc.impact_level.value,
            "severity": severity,
            "source": SOURCE_KIND,
            "linked_change": linked_change,
            "change_context": change_context,
            "change_title": report.change_title,
            "change_summary": report.change_summary,
            "summary": doc.reason,
            "confidence": doc.confidence,
            "evidence_mode": report.evidence_mode,
            "evidence_summary": report.evidence_summary,
            "links": list(links),
            "metadata": {
                "doc_metadata": doc.metadata,
            },
            "origin_investigation_id": report.metadata.get("origin_investigation_id"),
            "evidence_ids": doc.metadata.get("evidence_ids")
            or report.metadata.get("evidence_ids")
            or [],
        }
        brain_trace_url = report.metadata.get("brain_trace_url")
        brain_universe_url = report.metadata.get("brain_universe_url")
        cerebros_query_id = report.metadata.get("cerebros_query_id") or report.metadata.get("query_id")
        if brain_trace_url:
            payload["brain_trace_url"] = brain_trace_url
            payload["metadata"]["brain_trace_url"] = brain_trace_url
        if brain_universe_url:
            payload["brain_universe_url"] = brain_universe_url
            payload["metadata"]["brain_universe_url"] = brain_universe_url
        if cerebros_query_id:
            payload["cerebros_query_id"] = cerebros_query_id
            payload["metadata"]["cerebros_query_id"] = cerebros_query_id
        slack_context = report.metadata.get("slack_context") or {}
        if slack_context:
            payload["slack_context"] = slack_context
        if doc_update_hint:
            payload["doc_update_hint"] = doc_update_hint
            payload["metadata"]["doc_update_hint"] = doc_update_hint
        return payload, key

    def _build_change_context(self, report: ImpactReport) -> Dict[str, Any]:
        change_meta = report.metadata.get("change") or {}
        metadata = change_meta.get("metadata") or {}
        slack_meta = report.metadata.get("slack_context") or {}
        link_url = metadata.get("html_url") or metadata.get("url")
        context = {
            "identifier": report.change_id,
            "repo": change_meta.get("repo") or metadata.get("repo_full_name"),
            "title": change_meta.get("title") or report.change_title,
            "url": link_url,
            "commits": metadata.get("commits"),
            "source_kind": "slack" if slack_meta else "git",
        }
        if slack_meta.get("permalink"):
            context["slack_permalink"] = slack_meta["permalink"]
        if slack_meta.get("thread_id"):
            context["slack_thread"] = slack_meta["thread_id"]
        pr_number = metadata.get("pr_number")
        if pr_number is not None:
            context["pr_number"] = pr_number
        return context

    def _resolve_component_ids(self, doc: ImpactedEntity, graph: DependencyGraph) -> List[str]:
        metadata_value = doc.metadata or {}
        component_id = metadata_value.get("component_id")
        ids: List[str] = []
        if component_id:
            ids.append(str(component_id))
        from_graph = graph.doc_to_components.get(doc.entity_id) or set()
        ids.extend(list(from_graph))
        return sorted({value for value in ids if value})

    def _resolve_service_ids(
        self,
        component_ids: Iterable[str],
        graph: DependencyGraph,
    ) -> List[str]:
        services = []
        for component_id in component_ids:
            service_id = graph.service_for_component(component_id)
            if service_id:
                services.append(service_id)
        return sorted({service for service in services if service})

    def _resolve_repo_id(
        self,
        doc_props: Dict[str, Any],
        component_ids: Sequence[str],
        graph: DependencyGraph,
        report: ImpactReport,
    ) -> str:
        repo_value = doc_props.get("repo")
        if repo_value:
            return str(repo_value)
        for component_id in component_ids:
            repo = graph.component_to_repo.get(component_id)
            if repo:
                return str(repo)
        change_meta = report.metadata.get("change") or {}
        repo_hint = change_meta.get("repo")
        if repo_hint:
            return str(repo_hint)
        metadata = change_meta.get("metadata") or {}
        repo_full = metadata.get("repo_full_name")
        if repo_full:
            return str(repo_full)
        return ""

    @staticmethod
    def _resolve_doc_path(doc_props: Dict[str, Any], fallback: str) -> str:
        return str(doc_props.get("path") or doc_props.get("url") or fallback)

    def _build_doc_url(self, doc_props: Dict[str, Any], doc_path: str, repo_id: str) -> str:
        explicit_url = doc_props.get("url")
        if explicit_url:
            return str(explicit_url)

        portal_url = self._portal_url_for_path(doc_path)
        if portal_url:
            return portal_url

        repo_hint = doc_props.get("repo") or repo_id or ""
        normalized_path = doc_path.lstrip("/")
        if "/" in (repo_hint or ""):
            return f"https://github.com/{repo_hint}/blob/main/{normalized_path}"
        if repo_hint:
            return f"{repo_hint}:{normalized_path}"
        return normalized_path
    def _portal_url_for_path(self, doc_path: Optional[str]) -> Optional[str]:
        if not doc_path:
            return None
        docs_cfg = (self.config_context.data.get("docs") or {})
        base = (docs_cfg.get("portal_base_url") or "").strip()
        if not base:
            return None
        normalized = self._normalize_doc_path(doc_path)
        slug_map = docs_cfg.get("portal_slug_map") or {}
        if slug_map.get(doc_path):
            slug = str(slug_map[doc_path]).strip("/")
        else:
            slug = normalized
        if not slug:
            return base.rstrip("/")
        return f"{base.rstrip('/')}/{slug.strip('/')}/"

    @staticmethod
    def _normalize_doc_path(doc_path: str) -> str:
        value = doc_path.strip().lstrip("/")
        if value.endswith(".md"):
            value = value[: -len(".md")]
        if value.startswith("docs-portal/docs/"):
            value = value[len("docs-portal/docs/") :]
        elif value.startswith("docs/"):
            value = value[len("docs/") :]
        return value.strip("/")


    def _classify_severity(self, doc: ImpactedEntity) -> str:
        metadata = doc.metadata or {}
        severity = _severity_from_level(doc.impact_level)
        relation = metadata.get("dependency_relation")
        raw_depth = metadata.get("dependency_depth") or 0
        try:
            depth = int(raw_depth)
        except (TypeError, ValueError):
            depth = 0
        confidence = doc.confidence or 0.0

        if relation == "direct" and confidence >= 0.85:
            return "high"
        if relation == "indirect":
            return "low" if depth and depth >= 2 else "medium"
        return severity

    @staticmethod
    def _build_doc_update_hint(doc: ImpactedEntity, report: ImpactReport) -> Optional[str]:
        candidates = [
            doc.reason,
            report.change_summary,
            report.change_title,
        ]
        for candidate in candidates:
            text = (candidate or "").strip()
            if not text:
                continue
            sentence = text.split(". ")[0].strip()
            return sentence[:280]
        return None

    def _issue_key(self, issue: Dict[str, Any]) -> Optional[str]:
        repo_id = issue.get("repo_id")
        doc_path = issue.get("doc_path")
        linked_change = issue.get("linked_change") or issue.get("source_change")
        return self._make_issue_key(repo_id, doc_path, linked_change)

    @staticmethod
    def _make_issue_key(
        repo_id: Optional[str],
        doc_path: Optional[str],
        linked_change: Optional[str],
    ) -> Optional[str]:
        if not linked_change:
            return None
        key_repo = repo_id or "__unknown_repo__"
        key_path = doc_path or "__unknown_doc__"
        return f"{key_repo}::{key_path}::{linked_change}"

    def _build_links(self, report: ImpactReport) -> List[Dict[str, str]]:
        links: List[Dict[str, str]] = []
        change_meta = report.metadata.get("change") or {}
        change_details = change_meta.get("metadata") or {}
        change_url = change_details.get("html_url") or change_details.get("url")
        if change_url:
            link_type = "pr" if change_details.get("pr_number") else "git"
            links.append(
                {
                    "type": link_type,
                    "label": change_meta.get("title") or change_url,
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

    def _load(self) -> List[Dict[str, Any]]:
        if not self.path or not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text()) or []
        except json.JSONDecodeError:
            return []

    def _save(self, issues: List[Dict[str, Any]]) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(issues, indent=2, sort_keys=True))
