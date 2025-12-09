from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Sequence

try:  # Neo4j is optional in some environments
    from neo4j import Session  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Session = None  # type: ignore

from ..graph import GraphService
from ..utils import load_config
from ..vector.service_factory import get_vector_search_service
from ..vector.vector_search_service import VectorSearchOptions, VectorSearchService

SEVERITY_BASE: Dict[str, float] = {
    "low": 0.3,
    "medium": 0.6,
    "high": 0.85,
    "critical": 1.0,
}

IMPACT_LEVEL_BASE: Dict[str, float] = {
    "low": 0.3,
    "medium": 0.6,
    "high": 0.9,
}

DEFAULT_WEIGHTS: Dict[str, float] = {
    "slack": 0.2,
    "git": 0.2,
    "doc": 0.2,
    "semantic": 0.2,
    "graph": 0.2,
}

CRITICAL_CHANNEL_IDS = {
    "#support",
    "#incidents",
    "#billing-service",
    "#security-team",
}

SLACK_ACTIVITY_SOURCES: Sequence[str] = (
    "slack",
    "slack_message",
    "slack_thread",
    "slack_dm",
)

CRITICAL_LABELS = {
    "breaking_change",
    "billing",
    "security",
    "auth",
}

logger = logging.getLogger(__name__)

_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_VECTOR_SERVICE: Optional[VectorSearchService] = None
_VECTOR_SERVICE_UNAVAILABLE: bool = False

SEMANTIC_PAIR_WEIGHTS: Dict[str, float] = {
    "doc_vs_slack": 0.3,
    "doc_vs_git": 0.3,
    "doc_vs_api": 0.4,
}

SEMANTIC_SOURCE_TYPES: Dict[str, List[str]] = {
    "doc_vs_slack": ["slack", "slack_message", "slack_thread"],
    "doc_vs_git": ["git_commit", "git_pr"],
    "doc_vs_api": ["doc"],
}


def severity_label_from_score(score: float) -> str:
    if score >= 85:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def recency_score(updated_at: datetime, now: datetime) -> float:
    hours_open = max(0.0, (now - updated_at).total_seconds() / 3600.0)
    if hours_open <= 24:
        return 1.0
    if hours_open <= 72:
        return 0.8
    if hours_open <= 7 * 24:
        return 0.6
    if hours_open <= 30 * 24:
        return 0.4
    return 0.3


@dataclass
class SlackFeatures:
    msg_count_7d: int = 0
    thread_count_7d: int = 0
    unique_authors_7d: int = 0
    max_signal_weight: float = 0.0
    avg_signal_weight: float = 0.0
    last_seen_hours: float = 1e9
    in_critical_channels: bool = False
    label_count: int = 0


@dataclass
class GitFeatures:
    pr_count_7d: int = 0
    commit_count_7d: int = 0
    doc_change_count_7d: int = 0
    breaking_label_count_7d: int = 0
    max_signal_weight: float = 0.0
    last_seen_hours: float = 1e9


@dataclass
class DocIssueFeatures:
    base_severity_score: float = 0.5
    impact_level_score: float = 0.5
    updated_at: datetime = datetime.now(timezone.utc)
    labels: Sequence[str] = ()
    repo_id: str = ""
    doc_path: str = ""
    component_count: int = 0


@dataclass
class GraphFeatures:
    num_components: int = 0
    num_docs: int = 0
    num_services: int = 0
    num_related_doc_issues: int = 0
    num_activity_signals_7d_slack: int = 0
    num_activity_signals_7d_git: int = 0
    num_support_cases: int = 0
    downstream_components_depth2: int = 0


@dataclass
class IssueSemanticContext:
    issue_text: str
    component_ids: List[str] = field(default_factory=list)
    doc_paths: List[str] = field(default_factory=list)
    api_ids: List[str] = field(default_factory=list)
    repo_id: Optional[str] = None
    labels: Sequence[str] = ()


def compute_issue_severity(
    issue_id: str,
    *,
    graph_service: Optional[GraphService] = None,
    session: Optional[Session] = None,
    now: Optional[datetime] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Compute the blended severity score for an Issue node."""

    if not graph_service and not session:
        raise ValueError("Either graph_service or session must be provided")

    now = now or datetime.now(timezone.utc)
    weight_map = weights or DEFAULT_WEIGHTS

    runner = _QueryRunner(graph_service=graph_service, session=session)

    slack_features = extract_slack_features(runner, issue_id, now)
    git_features = extract_git_features(runner, issue_id, now)
    doc_features = extract_doc_issue_features(runner, issue_id)
    graph_features = extract_graph_features(runner, issue_id, now)

    slack_eval = _evaluate_slack_signals(slack_features)
    git_eval = _evaluate_git_activity(git_features)
    doc_eval = _evaluate_doc_issue(doc_features, now)
    semantic_detail = _semantic_severity_detailed(issue_id, runner=runner)
    graph_eval = _evaluate_graph_activity(graph_features)

    slack_score = float(slack_eval["score"])
    git_score = float(git_eval["score"])
    doc_score = float(doc_eval["score"])
    semantic_score = float(semantic_detail.get("score", 0.0))
    semantic_pairs = semantic_detail.get("pairs") or {}
    graph_score = float(graph_eval["score"])

    if (
        graph_features.num_activity_signals_7d_slack > 0
        and slack_features.msg_count_7d == 0
    ):
        logger.debug(
            "[SEVERITY_DEBUG] Slack mismatch detected for issue=%s graph_slack=%s slack_msgs=%s sources=%s",
            issue_id,
            graph_features.num_activity_signals_7d_slack,
            slack_features.msg_count_7d,
            SLACK_ACTIVITY_SOURCES,
        )

    syntactic_components = [slack_score, git_score, doc_score]
    syntactic_score = (
        sum(syntactic_components) / len(syntactic_components) if syntactic_components else 0.0
    )
    relationship_score = graph_score

    score_0_1 = (
        weight_map.get("slack", 0.0) * slack_score
        + weight_map.get("git", 0.0) * git_score
        + weight_map.get("doc", 0.0) * doc_score
        + weight_map.get("semantic", 0.0) * semantic_score
        + weight_map.get("graph", 0.0) * graph_score
    )
    score = max(0.0, min(score_0_1, 1.0)) * 100.0
    severity_label = severity_label_from_score(score)
    normalized = round(score / 10.0, 2)
    details = {
        "slack": _serialize_slack_features(slack_features),
        "git": _serialize_git_features(git_features),
        "doc": _serialize_doc_features(doc_features),
        "graph": _serialize_graph_features(graph_features),
        "semantic": {
            "pairs": semantic_pairs,
            "weighted_drift": semantic_detail.get("weighted_drift"),
            "weight_sum": semantic_detail.get("weight_sum"),
        },
    }
    contributions_float = {
        "slack": weight_map.get("slack", 0.0) * slack_score,
        "git": weight_map.get("git", 0.0) * git_score,
        "doc": weight_map.get("doc", 0.0) * doc_score,
        "semantic": weight_map.get("semantic", 0.0) * semantic_score,
        "graph": weight_map.get("graph", 0.0) * graph_score,
    }
    contributions = {key: round(value, 4) for key, value in contributions_float.items()}
    total_contribution = sum(contributions_float.values())
    try:
        assert abs(score_0_1 - total_contribution) <= 1e-6
    except AssertionError:
        logger.warning(
            "[SEVERITY_DEBUG] Contribution mismatch issue=%s score=%s contributions_sum=%s breakdown=%s weights=%s",
            issue_id,
            round(score_0_1, 6),
            round(total_contribution, 6),
            {
                "slack": round(slack_score, 6),
                "git": round(git_score, 6),
                "doc": round(doc_score, 6),
                "semantic": round(semantic_score, 6),
                "graph": round(graph_score, 6),
            },
            weight_map,
        )
    weights_payload = {
        "slack": weight_map.get("slack", 0.0),
        "git": weight_map.get("git", 0.0),
        "doc": weight_map.get("doc", 0.0),
        "semantic": weight_map.get("semantic", 0.0),
        "graph": weight_map.get("graph", 0.0),
    }

    explanation_inputs = {
        "slack": _build_explanation_input(
            label="Slack signals",
            score=slack_score,
            weight=weight_map.get("slack"),
            contribution=contributions_float["slack"],
            raw_features=details["slack"],
            terms=slack_eval.get("terms"),
        ),
        "git": _build_explanation_input(
            label="Git + doc changes",
            score=git_score,
            weight=weight_map.get("git"),
            contribution=contributions_float["git"],
            raw_features=details["git"],
            terms=git_eval.get("terms"),
        ),
        "doc": _build_explanation_input(
            label="Doc issue health",
            score=doc_score,
            weight=weight_map.get("doc"),
            contribution=contributions_float["doc"],
            raw_features=details["doc"],
            terms=doc_eval.get("terms"),
        ),
        "semantic": _build_explanation_input(
            label="Semantic drift",
            score=semantic_score,
            weight=weight_map.get("semantic"),
            contribution=contributions_float["semantic"],
            raw_features=details["semantic"],
            terms={
                "pairs": semantic_pairs,
                "weighted_drift": semantic_detail.get("weighted_drift"),
                "weight_sum": semantic_detail.get("weight_sum"),
            },
        ),
        "graph": _build_explanation_input(
            label="Blast radius / relationship graph",
            score=graph_score,
            weight=weight_map.get("graph"),
            contribution=contributions_float["graph"],
            raw_features=details["graph"],
            terms=graph_eval.get("terms"),
        ),
        "syntactic": {
            "label": "Syntactic composite",
            "score": round(syntactic_score, 4),
            "definition": "Average of Slack, Git, and Doc heuristics",
            "components": {
                "slack": round(slack_score, 4),
                "git": round(git_score, 4),
                "doc": round(doc_score, 4),
            },
        },
        "relationship": {
            "label": "Relationship / graph",
            "score": round(relationship_score, 4),
        },
    }
    explanation = {
        "formula": "CRT = 10 * Σ(weight_i × score_i)",
        "inputs": {key: value for key, value in explanation_inputs.items() if value},
        "final": {
            "score_0_1": round(score_0_1, 6),
            "score_0_10": round(score_0_1 * 10.0, 4),
            "score_0_100": round(score, 4),
            "label": severity_label,
        },
    }

    return {
        "score": round(score, 1),
        "score_0_10": normalized,
        "label": severity_label,
        "breakdown": {
            "slack": round(slack_score, 3),
            "git": round(git_score, 3),
            "doc": round(doc_score, 3),
            "semantic": round(semantic_score, 3),
            "graph": round(graph_score, 3),
            "syntactic": round(syntactic_score, 3),
            "relationship": round(relationship_score, 3),
        },
        "details": details,
        "contributions": contributions,
        "weights": weights_payload,
        "semantic_pairs": semantic_pairs,
        "explanation": explanation,
    }


class _QueryRunner:
    """Small helper to allow either GraphService or explicit Neo4j session."""

    def __init__(
        self, *, graph_service: Optional[GraphService], session: Optional[Session]
    ) -> None:
        self._graph_service = graph_service
        self._session = session

    def run(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        params = params or {}
        if self._graph_service and self._graph_service.is_available():
            return self._graph_service.run_query(query, params) or []
        if self._session is not None:
            result = self._session.run(query, params)
            rows: List[Dict[str, Any]] = []
            for record in result:
                rows.append({key: record[key] for key in record.keys()})
            return rows
        return []


def extract_slack_features(
    runner: _QueryRunner, issue_id: str, now: datetime
) -> SlackFeatures:
    """Aggregate Slack-derived ActivitySignal metrics for an issue."""

    query = """
    MATCH (i:Issue {id: $issue_id})-[:AFFECTS_COMPONENT]->(c:Component)
    MATCH (sig:ActivitySignal)-[rel:SIGNALS_COMPONENT]->(c)
    WHERE toLower(sig.source) IN $slack_sources
      AND (rel.last_seen IS NULL OR datetime(rel.last_seen) >= datetime() - duration('P7D'))
    RETURN
        count(DISTINCT sig) AS msg_count,
        count(DISTINCT sig.thread_ts) AS thread_count,
        count(DISTINCT sig.user) AS author_count,
        max(rel.signal_weight) AS max_weight,
        avg(rel.signal_weight) AS avg_weight,
        min(rel.last_seen) AS min_last_seen,
        collect(DISTINCT coalesce(sig.channel_name, sig.channel_id)) AS channels,
        reduce(acc = 0, labels IN collect(coalesce(sig.labels, [])) | acc + size(labels)) AS label_count
    """
    record = (
        runner.run(
            query,
            {"issue_id": issue_id, "slack_sources": [src.lower() for src in SLACK_ACTIVITY_SOURCES]},
        )
        or [None]
    )[0]
    if not record:
        return SlackFeatures()

    min_last_seen = _coerce_datetime(record.get("min_last_seen"), now)
    hours_since = (now - min_last_seen).total_seconds() / 3600.0 if min_last_seen else 1e9
    channels: Sequence[str] = [ch for ch in (record.get("channels") or []) if ch]

    return SlackFeatures(
        msg_count_7d=record.get("msg_count", 0) or 0,
        thread_count_7d=record.get("thread_count", 0) or 0,
        unique_authors_7d=record.get("author_count", 0) or 0,
        max_signal_weight=record.get("max_weight", 0.0) or 0.0,
        avg_signal_weight=record.get("avg_weight", 0.0) or 0.0,
        last_seen_hours=hours_since,
        in_critical_channels=any(
            (ch or "").lower() in CRITICAL_CHANNEL_IDS for ch in channels
        ),
        label_count=record.get("label_count", 0) or 0,
    )


def slack_severity(features: SlackFeatures) -> float:
    return float(_evaluate_slack_signals(features)["score"])


def _evaluate_slack_signals(features: SlackFeatures) -> Dict[str, Any]:
    msg_term = math.log1p(max(features.msg_count_7d, 0))
    thread_term = math.log1p(max(features.thread_count_7d, 0))
    author_term = math.log1p(max(features.unique_authors_7d, 0))
    recency_term = max(0.0, min(1.0, 1.0 - features.last_seen_hours / (24 * 7)))
    weight_term = min(max(features.max_signal_weight, 0.0) / 5.0, 1.0)
    channel_bonus = 0.1 if features.in_critical_channels else 0.0

    raw = (
        0.3 * msg_term
        + 0.2 * thread_term
        + 0.2 * author_term
        + 0.2 * recency_term
        + 0.1 * weight_term
        + channel_bonus
    )
    normalized = max(0.0, min(raw / 4.0, 1.0))
    if features.msg_count_7d <= 0:
        # Allow recency/weight to contribute minimally even when no Slack messages were counted,
        # so long as other signals (e.g., recency, graph-level slack activity) suggest freshness.
        normalized = min(normalized, 0.15)
    terms = {
        "msg_term": round(msg_term, 4),
        "thread_term": round(thread_term, 4),
        "author_term": round(author_term, 4),
        "recency_term": round(recency_term, 4),
        "weight_term": round(weight_term, 4),
        "channel_bonus": round(channel_bonus, 4),
        "raw_score": round(raw, 4),
        "normalized_score": round(normalized, 4),
    }
    return {"score": normalized, "terms": terms}


def extract_git_features(
    runner: _QueryRunner, issue_id: str, now: datetime
) -> GitFeatures:
    query = """
    MATCH (i:Issue {id: $issue_id})-[:AFFECTS_COMPONENT]->(c:Component)
    MATCH (sig:ActivitySignal)-[rel:SIGNALS_COMPONENT]->(c)
    WHERE sig.source IN ["github_pr", "github_commit"]
      AND (rel.last_seen IS NULL OR datetime(rel.last_seen) >= datetime() - duration('P7D'))
    RETURN
        count(DISTINCT CASE WHEN sig.source = "github_pr" THEN sig END) AS pr_count,
        count(DISTINCT CASE WHEN sig.source = "github_commit" THEN sig END) AS commit_count,
        count(DISTINCT CASE WHEN sig.is_doc_change = true THEN sig END) AS doc_changes,
        count(DISTINCT CASE WHEN "breaking_change" IN sig.labels THEN sig END) AS breaking_labels,
        max(rel.signal_weight) AS max_weight,
        min(rel.last_seen) AS min_last_seen
    """
    record = (runner.run(query, {"issue_id": issue_id}) or [None])[0]
    if not record:
        return GitFeatures()

    min_last_seen = _coerce_datetime(record.get("min_last_seen"), now)
    hours_since = (now - min_last_seen).total_seconds() / 3600.0 if min_last_seen else 1e9

    return GitFeatures(
        pr_count_7d=record.get("pr_count", 0) or 0,
        commit_count_7d=record.get("commit_count", 0) or 0,
        doc_change_count_7d=record.get("doc_changes", 0) or 0,
        breaking_label_count_7d=record.get("breaking_labels", 0) or 0,
        max_signal_weight=record.get("max_weight", 0.0) or 0.0,
        last_seen_hours=hours_since,
    )


def git_severity(features: GitFeatures) -> float:
    return float(_evaluate_git_activity(features)["score"])


def _evaluate_git_activity(features: GitFeatures) -> Dict[str, Any]:
    pr_term = math.log1p(max(features.pr_count_7d, 0))
    commit_term = math.log1p(max(features.commit_count_7d, 0))
    doc_term = math.log1p(max(features.doc_change_count_7d, 0))
    break_term = math.log1p(max(features.breaking_label_count_7d, 0))
    recency_term = max(0.0, min(1.0, 1.0 - features.last_seen_hours / (24 * 14)))
    weight_term = min(max(features.max_signal_weight, 0.0) / 5.0, 1.0)

    raw = (
        0.3 * pr_term
        + 0.2 * commit_term
        + 0.2 * doc_term
        + 0.1 * break_term
        + 0.1 * recency_term
        + 0.1 * weight_term
    )
    normalized = max(0.0, min(raw / 4.0, 1.0))
    if features.pr_count_7d == 0 and features.commit_count_7d == 0:
        normalized = 0.0
    terms = {
        "pr_term": round(pr_term, 4),
        "commit_term": round(commit_term, 4),
        "doc_term": round(doc_term, 4),
        "breaking_term": round(break_term, 4),
        "recency_term": round(recency_term, 4),
        "weight_term": round(weight_term, 4),
        "raw_score": round(raw, 4),
        "normalized_score": round(normalized, 4),
    }
    return {"score": normalized, "terms": terms}


def extract_doc_issue_features(
    runner: _QueryRunner, issue_id: str
) -> DocIssueFeatures:
    query = """
    MATCH (i:Issue {id: $issue_id})
    OPTIONAL MATCH (i)-[:AFFECTS_COMPONENT]->(c:Component)
    RETURN
        coalesce(toLower(i.severity), 'medium') AS severity,
        coalesce(toLower(i.impact_level), toLower(i.severity), 'medium') AS impact_level,
        i.updated_at AS updated_at,
        i.labels AS labels,
        i.repo_id AS repo_id,
        i.doc_path AS doc_path,
        count(DISTINCT c) AS component_count
    """
    record = (runner.run(query, {"issue_id": issue_id}) or [None])[0]
    if not record:
        return DocIssueFeatures()

    updated_at = _coerce_datetime(record.get("updated_at"), datetime.now(timezone.utc))
    severity = record.get("severity", "medium")
    impact_level = record.get("impact_level", severity)

    return DocIssueFeatures(
        base_severity_score=SEVERITY_BASE.get(severity, 0.6),
        impact_level_score=IMPACT_LEVEL_BASE.get(impact_level, 0.6),
        updated_at=updated_at,
        labels=record.get("labels") or [],
        repo_id=record.get("repo_id") or "",
        doc_path=record.get("doc_path") or "",
        component_count=record.get("component_count", 0) or 0,
    )


def doc_issue_severity(features: DocIssueFeatures, now: datetime) -> float:
    return float(_evaluate_doc_issue(features, now)["score"])


def _evaluate_doc_issue(features: DocIssueFeatures, now: datetime) -> Dict[str, Any]:
    base = 0.7 * features.base_severity_score + 0.3 * features.impact_level_score
    recency = recency_score(features.updated_at, now)
    blast = min(features.component_count / 4.0, 1.0)
    label_bonus = 0.1 if any(lbl in CRITICAL_LABELS for lbl in features.labels) else 0.0

    raw = 0.4 * base + 0.3 * blast + 0.3 * recency + label_bonus
    normalized = max(0.0, min(raw, 1.0))
    terms = {
        "base_term": round(base, 4),
        "recency_term": round(recency, 4),
        "blast_term": round(blast, 4),
        "label_bonus": round(label_bonus, 4),
        "raw_score": round(raw, 4),
        "normalized_score": round(normalized, 4),
    }
    return {"score": normalized, "terms": terms}


def semantic_severity(issue_id: str) -> float:
    """Semantic severity helper exposed for compatibility."""

    try:
        result = _semantic_severity_detailed(issue_id, runner=None)
        return float(result.get("score", 0.0))
    except Exception:
        return 0.0


def _semantic_severity_detailed(
    issue_id: str,
    runner: Optional[_QueryRunner],
) -> Dict[str, Any]:
    empty_payload: Dict[str, Any] = {
        "score": 0.0,
        "pairs": {},
        "weight_sum": 0.0,
        "weighted_drift": 0.0,
        "pair_weights": dict(SEMANTIC_PAIR_WEIGHTS),
    }
    if runner is None:
        return empty_payload

    context = _extract_issue_semantic_context(runner, issue_id)
    if not context or not context.issue_text.strip():
        return empty_payload

    vector_service = _get_vector_service()
    if not vector_service:
        return empty_payload

    pairs: Dict[str, Dict[str, Any]] = {}
    weight_sum = 0.0
    weighted_drift = 0.0

    for pair_name, weight in SEMANTIC_PAIR_WEIGHTS.items():
        pair_result = _semantic_pair_similarity(vector_service, context, pair_name)
        if not pair_result:
            continue
        similarity = max(0.0, min(pair_result["similarity"], 1.0))
        drift = max(0.0, min(1.0 - similarity, 1.0))
        pairs[pair_name] = {
            "cosine": round(similarity, 4),
            "drift": round(drift, 4),
            "matches": pair_result.get("matches", 0),
        }
        weight_sum += weight
        weighted_drift += weight * drift

    score = round(weighted_drift / weight_sum, 4) if weight_sum else 0.0
    return {
        "score": score,
        "pairs": pairs,
        "weight_sum": round(weight_sum, 4),
        "weighted_drift": round(weighted_drift, 4),
        "pair_weights": dict(SEMANTIC_PAIR_WEIGHTS),
    }


def _semantic_pair_similarity(
    service: VectorSearchService,
    context: IssueSemanticContext,
    pair_name: str,
) -> Optional[Dict[str, float]]:
    source_types = SEMANTIC_SOURCE_TYPES.get(pair_name)
    if not source_types:
        return None

    metadata_filters = _build_metadata_filters(pair_name, context)
    options = VectorSearchOptions(
        top_k=6,
        min_score=0.25,
        source_types=source_types,
        components=list(context.component_ids) or None,
        metadata_filters=metadata_filters,
    )
    try:
        results = service.semantic_search(context.issue_text, options)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug("[SEVERITY][SEM] Vector query failed for %s: %s", pair_name, exc)
        return None

    scores: List[float] = []
    for chunk in results or []:
        metadata = chunk.metadata or {}
        score_value = metadata.get("_score")
        try:
            score_float = float(score_value)
        except (TypeError, ValueError):
            continue
        scores.append(max(0.0, min(score_float, 1.0)))

    if not scores:
        return None

    return {
        "similarity": sum(scores) / len(scores),
        "matches": len(scores),
    }


def _build_metadata_filters(pair_name: str, context: IssueSemanticContext) -> Dict[str, List[str]]:
    filters: Dict[str, List[str]] = {}
    components = [comp for comp in context.component_ids if comp]

    if pair_name == "doc_vs_slack":
        if components:
            filters["component_ids"] = components
        label_values = [str(label) for label in context.labels if label]
        if label_values:
            filters["labels"] = label_values
    elif pair_name == "doc_vs_git":
        if components:
            filters["component_ids"] = components
        if context.doc_paths:
            filters["doc_paths"] = context.doc_paths
        repo_filters: List[str] = []
        if context.repo_id:
            repo_filters.append(context.repo_id)
        if repo_filters:
            filters["repo"] = repo_filters
            filters["repo_slug"] = repo_filters
    elif pair_name == "doc_vs_api":
        if context.api_ids:
            filters["apis"] = context.api_ids
        if context.doc_paths:
            filters["doc_path"] = context.doc_paths
        if components:
            filters["components"] = components

    return {key: value for key, value in filters.items() if value}


def _extract_issue_semantic_context(
    runner: _QueryRunner,
    issue_id: str,
) -> Optional[IssueSemanticContext]:
    query = """
    MATCH (i:Issue {id: $issue_id})
    OPTIONAL MATCH (i)-[:AFFECTS_COMPONENT]->(c:Component)
    OPTIONAL MATCH (i)-[:IMPACTS_DOC]->(doc:Doc)
    OPTIONAL MATCH (doc)-[:DOC_DOCUMENTS_API]->(doc_api:APIEndpoint)
    OPTIONAL MATCH (i)-[:MODIFIES_API|:MODIFIES_ENDPOINT]->(api:APIEndpoint)
    RETURN
        i.title AS title,
        i.summary AS summary,
        i.description AS description,
        i.doc_path AS issue_doc_path,
        i.repo_id AS repo_id,
        i.labels AS labels,
        collect(DISTINCT c.id) AS component_ids,
        collect(
            DISTINCT CASE
                WHEN doc IS NULL THEN NULL
                ELSE coalesce(doc.doc_path, doc.id)
            END
        ) AS doc_paths,
        collect(DISTINCT coalesce(doc_api.id, doc_api.name)) AS doc_api_ids,
        collect(DISTINCT coalesce(api.id, api.name)) AS direct_api_ids
    """
    record = (runner.run(query, {"issue_id": issue_id}) or [None])[0]
    if not record:
        return None

    component_ids = [str(cid) for cid in (record.get("component_ids") or []) if cid]
    doc_paths = [str(path) for path in (record.get("doc_paths") or []) if path]
    api_ids = [
        str(api)
        for api in (
            (record.get("doc_api_ids") or [])
            + (record.get("direct_api_ids") or [])
        )
        if api
    ]
    labels = tuple(record.get("labels") or [])

    parts: List[str] = []
    for field in ("title", "summary", "description"):
        value = record.get(field)
        if value:
            parts.append(str(value))
    doc_path = record.get("issue_doc_path")
    if doc_path:
        parts.append(f"Doc path: {doc_path}")
    if component_ids:
        parts.append(f"Components: {', '.join(component_ids)}")
    if labels:
        parts.append(f"Labels: {', '.join(str(label) for label in labels)}")

    issue_text = "\n".join(parts).strip()
    if not issue_text:
        issue_text = issue_id

    return IssueSemanticContext(
        issue_text=issue_text,
        component_ids=component_ids,
        doc_paths=doc_paths,
        api_ids=api_ids,
        repo_id=record.get("repo_id"),
        labels=labels,
    )


def _get_vector_service() -> Optional[VectorSearchService]:
    global _VECTOR_SERVICE, _VECTOR_SERVICE_UNAVAILABLE, _CONFIG_CACHE

    if _VECTOR_SERVICE:
        return _VECTOR_SERVICE
    if _VECTOR_SERVICE_UNAVAILABLE:
        return None

    try:
        if _CONFIG_CACHE is None:
            _CONFIG_CACHE = load_config()
        service = get_vector_search_service(_CONFIG_CACHE)
    except Exception as exc:  # pragma: no cover - configuration errors
        logger.debug("[SEVERITY][SEM] Vector service unavailable: %s", exc)
        _VECTOR_SERVICE_UNAVAILABLE = True
        return None

    if not service:
        _VECTOR_SERVICE_UNAVAILABLE = True
        return None

    _VECTOR_SERVICE = service
    return service


def extract_graph_features(
    runner: _QueryRunner, issue_id: str, now: datetime
) -> GraphFeatures:
    base_query = """
    MATCH (i:Issue {id: $issue_id})
    OPTIONAL MATCH (i)-[:AFFECTS_COMPONENT]->(c:Component)
    WITH i, collect(DISTINCT c.id) AS component_ids
    OPTIONAL MATCH (i)-[:IMPACTS_DOC]->(d:Doc)
    WITH i, component_ids, count(DISTINCT d) AS num_docs
    OPTIONAL MATCH (svc:Service)-[:HAS_COMPONENT]->(c:Component)
    WHERE c.id IN component_ids
    WITH i, component_ids, num_docs, count(DISTINCT svc) AS num_services
    OPTIONAL MATCH (other:Issue)-[:AFFECTS_COMPONENT]->(c2:Component)
    WHERE c2.id IN component_ids AND other.id <> i.id
    RETURN component_ids,
           size(component_ids) AS num_components,
           num_docs,
           num_services,
           count(DISTINCT other) AS num_related_doc_issues
    """

    base_record = (runner.run(base_query, {"issue_id": issue_id}) or [None])[0]
    if not base_record:
        return GraphFeatures()

    component_ids: List[str] = base_record.get("component_ids") or []
    if not component_ids:
        return GraphFeatures()

    counts = {
        "num_components": base_record.get("num_components", 0) or 0,
        "num_docs": base_record.get("num_docs", 0) or 0,
        "num_services": base_record.get("num_services", 0) or 0,
        "num_related_doc_issues": base_record.get("num_related_doc_issues", 0) or 0,
    }

    signal_params = {
        "component_ids": component_ids,
        "cutoff": now.isoformat(),
    }

    slack_query = """
    MATCH (sig:ActivitySignal)-[rel:SIGNALS_COMPONENT]->(c:Component)
    WHERE c.id IN $component_ids
      AND toLower(sig.source) IN $slack_sources
      AND (rel.last_seen IS NULL OR datetime(rel.last_seen) >= datetime($cutoff) - duration('P7D'))
    RETURN count(DISTINCT sig) AS slack_count
    """
    git_query = """
    MATCH (sig:ActivitySignal)-[rel:SIGNALS_COMPONENT]->(c:Component)
    WHERE c.id IN $component_ids
      AND sig.source IN ["github_pr", "github_commit"]
      AND (rel.last_seen IS NULL OR datetime(rel.last_seen) >= datetime($cutoff) - duration('P7D'))
    RETURN count(DISTINCT sig) AS git_count
    """
    support_query = """
    MATCH (case:SupportCase)-[rel:SUPPORTS_COMPONENT]->(c:Component)
    WHERE c.id IN $component_ids
      AND (rel.last_seen IS NULL OR datetime(rel.last_seen) >= datetime($cutoff) - duration('P7D'))
    RETURN count(DISTINCT case) AS support_count
    """
    downstream_query = """
    MATCH (c:Component)
    WHERE c.id IN $component_ids
    MATCH (c)-[:COMPONENT_USES_COMPONENT|DEPENDS_ON*1..2]->(down:Component)
    RETURN count(DISTINCT down) AS downstream_count
    """

    slack_params = dict(signal_params)
    slack_params["slack_sources"] = [src.lower() for src in SLACK_ACTIVITY_SOURCES]
    slack_record = (runner.run(slack_query, slack_params) or [None])[0] or {}
    git_record = (runner.run(git_query, signal_params) or [None])[0] or {}
    support_record = (runner.run(support_query, signal_params) or [None])[0] or {}
    downstream_record = (runner.run(downstream_query, {"component_ids": component_ids}) or [None])[0] or {}

    return GraphFeatures(
        num_components=counts["num_components"],
        num_docs=counts["num_docs"],
        num_services=counts["num_services"],
        num_related_doc_issues=counts["num_related_doc_issues"],
        num_activity_signals_7d_slack=slack_record.get("slack_count", 0) or 0,
        num_activity_signals_7d_git=git_record.get("git_count", 0) or 0,
        num_support_cases=support_record.get("support_count", 0) or 0,
        downstream_components_depth2=downstream_record.get("downstream_count", 0) or 0,
    )


def graph_severity(features: GraphFeatures) -> float:
    return float(_evaluate_graph_activity(features)["score"])


def _evaluate_graph_activity(features: GraphFeatures) -> Dict[str, Any]:
    blast_term = min(
        (
            0.4 * features.num_components
            + 0.2 * features.num_docs
            + 0.2 * features.num_services
            + 0.2 * features.downstream_components_depth2
        )
        / 10.0,
        1.0,
    )
    related_term = min(features.num_related_doc_issues / 5.0, 1.0)
    activity_raw = (
        features.num_activity_signals_7d_slack
        + features.num_activity_signals_7d_git
        + features.num_support_cases
    )
    activity_term = min(math.log1p(max(activity_raw, 0)) / 3.0, 1.0)

    raw = 0.5 * blast_term + 0.3 * activity_term + 0.2 * related_term
    normalized = max(0.0, min(raw, 1.0))
    terms = {
        "blast_term": round(blast_term, 4),
        "activity_term": round(activity_term, 4),
        "related_term": round(related_term, 4),
        "activity_signal_count": int(activity_raw),
        "raw_score": round(raw, 4),
        "normalized_score": round(normalized, 4),
    }
    return {"score": normalized, "terms": terms}


def _serialize_slack_features(features: SlackFeatures) -> Dict[str, Any]:
    recency = None
    if features.last_seen_hours < 1e8:
        recency = round(features.last_seen_hours, 2)
    return {
        "msg_count_7d": features.msg_count_7d,
        "thread_count_7d": features.thread_count_7d,
        "unique_authors_7d": features.unique_authors_7d,
        "max_signal_weight": round(features.max_signal_weight, 3),
        "avg_signal_weight": round(features.avg_signal_weight, 3),
        "last_seen_hours": recency,
        "in_critical_channels": features.in_critical_channels,
        "label_count": features.label_count,
    }


def _serialize_git_features(features: GitFeatures) -> Dict[str, Any]:
    recency = None
    if features.last_seen_hours < 1e8:
        recency = round(features.last_seen_hours, 2)
    return {
        "pr_count_7d": features.pr_count_7d,
        "commit_count_7d": features.commit_count_7d,
        "doc_change_count_7d": features.doc_change_count_7d,
        "breaking_label_count_7d": features.breaking_label_count_7d,
        "max_signal_weight": round(features.max_signal_weight, 3),
        "last_seen_hours": recency,
    }


def _serialize_doc_features(features: DocIssueFeatures) -> Dict[str, Any]:
    return {
        "base_severity_score": round(features.base_severity_score, 3),
        "impact_level_score": round(features.impact_level_score, 3),
        "updated_at": _serialize_datetime(features.updated_at),
        "labels": list(features.labels or []),
        "component_count": features.component_count,
        "repo_id": features.repo_id,
        "doc_path": features.doc_path,
    }


def _serialize_graph_features(features: GraphFeatures) -> Dict[str, Any]:
    return {
        "num_components": features.num_components,
        "num_docs": features.num_docs,
        "num_services": features.num_services,
        "num_related_doc_issues": features.num_related_doc_issues,
        "num_activity_signals_7d_slack": features.num_activity_signals_7d_slack,
        "num_activity_signals_7d_git": features.num_activity_signals_7d_git,
        "num_support_cases": features.num_support_cases,
        "downstream_components_depth2": features.downstream_components_depth2,
    }


def _build_explanation_input(
    *,
    label: str,
    score: float,
    weight: Optional[float],
    contribution: Optional[float],
    raw_features: Optional[Dict[str, Any]],
    terms: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "label": label,
        "score": round(score, 4),
    }
    if weight is not None:
        payload["weight"] = round(weight, 4)
    if contribution is not None:
        payload["contribution"] = round(contribution, 6)
    if raw_features:
        payload["raw_features"] = raw_features
    if terms:
        payload["terms"] = terms
    return payload


def _coerce_datetime(value: Any, default: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return default
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if hasattr(value, "to_native"):
        return value.to_native()
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return default
    return default


def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
