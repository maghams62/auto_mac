from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from ..utils import load_config
from .hashtag_resolver import HashtagResolver, ResolvedTarget


class SlashQueryIntent(str, Enum):
    SUMMARIZE = "summarize"
    LIST = "list"
    STATUS = "status"
    COMPARE = "compare"
    INVESTIGATE = "investigate"


@dataclass
class TimeScope:
    start: Optional[datetime]
    end: Optional[datetime]
    label: str
    source: str = "parser"

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "label": self.label,
            "source": self.source,
        }


@dataclass
class SlashQueryPlan:
    raw: str
    command: Optional[str]
    intent: SlashQueryIntent
    targets: List[ResolvedTarget] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)
    time_scope: Optional[TimeScope] = None
    keywords: List[str] = field(default_factory=list)
    required_outputs: List[str] = field(default_factory=list)
    tone: Optional[str] = None
    format_hint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw": self.raw,
            "command": self.command,
            "intent": self.intent.value,
            "targets": [target.to_dict() for target in self.targets],
            "hashtags": list(self.hashtags),
            "time_scope": self.time_scope.to_dict() if self.time_scope else None,
            "keywords": list(self.keywords),
            "required_outputs": list(self.required_outputs),
            "tone": self.tone,
            "format_hint": self.format_hint,
        }


class SlashQueryPlanner:
    """Shared intent + hashtag planner used across slash command orchestrators."""

    _STOPWORDS = {
        "the",
        "and",
        "for",
        "with",
        "about",
        "what",
        "whats",
        "when",
        "where",
        "why",
        "last",
        "this",
        "that",
        "please",
        "can",
        "you",
    }

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        hashtag_resolver: Optional[HashtagResolver] = None,
    ):
        self.config = config or load_config()
        self.hashtag_resolver = hashtag_resolver or HashtagResolver(config=self.config)

    def plan(self, text: str, *, command: Optional[str] = None) -> SlashQueryPlan:
        raw_text = text or ""
        stripped = raw_text.strip()
        hashtags = self.hashtag_resolver.extract_hashtags(stripped)
        targets = self.hashtag_resolver.resolve_many(hashtags)
        time_scope = self._extract_time_scope(stripped)
        intent = self._infer_intent(stripped, command)
        required_outputs = self._infer_required_outputs(stripped)
        format_hint = self._infer_format_hint(stripped)
        tone = self._infer_tone(stripped)
        keywords = self._extract_keywords(stripped, hashtags)

        return SlashQueryPlan(
            raw=raw_text,
            command=command,
            intent=intent,
            targets=targets,
            hashtags=hashtags,
            time_scope=time_scope,
            keywords=keywords,
            required_outputs=required_outputs,
            tone=tone,
            format_hint=format_hint,
        )

    # ------------------------------------------------------------------ #
    # Intent + tone helpers

    def _infer_intent(self, text: str, command: Optional[str]) -> SlashQueryIntent:
        lowered = text.lower()
        if "compare" in lowered or "versus" in lowered or " vs " in lowered:
            return SlashQueryIntent.COMPARE
        if any(word in lowered for word in ["status", "latest", "update", "state of"]):
            return SlashQueryIntent.STATUS
        if any(word in lowered for word in ["list", "show me", "enumerate", "top", "recent"]):
            return SlashQueryIntent.LIST
        if any(word in lowered for word in ["incident", "investigate", "root cause", "why did"]):
            return SlashQueryIntent.INVESTIGATE
        if command and command.lower() in {"git", "slack", "cerebros"} and not lowered:
            return SlashQueryIntent.STATUS
        return SlashQueryIntent.SUMMARIZE

    def _infer_required_outputs(self, text: str) -> List[str]:
        lowered = text.lower()
        outputs: List[str] = []
        if "diff" in lowered or "delta" in lowered:
            outputs.append("diff")
        if "side by side" in lowered or "side-by-side" in lowered:
            outputs.append("comparison")
        if "bullet" in lowered or "bullets" in lowered:
            outputs.append("bullets")
        if "one-liner" in lowered or "one liner" in lowered:
            outputs.append("one_liner")
        return outputs

    def _infer_format_hint(self, text: str) -> Optional[str]:
        lowered = text.lower()
        if "bullet" in lowered or "bulleted" in lowered:
            return "bullets"
        if "table" in lowered:
            return "table"
        if "one-liner" in lowered or "one liner" in lowered:
            return "one_liner"
        return None

    def _infer_tone(self, text: str) -> Optional[str]:
        lowered = text.lower()
        if "casual" in lowered:
            return "casual"
        if "formal" in lowered:
            return "formal"
        if "executive" in lowered:
            return "executive"
        if "one-liner" in lowered:
            return "concise"
        return None

    def _extract_keywords(self, text: str, hashtags: Sequence[str]) -> List[str]:
        if not text:
            return []
        tokens = re.findall(r"[A-Za-z0-9_/.\-]+", text.lower())
        excluded = {tag.lower() for tag in hashtags}
        keywords: List[str] = []
        for token in tokens:
            if len(token) <= 2:
                continue
            if token in self._STOPWORDS or token in excluded:
                continue
            if token not in keywords:
                keywords.append(token)
        return keywords[:20]

    # ------------------------------------------------------------------ #
    # Time parsing helpers

    def _extract_time_scope(self, text: str) -> Optional[TimeScope]:
        if not text:
            return None
        lowered = text.lower()
        now = datetime.now(timezone.utc)
        if "today" in lowered:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return TimeScope(start=start, end=now, label="today")
        if "yesterday" in lowered:
            start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            return TimeScope(start=start, end=end, label="yesterday")
        if "this week" in lowered:
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            return TimeScope(start=start, end=now, label="this week")
        if "last week" in lowered:
            end = now - timedelta(days=now.weekday())
            start = end - timedelta(days=7)
            return TimeScope(start=start, end=end, label="last week")

        range_match = re.search(r"(last|past)\s+(\d+)\s*(hours?|hrs?|h|days?|d|weeks?|w)", lowered)
        if range_match:
            value = int(range_match.group(2))
            unit = range_match.group(3)
            hours = value
            if unit.startswith("day") or unit == "d":
                hours = value * 24
            elif unit.startswith("week") or unit == "w":
                hours = value * 24 * 7
            start = now - timedelta(hours=hours)
            label_unit = "hours" if unit.startswith("h") else "days" if hours % 24 == 0 else "hours"
            label_value = value if label_unit != "hours" else value
            label = f"last {label_value} {label_unit}"
            return TimeScope(start=start, end=now, label=label)

        since_match = re.search(r"since\s+([0-9]{4}-[0-9]{2}-[0-9]{2})", lowered)
        if since_match:
            iso_value = since_match.group(1)
            try:
                start = datetime.fromisoformat(iso_value).replace(tzinfo=timezone.utc)
            except ValueError:
                start = None
            if start:
                return TimeScope(start=start, end=now, label=f"since {iso_value}")
        return None

