from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from ..slash_git.data_source import BaseGitDataSource, LiveGitDataSource, SyntheticGitDataSource
from ..slash_git.planner import GitQueryPlanner
from .cache import ActivityGraphCache, build_cache
from .metrics import activity_graph_metrics
from .models import ComponentActivity, TimeWindow
from .prioritization import DOC_SEVERITY_WEIGHTS
from .signals import DocIssueSignalsExtractor, GitSignalsExtractor, SlackSignalsExtractor

logger = logging.getLogger(__name__)


class ActivityScoringResult(NamedTuple):
    activity: float
    dissatisfaction: float
    breakdown: Dict[str, float]


class ActivityScoringEngine:
    """
    Applies configurable weights + time decay to turn raw signal events
    into Activity Graph scores.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        slack_cfg = cfg.get("slack") or {}
        git_cfg = cfg.get("git") or {}
        doc_cfg = cfg.get("doc_issues") or {}
        decay_cfg = cfg.get("time_decay") or {}

        self.slack_conversation_weight = float(slack_cfg.get("conversation_weight", 0.4))
        self.slack_complaint_weight = float(slack_cfg.get("complaint_weight", 0.9))
        self.git_commit_weight = float(git_cfg.get("commit_weight", 0.8))
        self.git_pr_weight = float(git_cfg.get("pr_weight", 1.2))

        severity_cfg = doc_cfg.get("severity_weights") or {}
        self.doc_severity_weights = {**DOC_SEVERITY_WEIGHTS, **severity_cfg}

        bucket_cfg: Dict[str, Any] = decay_cfg.get("buckets") or {}
        self.decay_rules: List[Tuple[float, float]] = self._build_decay_rules(bucket_cfg)
        self.decay_default = float(decay_cfg.get("default", 0.1))

    def score(
        self,
        git_counts,
        slack_counts,
        doc_counts,
        *,
        include_debug: bool = False,
    ) -> ActivityScoringResult:
        commit_score = self._score_git_events(git_counts.events, "commit", self.git_commit_weight)
        pr_score = self._score_git_events(git_counts.events, "pr", self.git_pr_weight)
        slack_activity_score, slack_diss_score = self._score_slack(slack_counts.events)
        doc_score = self._score_doc_issues(doc_counts)

        activity_total = commit_score + pr_score + slack_activity_score
        dissatisfaction_total = slack_diss_score + doc_score

        breakdown: Dict[str, float] = {}
        if include_debug:
            breakdown = {
                "git_commits_score": round(commit_score, 3),
                "git_prs_score": round(pr_score, 3),
                "slack_conversations_score": round(slack_activity_score, 3),
                "slack_complaints_score": round(slack_diss_score, 3),
                "doc_issues_score": round(doc_score, 3),
            }

        return ActivityScoringResult(activity_total, dissatisfaction_total, breakdown)

    def _score_git_events(self, events, kind: str, base_weight: float) -> float:
        total = 0.0
        for event in events:
            if event.kind != kind:
                continue
            total += base_weight * self._decay_multiplier(event.timestamp)
        return total

    def _score_slack(self, events) -> Tuple[float, float]:
        activity_total = 0.0
        dissatisfaction_total = 0.0
        for event in events:
            decay = self._decay_multiplier(event.timestamp)
            activity_total += self.slack_conversation_weight * decay
            if event.kind == "complaint":
                dissatisfaction_total += self.slack_complaint_weight * decay
        return activity_total, dissatisfaction_total

    def _score_doc_issues(self, counts) -> float:
        breakdown = counts.severity_breakdown or {}
        total = 0.0
        for severity, num in breakdown.items():
            if not num:
                continue
            multiplier = self.doc_severity_weights.get(severity, self.doc_severity_weights.get("medium", 1.0))
            total += num * multiplier
        if total == 0.0 and counts.severity_weight:
            # Back-compat: rely on pre-existing aggregate weight if no breakdown present.
            total = counts.severity_weight
        return total

    def _decay_multiplier(self, timestamp: Optional[datetime]) -> float:
        if not timestamp:
            return self.decay_default
        age_seconds = max(0.0, (datetime.now(timezone.utc) - timestamp).total_seconds())
        for threshold, multiplier in self.decay_rules:
            if age_seconds <= threshold:
                return multiplier
        return self.decay_default

    @staticmethod
    def _build_decay_rules(bucket_cfg: Dict[str, Any]) -> List[Tuple[float, float]]:
        rules: List[Tuple[float, float]] = []
        for label, multiplier in bucket_cfg.items():
            seconds = ActivityScoringEngine._parse_duration_seconds(label)
            if seconds is None:
                continue
            try:
                rules.append((seconds, float(multiplier)))
            except (TypeError, ValueError):
                continue
        rules.sort(key=lambda item: item[0])
        return rules or [(3600.0, 1.0), (86400.0, 0.7), (604800.0, 0.4), (2592000.0, 0.15)]

    @staticmethod
    def _parse_duration_seconds(label: Optional[str]) -> Optional[float]:
        if not label:
            return None
        normalized = str(label).strip().lower()
        try:
            if normalized.endswith("h"):
                return float(normalized[:-1]) * 3600.0
            if normalized.endswith("d"):
                return float(normalized[:-1]) * 86400.0
        except ValueError:
            return None
        return None


class ActivityGraphService:
    def __init__(
        self,
        config: Optional[Dict[str, any]] = None,
        *,
        git_source: Optional[BaseGitDataSource] = None,
        git_signals: Optional[GitSignalsExtractor] = None,
        slack_signals: Optional[SlackSignalsExtractor] = None,
        doc_issue_signals: Optional[DocIssueSignalsExtractor] = None,
        cache: Optional[ActivityGraphCache] = None,
    ):
        self.config = config or {}
        self.planner = GitQueryPlanner(self.config)
        self.catalog = self.planner.catalog

        slash_git_cfg = (self.config.get("slash_git") or {})
        ag_cfg = self.config.get("activity_graph") or {}
        if git_source is None:
            if slash_git_cfg.get("use_live_data"):
                git_source = LiveGitDataSource(self.config)
            else:
                git_source = SyntheticGitDataSource(self.config)

        git_log_path = ag_cfg.get("git_graph_path") or slash_git_cfg.get("graph_log_path")
        git_log_path = Path(git_log_path) if git_log_path else None
        self.git_signals = git_signals or GitSignalsExtractor(git_source, log_path=git_log_path)
        slack_path = Path(ag_cfg.get("slack_graph_path", "data/logs/slash/slack_graph.jsonl"))
        impact_cfg = self.config.get("impact") or {}
        data_mode = (impact_cfg.get("data_mode") or "live").lower()
        doc_default = "data/synthetic_git/doc_issues.json" if data_mode == "synthetic" else "data/live/doc_issues.json"
        doc_ingest_cfg = (self.config.get("activity_ingest") or {}).get("doc_issues") or {}
        doc_path_value = ag_cfg.get("doc_issues_path") or doc_ingest_cfg.get("path") or doc_default
        doc_path = Path(doc_path_value)
        self.slack_signals = slack_signals or SlackSignalsExtractor(slack_path)
        self.doc_issue_signals = doc_issue_signals or DocIssueSignalsExtractor(doc_path)
        self.cache = cache or build_cache(self.config)
        scoring_cfg = ag_cfg.get("scoring") or {}
        self.scoring_engine = ActivityScoringEngine(scoring_cfg)
        trend_cfg = scoring_cfg.get("trend") or {}
        self.default_window_label = trend_cfg.get("baseline_window", "7d")

    def compute_component_activity(
        self,
        component_id: str,
        time_window: TimeWindow,
        *,
        include_debug: bool = False,
    ) -> ComponentActivity:
        return self._compute_component_activity(
            component_id,
            time_window,
            include_debug=include_debug,
            allow_cache=not include_debug,
            compute_trend=True,
        )

    def _compute_component_activity(
        self,
        component_id: str,
        time_window: TimeWindow,
        *,
        include_debug: bool = False,
        allow_cache: bool = True,
        compute_trend: bool = True,
    ) -> ComponentActivity:
        component = self.catalog.get_component(component_id)
        if not component:
            raise ValueError(f"Unknown component_id: {component_id}")
        repo = self.catalog.get_repo(component.repo_id)
        if not repo:
            raise ValueError(f"Unknown repo_id: {component.repo_id}")

        cache_key = f"component::{component.id}::{time_window.label}"
        cached: Optional[ComponentActivity] = None
        if allow_cache and not include_debug:
            cached = self._cache_get(cache_key)
            if cached:
                return cached

        git_counts = self.git_signals.count_events(repo, component, time_window)
        slack_counts = self.slack_signals.count(component.id, time_window)
        doc_counts = self.doc_issue_signals.count(component.id)

        scoring_result = self.scoring_engine.score(
            git_counts,
            slack_counts,
            doc_counts,
            include_debug=include_debug,
        )

        activity_score = round(scoring_result.activity, 2)
        dissatisfaction_score = round(scoring_result.dissatisfaction, 2)
        debug_breakdown = scoring_result.breakdown if include_debug else None

        recent_slack_events = []
        for event in slack_counts.events[:3]:
            metadata = event.metadata or {}
            recent_slack_events.append(
                {
                    "kind": event.kind,
                    "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                    "channel_id": metadata.get("channel_id"),
                    "channel_name": metadata.get("channel_name"),
                    "permalink": metadata.get("permalink"),
                    "sentiment": metadata.get("sentiment"),
                    "text": metadata.get("text"),
                }
            )

        result = ComponentActivity(
            component_id=component.id,
            component_name=component.name,
            activity_score=activity_score,
            dissatisfaction_score=dissatisfaction_score,
            git_events=git_counts.total,
            slack_conversations=slack_counts.conversations,
            slack_complaints=slack_counts.complaints,
            open_doc_issues=doc_counts.open_issues,
            time_window_label=time_window.label,
            debug_breakdown=debug_breakdown,
            recent_slack_events=recent_slack_events or None,
        )
        if compute_trend:
            try:
                previous_window = time_window.previous()
                previous_activity = self._compute_component_activity(
                    component.id,
                    previous_window,
                    include_debug=False,
                    allow_cache=False,
                    compute_trend=False,
                )
                result.trend_delta = round(result.activity_score - previous_activity.activity_score, 2)
            except ValueError:
                result.trend_delta = None

        if allow_cache and not include_debug:
            self._cache_set(cache_key, result)
        return result

    def top_dissatisfied_components(self, limit: int = 5, time_window: Optional[TimeWindow] = None) -> List[ComponentActivity]:
        window = time_window or TimeWindow.from_label(self.default_window_label)
        results: List[ComponentActivity] = []
        for repo in self.catalog.iter_repos():
            for component in repo.components.values():
                results.append(self.compute_component_activity(component.id, window))
        results.sort(key=lambda item: item.dissatisfaction_score, reverse=True)
        return results[:limit]

    def top_active_components(self, limit: int = 5, time_window: Optional[TimeWindow] = None) -> List[ComponentActivity]:
        window = time_window or TimeWindow.from_label(self.default_window_label)
        results: List[ComponentActivity] = []
        for repo in self.catalog.iter_repos():
            for component in repo.components.values():
                results.append(self.compute_component_activity(component.id, window))
        results.sort(key=lambda item: item.activity_score, reverse=True)
        return results[:limit]

    def compute_quadrant(
        self,
        *,
        limit: int = 25,
        time_window: Optional[TimeWindow] = None,
    ) -> List[Dict[str, Any]]:
        """
        Normalize activity vs dissatisfaction scores for each component so frontends can render a quadrant.
        """
        window = time_window or TimeWindow.last_days(7)
        observations: List[Dict[str, Any]] = []
        for repo in self.catalog.iter_repos():
            for component in repo.components.values():
                activity = self.compute_component_activity(component.id, window)
                observations.append(
                    {
                        "activity": activity,
                        "repo_id": repo.id or component.repo_id,
                        "repo_name": repo.name or component.repo_id or "unknown_repo",
                    }
                )

        if not observations:
            return []

        max_activity = max(item["activity"].activity_score for item in observations) or 1.0
        max_diss = max(item["activity"].dissatisfaction_score for item in observations) or 1.0

        points: List[Dict[str, Any]] = []
        for entry in observations:
            activity = entry["activity"]
            normalized_activity = (
                (activity.activity_score / max_activity) * 100 if max_activity > 0 else 0.0
            )
            normalized_diss = (
                (activity.dissatisfaction_score / max_diss) * 100 if max_diss > 0 else 0.0
            )
            points.append(
                {
                    "componentId": activity.component_id,
                    "componentName": activity.component_name,
                    "repoId": entry["repo_id"],
                    "repoName": entry["repo_name"],
                    "activityScore": round(normalized_activity, 2),
                    "dissatisfactionScore": round(normalized_diss, 2),
                    "gitEvents": activity.git_events,
                    "slackConversations": activity.slack_conversations,
                    "slackComplaints": activity.slack_complaints,
                    "docIssues": activity.open_doc_issues,
                    "trendDelta": activity.trend_delta,
                    "rawActivityScore": activity.activity_score,
                    "rawDissatisfactionScore": activity.dissatisfaction_score,
                }
            )

        points.sort(key=lambda point: point["dissatisfactionScore"], reverse=True)
        return points[:limit]

    def metrics_snapshot(self) -> Dict[str, object]:
        return activity_graph_metrics.snapshot()

    def _cache_get(self, key: str) -> Optional[ComponentActivity]:
        if not self.cache:
            return None
        payload = self.cache.get(key)
        if not payload:
            activity_graph_metrics.cache_miss()
            return None
        activity_graph_metrics.cache_hit()
        logger.info("[ACTIVITY GRAPH] cache hit (%s)", key)
        return ComponentActivity(**payload)

    def _cache_set(self, key: str, value: ComponentActivity) -> None:
        if not self.cache:
            return
        logger.info("[ACTIVITY GRAPH] cache populate (%s)", key)
        self.cache.set(key, asdict(value))

