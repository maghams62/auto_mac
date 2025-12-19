from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Literal, Sequence


SourceType = Literal["slack_message", "slack_thread_summary", "git_commit", "git_pr"]


@dataclass
class ActivityEvent:
    id: str
    source_type: SourceType
    text_raw: str
    timestamp: datetime

    service_ids: List[str] = field(default_factory=list)
    component_ids: List[str] = field(default_factory=list)
    apis: List[str] = field(default_factory=list)

    repo: str | None = None
    branch: str | None = None
    channel: str | None = None
    channel_id: str | None = None
    labels: List[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def _load_json(path: Path) -> List[dict]:
    if path.suffix == ".jsonl":
        records = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
        return records
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        raise ValueError("Missing timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {value}") from exc


def _normalize_slack(record: dict) -> ActivityEvent:
    source_type = record["source_type"]
    if source_type not in {"slack_message", "slack_thread_summary"}:
        raise ValueError(f"Unexpected slack source_type {source_type}")

    return ActivityEvent(
        id=record["id"],
        source_type=source_type,  # type: ignore[arg-type]
        text_raw=record["text_raw"],
        timestamp=_parse_timestamp(record["timestamp"]),
        service_ids=list(record.get("service_ids", [])),
        component_ids=list(record.get("component_ids", [])),
        apis=list(record.get("related_apis", [])),
        channel=record.get("channel"),
        channel_id=record.get("channel_id"),
        labels=list(record.get("labels", [])),
        raw=record,
    )


def _normalize_git(record: dict) -> ActivityEvent:
    source_type = record["source_type"]
    if source_type not in {"git_commit", "git_pr"}:
        raise ValueError(f"Unexpected git source_type {source_type}")

    return ActivityEvent(
        id=record["id"],
        source_type=source_type,  # type: ignore[arg-type]
        text_raw=record.get("text_for_embedding") or record.get("message") or "",
        timestamp=_parse_timestamp(record["timestamp"]),
        service_ids=list(record.get("service_ids", [])),
        component_ids=list(record.get("component_ids", [])),
        apis=list(record.get("changed_apis") or record.get("related_apis") or []),
        repo=record.get("repo"),
        branch=record.get("branch"),
        labels=list(record.get("labels", [])),
        raw=record,
    )


def load_slack_events(path: str | Path) -> List[ActivityEvent]:
    records = _load_json(Path(path))
    return [_normalize_slack(rec) for rec in records]


def load_git_events(path: str | Path) -> List[ActivityEvent]:
    records = _load_json(Path(path))
    return [_normalize_git(rec) for rec in records]


def load_all_events(
    slack_path: str | Path,
    git_path: str | Path,
) -> List[ActivityEvent]:
    events: List[ActivityEvent] = []
    events.extend(load_slack_events(slack_path))
    events.extend(load_git_events(git_path))
    return events

