from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence
from collections import Counter
import os

from src.cerebros.graph_reasoner import (
    CerebrosReasonerResult,
    run_cerebros_reasoner,
    _build_cerebros_sources_from_evidence,
)
from src.utils.git_urls import rewrite_github_url
from src.services.slash_query_plan import SlashQueryPlan
from src.traceability.incidents import STRUCTURED_INCIDENT_FIELDS, build_incident_candidate
from src.activity_graph.severity import compute_issue_severity
from src.graph import GraphService

logger = logging.getLogger(__name__)

SLASH_DEFAULT_SOURCES = [
    "git",
    "slack",
    "docs",
    "issues",
    "doc_issues",
    "activity_graph",
]

def run_slash_cerebros_query(
    *,
    config: Dict[str, Any],
    query: str,
    component_id: Optional[str] = None,
    query_plan: Optional[SlashQueryPlan] = None,
    sources: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Execute the multi-source Cerebros reasoner and normalize the result into
    the slash payload structure the UI expects.
    """
    graph_params: Dict[str, Any] = {}
    if component_id:
        graph_params["componentId"] = component_id

    reasoner_result = run_cerebros_reasoner(
        config=config,
        query=query,
        graph_params=graph_params,
        sources=list(sources) if sources else list(SLASH_DEFAULT_SOURCES),
    )
    evidence_payload = reasoner_result.evidence_payload or {}
    raw_evidence = []
    if isinstance(evidence_payload, dict):
        raw_evidence = evidence_payload.get("evidence") or []
        if not isinstance(raw_evidence, list):
            raw_evidence = []
    evidence_counts: Counter[str] = Counter()
    for item in raw_evidence:
        if isinstance(item, dict):
            source = str(item.get("source_type") or "unknown").lower()
            evidence_counts[source] += 1
    logger.info(
        "[CEREBROS_DEBUG] query=%s sources=%s evidence_counts=%s",
        query,
        reasoner_result.sources_queried,
        dict(evidence_counts),
    )

    payload = _build_slash_cerebros_payload(reasoner_result, query_plan=query_plan, config=config)
    severity_payload = (payload.get("data") or {}).get("severity")
    if severity_payload:
        logger.info(
            "[CEREBROS_DEBUG] severity=%s score=%s breakdown=%s",
            severity_payload.get("label"),
            severity_payload.get("score_0_10"),
            severity_payload.get("breakdown"),
        )
    else:
        logger.info("[CEREBROS_DEBUG] severity=None")

    return payload


def build_search_slash_cerebros_payload(
    *,
    query: str,
    search_result: Dict[str, Any],
    query_plan: Optional[SlashQueryPlan] = None,
) -> Dict[str, Any]:
    """
    Convert a legacy /cerebros search response into the slash summary payload so the
    frontend can render the same UI even when the graph pipeline is unavailable.
    """
    sanitized_query = (query or "").strip()
    data = dict(search_result.get("data") or {})
    data.setdefault("query", sanitized_query)
    data.setdefault("severity_score", 5)
    message = (
        search_result.get("message")
        or (sanitized_query and f'Top matches for "{sanitized_query}"')
        or "Cerebros search completed."
    )

    sources = _build_cerebros_sources_from_results((data.get("results") or [])[:10])
    context = _build_cerebros_context(data, query_plan=query_plan)

    analysis_input: Dict[str, Any] = {
        "modalities_used": data.get("modalities_used"),
        "total": data.get("total"),
        "cerebros_answer": data.get("cerebros_answer") or {},
    }
    analysis = _build_cerebros_analysis(analysis_input)

    payload = {
        "type": "slash_cerebros_summary",
        "status": search_result.get("status") or "success",
        "message": message,
        "context": context or None,
        "sources": sources,
        "analysis": analysis or None,
        "cerebros_answer": {
            "answer": message,
            "option": "generic",
            "doc_priorities": [],
        },
        "data": data,
    }
    return payload


def _build_slash_cerebros_payload(
    result: CerebrosReasonerResult,
    *,
    query_plan: Optional[SlashQueryPlan] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = dict(result.response_payload or {})
    data.setdefault("doc_insights", result.doc_insights)
    message = (
        (result.cerebros_answer or {}).get("answer")
        or result.summary
        or "Cerebros search completed."
    )

    sources: List[Dict[str, Any]] = []
    sources.extend(_build_cerebros_sources_from_results(data.get("results") or []))
    sources.extend(
        _normalize_cerebros_answer_sources(
            (data.get("cerebros_answer") or {}).get("sources")
        )
    )
    sources.extend(
        _normalize_doc_priority_sources(
            (result.cerebros_answer or {}).get("doc_priorities")
        )
    )
    evidence_field = data.get("evidence") or data.get("evidence_payload")
    sources.extend(_build_cerebros_sources_from_evidence(evidence_field))
    sources = _dedupe_cerebros_sources(sources)

    context = _build_cerebros_context(data, query_plan=query_plan)
    analysis = _build_cerebros_analysis(data)
    traceability_evidence = _sources_to_traceability_evidence(sources)
    incident_candidate: Optional[Dict[str, Any]] = None
    if traceability_evidence:
        cerebros_answer = result.cerebros_answer or {}
        component_candidates = list(
            {*(result.component_ids or []), *((cerebros_answer.get("components") or []) or [])}
        )
        doc_priorities = list(cerebros_answer.get("doc_priorities") or [])
        structured_fields = {
            field: value
            for field in STRUCTURED_INCIDENT_FIELDS
            if (value := cerebros_answer.get(field)) not in (None, [], {}, "")
        }
        incident_candidate = build_incident_candidate(
            query=result.query,
            summary_text=result.summary,
            components=component_candidates,
            doc_priorities=doc_priorities,
            sources_queried=result.sources_queried,
            traceability_evidence=traceability_evidence,
            investigation_id=None,
            raw_trace_id=data.get("query_id"),
            source_command="slash_cerebros",
            llm_explanation=cerebros_answer.get("answer"),
            project_id=result.project_id,
            issue_id=result.issue_id,
            structured_fields=structured_fields or None,
        )

    severity_payload = _compute_slash_severity(result, config or {})
    if severity_payload:
        data["severity_score"] = severity_payload.get("score_0_10")
        data["severity_score_100"] = severity_payload.get("score")
        data["severity_label"] = severity_payload.get("label")
        data["severity"] = severity_payload

    if incident_candidate and severity_payload:
        incident_candidate["severity_payload"] = severity_payload
        incident_candidate["severity_score"] = severity_payload.get("score_0_10")
        incident_candidate["severity_score_100"] = severity_payload.get("score")
        incident_candidate["severity_breakdown"] = severity_payload.get("breakdown")
        incident_candidate["severity_details"] = severity_payload.get("details")
        incident_candidate["severity_contributions"] = severity_payload.get("contributions")
        incident_candidate["severity_weights"] = severity_payload.get("weights")
        incident_candidate["severity_semantic_pairs"] = severity_payload.get("semantic_pairs")
        incident_candidate["severity_label"] = severity_payload.get("label")

    payload = {
        "type": "slash_cerebros_summary",
        "status": data.get("status") or "success",
        "message": message,
        "context": context or None,
        "sources": sources,
        "analysis": analysis or None,
        "cerebros_answer": result.cerebros_answer,
        "data": data,
    }
    if incident_candidate:
        payload["incident_candidate"] = incident_candidate
    return payload


def _build_cerebros_context(
    data: Dict[str, Any],
    *,
    query_plan: Optional[SlashQueryPlan],
) -> Dict[str, Any]:
    context = {
        "modalities_used": data.get("modalities_used"),
        "total_results": data.get("total"),
        "query_plan": _serialize_query_plan(query_plan),
        "graph_context": data.get("graph_context"),
    }
    return {key: value for key, value in context.items() if value not in (None, [], {}, "")}


def _build_cerebros_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    analysis: Dict[str, Any] = {}
    modalities = data.get("modalities_used")
    if modalities:
        analysis["modalities_used"] = modalities
    total = data.get("total")
    if isinstance(total, int):
        analysis["result_count"] = total
    answer = data.get("cerebros_answer") or {}
    doc_priorities = answer.get("doc_priorities")
    if doc_priorities:
        analysis["doc_priorities"] = doc_priorities
    components = answer.get("components")
    if components:
        analysis["components"] = components
    return analysis


def _compute_slash_severity(
    result: CerebrosReasonerResult,
    config: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    issue_id = _resolve_issue_id(result)
    if not issue_id:
        return None

    try:
        graph_service = GraphService(config)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("[CEREBROS][SEVERITY] Graph service unavailable: %s", exc)
        return None

    if not graph_service.is_available():
        graph_service.close()
        return None

    try:
        return compute_issue_severity(issue_id, graph_service=graph_service)
    except Exception as exc:  # pragma: no cover - severity errors shouldn't break slash
        logger.warning("[CEREBROS][SEVERITY] Failed to compute severity for %s: %s", issue_id, exc)
        return None
    finally:
        graph_service.close()


def _resolve_issue_id(result: CerebrosReasonerResult) -> Optional[str]:
    if result.issue_id:
        return str(result.issue_id)

    payload_candidates: List[Any] = []
    if isinstance(result.cerebros_answer, dict):
        payload_candidates.extend(result.cerebros_answer.get("doc_priorities") or [])

    response_payload = result.response_payload or {}
    if isinstance(response_payload, dict):
        payload_candidates.extend(
            (response_payload.get("cerebros_answer") or {}).get("doc_priorities") or []
        )
        payload_candidates.extend(response_payload.get("doc_priorities") or [])
        response_issue = response_payload.get("issue_id")
        if response_issue:
            return str(response_issue)

    for entry in payload_candidates:
        if not isinstance(entry, dict):
            continue
        issue_id = entry.get("issue_id")
        if issue_id:
            return str(issue_id)

    source_candidates: List[Any] = []
    if isinstance(result.cerebros_answer, dict):
        source_candidates.extend(result.cerebros_answer.get("sources") or [])

    evidence_block = ((result.response_payload or {}).get("evidence") or {})
    source_candidates.extend((evidence_block.get("evidence") or []))

    for source in source_candidates:
        if not isinstance(source, dict):
            continue
        source_type = str(
            source.get("type")
            or source.get("source_type")
            or (source.get("source") if isinstance(source.get("source"), str) else "")
            or ""
        ).lower()
        if source_type not in {"doc_issue", "issue", "doc", "doc_issues"}:
            continue
        metadata = source.get("metadata") or {}
        for candidate in (
            source.get("id"),
            source.get("entity_id"),
            metadata.get("doc_issue_id"),
            source.get("doc_issue_id"),
        ):
            if candidate:
                return str(candidate)
    return None


def _build_cerebros_sources_from_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for idx, item in enumerate(results or []):
        normalized = _normalize_cerebros_result_source(item, idx + 1)
        if normalized:
            sources.append(normalized)
    return sources


def _normalize_cerebros_result_source(
    item: Dict[str, Any],
    rank: int,
) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    metadata = item.get("metadata") or {}
    modality = (item.get("modality") or item.get("source_type") or "").lower()
    source_type = _map_cerebros_source_type(modality)
    url = item.get("url") or metadata.get("url")

    if source_type == "slack":
        # Prefer an app deeplink when possible so Slack evidence opens the native app
        # rather than a browser tab. Fall back to the permalink when we lack enough
        # metadata (team/channel/timestamp).
        url = _build_slack_deeplink_url(metadata) or url or metadata.get("permalink")
    elif source_type == "git":
        url = url or _build_git_source_url(metadata)
    elif source_type == "issue":
        url = url or metadata.get("url") or metadata.get("permalink")
    elif source_type == "doc":
        candidate = url or metadata.get("doc_url") or metadata.get("path")
        if candidate and not str(candidate).startswith(("http://", "https://", "file://")):
            url = f"file://{candidate}"
        else:
            url = candidate
    else:
        url = url or metadata.get("permalink")

    label = (
        item.get("title")
        or metadata.get("display_name")
        or metadata.get("doc_title")
        or metadata.get("repo")
        or metadata.get("channel_name")
        or url
    )
    if not label or not url:
        return None

    url = rewrite_github_url(url)

    snippet = (item.get("text") or "").strip()
    if len(snippet) > 320:
        snippet = snippet[:317] + "..."

    score = item.get("score")
    try:
        score_val = float(score) if score is not None else None
    except (TypeError, ValueError):
        score_val = None

    return {
        "id": item.get("chunk_id")
        or metadata.get("chunk_id")
        or metadata.get("source_id")
        or f"{source_type}:{rank}",
        "type": source_type,
        "label": label,
        "url": url,
        "snippet": snippet or None,
        "score": score_val,
        "modality": modality or source_type,
        "channel": metadata.get("channel_name") or metadata.get("channel"),
        "repo": metadata.get("repo") or metadata.get("repo_slug"),
        "doc_id": metadata.get("doc_id") or metadata.get("source_id") or metadata.get("path"),
        "timestamp": metadata.get("iso_time") or metadata.get("ts"),
        "component": metadata.get("component_id"),
        "rank": rank,
    }


def _build_slack_deeplink_url(metadata: Dict[str, Any]) -> Optional[str]:
    """
    Build a Slack app deeplink for Cerebros sources when possible.

    The goal is:
    - Slack evidence → open Slack app directly (channel/thread view)
    - Git evidence → continue to open in browser via https://github.com/...

    We rely on either:
    - metadata.workspace_id (if populated during ingestion/search), or
    - SLACK_TEAM_ID / SLACK_WORKSPACE_ID environment variables
    for the Slack workspace identifier.
    """
    channel_id = metadata.get("channel_id") or metadata.get("channel")
    if not channel_id:
        return None

    # Prefer per-message deep link when we have a timestamp
    ts = metadata.get("thread_ts") or metadata.get("ts")

    # Workspace / team identifier for the deeplink
    team_id = (
        metadata.get("workspace_id")
        or os.getenv("SLACK_TEAM_ID")
        or os.getenv("SLACK_WORKSPACE_ID")
    )
    if not team_id:
        return None

    # Slack deeplink format:
    #   slack://channel?team={TEAM_ID}&id={CHANNEL_ID}&message={TS}
    # The message parameter is optional; if omitted, Slack opens the channel.
    base = f"slack://channel?team={team_id}&id={channel_id}"
    if ts:
        # Timestamps are typically in seconds.millis; Slack deeplinks expect the raw ts.
        ts_str = str(ts).strip()
        if ts_str:
            return f"{base}&message={ts_str}"
    return base


def _normalize_cerebros_answer_sources(raw_sources: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_sources, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for idx, entry in enumerate(raw_sources):
        if not isinstance(entry, dict):
            continue
        label = entry.get("label") or entry.get("title") or entry.get("url")
        url = rewrite_github_url(entry.get("url"))
        if not label or not url:
            continue
        normalized.append(
            {
                "id": entry.get("id") or f"{entry.get('type', 'source')}:{idx}",
                "type": entry.get("type") or entry.get("source_type"),
                "label": label,
                "url": url,
                "snippet": entry.get("detail"),
                "doc_id": entry.get("doc_id"),
                "channel": entry.get("channel"),
                "repo": entry.get("repo"),
                "modality": entry.get("type") or entry.get("source_type"),
            }
        )
    return normalized


def _normalize_doc_priority_sources(doc_priorities: Any) -> List[Dict[str, Any]]:
    if not isinstance(doc_priorities, list):
        return []
    sources: List[Dict[str, Any]] = []
    for entry in doc_priorities:
        if not isinstance(entry, dict):
            continue
        url = rewrite_github_url(entry.get("doc_url"))
        if not url:
            continue
        label = entry.get("doc_title") or entry.get("doc_id") or url
        sources.append(
            {
                "id": entry.get("doc_id") or label,
                "type": "doc",
                "label": label,
                "url": url,
                "snippet": entry.get("reason"),
                "doc_id": entry.get("doc_id"),
                "component": entry.get("component_id"),
                "score": entry.get("score"),
            }
        )
    return sources


def _dedupe_cerebros_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ordered: List[Dict[str, Any]] = []
    seen: set = set()
    for entry in sources:
        key = (entry.get("url"), entry.get("label"))
        if not entry.get("url") or key in seen:
            continue
        seen.add(key)
        ordered.append(entry)
    return ordered


def _sources_to_traceability_evidence(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    for idx, source in enumerate(sources):
        if not isinstance(source, dict):
            continue
        evidence.append(
            {
                "evidence_id": source.get("id") or source.get("url") or f"source:{idx}",
                "source": source.get("type") or source.get("modality") or "doc",
                "title": source.get("label") or source.get("snippet"),
                "url": source.get("url"),
                "metadata": {
                    "timestamp": source.get("timestamp"),
                    "component_id": source.get("component"),
                    "channel": source.get("channel"),
                    "repo": source.get("repo"),
                },
            }
        )
    return evidence


def _map_cerebros_source_type(modality: str) -> str:
    mapping = {
        "slack": "slack",
        "git": "git",
        "github": "git",
        "docs": "doc",
        "files": "doc",
        "doc": "doc",
        "issues": "issue",
        "issue": "issue",
        "tickets": "issue",
        "youtube": "youtube",
        "graph": "graph",
    }
    return mapping.get(modality, modality or "doc")


def _build_git_source_url(metadata: Dict[str, Any]) -> Optional[str]:
    repo = metadata.get("repo") or metadata.get("repo_slug")
    if not repo:
        return None
    repo = repo.strip("/")
    number = metadata.get("number") or metadata.get("pr_number")
    sha = metadata.get("sha") or metadata.get("commit_sha")
    kind = (metadata.get("kind") or "").lower()
    if number and (kind == "pr" or metadata.get("type") == "pr"):
        return f"https://github.com/{repo}/pull/{number}"
    if sha:
        return f"https://github.com/{repo}/commit/{sha}"
    if number:
        return f"https://github.com/{repo}/pull/{number}"
    return None


def _serialize_query_plan(plan: Optional[SlashQueryPlan]) -> Optional[Dict[str, Any]]:
    if not plan:
        return None
    if hasattr(plan, "to_dict"):
        return plan.to_dict()
    if isinstance(plan, dict):
        return plan
    try:
        return dict(plan)
    except Exception:
        return {"raw": str(plan)}

