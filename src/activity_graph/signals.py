from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .models import TimeWindow
from ..slash_git.data_source import BaseGitDataSource
from ..slash_git.models import GitTargetComponent, GitTargetRepo
from ..utils.component_ids import resolve_component_id

logger = logging.getLogger(__name__)


@dataclass
class SignalEvent:
    kind: str
    timestamp: Optional[datetime]
    metadata: Optional[Dict[str, Any]] = None


RECENCY_BUCKETS: Tuple[Tuple[str, float], ...] = (
    ("1h", 3600.0),
    ("24h", 86400.0),
    ("7d", 604800.0),
    ("30d", 2592000.0),
)
RECENCY_BUCKET_DEFAULT_LABEL = "older"


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        normalized = value
        if normalized.endswith("Z"):
            normalized = normalized.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _bucketize_events(events: Sequence[SignalEvent]) -> Dict[str, int]:
    now = datetime.now(timezone.utc)
    counts = {label: 0 for label, _ in RECENCY_BUCKETS}
    counts[RECENCY_BUCKET_DEFAULT_LABEL] = 0
    for event in events:
        if not event.timestamp:
            counts[RECENCY_BUCKET_DEFAULT_LABEL] += 1
            continue
        age_seconds = max(0.0, (now - event.timestamp).total_seconds())
        bucket_found = False
        for label, threshold in RECENCY_BUCKETS:
            if age_seconds <= threshold:
                counts[label] += 1
                bucket_found = True
                break
        if not bucket_found:
            counts[RECENCY_BUCKET_DEFAULT_LABEL] += 1
    return counts


@dataclass
class GitSignalCounts:
    commits: int
    prs: int
    events: List[SignalEvent] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.commits + self.prs

    @property
    def recency_buckets(self) -> Dict[str, int]:
        return _bucketize_events(self.events)


@dataclass
class SlackSignalCounts:
    conversations: int
    complaints: int
    events: List[SignalEvent] = field(default_factory=list)

    @property
    def recency_buckets(self) -> Dict[str, int]:
        return _bucketize_events(self.events)


@dataclass
class DocIssueCounts:
    open_issues: int
    severity_weight: float
    severity_breakdown: Dict[str, int] = field(default_factory=dict)


class GitSignalsExtractor:
    def __init__(self, data_source: BaseGitDataSource, log_path: Optional[Path] = None):
        self.data_source = data_source
        self.log_path = Path(log_path) if log_path else None

    def count_events(
        self,
        repo: GitTargetRepo,
        component: Optional[GitTargetComponent],
        window: TimeWindow,
    ) -> GitSignalCounts:
        if self.log_path and self.log_path.exists():
            from_log = self._count_from_log(component.id if component else None, window)
            if from_log:
                return from_log
        try:
            commits = self.data_source.get_commits(repo, component, window)
            prs = self.data_source.get_prs(repo, component, window)
        except Exception as exc:  # pragma: no cover - fallback path
            logger.warning("[ACTIVITY GRAPH] Failed to fetch git signals (%s); defaulting to zero.", exc)
            return GitSignalCounts(commits=0, prs=0)
        events: List[SignalEvent] = []
        for commit in commits:
            ts = commit.get("timestamp") or commit.get("date")
            events.append(
                SignalEvent(
                    kind="commit",
                    timestamp=_parse_timestamp(ts),
                    metadata={"repo": commit.get("repo"), "sha": commit.get("commit_sha") or commit.get("sha")},
                )
            )
        for pr in prs:
            events.append(
                SignalEvent(
                    kind="pr",
                    timestamp=_parse_timestamp(pr.get("timestamp")),
                    metadata={"repo": pr.get("repo"), "number": pr.get("pr_number")},
                )
            )
        return GitSignalCounts(commits=len(commits), prs=len(prs), events=events)

    def _count_from_log(self, component_id: Optional[str], window: TimeWindow) -> Optional[GitSignalCounts]:
        if not component_id:
            return None
        component_id = resolve_component_id(component_id)
        if not component_id:
            return None
        commits = 0
        prs = 0
        events: List[SignalEvent] = []
        found = False
        for event in self._read_log_events():
            components = event.get("component_ids") or []
            if component_id not in components:
                continue
            ts = event.get("timestamp") or (event.get("properties") or {}).get("timestamp")
            if not self._within_window(ts, window):
                continue
            event_type = (event.get("event_type") or event.get("type") or "").lower()
            timestamp = _parse_timestamp(ts)
            if event_type == "pr":
                prs += 1
                events.append(SignalEvent(kind="pr", timestamp=timestamp, metadata={"source": "log"}))
            else:
                commits += 1
                events.append(SignalEvent(kind="commit", timestamp=timestamp, metadata={"source": "log"}))
            found = True
        if not found:
            return None
        return GitSignalCounts(commits=commits, prs=prs, events=events)

    def _read_log_events(self) -> Iterable[Dict[str, Any]]:
        if not self.log_path or not self.log_path.exists():
            return []
        with self.log_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    @staticmethod
    def _within_window(timestamp: Optional[str], window: TimeWindow) -> bool:
        if not timestamp:
            return False
        ts_value = timestamp
        if ts_value.endswith("Z"):
            ts_value = ts_value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(ts_value)
        except ValueError:
            return False
        return window.start <= dt <= window.end


class SlackSignalsExtractor:
    def __init__(self, path: Path):
        self.path = path

    def count(self, component_id: str, window: TimeWindow) -> SlackSignalCounts:
        component_id = resolve_component_id(component_id) or component_id
        conversations = 0
        complaints = 0
        events: List[SignalEvent] = []
        for event in self._read_events():
            if component_id not in event.get("component_ids", []):
                continue
            ts = (event.get("properties") or {}).get("timestamp")
            if not self._within_window(ts, window):
                continue
            properties = event.get("properties") or {}
            conversations += 1
            labels = properties.get("labels", [])
            if any(label.lower() == "complaint" for label in labels):
                complaints += 1
                kind = "complaint"
            else:
                kind = "conversation"
            events.append(
                SignalEvent(
                    kind=kind,
                    timestamp=_parse_timestamp(ts),
                    metadata={
                        "channel_id": properties.get("channel_id"),
                        "channel_name": properties.get("channel_name"),
                        "permalink": properties.get("permalink"),
                        "text": properties.get("text"),
                        "sentiment": properties.get("sentiment"),
                    },
                )
            )
        return SlackSignalCounts(conversations=conversations, complaints=complaints, events=events)

    def _read_events(self) -> Iterable[Dict[str, any]]:
        if not self.path.exists():
            return []
        with self.path.open() as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    @staticmethod
    def _within_window(ts: Optional[str], window: TimeWindow) -> bool:
        if not ts:
            return False
        try:
            if ts.endswith("Z"):
                ts = ts.replace("Z", "+00:00")
            from datetime import datetime

            dt = datetime.fromisoformat(ts)
        except ValueError:
            return False
        return window.start <= dt <= window.end


class DocIssueSignalsExtractor:
    def __init__(self, path: Path):
        self.path = path

    def count(self, component_id: str) -> DocIssueCounts:
        component_id = resolve_component_id(component_id) or component_id
        open_count = 0
        severity_weight = 0.0
        severity_breakdown: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for issue in self._read_issues():
            if component_id not in issue.get("component_ids", []):
                continue
            if issue.get("state") != "open":
                continue
            open_count += 1
            severity = (issue.get("severity") or "medium").lower()
            normalized_severity = severity if severity in severity_breakdown else "medium"
            severity_breakdown[normalized_severity] += 1
            if normalized_severity == "critical":
                severity_weight += 2.0
            elif normalized_severity == "high":
                severity_weight += 1.5
            elif normalized_severity == "low":
                severity_weight += 0.5
            else:
                severity_weight += 1.0
        return DocIssueCounts(
            open_issues=open_count,
            severity_weight=severity_weight,
            severity_breakdown=severity_breakdown,
        )

    def _read_issues(self) -> Iterable[Dict[str, any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return []
        if isinstance(data, list):
            return data
        return []

