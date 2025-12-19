"""
Natural-language parser for /git commands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from .models import GitQueryMode, TimeWindow, normalize_alias_token


_STOPWORDS = {
    "what",
    "whats",
    "changed",
    "change",
    "in",
    "the",
    "last",
    "this",
    "week",
    "weeks",
    "day",
    "days",
    "hour",
    "hours",
    "recent",
    "repo",
    "repository",
    "component",
    "service",
    "for",
    "about",
    "on",
    "of",
    "show",
    "me",
    "please",
    "git",
    "/git",
    "latest",
    "activity",
    "happened",
    "did",
    "summary",
    "summarize",
    "since",
    "today",
    "yesterday",
    "lastweek",
    "thisweek",
}


@dataclass
class ParsedGitQuery:
    raw: str
    mode: GitQueryMode
    tokens: List[str] = field(default_factory=list)
    entity_hints: List[str] = field(default_factory=list)
    quoted_phrases: List[str] = field(default_factory=list)
    pr_number: Optional[int] = None
    issue_ids: List[str] = field(default_factory=list)
    authors: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    topic: Optional[str] = None
    time_window: Optional[TimeWindow] = None


class GitQueryParser:
    """Regex-based parser to extract Git query intents."""

    def __init__(self, default_days: int = 7):
        self.default_days = max(1, default_days)

    def parse(self, command: str) -> ParsedGitQuery:
        if not command or not command.strip():
            raise ValueError("Git parser requires a non-empty command.")

        normalized = command.strip()
        lower = normalized.lower()
        pr_number = self._extract_pr_number(lower)
        issue_ids = self._extract_issue_ids(lower)
        authors = self._extract_authors(lower)
        mode = self._infer_mode(lower, pr_number, issue_ids, authors)
        time_window = self._extract_time_window(lower)
        tokens = self._tokenize(lower)
        keywords = [token for token in tokens if token not in _STOPWORDS]
        entity_hints = self._build_entity_hints(keywords, lower)
        quoted = self._extract_quoted_phrases(normalized)
        topic = self._extract_topic(lower, quoted)

        parsed = ParsedGitQuery(
            raw=normalized,
            mode=mode,
            tokens=tokens,
            entity_hints=entity_hints,
            quoted_phrases=quoted,
            pr_number=pr_number,
            issue_ids=issue_ids,
            authors=authors,
            keywords=keywords,
            topic=topic,
            time_window=time_window,
        )
        return parsed

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r"[a-z0-9_/.-]+", text)
        normalized = []
        seen = set()
        for word in words:
            cleaned = normalize_alias_token(word)
            if cleaned and cleaned not in seen:
                normalized.append(cleaned)
                seen.add(cleaned)
        return normalized

    def _build_entity_hints(self, keywords: List[str], lower: str) -> List[str]:
        hints = list(keywords)
        range_hints = re.findall(r"(?:in|for|on)\s+([a-z0-9\-/ ]{2,40})", lower)
        time_tokens = {"last", "week", "weeks", "day", "days", "recent", "hour", "hours"}
        for hint in range_hints:
            normalized = normalize_alias_token(hint)
            if not normalized:
                continue
            tokens = [token for token in normalized.split(" ") if token]
            while tokens and (tokens[-1] in time_tokens or tokens[-1].isdigit()):
                tokens.pop()
            if tokens and tokens[0] == "the":
                tokens = tokens[1:]
            candidate = " ".join(tokens)
            if candidate and candidate not in hints:
                hints.append(candidate)
            elif normalized and normalized not in hints:
                hints.append(normalized)
        return hints

    def _extract_pr_number(self, text: str) -> Optional[int]:
        match = re.search(r"(?:pr|pull request)\s*#?(\d+)", text)
        if match:
            return int(match.group(1))
        hash_match = re.search(r"#(\d+)", text)
        if hash_match and "pr" in text:
            return int(hash_match.group(1))
        return None

    def _extract_issue_ids(self, text: str) -> List[str]:
        issue_ids: List[str] = []
        for pattern in [r"issue\s+#?([a-z0-9_-]+)", r"bug\s+#?([a-z0-9_-]+)", r"#(issue-[0-9a-z]+)"]:
            for match in re.findall(pattern, text):
                issue_ids.append(match)
        return issue_ids

    def _extract_authors(self, text: str) -> List[str]:
        authors = []
        for match in re.findall(r"\bby\s+([a-z0-9_\-./]+)", text):
            authors.append(match.strip())
        return authors

    def _infer_mode(
        self,
        text: str,
        pr_number: Optional[int],
        issue_ids: List[str],
        authors: List[str],
    ) -> GitQueryMode:
        if pr_number is not None or "pull request" in text or "/pr" in text:
            return GitQueryMode.PR_SUMMARY
        if issue_ids or "bug" in text or "issue" in text:
            return GitQueryMode.ISSUE_BUG_FOCUS
        if authors:
            return GitQueryMode.AUTHOR_FOCUS
        if "component" in text or "area" in text:
            return GitQueryMode.COMPONENT_ACTIVITY
        return GitQueryMode.REPO_ACTIVITY

    def _extract_quoted_phrases(self, text: str) -> List[str]:
        phrases: List[str] = []
        for match in re.findall(r'"([^"]+)"', text):
            cleaned = match.strip()
            if cleaned:
                phrases.append(cleaned)
        for match in re.findall(r"'([^']+)'", text):
            cleaned = match.strip()
            if cleaned:
                phrases.append(cleaned)
        return phrases

    def _extract_topic(self, lower: str, quoted_phrases: List[str]) -> Optional[str]:
        if quoted_phrases:
            return quoted_phrases[0]
        match = re.search(r"(?:about|regarding|for)\s+([a-z0-9 _./-]+)", lower)
        if match:
            topic = match.group(1).strip()
            topic = re.sub(r"\s+", " ", topic)
            return topic
        return None

    def _extract_time_window(self, text: str) -> Optional[TimeWindow]:
        now = datetime.now(timezone.utc)

        if "today" in text:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return TimeWindow(start=start, end=now, label="today", source="parser")
        if "yesterday" in text:
            start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            return TimeWindow(start=start, end=end, label="yesterday", source="parser")
        if "this week" in text:
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            return TimeWindow(start=start, end=now, label="this week", source="parser")
        if "last week" in text:
            end = now - timedelta(days=now.weekday())
            start = end - timedelta(days=7)
            return TimeWindow(start=start, end=end, label="last week", source="parser")

        range_match = re.search(r"last\s+(\d+)\s*(day|days|week|weeks|hour|hours|d|w|h)", text)
        if range_match:
            value = int(range_match.group(1))
            unit = range_match.group(2)
            hours = value
            if unit.startswith("week") or unit == "w":
                hours = value * 24 * 7
            elif unit.startswith("day") or unit == "d":
                hours = value * 24
            start = now - timedelta(hours=hours)
            label = f"last {value} {unit if unit.endswith('s') else unit}"
            return TimeWindow(start=start, end=now, label=label, source="parser")

        since_match = re.search(r"since\s+([0-9]{4}-[0-9]{2}-[0-9]{2})", text)
        if since_match:
            start = self._parse_iso_date(since_match.group(1))
            if start:
                return TimeWindow(start=start, end=now, label=f"since {since_match.group(1)}", source="parser")

        return None

    def _parse_iso_date(self, value: str) -> Optional[datetime]:
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None

