from __future__ import annotations

import copy
import json
import logging
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.activity_graph.prioritization import (
    compute_doc_priorities,
    estimate_doc_issue_pressure,
    get_activity_signal_weights,
)
from src.agent.doc_insights_agent import (
    get_component_activity as get_component_activity_tool,
    get_context_impacts as get_context_impacts_tool,
    list_doc_issues as list_doc_issues_tool,
    resolve_component_id as resolve_component_id_tool,
)
from src.agent.multi_source_reasoner import MultiSourceReasoner
from src.utils.git_urls import determine_repo_owner_override, rewrite_github_url

logger = logging.getLogger(__name__)

def _find_traceability_matches(
    *,
    config: Optional[Dict[str, Any]],
    query: str,
    component_hints: Sequence[str],
) -> List[Dict[str, Any]]:
    """
    Placeholder for future traceability enrichment.

    The production system can hydrate reasoning with previously recorded traceability
    evidence. When that infrastructure is unavailable we simply return an empty list
    so the Cerebros graph pipeline continues to function instead of raising.
    """
    traceability_cfg = (config or {}).get("traceability") or {}
    if not traceability_cfg.get("enabled"):
        return []

    logger.debug(
        "[CEREBROS][GRAPH] Traceability enrichment disabled or not implemented "
        "(query=%s, hints=%s).",
        query,
        ", ".join(component_hints) if component_hints else "none",
    )
    return []


def _inject_traceability_evidence(
    evidence_payload: Optional[Dict[str, Any]],
    matches: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not matches:
        return evidence_payload or {}

    payload = dict(evidence_payload or {})
    evidence_list = list(payload.get("evidence") or [])
    seen_ids = {str(entry.get("evidence_id") or entry.get("id")) for entry in evidence_list if isinstance(entry, dict)}

    for match in matches:
        for entry in match.get("evidence", []):
            if not isinstance(entry, dict):
                continue
            evidence_id = str(entry.get("evidence_id") or entry.get("id") or len(evidence_list))
            if evidence_id in seen_ids:
                continue
            evidence_list.append(entry)
            seen_ids.add(evidence_id)

    payload["evidence"] = evidence_list
    return payload


def _apply_traceability_structured_fields(
    doc_insights_bundle: Dict[str, Any],
    matches: Sequence[Dict[str, Any]],
    component_ids: List[str],
) -> None:
    if not matches or not isinstance(doc_insights_bundle, dict):
        return

    for match in matches:
        # Merge in any structured fields (component activity, impacts, etc.)
        extra_doc_insights = match.get("doc_insights")
        if isinstance(extra_doc_insights, dict):
            for key, value in extra_doc_insights.items():
                doc_insights_bundle.setdefault(key, value)

        # Expand component hints if traceability has known components
        for component in match.get("components") or []:
            if not component:
                continue
            if component not in component_ids:
                component_ids.append(component)

INCIDENT_SLICE_CYPHER = """
MATCH (component:Component {id: $component_id})
MATCH (incident:Investigation)-[:TOUCHES_COMPONENT]->(component)
OPTIONAL MATCH (incident)-[:SUPPORTS]->(issue:DocIssue)
OPTIONAL MATCH (incident)-[:EMITTED]->(evidence:Evidence)
RETURN DISTINCT
    incident.id AS investigation_id,
    coalesce(incident.question, incident.summary) AS question,
    incident.status AS status,
    incident.created_at AS created_at,
    collect(DISTINCT issue.id) AS doc_issue_ids,
    collect(DISTINCT evidence.id) AS evidence_ids
ORDER BY coalesce(incident.created_at, datetime({epochMillis: 0})) DESC
LIMIT 25
"""


@dataclass
class CerebrosReasonerResult:
    query: str
    summary: str
    response_payload: Dict[str, Any]
    evidence_payload: Dict[str, Any]
    doc_insights: Optional[Dict[str, Any]]
    cerebros_answer: Dict[str, Any]
    sources_queried: List[str]
    summary_context: Optional[Dict[str, Any]] = None
    sources_without_evidence: Optional[List[str]] = None
    drift_hints: Optional[Dict[str, Any]] = None
    component_ids: Optional[List[str]] = None
    issue_id: Optional[str] = None
    project_id: Optional[str] = None
    conflicts: Optional[List[Dict[str, Any]]] = None
    information_gaps: Optional[List[Dict[str, Any]]] = None


def get_enabled_reasoner_sources(config: Dict[str, Any]) -> List[str]:
    """
    Public helper so callers can inspect which sources the MultiSourceReasoner
    will use for the current configuration snapshot.
    """
    return MultiSourceReasoner.determine_enabled_sources(config)


def run_cerebros_reasoner(
    *,
    config: Dict[str, Any],
    query: str,
    graph_params: Optional[Dict[str, Any]] = None,
    sources: Optional[Sequence[str]] = None,
) -> CerebrosReasonerResult:
    """
    Execute the multi-source Cerebros reasoning pipeline and return a normalized payload.
    """
    if not query or not query.strip():
        raise ValueError("Query is required for Cerebros reasoner")

    config = config or {}
    graph_params = copy.deepcopy(graph_params) if graph_params else {}
    repo_owner_override = determine_repo_owner_override(config)

    component_id = (
        graph_params.get("componentId")
        or graph_params.get("component_id")
        or graph_params.get("component")
    )
    issue_id = graph_params.get("issueId") or graph_params.get("issue_id")
    project_id = graph_params.get("projectId") or graph_params.get("project_id")

    enabled_sources = get_enabled_reasoner_sources(config)
    requested_sources = list(sources) if sources else []
    if requested_sources:
        filtered_sources = [src for src in requested_sources if src in enabled_sources]
        if not filtered_sources:
            logger.warning(
                "[CEREBROS][GRAPH] Requested sources=%s but none are enabled (enabled=%s)",
                requested_sources,
                enabled_sources,
            )
        sources = filtered_sources or enabled_sources
    else:
        sources = enabled_sources

    reasoner = MultiSourceReasoner(config)
    result = reasoner.query(query=query, sources=list(sources))

    summary = result.get("summary") or "Graph reasoning completed."
    sources_queried = result.get("sources_queried") or list(sources)
    summary_context = result.get("summary_context") or {}
    sources_without_evidence = result.get("sources_without_evidence") or []
    drift_hints = result.get("drift_hints") or {}
    conflicts = result.get("conflicts") or []
    information_gaps = result.get("gaps") or []

    evidence_payload = result.get("evidence") or {}
    if not isinstance(evidence_payload, dict):
        evidence_payload = {"evidence": evidence_payload}
    traceability_hints: List[str] = []
    if component_id:
        traceability_hints.append(component_id)
    extra_hint = graph_params.get("component_hint")
    if extra_hint and extra_hint not in traceability_hints:
        traceability_hints.append(extra_hint)

    traceability_matches = _find_traceability_matches(
        config=config,
        query=query,
        component_hints=traceability_hints,
    )
    if traceability_matches:
        evidence_payload = _inject_traceability_evidence(evidence_payload, traceability_matches)

    doc_insights_bundle: Dict[str, Any] = {}
    component_ids: List[str] = []
    canonical_component_id: Optional[str] = component_id
    if component_id:
        component_ids.append(component_id)

    context_resolution_cfg = (config.get("context_resolution") or {})
    impact_settings = context_resolution_cfg.get("impact", {}) or {}
    impact_depth = int(
        graph_params.get("impactDepth")
        or graph_params.get("maxDepth")
        or impact_settings.get("default_max_depth", 2)
    )

    graph_cfg = (config.get("graph") or {})
    graph_enabled = bool(graph_cfg.get("enabled", False))

    component_hint = component_id or extra_hint
    if component_hint:
        resolved_component = resolve_component_id_tool.invoke({"name": component_hint})
        if isinstance(resolved_component, dict) and not resolved_component.get("error"):
            doc_insights_bundle["resolved_component"] = resolved_component
            canonical_component_id = resolved_component.get("component_id") or component_id
            if canonical_component_id and canonical_component_id not in component_ids:
                component_ids.append(canonical_component_id)

    component_activity: Optional[Dict[str, Any]] = None
    doc_issues_payload: Optional[Dict[str, Any]] = None

    if not canonical_component_id:
        guessed_component = _guess_component_from_query(query)
        if guessed_component:
            doc_insights_bundle["resolved_component"] = guessed_component
            canonical_component_id = guessed_component.get("component_id")
            if canonical_component_id and canonical_component_id not in component_ids:
                component_ids.append(canonical_component_id)
        if not canonical_component_id:
            # Record why graph context/dependency impacts could not be computed.
            doc_insights_bundle.setdefault(
                "context_impacts",
                {
                    "reason": "No component_id could be resolved for this query; graph context was skipped.",
                },
            )
            logger.info(
                "[CEREBROS][GRAPH] Skipping context impacts – no component_id resolved (query=%s)",
                query,
            )

    if canonical_component_id:
        activity_window = (
            graph_params.get("activityWindow")
            or graph_params.get("window")
            or "7d"
        )
        component_activity = _invoke_tool_safely(
            get_component_activity_tool,
            {"component_id": canonical_component_id, "window": activity_window},
        )
        if component_activity:
            doc_insights_bundle["component_activity"] = component_activity

        doc_issues_payload = _invoke_tool_safely(
            list_doc_issues_tool,
            {"component_id": canonical_component_id},
        )
        if doc_issues_payload:
            doc_insights_bundle["doc_issues"] = doc_issues_payload

        if graph_enabled:
            context_impacts_payload = _invoke_tool_safely(
                get_context_impacts_tool,
                {
                    "component_id": canonical_component_id,
                    "depth": impact_depth,
                    "include_docs": True,
                    "include_services": True,
                },
            )
            if context_impacts_payload:
                doc_insights_bundle["context_impacts"] = context_impacts_payload
                _attach_graph_query_metadata(
                    doc_insights_bundle,
                    "context_impacts",
                    context_impacts_payload.get("graph_query"),
                )
        else:
            # Graph is disabled; record a structured reason instead of attempting queries.
            doc_insights_bundle.setdefault(
                "context_impacts",
                {
                    "reason": "Graph integration is disabled; dependency impacts and Cypher slices are unavailable.",
                },
            )
            logger.info(
                "[CEREBROS][GRAPH] Skipping context impacts – graph disabled in configuration (query=%s)",
                query,
            )
        _attach_incident_slice_query(doc_insights_bundle, canonical_component_id)

        if traceability_matches:
            _apply_traceability_structured_fields(
                doc_insights_bundle,
                traceability_matches,
                component_ids,
            )

        if component_activity and doc_issues_payload:
            weights = get_activity_signal_weights(config)
            priorities = compute_doc_priorities(
                doc_issues_payload.get("doc_issues"),
                component_activity,
                weights,
            )
            if priorities:
                doc_insights_bundle["doc_priorities"] = priorities

    doc_insights = doc_insights_bundle or None

    cerebros_answer = _build_cerebros_answer(
        query=query,
        summary=summary,
        evidence_payload=evidence_payload,
        doc_insights=doc_insights,
        component_ids=component_ids,
        owner_override=repo_owner_override,
        conflicts=conflicts,
        information_gaps=information_gaps,
    )

    if (
        doc_insights
        and cerebros_answer.get("option") == "activity_graph"
    ):
        narrative_context = _build_option1_context(
            doc_insights=doc_insights,
            doc_priorities=cerebros_answer.get("doc_priorities"),
            allowed_sources=sources,
        )
        if narrative_context:
            try:
                narrative = Option1NarrativeGenerator(config).generate(
                    query=query,
                    context=narrative_context,
                )
                if narrative:
                    cerebros_answer["answer"] = narrative
                    if narrative_context.get("source_payload"):
                        cerebros_answer["sources"] = narrative_context["source_payload"]
                    cerebros_answer["analysis_context"] = narrative_context
            except Exception as exc:  # pragma: no cover - narrative failures shouldn't crash pipeline
                logger.warning(
                    "[CEREBROS][GRAPH] Option1 narrative generation failed: %s",
                    exc,
                )

    response_payload: Dict[str, Any] = {
        "query": query,
        "summary": summary,
        "sources": sources_queried,
        "evidence": evidence_payload,
        "graphParams": graph_params,
        "message": "Graph reasoning completed.",
        "cerebros_answer": cerebros_answer,
    }
    severity_payload = _extract_severity_payload(cerebros_answer.get("doc_priorities"))
    if severity_payload:
        response_payload.update(severity_payload)
    if doc_insights:
        response_payload["doc_insights"] = doc_insights
    if summary_context:
        response_payload["summary_context"] = summary_context
    if sources_without_evidence:
        response_payload["sources_without_evidence"] = sources_without_evidence
    if drift_hints:
        response_payload["drift_hints"] = drift_hints
    if conflicts:
        response_payload["conflicts"] = conflicts
    if information_gaps:
        response_payload["gaps"] = information_gaps

    component_ids_out = component_ids or None
    return CerebrosReasonerResult(
        query=query,
        summary=summary,
        response_payload=response_payload,
        evidence_payload=evidence_payload,
        doc_insights=doc_insights,
        cerebros_answer=cerebros_answer,
        sources_queried=sources_queried,
        summary_context=summary_context or None,
        sources_without_evidence=sources_without_evidence or None,
        drift_hints=drift_hints or None,
        component_ids=component_ids_out,
        issue_id=issue_id,
        project_id=project_id,
        conflicts=conflicts or None,
        information_gaps=information_gaps or None,
    )


def _invoke_tool_safely(tool, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        result = tool.invoke(payload)
    except Exception as exc:  # pragma: no cover - defensive safety net
        logger.warning("[CEREBROS][GRAPH] Tool %s failed: %s", getattr(tool, "name", tool), exc)
        return None
    if not isinstance(result, dict):
        return None
    if result.get("error"):
        return None
    return result


def _attach_graph_query_metadata(
    target: Dict[str, Any],
    label: str,
    payload: Optional[Dict[str, Any]],
) -> None:
    if not payload:
        return
    graph_bucket = target.setdefault("graph_query", {})
    if isinstance(graph_bucket, dict):
        graph_bucket[label] = payload


def _attach_incident_slice_query(target: Dict[str, Any], component_id: Optional[str]) -> None:
    if not component_id:
        return
    graph_bucket = target.setdefault("graph_query", {})
    if isinstance(graph_bucket, dict):
        graph_bucket["incident_slice"] = {
            "label": "incident_slice",
            "cypher": INCIDENT_SLICE_CYPHER.strip(),
            "params": {"component_id": component_id},
        }


def _classify_cerebros_option(
    query: str,
    doc_insights: Optional[Dict[str, Any]],
) -> str:
    normalized = (query or "").lower()
    option1_keywords = [
        "activity",
        "activity graph",
        "dissatisfaction",
        "dissatisfied",
        "complaint",
        "complaints",
        "doc issue",
        "doc issues",
        "documentation health",
        "docs causing pain",
        "prioritize docs",
        "doc prioritization",
        "documentation drift",
        "doc drift",
    ]
    option2_keywords = [
        "blast radius",
        "downstream",
        "upstream",
        "impact",
        "impacted",
        "impacting",
        "depends on",
        "dependencies",
        "dependency",
        "ripple effect",
        "who depends",
        "which services depend",
        "callers",
        "consumers",
    ]

    option2_hit = any(keyword in normalized for keyword in option2_keywords)
    option1_hit = any(keyword in normalized for keyword in option1_keywords)

    if option2_hit:
        return "cross_system_context"
    if option1_hit:
        return "activity_graph"

    if isinstance(doc_insights, dict):
        has_activity = bool(doc_insights.get("component_activity"))
        has_impacts = bool(doc_insights.get("context_impacts"))
        has_doc_priorities = bool(doc_insights.get("doc_priorities"))
        has_doc_issues = bool((doc_insights.get("doc_issues") or {}).get("doc_issues"))

        if has_doc_priorities or has_doc_issues:
            if not option2_hit:
                return "activity_graph"

        if has_activity and has_impacts:
            # Fall back to cross-system context only when we have explicit impact data
            # and no doc-prioritization cues.
            return "cross_system_context"
        if has_activity:
            return "activity_graph"
        if has_impacts:
            return "cross_system_context"

    return "generic"


def _build_cerebros_sources_from_evidence(
    evidence_payload: Any,
    *,
    owner_override: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not evidence_payload:
        return []

    raw_items: List[Dict[str, Any]] = []
    if isinstance(evidence_payload, dict):
        raw = evidence_payload.get("evidence")
        if isinstance(raw, list):
            raw_items = [item for item in raw if isinstance(item, dict)]
    elif isinstance(evidence_payload, list):
        raw_items = [item for item in evidence_payload if isinstance(item, dict)]

    sources: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()

    for item in raw_items:
        source_type = (item.get("source_type") or item.get("sourceType") or "").lower()
        url = item.get("url")
        url = rewrite_github_url(url, owner_override=owner_override)
        if not url or not isinstance(url, str):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)

        label = item.get("source_name") or item.get("title") or url
        metadata = item.get("metadata") or {}

        if source_type == "slack":
            sources.append(
                {
                    "type": "slack",
                    "label": label,
                    "url": url,
                    "channel": metadata.get("channel") or metadata.get("channel_name"),
                    "component": metadata.get("component_id"),
                }
            )
        elif source_type == "git":
            sources.append(
                {
                    "type": "git",
                    "label": label,
                    "url": url,
                    "repo": metadata.get("repo") or metadata.get("repository"),
                    "pr": metadata.get("pr_number") or metadata.get("number"),
                    "component": metadata.get("component_id"),
                }
            )
        elif source_type in {"docs", "doc", "documentation"}:
            sources.append(
                {
                    "type": "doc",
                    "label": label,
                    "url": url,
                    "doc_id": item.get("entity_id"),
                    "component": metadata.get("component") or metadata.get("component_id"),
                }
            )
        elif source_type in {"issues", "issue", "ticket"}:
            sources.append(
                {
                    "type": "issue",
                    "label": label,
                    "url": url,
                    "tracker": metadata.get("tracker"),
                    "key": metadata.get("key") or metadata.get("id"),
                    "component": metadata.get("component_id"),
                }
            )
        elif source_type in {"doc_issue", "doc_issues"}:
            sources.append(
                {
                    "type": "doc_issue",
                    "label": label,
                    "url": url,
                    "severity": metadata.get("severity"),
                    "doc_path": metadata.get("doc_path"),
                    "components": metadata.get("component_ids") or metadata.get("component"),
                    "id": metadata.get("doc_issue_id") or item.get("entity_id"),
                }
            )

    return sources


def _doc_priority_sources(
    priorities: Optional[Sequence[Dict[str, Any]]],
    *,
    owner_override: Optional[str] = None,
) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    if not priorities:
        return sources
    for entry in priorities:
        if not isinstance(entry, dict):
            continue
        url = rewrite_github_url(entry.get("doc_url"), owner_override=owner_override)
        if not url:
            continue
        label = entry.get("doc_title") or entry.get("doc_id") or url
        sources.append(
            {
                "type": "doc",
                "label": label,
                "url": url,
                "doc_id": entry.get("doc_id"),
                "component": entry.get("component_id"),
            }
        )
    return sources


def _doc_issue_sources(
    doc_issues_payload: Optional[Dict[str, Any]],
    *,
    owner_override: Optional[str] = None,
) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    if not isinstance(doc_issues_payload, dict):
        return sources
    doc_issues = doc_issues_payload.get("doc_issues")
    if not isinstance(doc_issues, list):
        return sources
    for issue in doc_issues:
        if not isinstance(issue, dict):
            continue
        url = rewrite_github_url(issue.get("doc_url"), owner_override=owner_override)
        if not url:
            links = issue.get("links")
            if isinstance(links, list) and links:
                url = rewrite_github_url(links[0].get("url"), owner_override=owner_override)
        if not url:
            continue
        label = issue.get("doc_title") or issue.get("doc_id") or issue.get("summary")
        if not label:
            continue
        components = issue.get("component_ids") or []
        sources.append(
            {
                "type": "doc",
                "label": label,
                "url": url,
                "doc_id": issue.get("doc_id"),
                "component": components[0] if components else None,
            }
        )
    return sources


def _build_option1_context(
    *,
    doc_insights: Dict[str, Any],
    doc_priorities: Optional[Sequence[Dict[str, Any]]],
    allowed_sources: Optional[Sequence[str]] = None,
) -> Optional[Dict[str, Any]]:
    issues_payload = (doc_insights.get("doc_issues") or {}).get("doc_issues") or []
    if not issues_payload:
        return None

    component_meta = (doc_insights.get("resolved_component") or {})
    component_name = component_meta.get("component_name") or component_meta.get("input")

    top_doc_id = None
    if doc_priorities:
        for priority_entry in doc_priorities:
            candidate_id = priority_entry.get("doc_id")
            if candidate_id:
                top_doc_id = candidate_id
                break

    focus_issue = None
    if top_doc_id:
        focus_issue = next((issue for issue in issues_payload if issue.get("doc_id") == top_doc_id), None)
    if not focus_issue:
        focus_issue = issues_payload[0]

    focus_doc = {
        "doc_id": focus_issue.get("doc_id"),
        "title": focus_issue.get("doc_title") or focus_issue.get("doc_path") or focus_issue.get("doc_id"),
        "doc_url": focus_issue.get("doc_url"),
        "summary": focus_issue.get("summary") or focus_issue.get("change_summary") or focus_issue.get("change_title"),
        "labels": focus_issue.get("labels") or [],
        "impact_level": focus_issue.get("impact_level"),
        "severity": focus_issue.get("severity"),
    }
    if doc_priorities:
        focus_priority = next((entry for entry in doc_priorities if entry.get("doc_id") == focus_doc["doc_id"]), None)
        if focus_priority:
            focus_doc["priority_reason"] = focus_priority.get("reason")

    sources_index: Dict[str, Dict[str, Any]] = {}
    allowed_modalities = set(allowed_sources) if allowed_sources else None

    def _modality_enabled(source_type: str) -> bool:
        if not allowed_modalities:
            return True
        mapping = {"doc": "docs", "git": "git", "slack": "slack"}
        mapped = mapping.get(source_type, source_type)
        return mapped in allowed_modalities

    def _register_source(payload: Dict[str, Any]) -> str:
        sid = payload.get("id")
        if not sid:
            sid = f"{payload.get('type', 'unknown')}:{len(sources_index) + 1}"
            payload["id"] = sid
        if sid not in sources_index:
            sources_index[sid] = payload
        return sid

    def _doc_source(issue: Dict[str, Any]) -> str:
        if not _modality_enabled("doc"):
            return ""
        return _register_source(
            {
                "id": f"doc:{issue.get('doc_id') or issue.get('doc_title')}",
                "type": "doc",
                "label": issue.get("doc_title") or issue.get("doc_id"),
                "url": issue.get("doc_url"),
                "doc_id": issue.get("doc_id"),
                "detail": issue.get("summary"),
            }
        )

    def _slack_source(thread: Dict[str, Any]) -> str:
        if not _modality_enabled("slack"):
            return ""
        identifier = thread.get("thread_id") or thread.get("permalink") or thread.get("channel")
        label = thread.get("channel") or "Slack thread"
        return _register_source(
            {
                "id": f"slack:{identifier}",
                "type": "slack",
                "label": f"{label} thread",
                "url": thread.get("permalink"),
                "detail": thread.get("text"),
            }
        )

    def _git_source(change: Dict[str, Any]) -> str:
        if not _modality_enabled("git"):
            return ""
        identifier = change.get("identifier") or change.get("title")
        return _register_source(
            {
                "id": f"git:{identifier}",
                "type": "git",
                "label": change.get("title") or "Git change",
                "url": change.get("url") or change.get("identifier"),
                "detail": change.get("summary"),
            }
        )

    doc_issue_summaries: List[Dict[str, Any]] = []
    git_changes: List[Dict[str, Any]] = []
    slack_threads: List[Dict[str, Any]] = []
    drift_items: List[Dict[str, Any]] = []

    for issue in issues_payload:
        summary_entry = {
            "doc_id": issue.get("doc_id"),
            "title": issue.get("doc_title") or issue.get("doc_id"),
            "summary": issue.get("summary") or issue.get("change_summary"),
            "change_title": issue.get("change_title"),
            "impact_level": issue.get("impact_level"),
            "severity": issue.get("severity"),
            "doc_url": issue.get("doc_url"),
            "labels": issue.get("labels") or [],
        }
        doc_issue_summaries.append(summary_entry)

        source_ids = [
            _doc_source(issue)
        ]

        change_context = issue.get("change_context") or {}
        source_kind = (change_context.get("source_kind") or "").lower()
        if source_kind in {"git", "code", "github"}:
            git_entry = {
                "title": change_context.get("title") or issue.get("change_title"),
                "identifier": change_context.get("identifier"),
                "repo": change_context.get("repo"),
                "summary": issue.get("summary") or issue.get("change_summary"),
                "doc_id": issue.get("doc_id"),
                "url": change_context.get("url"),
            }
            git_changes.append(git_entry)
            source_ids.append(_git_source(git_entry))

        slack_context = issue.get("slack_context") or {}
        if slack_context.get("text") or slack_context.get("permalink"):
            slack_entry = {
                "channel": slack_context.get("channel"),
                "text": slack_context.get("text"),
                "permalink": slack_context.get("permalink"),
                "thread_id": slack_context.get("thread_id"),
                "doc_id": issue.get("doc_id"),
            }
            slack_threads.append(slack_entry)
            source_ids.append(_slack_source(slack_entry))

        docs_say = summary_entry["summary"] or "Docs do not yet describe this change."
        reality_hint = (
            change_context.get("title")
            or change_context.get("summary")
            or slack_context.get("text")
            or issue.get("change_title")
            or issue.get("doc_update_hint")
        )
        reality_text = reality_hint or "Recent activity shows the implementation differs from the doc."
        recommended_fix = issue.get("doc_update_hint") or f"Update {summary_entry['title']} to match the current rollout."

        drift_items.append(
            {
                "title": summary_entry["title"] or "Doc drift",
                "docs_say": docs_say,
                "reality": reality_text,
                "severity": summary_entry["severity"],
                "impact_level": summary_entry["impact_level"],
                "sources": [sid for sid in source_ids if sid],
                "recommended_fix": recommended_fix,
            }
        )

    component_activity = doc_insights.get("component_activity") or {}
    for event in component_activity.get("recent_slack_events") or []:
        slack_entry = {
            "channel": event.get("channel_name"),
            "text": event.get("text") or event.get("metadata", {}).get("text"),
            "permalink": event.get("permalink"),
            "thread_id": event.get("metadata", {}).get("thread_id"),
        }
        slack_threads.append(slack_entry)
        source_id = _slack_source(slack_entry)
        if drift_items:
            drift_items[0]["sources"].append(source_id)

    context_impacts = doc_insights.get("context_impacts") or {}
    impacted_components = []
    impacted_docs = []
    for impact in context_impacts.get("impacts") or []:
        impacted_components.extend(impact.get("dependent_components") or [])
        impacted_docs.extend(impact.get("docs") or [])

    for doc_id in impacted_docs[:5]:
        _register_source(
            {
                "id": f"doc:{doc_id}",
                "type": "doc",
                "label": doc_id,
                "url": None,
                "doc_id": doc_id,
                "detail": "Downstream doc impacted",
            }
        )

    structured_sources = []
    for source in sources_index.values():
        payload = {
            "type": source.get("type"),
            "label": source.get("label"),
            "url": source.get("url"),
            "doc_id": source.get("doc_id"),
            "id": source.get("id"),
        }
        structured_sources.append(payload)

    return {
        "component_name": component_name,
        "focus_doc": focus_doc,
        "doc_issues": doc_issue_summaries,
        "git_changes": git_changes[:5],
        "slack_threads": slack_threads[:5],
        "component_activity": {
            "activity_score": component_activity.get("activity_score"),
            "dissatisfaction_score": component_activity.get("dissatisfaction_score"),
            "git_events": component_activity.get("git_events"),
            "slack_conversations": component_activity.get("slack_conversations"),
            "slack_complaints": component_activity.get("slack_complaints"),
        },
        "drift_items": drift_items,
        "impacted_components": list(dict.fromkeys(impacted_components)),
        "sources": sources_index,
        "source_payload": structured_sources,
    }


def _truncate_text(text: Optional[str], limit: int = 320) -> str:
    if not text:
        return ""
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 3].rstrip() + "..."


class _FootnoteTracker:
    def __init__(self, sources_index: Dict[str, Dict[str, Any]]):
        self.sources_index = sources_index or {}
        self.assigned: Dict[str, int] = {}
        self.order: List[str] = []

    def markers(self, source_ids: Optional[Sequence[str]]) -> str:
        if not source_ids:
            return ""
        markers: List[str] = []
        for sid in source_ids:
            if not sid or sid not in self.sources_index:
                continue
            if sid not in self.assigned:
                self.assigned[sid] = len(self.order) + 1
                self.order.append(sid)
            markers.append(f"[{self.assigned[sid]}]")
        return "".join(markers)

    def render_evidence(self) -> str:
        lines: List[str] = []
        for sid in self.order:
            source = self.sources_index.get(sid) or {}
            label = source.get("label") or "Evidence"
            detail = source.get("detail") or source.get("url") or ""
            prefix = f"[{self.assigned[sid]}] {label}"
            if detail:
                lines.append(f"{prefix} — {detail}")
            else:
                lines.append(prefix)
        return "\n".join(lines)


class Option1NarrativeGenerator:
    """Structured synthesis for Option 1 doc prioritization answers."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def generate(self, *, query: str, context: Dict[str, Any]) -> Optional[str]:
        drift_items = context.get("drift_items") or []
        if not drift_items:
            return None

        tracker = _FootnoteTracker(context.get("sources") or {})
        summary = self._build_summary(context, drift_items)
        drift_section = self._build_drift_section(drift_items, tracker)
        actions_section = self._build_actions_section(drift_items, tracker)
        evidence_section = tracker.render_evidence()

        sections = [
            f"Summary\n{summary}",
            "What’s drifting\n" + drift_section,
            "What to change now\n" + actions_section,
        ]
        if evidence_section:
            sections.append("Evidence\n" + evidence_section)
        return "\n\n".join(section.strip() for section in sections if section.strip())

    def _build_summary(self, context: Dict[str, Any], drift_items: Sequence[Dict[str, Any]]) -> str:
        component = context.get("component_name") or context.get("focus_doc", {}).get("title") or "The docs"
        drift_labels = ", ".join(item.get("title") for item in drift_items[:3] if item.get("title"))
        impacted = context.get("impacted_components") or []
        impact_clause = ""
        if impacted:
            impact_clause = f" Downstream components already feeling it: {', '.join(impacted[:3])}."
        return (
            f"{component} documentation is drifting in {len(drift_items)} area(s): {drift_labels or 'doc issues'}."
            f"{impact_clause}"
        )

    def _build_drift_section(
        self,
        drift_items: Sequence[Dict[str, Any]],
        tracker: _FootnoteTracker,
    ) -> str:
        lines: List[str] = []
        for idx, item in enumerate(drift_items[:3], start=1):
            markers = tracker.markers(item.get("sources"))
            title = item.get("title") or f"Issue {idx}"
            lines.append(f"{idx}. {title} {markers}".rstrip())
            lines.append(f"   • Docs say: {self._clean(item.get('docs_say'))}")
            lines.append(f"   • Reality: {self._clean(item.get('reality'))}")
            severity = item.get("severity")
            impact = item.get("impact_level")
            if severity or impact:
                lines.append(f"   • Severity: {severity or 'n/a'} · Impact: {impact or 'n/a'}")
        return "\n".join(lines) or "No drift captured."

    def _build_actions_section(
        self,
        drift_items: Sequence[Dict[str, Any]],
        tracker: _FootnoteTracker,
    ) -> str:
        actions: List[str] = []
        for item in drift_items[:3]:
            recommendation = item.get("recommended_fix") or f"Update {item.get('title')} to match production."
            markers = tracker.markers(item.get("sources"))
            actions.append(f"- {recommendation} {markers}".rstrip())
        return "\n".join(actions) or "- No immediate doc updates suggested."

    @staticmethod
    def _clean(value: Optional[str]) -> str:
        return _truncate_text(value, 240) or "Not specified."


def _guess_component_from_query(query: Optional[str]) -> Optional[Dict[str, Any]]:
    if not query:
        return None

    lowered = query.lower()
    candidates: List[str] = []

    # 1) Single-token candidates (comp: ids, hyphenated names, *-api, *-service, etc.)
    candidates.extend(_extract_component_tokens(query))

    # 2) N-gram phrases ("core api", "billing service", "core api platform", etc.)
    words = [
        w.strip("?:,.'\"")
        for w in re.findall(r"[a-z0-9][a-z0-9_\-:/]*", lowered)
        if w.strip("?:,.'\"")
    ]
    for n in (2, 3):
        for i in range(len(words) - n + 1):
            window = words[i : i + n]
            if not any(tok not in _COMPONENT_STOPWORDS for tok in window):
                continue
            phrase_space = " ".join(window)
            phrase_hyphen = "-".join(window)
            candidates.append(phrase_space)
            candidates.append(phrase_hyphen)

    # 3) De-duplicate while preserving order
    seen: set[str] = set()
    ordered_candidates: List[str] = []
    for cand in candidates:
        if cand and cand not in seen:
            seen.add(cand)
            ordered_candidates.append(cand)

    for candidate in ordered_candidates:
        resolved = _invoke_tool_safely(resolve_component_id_tool, {"name": candidate})
        if resolved and not resolved.get("error"):
            return resolved
    return None


_COMPONENT_STOPWORDS = {
    "docs",
    "doc",
    "which",
    "should",
    "update",
    "first",
    "for",
    "what",
    "we",
    "the",
    "this",
    "that",
    "need",
    "want",
    "service",
}


def _extract_component_tokens(query: str) -> List[str]:
    lowered = query.lower()
    tokens: List[str] = []
    for match in re.findall(r"(comp:[a-z0-9:_-]+)", lowered):
        tokens.append(match)
    for word in re.findall(r"[a-z0-9][a-z0-9_\-:/]+", lowered):
        cleaned = word.strip("?:,.'\"")
        if not cleaned or cleaned in _COMPONENT_STOPWORDS:
            continue
        if cleaned.startswith("comp:"):
            tokens.append(cleaned)
            continue
        if "-" in cleaned or cleaned.endswith(("api", "service", "platform", "component")):
            tokens.append(cleaned)
    return tokens


def _maybe_enrich_summary(
    summary: Optional[str],
    doc_priorities: Optional[Sequence[Dict[str, Any]]],
) -> str:
    if not doc_priorities:
        return summary or ""
    normalized = (summary or "").strip().lower()
    if normalized and "no evidence" not in normalized:
        return summary or ""
    top = doc_priorities[0]
    label = top.get("doc_title") or top.get("doc_id") or "Top doc"
    reason = top.get("reason")
    if reason:
        return f"{label} should be updated first because {reason}."
    return f"{label} should be updated first based on recent multi-modal activity."


def _extract_doc_issue_list(doc_insights: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(doc_insights, dict):
        return []
    payload = doc_insights.get("doc_issues")
    if isinstance(payload, dict):
        candidate = payload.get("doc_issues")
    elif isinstance(payload, list):
        candidate = payload
    else:
        candidate = None
    return [issue for issue in (candidate or []) if isinstance(issue, dict)]


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _extract_graph_query(doc_insights: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(doc_insights, dict):
        return None
    payload = doc_insights.get("graph_query")
    if isinstance(payload, dict) and payload:
        return payload
    return None


def _compute_activity_score(
    component_activity: Optional[Dict[str, Any]],
    doc_issues: Sequence[Dict[str, Any]],
) -> Optional[float]:
    activity_score = _coerce_float(
        component_activity.get("activity_score") if isinstance(component_activity, dict) else None
    )
    if activity_score is not None:
        return round(activity_score, 2)

    component_activity = component_activity or {}
    git_events = _coerce_int(component_activity.get("git_events"))
    slack_threads = _coerce_int(component_activity.get("slack_conversations"))
    fallback = 0.0
    if git_events:
        fallback += git_events * 0.8
    if slack_threads:
        fallback += slack_threads * 0.4
    doc_pressure = estimate_doc_issue_pressure(doc_issues)
    if doc_pressure:
        fallback += doc_pressure * 0.2
    return round(fallback, 2) if fallback > 0 else None


def _compute_dissatisfaction_score(
    component_activity: Optional[Dict[str, Any]],
    doc_issues: Sequence[Dict[str, Any]],
) -> Optional[float]:
    dissatisfaction_score = _coerce_float(
        component_activity.get("dissatisfaction_score") if isinstance(component_activity, dict) else None
    )
    if dissatisfaction_score is not None:
        return round(dissatisfaction_score, 2)

    component_activity = component_activity or {}
    slack_complaints = _coerce_int(component_activity.get("slack_complaints"))
    fallback = 0.0
    if slack_complaints:
        fallback += slack_complaints * 0.9
    doc_pressure = estimate_doc_issue_pressure(doc_issues)
    if doc_pressure:
        fallback += doc_pressure
    if fallback <= 0 and doc_issues:
        # Ensure doc drift scenarios without explicit complaints still surface dissatisfaction
        fallback = max(0.75, len(doc_issues) * 0.5)
    return round(fallback, 2) if fallback > 0 else None


def _build_structured_reasoning_payload(
    *,
    doc_insights: Optional[Dict[str, Any]],
    doc_priorities: Optional[Sequence[Dict[str, Any]]],
    answer_text: str,
) -> Dict[str, Any]:
    doc_issue_list = _extract_doc_issue_list(doc_insights)
    component_activity = doc_insights.get("component_activity") if isinstance(doc_insights, dict) else {}
    context_impacts = doc_insights.get("context_impacts") if isinstance(doc_insights, dict) else {}

    structured: Dict[str, Any] = {}
    structured["activity_signals"] = _extract_activity_signals(component_activity, doc_issue_list)
    structured["dissatisfaction_signals"] = _extract_dissatisfaction_signals(component_activity, doc_issue_list)
    structured["dependency_impact"] = _extract_dependency_impact(context_impacts)
    structured["activity_score"] = _compute_activity_score(component_activity, doc_issue_list)
    structured["dissatisfaction_score"] = _compute_dissatisfaction_score(component_activity, doc_issue_list)
    if structured.get("dissatisfaction_score") in (None, 0) and doc_priorities:
        structured["dissatisfaction_score"] = round(max(0.75, len(doc_priorities) * 0.4), 2)
    structured["graph_query"] = _extract_graph_query(doc_insights)
    structured["root_cause_explanation"] = _infer_root_cause(answer_text, doc_priorities, doc_issue_list)
    structured["impact_summary"] = _summarize_dependency_impact(structured["dependency_impact"], doc_issue_list)
    structured["resolution_plan"] = _build_resolution_plan(doc_priorities, doc_issue_list)
    return {key: value for key, value in structured.items() if value not in (None, [], {}, "")}


def _build_source_divergence_payload(
    conflicts: Optional[Sequence[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    if not conflicts:
        return None
    items: List[Dict[str, Any]] = []
    summary_lines: List[str] = []
    for entry in conflicts:
        if not isinstance(entry, dict):
            continue
        source_one = str(entry.get("source1") or entry.get("source_1") or "").strip() or "Source A"
        source_two = str(entry.get("source2") or entry.get("source_2") or "").strip() or "Source B"
        description = str(entry.get("description") or entry.get("detail") or "").strip()
        payload = {
            "source1": source_one,
            "source2": source_two,
            "description": description,
        }
        items.append(payload)
        summary_lines.append(f"{source_one} vs {source_two}: {description or 'conflict detected'}")
    if not items:
        return None
    summary_body = "\n".join(f"- {line}" for line in summary_lines)
    summary = f"Evidence divergence detected across {len(items)} pair(s):\n{summary_body}"
    return {
        "summary": summary,
        "count": len(items),
        "items": items,
    }


def _build_information_gap_payload(
    gaps: Optional[Sequence[Dict[str, Any]]],
) -> Optional[List[Dict[str, Any]]]:
    if not gaps:
        return None
    normalized: List[Dict[str, Any]] = []
    for entry in gaps:
        if not isinstance(entry, dict):
            continue
        description = str(entry.get("description") or "").strip()
        gap_type = str(entry.get("type") or "").strip() or None
        if not description:
            continue
        normalized.append({"description": description, "type": gap_type})
    return normalized or None


def _extract_activity_signals(
    component_activity: Optional[Dict[str, Any]],
    doc_issues: Sequence[Dict[str, Any]],
) -> Dict[str, int]:
    component_activity = component_activity or {}
    mapping = {
        "git_events": "git_events",
        "slack_conversations": "slack_threads",
        "slack_complaints": "support_complaints",
        "open_doc_issues": "doc_issues",
    }
    signals: Dict[str, int] = {}
    for source_key, dest_key in mapping.items():
        try:
            value = int(component_activity.get(source_key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            signals[dest_key] = value
    if "doc_issues" not in signals and doc_issues:
        signals["doc_issues"] = len(doc_issues)
    return signals


def _extract_dissatisfaction_signals(
    component_activity: Optional[Dict[str, Any]],
    doc_issues: Sequence[Dict[str, Any]],
) -> Dict[str, int]:
    component_activity = component_activity or {}
    signals: Dict[str, int] = {}
    try:
        complaints = int(component_activity.get("slack_complaints") or 0)
    except (TypeError, ValueError):
        complaints = 0
    if complaints > 0:
        signals["slack_complaints"] = complaints
    critical_docs = sum(
        1 for issue in doc_issues if str(issue.get("severity") or "").lower() in {"high", "critical"}
    )
    if critical_docs > 0:
        signals["critical_doc_issues"] = critical_docs
    if doc_issues:
        signals["doc_issues"] = len(doc_issues)
    return signals


def _extract_dependency_impact(context_impacts: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(context_impacts, dict):
        return None
    impacts = context_impacts.get("impacts")
    reason = context_impacts.get("reason")
    if not isinstance(impacts, list) or not impacts:
        if reason:
            # Surface a structured explanation even when there are no concrete impacts.
            return {"impacts": [], "reason": str(reason)}
        return None
    impact_rows: List[Dict[str, Any]] = []
    component_set: List[str] = []
    doc_set: List[str] = []
    service_set: List[str] = []
    for entry in impacts:
        if not isinstance(entry, dict):
            continue
        component_id = entry.get("component_id")
        dependents = entry.get("dependent_components") or entry.get("components") or []
        docs = entry.get("docs_to_update") or entry.get("docs") or []
        services = entry.get("services") or entry.get("impacted_services") or []
        exposed_apis = entry.get("exposed_apis") or entry.get("apis") or []
        depth = entry.get("depth") or context_impacts.get("max_depth")
        payload = {
            "componentId": component_id,
            "dependentComponents": dependents,
            "docs": docs,
            "services": services,
            "exposedApis": exposed_apis,
            "severity": entry.get("severity") or entry.get("impact_level"),
            "depth": depth,
        }
        impact_rows.append(payload)
        if component_id:
            component_set.append(str(component_id))
        component_set.extend(str(dep) for dep in dependents or [])
        doc_set.extend(str(doc_id) for doc_id in docs or [])
        service_set.extend(str(service_id) for service_id in services or [])
    if not impact_rows:
        return None
    return {
        "impacts": impact_rows,
        "affectedComponents": sorted(dict.fromkeys(component_set)),
        "docsNeedingUpdates": sorted(dict.fromkeys(doc_set)),
        "servicesNeedingUpdates": sorted(dict.fromkeys(service_set)),
        "maxDepth": context_impacts.get("max_depth"),
    }


def _infer_root_cause(
    answer_text: str,
    doc_priorities: Optional[Sequence[Dict[str, Any]]],
    doc_issues: Sequence[Dict[str, Any]],
) -> Optional[str]:
    if doc_priorities:
        top = doc_priorities[0]
        doc_title = top.get("doc_title") or top.get("doc_id")
        reason = top.get("reason")
        if doc_title and reason:
            return f"{doc_title}: {reason}"
    for issue in doc_issues:
        summary = issue.get("summary") or issue.get("change_summary")
        if summary:
            return summary
    primary_line = (answer_text or "").strip().split("\n", 1)[0].strip()
    return primary_line or None


def _summarize_dependency_impact(
    dependency_payload: Optional[Dict[str, Any]],
    doc_issues: Sequence[Dict[str, Any]],
) -> Optional[str]:
    parts: List[str] = []
    components = (dependency_payload or {}).get("affectedComponents") or []
    docs = (dependency_payload or {}).get("docsNeedingUpdates") or []
    if components:
        parts.append(f"{len(components)} components")
    if docs:
        parts.append(f"{len(docs)} docs")
    if not parts and doc_issues:
        parts.append(f"{len(doc_issues)} docs")
    if not parts:
        return None
    summary = "Impacts " + " and ".join(parts)
    if components:
        summary += f" (e.g., {', '.join(components[:3])})"
    return summary + "."


def _build_resolution_plan(
    doc_priorities: Optional[Sequence[Dict[str, Any]]],
    doc_issues: Sequence[Dict[str, Any]],
) -> Optional[List[str]]:
    recommendations: List[str] = []
    for priority in doc_priorities or []:
        doc_title = priority.get("doc_title") or priority.get("doc_id")
        reason = priority.get("reason")
        if doc_title:
            if reason:
                recommendations.append(f"Update {doc_title}: {reason}")
            else:
                recommendations.append(f"Update {doc_title} to match current behavior.")
    for issue in doc_issues:
        hint = issue.get("doc_update_hint") or issue.get("recommended_fix")
        if hint:
            recommendations.append(str(hint))
    deduped: List[str] = []
    seen: set[str] = set()
    for item in recommendations:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    if not deduped:
        return None
    return deduped[:5]


def _build_cerebros_answer(
    *,
    query: str,
    summary: str,
    evidence_payload: Any,
    doc_insights: Optional[Dict[str, Any]],
    component_ids: Optional[Sequence[str]],
    owner_override: Optional[str] = None,
    conflicts: Optional[Sequence[Dict[str, Any]]] = None,
    information_gaps: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    option = _classify_cerebros_option(query, doc_insights)

    ordered_components: List[str] = []
    seen_components: set[str] = set()
    for cid in component_ids or []:
        if cid and cid not in seen_components:
            seen_components.add(cid)
            ordered_components.append(cid)

    if isinstance(doc_insights, dict):
        resolved = doc_insights.get("resolved_component")
        if isinstance(resolved, dict):
            cid = resolved.get("component_id")
            if cid and cid not in seen_components:
                seen_components.add(cid)
                ordered_components.append(cid)
        impacts = doc_insights.get("context_impacts")
        if isinstance(impacts, dict):
            for impact in impacts.get("impacts") or []:
                if not isinstance(impact, dict):
                    continue
                cid = impact.get("component_id")
                if cid and cid not in seen_components:
                    seen_components.add(cid)
                    ordered_components.append(cid)

    sources = _build_cerebros_sources_from_evidence(
        evidence_payload,
        owner_override=owner_override,
    )
    if not sources and isinstance(doc_insights, dict):
        sources.extend(
            _doc_priority_sources(
                doc_insights.get("doc_priorities"),
                owner_override=owner_override,
            )
        )
    if not sources and isinstance(doc_insights, dict):
        sources.extend(
            _doc_issue_sources(
                doc_insights.get("doc_issues"),
                owner_override=owner_override,
            )
        )

    answer_payload: Dict[str, Any] = {
        "answer": summary,
        "option": option,
        "components": ordered_components or None,
        "sources": sources,
    }

    doc_priorities = (
        doc_insights.get("doc_priorities") if isinstance(doc_insights, dict) else None
    )
    summary = _maybe_enrich_summary(answer_payload["answer"], doc_priorities)
    answer_payload["answer"] = summary
    if doc_priorities:
        answer_payload["doc_priorities"] = doc_priorities

    structured_payload = _build_structured_reasoning_payload(
        doc_insights=doc_insights if isinstance(doc_insights, dict) else None,
        doc_priorities=doc_priorities,
        answer_text=answer_payload["answer"],
    )
    if structured_payload:
        answer_payload.update(structured_payload)
    divergence_payload = _build_source_divergence_payload(conflicts)
    if divergence_payload:
        answer_payload["source_divergence"] = divergence_payload
    gap_payload = _build_information_gap_payload(information_gaps)
    if gap_payload:
        answer_payload["information_gaps"] = gap_payload

    return answer_payload


def _extract_severity_payload(
    doc_priorities: Optional[Sequence[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    if not doc_priorities:
        return None
    for entry in doc_priorities:
        if not isinstance(entry, dict):
            continue
        score = entry.get("severity_score")
        if score is None:
            continue
        payload: Dict[str, Any] = {
            "severity_score": score,
            "severity_label": entry.get("severity_label"),
            "severity_breakdown": entry.get("severity_breakdown"),
            "severity_details": entry.get("severity_details"),
        }
        if entry.get("severity_score_100") is not None:
            payload["severity_score_100"] = entry.get("severity_score_100")
        issue_id = entry.get("issue_id")
        if issue_id:
            payload["severity_issue_id"] = issue_id
        return payload
    return None

