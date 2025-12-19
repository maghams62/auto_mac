from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict, defaultdict

from telemetry.config import log_structured
from src.search.query_trace import ChunkRef, QueryTrace, QueryTraceStore

logger = logging.getLogger(__name__)

INCIDENT_SOURCE_WEIGHTS = {
    "git": 1.0,
    "github": 1.0,
    "doc": 0.9,
    "docs": 0.9,
    "issue": 0.85,
    "ticket": 0.85,
    "slack": 0.7,
    "activity_graph": 0.65,
    "graph": 0.6,
    "unknown": 0.5,
}

STRUCTURED_INCIDENT_FIELDS = (
    "root_cause_explanation",
    "impact_summary",
    "resolution_plan",
    "activity_signals",
    "dissatisfaction_signals",
    "dependency_impact",
    "source_divergence",
    "information_gaps",
    "activity_score",
    "dissatisfaction_score",
    "graph_query",
)


def record_query_trace_from_evidence(
    store: QueryTraceStore,
    *,
    query_id: str,
    question: str,
    modalities_used: Optional[List[str]],
    traceability_evidence: List[Dict[str, Any]],
) -> None:
    if not query_id or not question or not store:
        return
    chunk_refs: List[ChunkRef] = []
    for idx, entry in enumerate(traceability_evidence):
        if not isinstance(entry, dict):
            continue
        chunk_refs.append(
            ChunkRef(
                chunk_id=str(entry.get("evidence_id") or entry.get("url") or f"trace:{idx}"),
                source_type=entry.get("source"),
                source_id=str(entry.get("evidence_id") or entry.get("url") or idx),
                modality=entry.get("source"),
                title=entry.get("title"),
                score=None,
                url=entry.get("url"),
                metadata=(entry.get("metadata") or {}),
            )
        )
    trace = QueryTrace(
        query_id=query_id,
        question=question,
        modalities_used=list(modalities_used or []),
        retrieved_chunks=chunk_refs,
        chosen_chunks=chunk_refs[:5],
    )
    try:
        store.append(trace)
    except Exception as exc:  # pragma: no cover - storage failures are logged
        logger.warning("[TRACEABILITY] Failed to persist query trace %s: %s", query_id, exc)


def build_incident_candidate(
    *,
    query: str,
    summary_text: str,
    components: List[str],
    doc_priorities: List[Dict[str, Any]],
    sources_queried: Optional[List[str]],
    traceability_evidence: List[Dict[str, Any]],
    investigation_id: Optional[str],
    raw_trace_id: Optional[str],
    source_command: str,
    llm_explanation: Optional[str] = None,
    project_id: Optional[str] = None,
    issue_id: Optional[str] = None,
    structured_fields: Optional[Dict[str, Any]] = None,
    brain_trace_url: Optional[str] = None,
    brain_universe_url: Optional[str] = None,
) -> Dict[str, Any]:
    scope_summary, timestamps = _summarize_incident_scope(
        components=components,
        doc_priorities=doc_priorities,
        traceability_evidence=traceability_evidence,
    )
    evidence_sources = [str(entry.get("source") or "").lower() for entry in traceability_evidence]
    severity, blast_radius_score, recency_info = _calculate_incident_scores(
        scope_summary=scope_summary,
        timestamps=timestamps,
        evidence_sources=evidence_sources,
    )
    counts = {
        "components": len(scope_summary["components"]),
        "docs": len(scope_summary["doc_ids"]),
        "issues": len(scope_summary["issue_ids"]),
        "slack_threads": len(scope_summary["slack_threads"]),
        "git_items": len(scope_summary["git_refs"]),
        "evidence": len(traceability_evidence),
    }
    candidate = {
        "investigation_id": investigation_id,
        "raw_trace_id": raw_trace_id,
        "query": query,
        "summary": summary_text or query,
        "llm_explanation": llm_explanation or summary_text,
        "components": scope_summary["components"],
        "doc_priorities": doc_priorities,
        "sources_used": sources_queried or [],
        "counts": counts,
        "impacted_nodes": scope_summary,
        "incident_scope": scope_summary,
        "severity": severity,
        "blast_radius_score": blast_radius_score,
        "source_command": source_command,
        "project_id": project_id,
        "issue_id": issue_id,
        "recency_info": recency_info,
        "modalities_used": sources_queried or [],
    }
    if traceability_evidence:
        candidate["evidence"] = traceability_evidence
    if brain_trace_url:
        candidate["brainTraceUrl"] = brain_trace_url
    if brain_universe_url:
        candidate["brainUniverseUrl"] = brain_universe_url
    structured_dict = structured_fields if isinstance(structured_fields, dict) else {}
    if structured_dict:
        for key in STRUCTURED_INCIDENT_FIELDS:
            value = structured_dict.get(key)
            if value not in (None, [], {}, ""):
                candidate[key] = value
    dependency_impact = structured_dict.get("dependency_impact")
    activity_signals = structured_dict.get("activity_signals")
    dissatisfaction_signals = structured_dict.get("dissatisfaction_signals")
    candidate["incident_entities"] = summarize_incident_entities(
        scope_summary,
        doc_priorities,
        dependency_impact,
        traceability_evidence,
        activity_signals,
        dissatisfaction_signals,
    )
    log_structured(
        "info",
        "Incident candidate built",
        metric="incidents.candidate_built",
        severity=severity,
        blast_radius_score=blast_radius_score,
        source_command=source_command,
        component_count=counts["components"],
        doc_count=counts["docs"],
        investigation_id=investigation_id,
        raw_trace_id=raw_trace_id,
    )
    return candidate


def summarize_incident_entities(
    scope_summary: Optional[Dict[str, Any]],
    doc_priorities: Optional[List[Dict[str, Any]]],
    dependency_impact: Optional[Dict[str, Any]],
    traceability_evidence: Optional[List[Dict[str, Any]]],
    activity_signals: Optional[Dict[str, Any]],
    dissatisfaction_signals: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    scope_summary = scope_summary or {}
    doc_priorities = doc_priorities or []
    traceability_evidence = traceability_evidence or []
    entities: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    evidence_index = _build_evidence_index(traceability_evidence)

    def _ensure_entity(entity_id: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
        entity = entities.get(entity_id)
        if entity is None:
            entity = {
                "id": entity_id,
                "name": defaults.get("name") or entity_id,
                "entityType": defaults.get("entityType") or "component",
                "activitySignals": {},
                "dissatisfactionSignals": {},
                "docStatus": None,
                "dependency": None,
                "suggestedAction": None,
                "evidenceIds": [],
            }
            entities[entity_id] = entity
        for key, value in defaults.items():
            if value is not None:
                entity[key] = value
        return entity

    # Doc priorities -> doc entities
    for idx, priority in enumerate(doc_priorities):
        if not isinstance(priority, dict):
            continue
        doc_id = str(priority.get("doc_id") or priority.get("doc_url") or priority.get("doc_title") or f"doc:{idx}")
        doc_name = priority.get("doc_title") or priority.get("doc_id") or doc_id
        entity = _ensure_entity(
            doc_id,
            {
                "name": doc_name,
                "entityType": "doc",
            },
        )
        if priority.get("reason"):
            entity["suggestedAction"] = priority["reason"]
        doc_status = dict(entity.get("docStatus") or {})
        if priority.get("reason"):
            doc_status["reason"] = priority["reason"]
        if priority.get("severity"):
            doc_status["severity"] = priority["severity"]
        if doc_status:
            entity["docStatus"] = doc_status
        entity["activitySignals"] = _merge_signal_maps(
            entity.get("activitySignals"),
            {"doc_priority": float(priority.get("score") or 1.0)},
        )
        matched_evidence = []
        matched_evidence.extend(evidence_index["by_doc"].get(doc_id, []))
        doc_url = priority.get("doc_url")
        if doc_url:
            matched_evidence.extend(evidence_index["by_doc_url"].get(doc_url, []))
        entity["evidenceIds"] = _merge_evidence_lists(entity.get("evidenceIds"), matched_evidence)

    # Dependency impacts -> component entities
    impacts = (dependency_impact or {}).get("impacts") if isinstance(dependency_impact, dict) else None
    if isinstance(impacts, list):
        for idx, impact in enumerate(impacts):
            if not isinstance(impact, dict):
                continue
            component_id = str(
                impact.get("component_id") or impact.get("componentId") or f"component:{idx}"
            )
            entity = _ensure_entity(
                component_id,
                {
                    "name": component_id,
                    "entityType": "component",
                },
            )
            entity["dependency"] = {
                "componentId": component_id,
                "dependentComponents": impact.get("dependent_components")
                or impact.get("dependentComponents")
                or [],
                "docs": impact.get("docs") or impact.get("docs_to_update") or [],
                "services": impact.get("services") or impact.get("servicesNeedingUpdates") or [],
                "exposedApis": impact.get("exposed_apis") or impact.get("exposedApis") or [],
                "depth": impact.get("depth") or (dependency_impact or {}).get("max_depth"),
                "severity": impact.get("severity"),
            }
            entity["activitySignals"] = _merge_signal_maps(
                entity.get("activitySignals"),
                {"dependent_components": len(entity["dependency"]["dependentComponents"])},
            )
            entity["dissatisfactionSignals"] = _merge_signal_maps(
                entity.get("dissatisfactionSignals"),
                {"docs_to_update": len(entity["dependency"]["docs"])},
            )
            if not entity.get("suggestedAction"):
                docs = entity["dependency"]["docs"]
                dependent_components = entity["dependency"]["dependentComponents"]
                if docs:
                    entity["suggestedAction"] = f"Update downstream docs: {', '.join(docs[:3])}"
                elif dependent_components:
                    entity["suggestedAction"] = f"Verify downstream services: {', '.join(dependent_components[:3])}"
            entity["evidenceIds"] = _merge_evidence_lists(
                entity.get("evidenceIds"),
                evidence_index["by_component"].get(component_id, []),
            )

    # Support / ticket evidence
    for idx, evidence in enumerate(traceability_evidence):
        if not isinstance(evidence, dict):
            continue
        source = str(evidence.get("source") or "").lower()
        if source not in {"support", "issue", "ticket"}:
            continue
        evidence_id = str(evidence.get("evidence_id") or evidence.get("id") or f"{source}:{idx}")
        entity = _ensure_entity(
            evidence_id,
            {
                "name": evidence.get("title") or evidence_id,
                "entityType": "ticket",
            },
        )
        entity["dissatisfactionSignals"] = _merge_signal_maps(
            entity.get("dissatisfactionSignals"),
            {f"{source}_cases": 1},
        )
        summary = (evidence.get("metadata") or {}).get("content")
        if summary and not entity.get("suggestedAction"):
            entity["suggestedAction"] = summary
        entity["evidenceIds"] = _merge_evidence_lists(entity.get("evidenceIds"), [evidence_id])

    # Slack evidence
    for idx, evidence in enumerate(traceability_evidence):
        if not isinstance(evidence, dict):
            continue
        source = str(evidence.get("source") or "").lower()
        if source != "slack":
            continue
        evidence_id = str(evidence.get("evidence_id") or f"slack:{idx}")
        entity = _ensure_entity(
            evidence_id,
            {
                "name": evidence.get("title") or "Slack thread",
                "entityType": "slack",
            },
        )
        entity["activitySignals"] = _merge_signal_maps(
            entity.get("activitySignals"),
            {"slack_threads": 1},
        )
        metadata = evidence.get("metadata") or {}
        if metadata.get("permalink") and not entity.get("suggestedAction"):
            entity["suggestedAction"] = f"Review thread in {metadata.get('channel') or '#channel'}"
        entity["evidenceIds"] = _merge_evidence_lists(entity.get("evidenceIds"), [evidence_id])

    # Git and doc activity / dissatisfaction evidence attached to components and docs
    for idx, evidence in enumerate(traceability_evidence):
        if not isinstance(evidence, dict):
            continue
        source = str(evidence.get("source") or "").lower()
        metadata = evidence.get("metadata") or {}
        evidence_id = str(
            evidence.get("evidence_id")
            or evidence.get("id")
            or evidence.get("url")
            or f"{source}:{idx}"
        )
        if not evidence_id:
            continue

        is_git_source = source in {"git", "github"}
        is_doc_source = source.startswith("doc")
        if not (is_git_source or is_doc_source):
            continue

        component_id = metadata.get("component_id") or metadata.get("component")
        doc_id = metadata.get("doc_id") or metadata.get("doc_path")
        doc_url = evidence.get("url")

        def _attach_to_entity(
            entity_id: str,
            defaults: Dict[str, Any],
            activity_delta: Optional[Dict[str, float]] = None,
            dissatisfaction_delta: Optional[Dict[str, float]] = None,
        ) -> None:
            entity = _ensure_entity(entity_id, defaults)
            if activity_delta:
                entity["activitySignals"] = _merge_signal_maps(
                    entity.get("activitySignals"),
                    activity_delta,
                )
            if dissatisfaction_delta:
                entity["dissatisfactionSignals"] = _merge_signal_maps(
                    entity.get("dissatisfactionSignals"),
                    dissatisfaction_delta,
                )
            entity["evidenceIds"] = _merge_evidence_lists(entity.get("evidenceIds"), [evidence_id])

        # Git evidence contributes git_events activity to components and docs it touches.
        if is_git_source:
            if component_id:
                _attach_to_entity(
                    str(component_id),
                    {
                        "name": str(component_id),
                        "entityType": "component",
                    },
                    activity_delta={"git_events": 1.0},
                )
            if doc_id or doc_url:
                doc_entity_id = str(doc_id or doc_url)
                _attach_to_entity(
                    doc_entity_id,
                    {
                        "name": str(doc_id or doc_url),
                        "entityType": "doc",
                    },
                    activity_delta={"git_events": 1.0},
                )

        # Doc / doc-issue style evidence contributes doc_issues to both activity and dissatisfaction.
        if is_doc_source:
            if doc_id or doc_url:
                doc_entity_id = str(doc_id or doc_url)
                _attach_to_entity(
                    doc_entity_id,
                    {
                        "name": str(doc_id or doc_url),
                        "entityType": "doc",
                    },
                    activity_delta={"doc_issues": 1.0},
                    dissatisfaction_delta={"doc_issues": 1.0},
                )
            if component_id:
                _attach_to_entity(
                    str(component_id),
                    {
                        "name": str(component_id),
                        "entityType": "component",
                    },
                    activity_delta={"doc_issues": 1.0},
                    dissatisfaction_delta={"doc_issues": 1.0},
                )

    # Aggregate fallback if nothing else exists
    if not entities and (activity_signals or dissatisfaction_signals):
        aggregate = _ensure_entity(
            "incident",
            {"name": "Incident aggregate", "entityType": "summary"},
        )
        aggregate["activitySignals"] = _merge_signal_maps(aggregate.get("activitySignals"), activity_signals)
        aggregate["dissatisfactionSignals"] = _merge_signal_maps(
            aggregate.get("dissatisfactionSignals"),
            dissatisfaction_signals,
        )
        if not aggregate.get("suggestedAction"):
            aggregate["suggestedAction"] = "See structured reasoning for recommended actions."

    return list(entities.values())


def _build_evidence_index(evidence_list: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
    index = {
        "by_id": {},
        "by_doc": defaultdict(list),
        "by_doc_url": defaultdict(list),
        "by_component": defaultdict(list),
    }
    for entry in evidence_list:
        if not isinstance(entry, dict):
            continue
        evidence_id = str(entry.get("evidence_id") or entry.get("id") or "")
        if evidence_id:
            index["by_id"][evidence_id] = entry
        metadata = entry.get("metadata") or {}
        doc_id = metadata.get("doc_id") or metadata.get("doc_path")
        if doc_id:
            index["by_doc"][str(doc_id)].append(evidence_id)
        doc_url = entry.get("url")
        if doc_url:
            index["by_doc_url"][doc_url].append(evidence_id)
        component_id = metadata.get("component_id") or metadata.get("component")
        if component_id:
            index["by_component"][str(component_id)].append(evidence_id)
    return index


def _merge_signal_maps(
    current: Optional[Dict[str, float]],
    new_values: Optional[Dict[str, float]],
) -> Dict[str, float]:
    merged: Dict[str, float] = dict(current or {})
    if not new_values:
        return merged
    for key, value in new_values.items():
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        merged[key] = round(merged.get(key, 0.0) + numeric, 4)
    return merged


def _merge_evidence_lists(existing: Optional[List[str]], additions: Optional[List[str]]) -> List[str]:
    combined: List[str] = list(existing or [])
    seen = set(combined)
    for evidence_id in additions or []:
        if not evidence_id or evidence_id in seen:
            continue
        seen.add(evidence_id)
        combined.append(evidence_id)
    return combined


def _summarize_incident_scope(
    *,
    components: List[str],
    doc_priorities: List[Dict[str, Any]],
    traceability_evidence: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[datetime]]:
    component_set = {str(component) for component in components if component}
    doc_ids: set[str] = set()
    issue_ids: set[str] = set()
    slack_threads: set[str] = set()
    git_refs: set[str] = set()
    timestamps: List[datetime] = []

    for priority in doc_priorities:
        doc_id = priority.get("doc_id")
        if doc_id:
            doc_ids.add(str(doc_id))
        ts = priority.get("updated_at") or priority.get("last_observed_at")
        parsed = _parse_evidence_timestamp(ts)
        if parsed:
            timestamps.append(parsed)

    for entry in traceability_evidence:
        source = str(entry.get("source") or "").lower()
        metadata = entry.get("metadata") or {}
        if source.startswith("doc"):
            doc_id = entry.get("evidence_id") or metadata.get("doc_id")
            if doc_id:
                doc_ids.add(str(doc_id))
        elif source in {"issue", "ticket"}:
            issue_id = entry.get("evidence_id") or metadata.get("id") or metadata.get("key")
            if issue_id:
                issue_ids.add(str(issue_id))
        elif source == "slack":
            channel = metadata.get("channel") or metadata.get("channel_id")
            ts = metadata.get("timestamp") or metadata.get("ts") or metadata.get("thread_ts")
            if channel and ts:
                slack_threads.add(f"{channel}:{ts}")
        elif source in {"git", "github"}:
            repo = metadata.get("repo") or metadata.get("repository")
            identifier = metadata.get("pr_number") or metadata.get("sha") or metadata.get("commit_sha")
            if repo and identifier:
                git_refs.add(f"{repo}:{identifier}")

        component_from_metadata = metadata.get("component_id")
        if component_from_metadata:
            component_set.add(str(component_from_metadata))

        ts_value = metadata.get("timestamp") or metadata.get("iso_time") or metadata.get("ts")
        parsed_ts = _parse_evidence_timestamp(ts_value)
        if parsed_ts:
            timestamps.append(parsed_ts)

    summary = {
        "components": sorted(component_set),
        "doc_ids": sorted(doc_ids),
        "issue_ids": sorted(issue_ids),
        "slack_threads": sorted(slack_threads),
        "git_refs": sorted(git_refs),
    }
    return summary, timestamps


def _calculate_incident_scores(
    *,
    scope_summary: Dict[str, Any],
    timestamps: List[datetime],
    evidence_sources: List[str],
) -> Tuple[str, int, Optional[Dict[str, Any]]]:
    trust_values = [
        INCIDENT_SOURCE_WEIGHTS.get(source.lower(), INCIDENT_SOURCE_WEIGHTS["unknown"])
        for source in evidence_sources
        if source
    ]
    trust_component = min(40.0, sum(trust_values) * 8.0)

    component_count = len(scope_summary.get("components", []))
    doc_count = len(scope_summary.get("doc_ids", []))
    issue_count = len(scope_summary.get("issue_ids", []))
    slack_count = len(scope_summary.get("slack_threads", []))
    git_count = len(scope_summary.get("git_refs", []))
    scope_component = min(
        35.0,
        component_count * 6 + doc_count * 4 + issue_count * 5 + (slack_count + git_count) * 3,
    )

    recency_component = 0.0
    recency_info: Optional[Dict[str, Any]] = None
    if timestamps:
        now = datetime.now(timezone.utc)
        freshness_scores: List[float] = []
        most_recent = max(timestamps)
        for ts in timestamps:
            age_hours = max(0.0, (now - ts).total_seconds() / 3600.0)
            freshness_scores.append(max(0.0, 1.0 - min(age_hours, 72.0) / 72.0))
        recency_component = min(25.0, (sum(freshness_scores) / len(freshness_scores)) * 25.0)
        recency_info = {
            "most_recent": most_recent.isoformat(),
            "hours_since": round(max(0.0, (now - most_recent).total_seconds() / 3600.0), 2),
        }

    total_score = round(min(100.0, trust_component + scope_component + recency_component))
    if total_score >= 80:
        severity = "critical"
    elif total_score >= 60:
        severity = "high"
    elif total_score >= 40:
        severity = "medium"
    else:
        severity = "low"
    return severity, total_score, recency_info


def _parse_evidence_timestamp(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc) if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (OverflowError, ValueError):
            return None
    if isinstance(raw, str):
        normalized = raw.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            try:
                as_float = float(raw)
                return datetime.fromtimestamp(as_float, tz=timezone.utc)
            except (ValueError, OverflowError):
                return None
    return None

