from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...integrations.slack_client import SlackAPIError
from ...integrations.slash_slack_tooling import SlashSlackToolingAdapter
from .analyzer import SlackConversationAnalyzer

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------
@dataclass
class TimeRange:
    start: Optional[datetime]
    end: Optional[datetime]

    @classmethod
    def from_hours(cls, hours: int) -> "TimeRange":
        end = datetime.now(tz=timezone.utc)
        start = end - timedelta(hours=hours)
        return cls(start=start, end=end)

    def to_slack_bounds(self) -> (Optional[str], Optional[str]):
        oldest = f"{self.start.timestamp():.6f}" if self.start else None
        latest = f"{self.end.timestamp():.6f}" if self.end else None
        return oldest, latest

    def contains(self, ts: Optional[str]) -> bool:
        if not ts:
            return True
        try:
            ts_value = float(ts)
        except (ValueError, TypeError):
            return True
        if self.start and ts_value < self.start.timestamp():
            return False
        if self.end and ts_value > self.end.timestamp():
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
        }

    def label(self) -> str:
        if not self.start:
            return "recently"
        delta = (self.end or datetime.now(tz=timezone.utc)) - self.start
        if delta.days >= 7:
            weeks = delta.days // 7
            return f"in the last {weeks} week{'s' if weeks != 1 else ''}"
        if delta.days >= 1:
            return f"in the last {delta.days} day{'s' if delta.days != 1 else ''}"
        hours = max(1, int(delta.total_seconds() // 3600))
        return f"in the last {hours} hour{'s' if hours != 1 else ''}"


@dataclass
class SlashSlackQuery:
    raw: str
    mode: str
    channel_id: Optional[str]
    channel_name: Optional[str]
    thread_ts: Optional[str]
    keywords: List[str]
    entity: Optional[str]
    time_range: TimeRange
    limit: int = 200


# ----------------------------------------------------------------------
# Parser
# ----------------------------------------------------------------------
class SlashSlackParser:
    THREAD_PATTERN = re.compile(r"https?://[^/]+/archives/(C[0-9A-Z]+)/p(\d+)")
    CHANNEL_ID_PATTERN = re.compile(r"\b(C[0-9A-Z]{8,})\b")
    CHANNEL_NAME_PATTERN = re.compile(r"#([A-Za-z0-9._-]+)")

    def __init__(self, default_channel_id: Optional[str], default_time_window_hours: int = 24):
        self.default_channel_id = default_channel_id
        self.default_time_window_hours = max(1, default_time_window_hours)

    def parse(self, command: str) -> SlashSlackQuery:
        if not command or not command.strip():
            raise ValueError("Provide a Slack request, e.g., `/slack summarize #backend last 24h`.")

        lower = command.lower()
        thread_info = self._extract_thread(command)
        channel_id = thread_info.get("channel_id") if thread_info else self._extract_channel_id(command)
        channel_name = self._extract_channel_name(command)
        thread_ts = thread_info.get("thread_ts") if thread_info else None

        mode = self._determine_mode(lower, thread_ts)
        keywords = self._extract_keywords(command)
        entity = self._extract_entity(command)
        time_range = self._extract_time_range(lower) or TimeRange.from_hours(self.default_time_window_hours)
        limit = self._extract_limit(command)

        if not channel_id and channel_name:
            # channel will be resolved later via adapter
            pass
        if not channel_id and thread_ts and not channel_name:
            channel_id = thread_info.get("channel_id")

        if not channel_id and not channel_name and mode == "channel_recap":
            channel_id = self.default_channel_id

        return SlashSlackQuery(
            raw=command.strip(),
            mode=mode,
            channel_id=channel_id,
            channel_name=channel_name,
            thread_ts=thread_ts,
            keywords=keywords,
            entity=entity,
            time_range=time_range,
            limit=limit,
        )

    def _determine_mode(self, lower: str, thread_ts: Optional[str]) -> str:
        if thread_ts:
            return "thread_recap"
        if "decision" in lower or "approve" in lower or "final" in lower:
            return "decision"
        if any(keyword in lower for keyword in ["task", "todo", "follow-up", "follow up", "action item"]):
            return "task"
        if "topic" in lower or "about" in lower or "discuss" in lower:
            return "topic"
        return "channel_recap"

    def _extract_thread(self, text: str) -> Dict[str, Optional[str]]:
        match = self.THREAD_PATTERN.search(text)
        if not match:
            return {"channel_id": None, "thread_ts": None}
        channel_id, compact_ts = match.groups()
        ts = f"{compact_ts[:-6]}.{compact_ts[-6:]}"
        return {"channel_id": channel_id, "thread_ts": ts}

    def _extract_channel_id(self, text: str) -> Optional[str]:
        match = self.CHANNEL_ID_PATTERN.search(text)
        if match:
            return match.group(1)
        return None

    def _extract_channel_name(self, text: str) -> Optional[str]:
        match = self.CHANNEL_NAME_PATTERN.search(text)
        if match:
            return match.group(1)
        return None

    def _extract_keywords(self, text: str) -> List[str]:
        tokens = []
        for token in re.findall(r"[A-Za-z0-9_/.-]+", text):
            if token.startswith("/"):
                continue
            if token.startswith("#"):
                continue
            if token.lower() in {"slack", "summarize", "summarise", "decision", "decisions", "tasks"}:
                continue
            tokens.append(token.lower())
        return tokens[:10]

    def _extract_entity(self, text: str) -> Optional[str]:
        quoted = re.search(r'"([^"]+)"', text) or re.search(r"'([^']+)'", text)
        if quoted:
            return quoted.group(1)
        about = re.search(r"(?:about|regarding|re)\s+([A-Za-z0-9 _./-]+)", text, flags=re.IGNORECASE)
        if about:
            return about.group(1).strip()
        return None

    def _extract_limit(self, text: str) -> int:
        match = re.search(r"limit\s+(\d+)", text, flags=re.IGNORECASE)
        if match:
            return max(5, min(400, int(match.group(1))))
        number_start = re.match(r"^\s*(\d+)\b", text.strip())
        if number_start:
            return max(5, min(400, int(number_start.group(1))))
        return 200

    def _extract_time_range(self, lower: str) -> Optional[TimeRange]:
        now = datetime.now(tz=timezone.utc)
        if "yesterday" in lower:
            start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            return TimeRange(start=start, end=end)
        if "today" in lower:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return TimeRange(start=start, end=now)

        match = re.search(r"last\s+(\d+)\s*(day|days|d|week|weeks|w|hour|hours|h)", lower)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            if unit.startswith("w"):
                hours = value * 24 * 7
            elif unit.startswith("d"):
                hours = value * 24
            else:
                hours = value
            return TimeRange.from_hours(hours)

        match_since = re.search(r"since\s+(\d{4}-\d{2}-\d{2})", lower)
        if match_since:
            try:
                start = datetime.fromisoformat(match_since.group(1)).replace(tzinfo=timezone.utc)
                return TimeRange(start=start, end=now)
            except ValueError:
                pass
        return None


# ----------------------------------------------------------------------
# Executors
# ----------------------------------------------------------------------
class BaseSlackExecutor:
    def __init__(self, tooling: SlashSlackToolingAdapter, default_channel_id: Optional[str] = None):
        self.tooling = tooling
        self.default_channel_id = default_channel_id

    def execute(self, query: SlashSlackQuery) -> Dict[str, Any]:  # pragma: no cover - overridden
        raise NotImplementedError

    def _resolve_channel_id(self, query: SlashSlackQuery) -> Optional[str]:
        channel_id = query.channel_id
        if not channel_id and query.channel_name:
            channel_id = self.tooling.resolve_channel_id(query.channel_name)
        if not channel_id:
            channel_id = self.default_channel_id
        return channel_id

    def _filter_by_time(self, messages: List[Dict[str, Any]], time_range: TimeRange) -> List[Dict[str, Any]]:
        return [msg for msg in messages if time_range.contains(msg.get("ts"))]

    def _conversation_id(self, *parts: Optional[str]) -> str:
        data = "|".join([part for part in parts if part])
        if not data:
            data = "slack"
        return hashlib.sha1(data.encode("utf-8")).hexdigest()[:20]

    def _build_result(
        self,
        *,
        messages: List[Dict[str, Any]],
        context: Dict[str, Any],
        keywords: List[str],
    ) -> Dict[str, Any]:
        analyzer = SlackConversationAnalyzer(messages)
        sections = analyzer.build_sections(keywords)
        summary = analyzer.build_summary(context, sections)
        graph = analyzer.build_graph(context, sections)
        preview = messages[: min(len(messages), 12)]
        return {
            "type": "slash_slack_summary",
            "message": summary,
            "sections": sections,
            "graph": graph,
            "context": context,
            "messages_preview": preview,
        }


class ChannelRecapExecutor(BaseSlackExecutor):
    def execute(self, query: SlashSlackQuery) -> Dict[str, Any]:
        channel_id = self._resolve_channel_id(query)
        if not channel_id:
            raise ValueError("Specify a channel (e.g., `/slack summarize #backend`).")

        oldest, latest = query.time_range.to_slack_bounds()
        data = self.tooling.fetch_channel_messages(channel_id, limit=query.limit, oldest=oldest, latest=latest)
        messages = self._filter_by_time(data["messages"], query.time_range)

        context = {
            "mode": "channel_recap",
            "channel_id": data["channel_id"],
            "channel_name": data["channel_name"],
            "channel_label": f"#{data['channel_name']}" if data.get("channel_name") else data["channel_id"],
            "conversation_id": self._conversation_id(data["channel_id"], oldest, latest),
            "time_window": query.time_range.to_dict(),
            "time_window_label": query.time_range.label(),
        }
        return self._build_result(messages=messages, context=context, keywords=query.keywords)


class ThreadRecapExecutor(BaseSlackExecutor):
    def execute(self, query: SlashSlackQuery) -> Dict[str, Any]:
        if not query.thread_ts:
            raise ValueError("Provide a Slack thread link to summarize.")
        channel_id = self._resolve_channel_id(query)
        if not channel_id:
            raise ValueError("Unable to determine channel for that thread.")

        data = self.tooling.fetch_thread(channel_id, query.thread_ts, limit=query.limit)
        messages = data["messages"]

        context = {
            "mode": "thread_recap",
            "channel_id": data["channel_id"],
            "channel_name": data["channel_name"],
            "channel_label": f"#{data['channel_name']}" if data.get("channel_name") else data["channel_id"],
            "thread_ts": query.thread_ts,
            "conversation_id": self._conversation_id(data["channel_id"], query.thread_ts),
            "time_window": query.time_range.to_dict(),
            "time_window_label": query.time_range.label(),
        }
        return self._build_result(messages=messages, context=context, keywords=query.keywords)


class DecisionExecutor(BaseSlackExecutor):
    def execute(self, query: SlashSlackQuery) -> Dict[str, Any]:
        search_terms = query.entity or " ".join(query.keywords) or query.raw
        channel_filter = query.channel_name or query.channel_id
        data = self.tooling.search_messages(search_terms, channel=channel_filter, limit=query.limit)
        messages = self._filter_by_time(data["messages"], query.time_range)

        context = {
            "mode": "decision",
            "channel_id": channel_filter,
            "channel_name": channel_filter,
            "channel_label": channel_filter or "Slack",
            "conversation_id": self._conversation_id(channel_filter, search_terms),
            "time_window": query.time_range.to_dict(),
            "time_window_label": query.time_range.label(),
            "search_terms": search_terms,
        }
        return self._build_result(messages=messages, context=context, keywords=query.keywords)


class TaskExecutor(BaseSlackExecutor):
    def execute(self, query: SlashSlackQuery) -> Dict[str, Any]:
        search_terms = query.entity or " ".join(query.keywords) or query.raw
        channel_filter = query.channel_name or query.channel_id
        data = self.tooling.search_messages(search_terms, channel=channel_filter, limit=query.limit)
        messages = self._filter_by_time(data["messages"], query.time_range)

        context = {
            "mode": "task",
            "channel_id": channel_filter,
            "channel_name": channel_filter,
            "channel_label": channel_filter or "Slack",
            "conversation_id": self._conversation_id(channel_filter, search_terms, "tasks"),
            "time_window": query.time_range.to_dict(),
            "time_window_label": query.time_range.label(),
            "search_terms": search_terms,
        }
        return self._build_result(messages=messages, context=context, keywords=query.keywords)


class TopicExecutor(BaseSlackExecutor):
    def execute(self, query: SlashSlackQuery) -> Dict[str, Any]:
        entity = query.entity or " ".join(query.keywords) or query.raw
        channel_filter = query.channel_name or query.channel_id
        data = self.tooling.search_messages(entity, channel=channel_filter, limit=query.limit)
        messages = self._filter_by_time(data["messages"], query.time_range)

        context = {
            "mode": "topic",
            "channel_id": channel_filter,
            "channel_name": channel_filter,
            "channel_label": channel_filter or "Slack",
            "entity": entity,
            "conversation_id": self._conversation_id(channel_filter, entity, "topic"),
            "time_window": query.time_range.to_dict(),
            "time_window_label": query.time_range.label(),
        }
        return self._build_result(messages=messages, context=context, keywords=[entity] + query.keywords)


# ----------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------
class SlashSlackOrchestrator:
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        tooling: Optional[SlashSlackToolingAdapter] = None,
    ):
        self.config = config or {}
        slack_cfg = self.config.get("slack", {})
        slash_cfg = self.config.get("slash_slack", {})
        default_channel_id = slash_cfg.get("default_channel_id") or slack_cfg.get("default_channel_id")
        default_time_window_hours = slash_cfg.get("default_time_window_hours", 24)
        workspace_url = slash_cfg.get("workspace_url")
        self.graph_emit_enabled = slash_cfg.get("graph_emit", True)

        self.tooling = tooling or SlashSlackToolingAdapter(config=self.config, workspace_url=workspace_url)
        self.parser = SlashSlackParser(default_channel_id=default_channel_id, default_time_window_hours=default_time_window_hours)
        self.executors: Dict[str, BaseSlackExecutor] = {
            "channel_recap": ChannelRecapExecutor(self.tooling, default_channel_id),
            "thread_recap": ThreadRecapExecutor(self.tooling, default_channel_id),
            "decision": DecisionExecutor(self.tooling, default_channel_id),
            "task": TaskExecutor(self.tooling, default_channel_id),
            "topic": TopicExecutor(self.tooling, default_channel_id),
        }
        log_path_str = slash_cfg.get("graph_log_path") or "data/logs/slash/slack_graph.jsonl"
        self._graph_log_path: Optional[Path] = None
        if self.graph_emit_enabled and log_path_str:
            log_path = Path(log_path_str)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._graph_log_path = log_path

    def handle(self, command: str, *, session_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            query = self.parser.parse(command)
        except ValueError as exc:
            logger.warning("[SLASH SLACK] parse error: %s", exc)
            return {"error": True, "message": str(exc)}

        executor = self.executors.get(query.mode)
        if not executor:
            return {"error": True, "message": f"Unsupported slack query type '{query.mode}'."}

        try:
            result = executor.execute(query)
        except SlackAPIError as exc:
            logger.error("[SLASH SLACK] Slack API error: %s", exc)
            return {"error": True, "message": str(exc)}
        except ValueError as exc:
            return {"error": True, "message": str(exc)}
        except Exception as exc:
            logger.exception("[SLASH SLACK] unexpected error")
            return {"error": True, "message": f"Unexpected Slack error: {exc}"}

        metadata = result.setdefault("metadata", {})
        metadata.update({
            "raw_command": command.strip(),
            "mode": query.mode,
            "session_id": session_id,
        })

        if self.graph_emit_enabled and result.get("graph"):
            self._emit_graph_payload(result["graph"], metadata)

        return result

    def _emit_graph_payload(self, graph_payload: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        if not self._graph_log_path:
            return
        entry = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "metadata": metadata,
            "graph": graph_payload,
        }
        try:
            with self._graph_log_path.open("a", encoding="utf-8") as log_file:
                json.dump(entry, log_file)
                log_file.write("\n")
        except Exception as exc:
            logger.warning("[SLASH SLACK] Failed to persist graph payload: %s", exc)

