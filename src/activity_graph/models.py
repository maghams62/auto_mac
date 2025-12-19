from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


@dataclass
class TimeWindow:
    start: datetime
    end: datetime
    label: str

    @classmethod
    def last_days(cls, days: int) -> "TimeWindow":
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        return cls(start=start, end=now, label=f"last {days} days")

    @classmethod
    def from_label(cls, label: str) -> "TimeWindow":
        normalized = (label or "").strip().lower()
        if normalized.endswith("d"):
            days = int(normalized[:-1] or 7)
            return cls.last_days(days)
        if normalized.endswith("h"):
            hours = int(normalized[:-1] or 24)
            now = datetime.now(timezone.utc)
            start = now - timedelta(hours=hours)
            return cls(start=start, end=now, label=f"last {hours} hours")
        if normalized.endswith("w"):
            weeks = int(normalized[:-1] or 1)
            return cls.last_days(weeks * 7)
        # Default to 7 days if label is empty/unknown
        return cls.last_days(7)

    def previous(self) -> "TimeWindow":
        duration = self.end - self.start
        new_end = self.start
        new_start = new_end - duration
        return TimeWindow(
            start=new_start,
            end=new_end,
            label=f"previous {self.label}",
        )


@dataclass
class ComponentActivity:
    component_id: str
    component_name: str
    activity_score: float
    dissatisfaction_score: float
    git_events: int
    slack_conversations: int
    slack_complaints: int
    open_doc_issues: int
    time_window_label: str
    debug_breakdown: Optional[Dict[str, float]] = None
    trend_delta: Optional[float] = None
    recent_slack_events: Optional[List[Dict[str, Any]]] = None

