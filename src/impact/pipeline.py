"""
High-level orchestration flows for impact analysis.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from ..config.context import ConfigContext, get_config_context
from ..graph import DependencyGraph, DependencyGraphBuilder, GraphIngestor, GraphService
from ..utils.component_ids import normalize_component_ids
from .doc_issues import DocIssueService
from .notification_service import ImpactNotificationService
from .evidence_graph import EvidenceGraphFormatter
from .graph_writer import ImpactGraphWriter
from .impact_analyzer import ImpactAnalyzer
from .models import GitChangePayload, ImpactReport, SlackComplaintContext

logger = logging.getLogger(__name__)


class ImpactPipeline:
    """
    Provides reusable flows for Git webhooks and Slack complaints.
    """

    def __init__(
        self,
        *,
        analyzer: Optional[ImpactAnalyzer] = None,
        dependency_graph: Optional[DependencyGraph] = None,
        graph_service: Optional[GraphService] = None,
        evidence_formatter: Optional[EvidenceGraphFormatter] = None,
        notifier: Optional[Callable[[ImpactReport], None]] = None,
        config_context: Optional[ConfigContext] = None,
    ):
        self._config_context = config_context or get_config_context()
        ctx = self._config_context
        context_settings = ctx.accessor.get_context_resolution_settings()
        impact_settings = context_settings.impact
        self.graph_service = graph_service or GraphService(ctx.data)
        if dependency_graph is None:
            dependency_graph = DependencyGraphBuilder(
                ctx.data,
                graph_service=self.graph_service,
            ).build(write_to_graph=False)
        self.analyzer = analyzer or ImpactAnalyzer(
            dependency_graph,
            graph_service=self.graph_service,
        )
        self.graph = dependency_graph
        self.ingestor = GraphIngestor(self.graph_service)
        evidence_settings = dependency_graph.settings.impact.evidence
        self.evidence_formatter = evidence_formatter or EvidenceGraphFormatter(evidence_settings)
        self.notifier = notifier
        self.notification_service = ImpactNotificationService(impact_settings.notifications)
        impact_cfg = ctx.data.get("impact") or {}
        self.data_mode = (impact_cfg.get("data_mode") or "live").lower()
        ag_cfg = ctx.data.get("activity_graph", {}) or {}
        doc_default = "data/synthetic_git/doc_issues.json" if self.data_mode == "synthetic" else "data/live/doc_issues.json"
        doc_ingest_cfg = (ctx.data.get("activity_ingest") or {}).get("doc_issues") or {}
        doc_issue_path_value = ag_cfg.get("doc_issues_path") or doc_ingest_cfg.get("path") or doc_default
        doc_issue_path = Path(doc_issue_path_value)
        self.doc_issue_service = DocIssueService(doc_issue_path)
        impact_log_default = (
            "data/synthetic_git/impact_events.jsonl" if self.data_mode == "synthetic" else "data/logs/impact_events.jsonl"
        )
        impact_log_path_value = ag_cfg.get("impact_events_path", impact_log_default)
        impact_log_path = Path(impact_log_path_value) if impact_log_path_value else None
        self.impact_graph_writer = ImpactGraphWriter(self.ingestor, impact_log_path)

    # ------------------------------------------------------------------
    # Public flows

    def process_git_event(
        self,
        change: GitChangePayload,
        *,
        slack_context: Optional[SlackComplaintContext] = None,
    ) -> ImpactReport:
        """
        Flow A: triggered by Git webhook payloads.
        """
        report = self.analyzer.analyze_git_change(change, slack_context=slack_context)
        self._persist_git_event(change, report)
        report = self.evidence_formatter.annotate(report)
        self._attach_reasoning_context(report)
        doc_issues = self._publish_report(report)
        self._notify(report, doc_issues)
        return report

    def process_slack_complaint(
        self,
        slack_context: SlackComplaintContext,
        *,
        recent_changes: Optional[List[GitChangePayload]] = None,
    ) -> ImpactReport:
        """
        Flow B: Slack complaint triggers downstream impact lookup.
        """
        if recent_changes:
            seed = recent_changes[0]
            aggregated = []
            for change in recent_changes:
                aggregated.extend(change.files)
            synthetic_change = GitChangePayload(
                identifier=f"slack:{slack_context.thread_id}",
                title=f"Slack complaint {slack_context.thread_id}",
                repo=seed.repo,
                files=aggregated,
            )
        else:
            synthetic_change = GitChangePayload(
                identifier=f"slack:{slack_context.thread_id}",
                title=f"Slack complaint {slack_context.thread_id}",
                repo="__virtual__",
                files=[],
            )
        seed_components = set(slack_context.component_ids or [])
        report = self.analyzer.analyze_git_change(
            synthetic_change,
            slack_context=slack_context,
            seed_components=seed_components,
        )
        self._persist_slack_event(slack_context)
        report = self.evidence_formatter.annotate(report)
        self._attach_reasoning_context(report)
        doc_issues = self._publish_report(report)
        self._notify(report, doc_issues)
        return report

    # ------------------------------------------------------------------
    # Persistence helpers

    def _persist_git_event(self, change: GitChangePayload, report: ImpactReport) -> None:
        if not self.ingestor.available():
            return
        component_ids = normalize_component_ids(entity.entity_id for entity in report.changed_components)
        api_ids = [entity.entity_id for entity in report.impacted_apis]
        properties = {
            "title": change.title,
            "repo": change.repo,
            "merged": change.merged,
        }
        self.ingestor.upsert_git_event(
            change.identifier,
            component_ids=component_ids,
            endpoint_ids=api_ids,
            properties=properties,
        )

    def _persist_slack_event(self, slack_context: SlackComplaintContext) -> None:
        if not self.ingestor.available():
            return
        props = {
            "channel": slack_context.channel,
            "text": slack_context.text,
        }
        self.ingestor.upsert_slack_event(
            slack_context.thread_id,
            component_ids=normalize_component_ids(slack_context.component_ids),
            endpoint_ids=slack_context.api_ids,
            properties=props,
        )

    def _publish_report(self, report: ImpactReport) -> List[Dict[str, Any]]:
        doc_issues: List[Dict[str, Any]] = []
        try:
            if self.doc_issue_service:
                doc_issues = self.doc_issue_service.create_from_impact(report, self.graph)
        except Exception as exc:
            logger.warning("[IMPACT PIPELINE] Failed to persist doc issues: %s", exc)
        try:
            if self.impact_graph_writer:
                self.impact_graph_writer.write(report, self.graph, doc_issues)
        except Exception as exc:
            logger.warning("[IMPACT PIPELINE] Failed to persist impact graph event: %s", exc)
        return doc_issues

    def _attach_reasoning_context(self, report: ImpactReport) -> None:
        context = {
            "impact_chain": self._format_impact_chain(report),
            "repos": sorted(self._collect_reasoning_repos(report)),
            "docs": self._collect_doc_update_entries(report),
            "summary": self._build_reasoning_summary(report),
        }
        report.metadata.setdefault("reasoning_context", {}).update(context)

    def _format_impact_chain(self, report: ImpactReport) -> str:
        changed = report.metadata.get("changed_component_ids") or [
            entity.entity_id for entity in report.changed_components
        ]
        downstream = [entity.entity_id for entity in report.impacted_components]
        chain: List[str] = []
        for component_id in changed + downstream:
            if component_id not in chain:
                chain.append(component_id)
        return " -> ".join(chain)

    def _collect_reasoning_repos(self, report: ImpactReport) -> Set[str]:
        repos: Set[str] = set()
        for entity in report.changed_components + report.impacted_components:
            repo = self.graph.component_to_repo.get(entity.entity_id)
            if repo:
                repos.add(str(repo))
        for doc in report.impacted_docs:
            props = self.graph.docs.get(doc.entity_id, {})
            repo = props.get("repo")
            if repo:
                repos.add(str(repo))
        change_meta = report.metadata.get("change") or {}
        change_repo = change_meta.get("repo")
        if change_repo:
            repos.add(str(change_repo))
        return repos

    def _collect_doc_update_entries(self, report: ImpactReport) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for doc in report.impacted_docs:
            props = self.graph.docs.get(doc.entity_id, {})
            hint = (doc.reason or "").split(". ")[0].strip()
            entries.append(
                {
                    "id": doc.entity_id,
                    "title": props.get("title") or doc.entity_id,
                    "repo": props.get("repo"),
                    "path": props.get("path"),
                    "hint": hint[:280] if hint else "",
                    "impact_level": doc.impact_level.value,
                }
            )
        return entries

    def _build_reasoning_summary(self, report: ImpactReport) -> str:
        doc_count = len(report.impacted_docs)
        component_count = len(report.impacted_components)
        change_title = report.change_title or report.change_id
        return (
            f"{change_title} touched {component_count} downstream component(s) "
            f"and requires updates to {doc_count} doc(s)."
        )

    # ------------------------------------------------------------------
    # Notifications

    def _notify(self, report: ImpactReport, doc_issues: List[Dict[str, Any]]) -> None:
        if self.notification_service:
            try:
                self.notification_service.maybe_notify(report, doc_issues)
            except Exception as exc:
                logger.error("[IMPACT PIPELINE] Optional notification service failed: %s", exc)
        if not self.notifier:
            return
        try:
            self.notifier(report)
        except Exception as exc:
            logger.error("[IMPACT PIPELINE] Notifier failed: %s", exc)

