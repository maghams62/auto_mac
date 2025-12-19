from __future__ import annotations

import json
import logging
import os
import re
import threading
from dataclasses import dataclass, replace, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hashlib
import httpx

from ...integrations.slack_client import SlackAPIError
from ...integrations.slash_slack_tooling import SlashSlackToolingAdapter
from ...reasoners import DocDriftAnswer, DocDriftReasoner
from .analyzer import SlackConversationAnalyzer
from .llm_formatter import SlashSlackLLMFormatter
from ...services.slack_context_service import SlackContextService
from ...services.slack_metadata import SlackMetadataService
from ...utils.slack import normalize_channel_name
from ...settings.automation import allows_auto_suggestions

if TYPE_CHECKING:
    from ...services.slash_query_plan import SlashQueryPlan

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
    channel_scope_ids: List[str] = field(default_factory=list)
    channel_scope_labels: List[str] = field(default_factory=list)
    unresolved_channel_tokens: List[str] = field(default_factory=list)


# ----------------------------------------------------------------------
# Parser
# ----------------------------------------------------------------------
class SlashSlackParser:
    THREAD_PATTERN = re.compile(r"https?://[^/]+/archives/(C[0-9A-Z]+)/p(\d+)")
    CHANNEL_ID_PATTERN = re.compile(r"\b(C[0-9A-Z]{8,})\b")
    CHANNEL_NAME_PATTERN = re.compile(r"#([A-Za-z0-9._-]+)")
    CHANNEL_HINT_PATTERN = re.compile(
        r"(?:conversation\s+in|in|from|on|within|channel)\s+([#A-Za-z0-9._\-/ ]{2,80})",
        flags=re.IGNORECASE,
    )

    @staticmethod
    def _normalize_channel_token(token: Optional[str]) -> Optional[str]:
        return normalize_channel_name(token)

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
            return self._normalize_channel_token(match.group(1))
        return None

    def extract_channel_hints(self, text: str) -> List[str]:
        hints: List[str] = []
        for match in self.CHANNEL_HINT_PATTERN.finditer(text):
            candidate = match.group(1)
            tokens = re.findall(r"[A-Za-z0-9._-]+", candidate)
            if not tokens:
                continue
            for length in range(len(tokens), 0, -1):
                joined = "-".join(tokens[:length])
                normalized = self._normalize_channel_token(joined)
                if normalized:
                    hints.append(normalized)
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for hint in hints:
            if hint not in seen:
                seen.add(hint)
                unique.append(hint)
        return unique

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

    def _resolve_channel_id(self, query: SlashSlackQuery, *, require: bool = False) -> Optional[str]:
        channel_id = query.channel_id
        channel_requested = bool(query.channel_name or query.channel_id)
        if not channel_id and query.channel_name:
            channel_id = self.tooling.resolve_channel_id(query.channel_name)
            if not channel_id and require:
                channel_label = f"#{query.channel_name}"
                suggestions = self.tooling.suggest_channels(query.channel_name, limit=5)
                if suggestions:
                    formatted = ", ".join(f"#{name}" for name in suggestions)
                    raise ValueError(f"Slack channel {channel_label} was not found. Did you mean: {formatted}?")
                raise ValueError(f"Slack channel {channel_label} was not found.")
        if not channel_id:
            channel_id = self.default_channel_id
        if require and not channel_id:
            raise ValueError("Specify a channel (e.g., `/slack summarize #backend`).")
        if require and not channel_requested and channel_id == self.default_channel_id and not query.channel_name:
            # When no explicit channel was provided, note that we're using the default silently
            logger.debug("Using default channel_id=%s for channel recap", channel_id)
        return channel_id

    def _filter_by_time(self, messages: List[Dict[str, Any]], time_range: TimeRange) -> List[Dict[str, Any]]:
        return [msg for msg in messages if time_range.contains(msg.get("ts"))]

    def _conversation_id(self, *parts: Optional[str]) -> str:
        data = "|".join([part for part in parts if part])
        if not data:
            data = "slack"
        return hashlib.sha1(data.encode("utf-8")).hexdigest()[:20]

    def _build_analysis(
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
            "summary": summary,
            "sections": sections,
            "graph": graph,
            "context": context,
            "messages_preview": preview,
            "messages": messages,
        }


class ChannelRecapExecutor(BaseSlackExecutor):
    def execute(self, query: SlashSlackQuery) -> Dict[str, Any]:
        channel_id = self._resolve_channel_id(query, require=True)
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
        return self._build_analysis(messages=messages, context=context, keywords=query.keywords)


class ThreadRecapExecutor(BaseSlackExecutor):
    def execute(self, query: SlashSlackQuery) -> Dict[str, Any]:
        if not query.thread_ts:
            raise ValueError("Provide a Slack thread link to summarize.")
        channel_id = self._resolve_channel_id(query, require=True)
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
        return self._build_analysis(messages=messages, context=context, keywords=query.keywords)


class DecisionExecutor(BaseSlackExecutor):
    def execute(self, query: SlashSlackQuery) -> Dict[str, Any]:
        search_terms = query.entity or " ".join(query.keywords) or query.raw
        channel_filter = query.channel_id or query.channel_name
        data = self.tooling.search_messages(search_terms, channel=channel_filter, limit=query.limit)
        warnings = list(dict.fromkeys(data.get("warnings") or []))
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
        analysis = self._build_analysis(messages=messages, context=context, keywords=query.keywords)
        if warnings:
            prior = analysis.get("warnings") or []
            analysis["warnings"] = list(dict.fromkeys(prior + warnings))
        return analysis


class TaskExecutor(BaseSlackExecutor):
    def execute(self, query: SlashSlackQuery) -> Dict[str, Any]:
        search_terms = query.entity or " ".join(query.keywords) or query.raw
        channel_filter = query.channel_id or query.channel_name
        data = self.tooling.search_messages(search_terms, channel=channel_filter, limit=query.limit)
        warnings = list(dict.fromkeys(data.get("warnings") or []))
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
        analysis = self._build_analysis(messages=messages, context=context, keywords=query.keywords)
        if warnings:
            prior = analysis.get("warnings") or []
            analysis["warnings"] = list(dict.fromkeys(prior + warnings))
        return analysis


class TopicExecutor(BaseSlackExecutor):
    def execute(self, query: SlashSlackQuery) -> Dict[str, Any]:
        entity = query.entity or " ".join(query.keywords) or query.raw
        channel_filter = query.channel_id or query.channel_name
        data = self.tooling.search_messages(entity, channel=channel_filter, limit=query.limit)
        warnings = list(dict.fromkeys(data.get("warnings") or []))
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
        analysis = self._build_analysis(messages=messages, context=context, keywords=[entity] + query.keywords)
        if warnings:
            prior = analysis.get("warnings") or []
            analysis["warnings"] = list(dict.fromkeys(prior + warnings))
        return analysis


# ----------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------
class SlashSlackMetadataSingleton:
    """Provide a shared metadata service instance for slash flows."""

    _instance: Optional[SlackMetadataService] = None
    _lock = threading.Lock()

    @classmethod
    def get(cls, config: Optional[Dict[str, Any]] = None) -> SlackMetadataService:
        with cls._lock:
            if cls._instance is None:
                if config is None:
                    raise ValueError("Config required to initialize Slack metadata service.")
                cls._instance = SlackMetadataService(config=config)
            return cls._instance


class SlashSlackOrchestrator:
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        tooling: Optional[SlashSlackToolingAdapter] = None,
        llm_formatter: Optional[SlashSlackLLMFormatter] = None,
        reasoner: Optional[DocDriftReasoner] = None,
        metadata_service: Optional[SlackMetadataService] = None,
    ):
        self.config = config or {}
        slack_cfg = self.config.get("slack", {})
        slash_cfg = self.config.get("slash_slack", {})
        default_channel_id = slash_cfg.get("default_channel_id") or slack_cfg.get("default_channel_id")
        default_time_window_hours = slash_cfg.get("default_time_window_hours", 24)
        workspace_url = slash_cfg.get("workspace_url")
        self.graph_emit_enabled = slash_cfg.get("graph_emit", True)
        self.debug_block_enabled = slash_cfg.get("debug_block_enabled", True)
        self.debug_source_label = (
            slash_cfg.get("debug_source_label")
            or slack_cfg.get("debug_source_label")
            or "synthetic_slack"
        )

        self.metadata_service = metadata_service or SlashSlackMetadataSingleton.get(config=self.config)
        self.tooling = tooling or SlashSlackToolingAdapter(
            config=self.config,
            workspace_url=workspace_url,
            metadata_service=self.metadata_service,
        )
        self.context_service = SlackContextService(config=self.config)
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
        if llm_formatter is not None:
            self.llm_formatter = llm_formatter
        else:
            try:
                self.llm_formatter = SlashSlackLLMFormatter(self.config)
            except Exception as exc:
                logger.warning("[SLASH SLACK] Unable to initialize LLM formatter: %s", exc)
                self.llm_formatter = None

        reasoner_enabled = slash_cfg.get("doc_drift_reasoner", True)
        self.doc_drift_keywords = [
            kw.lower()
            for kw in slash_cfg.get("doc_drift_keywords", ["doc drift", "drift", "api drift"])
            if isinstance(kw, str) and kw.strip()
        ]
        self.empty_channel_fallback_hours = slash_cfg.get("empty_channel_fallback_hours", 72)
        self.empty_channel_search_limit = slash_cfg.get("empty_channel_search_limit", 40)
        self.reasoner: Optional[DocDriftReasoner] = None
        if reasoner_enabled:
            if reasoner is not None:
                self.reasoner = reasoner
            else:
                try:
                    self.reasoner = DocDriftReasoner(self.config)
                except Exception as exc:
                    logger.warning("[SLASH SLACK] Unable to initialize doc drift reasoner: %s", exc)
                    self.reasoner = None
        impact_cfg = self.config.get("impact") or {}
        self.impact_auto_enabled = allows_auto_suggestions("api_params")
        self.impact_endpoint_base = impact_cfg.get("endpoint_base") or os.getenv("IMPACT_ENDPOINT_BASE")
    def handle(
        self,
        command: str,
        *,
        session_id: Optional[str] = None,
        plan: Optional["SlashQueryPlan"] = None,
    ) -> Dict[str, Any]:
        reasoner_payload = self._maybe_handle_with_reasoner(command, session_id=session_id)
        if reasoner_payload is not None:
            if plan:
                metadata = reasoner_payload.setdefault("metadata", {})
                metadata["query_plan"] = plan.to_dict()
            return reasoner_payload

        try:
            query = self.parser.parse(command)
            query = self._maybe_assign_channel_hint(query, command)
            query = self._ensure_scope_metadata(query)
        except ValueError as exc:
            logger.warning("[SLASH SLACK] parse error: %s", exc)
            return {"error": True, "message": str(exc)}

        if plan:
            query = self._apply_plan_to_query(query, plan)
            query = self._ensure_scope_metadata(query)

        executor = self.executors.get(query.mode)
        if not executor:
            return {"error": True, "message": f"Unsupported slack query type '{query.mode}'."}

        try:
            analysis = None
            if plan and not (query.channel_id or query.channel_name):
                analysis = self._build_semantic_analysis(plan, query)
            if not analysis:
                analysis = executor.execute(query)
            analysis = self._apply_empty_channel_fallback(query, executor, analysis)
            if plan and not (analysis.get("messages") or query.thread_ts):
                semantic_fallback = self._build_semantic_analysis(plan, query)
                if semantic_fallback:
                    prior_warnings = list(dict.fromkeys(analysis.get("warnings") or []))
                    if prior_warnings:
                        combined = list(dict.fromkeys(prior_warnings + (semantic_fallback.get("warnings") or [])))
                        semantic_fallback["warnings"] = combined
                    analysis = semantic_fallback
        except SlackAPIError as exc:
            logger.error("[SLASH SLACK] Slack API error: %s", exc)
            return {"error": True, "message": str(exc)}
        except ValueError as exc:
            return {"error": True, "message": str(exc)}
        except Exception as exc:
            logger.exception("[SLASH SLACK] unexpected error")
            return {"error": True, "message": f"Unexpected Slack error: {exc}"}

        context = analysis.setdefault("context", {})
        if query.channel_scope_labels:
            labels = context.setdefault("channel_scope_labels", [])
            for label in query.channel_scope_labels:
                if label not in labels:
                    labels.append(label)
        if query.channel_scope_ids:
            context.setdefault("channel_scope_ids", list(dict.fromkeys(query.channel_scope_ids)))
        if query.unresolved_channel_tokens:
            context.setdefault("channel_resolution_warnings", list(dict.fromkeys(query.unresolved_channel_tokens)))
        channel_label = context.get("channel_label")
        if channel_label:
            labels = context.setdefault("channel_scope_labels", [])
            if not labels:
                labels.append(channel_label)
            elif len(labels) == 1:
                labels[0] = channel_label
            elif channel_label not in labels:
                labels.append(channel_label)

        llm_payload: Optional[Dict[str, Any]] = None
        llm_error: Optional[str] = None
        if self.llm_formatter:
            try:
                llm_payload, llm_error = self.llm_formatter.generate(
                    query=self._serialize_query(query),
                    context=analysis.get("context", {}),
                    sections=analysis.get("sections", {}),
                    messages=analysis.get("messages", []),
                    graph=analysis.get("graph"),
                )
            except Exception as exc:
                logger.warning("[SLASH SLACK] LLM formatter raised error: %s", exc)
                llm_payload = None
                llm_error = str(exc)

        final_result = self._build_final_payload(
            command=command,
            session_id=session_id,
            query=query,
            analysis=analysis,
            llm_payload=llm_payload,
            llm_error=llm_error,
        )
        if plan:
            metadata = final_result.setdefault("metadata", {})
            metadata["query_plan"] = plan.to_dict()

        tooling_warnings: List[str] = []
        if hasattr(self.tooling, "consume_warnings"):
            tooling_warnings = list(dict.fromkeys(self.tooling.consume_warnings() or []))
        if tooling_warnings:
            metadata = final_result.setdefault("metadata", {})
            existing = metadata.get("retrieval_warnings") or []
            metadata["retrieval_warnings"] = list(dict.fromkeys(existing + tooling_warnings))

        msg_count = len(analysis.get("messages") or [])
        context = analysis.get("context") or {}
        if plan:
            self._attach_plan_context(context, plan)
            analysis["context"] = context
        logger.info(
            "[SLASH SLACK] Completed %s for channel=%s (%s messages)",
            query.mode,
            context.get("channel_label") or query.channel_name or query.channel_id or "unknown",
            msg_count,
        )

        graph_payload = final_result.get("graph")
        metadata = final_result.get("metadata", {})
        if self.graph_emit_enabled and graph_payload:
            self._emit_graph_payload(graph_payload, metadata)

        if self.impact_auto_enabled:
            self._enqueue_slack_impact(command, analysis, final_result)

        return final_result

    def _maybe_handle_with_reasoner(
        self,
        command: str,
        *,
        session_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if not self.reasoner:
            return None
        if not command or not command.strip():
            return None
        if not self._should_use_reasoner(command):
            return None
        try:
            answer = self.reasoner.answer_question(command, source="slack")
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("[SLASH SLACK] Doc drift reasoner failed: %s", exc)
            return None
        logger.info("[SLASH SLACK] Doc drift reasoner handled command '%s'", command.strip()[:80])
        if answer.error:
            logger.debug("[SLASH SLACK] Doc drift reasoner reported error: %s", answer.error)
        return self._build_reasoner_payload(command=command, session_id=session_id, answer=answer)

    def _should_use_reasoner(self, command: str) -> bool:
        if not self.doc_drift_keywords:
            return False
        lower = command.lower()
        return any(keyword in lower for keyword in self.doc_drift_keywords)

    def _build_reasoner_payload(
        self,
        *,
        command: str,
        session_id: Optional[str],
        answer: DocDriftAnswer,
    ) -> Dict[str, Any]:
        sections = answer.sections or {
            "topics": [{"title": "Doc drift overview", "insight": answer.summary, "evidence_ids": []}],
            "decisions": [],
            "tasks": [],
            "open_questions": [],
            "references": [],
        }
        if answer.next_steps:
            tasks = sections.setdefault("tasks", [])
            for step in answer.next_steps:
                tasks.append(
                    {
                        "description": step,
                        "assignees": [],
                        "due": "",
                        "timestamp": "",
                        "permalink": "",
                        "evidence_ids": [],
                    }
                )

        graph_payload = self._graph_payload_from_reasoner(answer)
        context = {
            "mode": "doc_drift",
            "question": answer.question,
            "scenario": answer.scenario.name,
            "api": answer.scenario.api,
            "graph_summary": self._graph_context_dict(answer),
            "vector_counts": {
                "slack": len(answer.vector_bundle.slack),
                "git": len(answer.vector_bundle.git),
                "docs": len(answer.vector_bundle.docs),
            },
        }
        metadata = {
            "raw_command": command.strip(),
            "mode": "doc_drift_reasoner",
            "session_id": session_id,
            "llm_used": True,
            "llm_error": answer.error,
        }
        metadata.update(answer.metadata or {})

        return {
            "type": "slash_slack_summary",
            "message": answer.summary,
            "sections": sections,
            "context": context,
            "graph": graph_payload,
            "entities": self._entities_from_reasoner(answer),
            "doc_drift": answer.doc_drift,
            "evidence": answer.evidence,
            "metadata": metadata,
        }

    def _apply_empty_channel_fallback(
        self,
        query: SlashSlackQuery,
        executor: BaseSlackExecutor,
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        messages = analysis.get("messages") or []
        if messages:
            return analysis
        if query.mode not in {"channel_recap"}:
            return analysis

        context = analysis.get("context") or {}
        channel_id = query.channel_id or context.get("channel_id")
        channel_label = context.get("channel_label") or query.channel_name or channel_id or "unknown"

        if self.empty_channel_fallback_hours:
            try:
                fallback_range = TimeRange.from_hours(self.empty_channel_fallback_hours)
                fallback_query = replace(query, time_range=fallback_range)
                logger.info(
                    "[SLASH SLACK] No recent messages for %s, expanding lookback to %sh",
                    channel_label,
                    self.empty_channel_fallback_hours,
                )
                analysis = executor.execute(fallback_query)
                context = analysis.setdefault("context", {})
                fallback_meta = context.setdefault("fallback", {})
                fallback_meta["expanded_time_window_hours"] = self.empty_channel_fallback_hours
                messages = analysis.get("messages") or []
            except Exception as exc:
                logger.warning("[SLASH SLACK] Expanded lookback failed: %s", exc)

        if messages or not channel_id:
            return analysis

        search_terms = " ".join(query.keywords).strip() or query.raw
        if not search_terms:
            return analysis

        try:
            logger.info(
                "[SLASH SLACK] Search fallback for %s with query '%s' (limit=%s)",
                channel_label,
                search_terms,
                self.empty_channel_search_limit,
            )
            search_data = self.tooling.search_messages(
                search_terms,
                channel=channel_id,
                limit=self.empty_channel_search_limit,
            )
            warnings = list(dict.fromkeys(search_data.get("warnings") or []))
            if warnings:
                analysis.setdefault("warnings", []).extend(warnings)
                context = analysis.setdefault("context", {})
                fallback_meta = context.setdefault("fallback", {})
                fallback_meta.setdefault("warnings", [])
                fallback_meta["warnings"].extend(warnings)
            search_messages = search_data.get("messages", [])
            if search_messages:
                context = analysis.get("context") or {}
                fallback_meta = context.setdefault("fallback", {})
                fallback_meta["search_terms"] = search_terms
                fallback_meta["search_matches"] = len(search_messages)
                new_analysis = executor._build_analysis(
                    messages=search_messages,
                    context=context,
                    keywords=query.keywords,
                )
                combined_warnings = list(dict.fromkeys((analysis.get("warnings") or []) + warnings))
                if combined_warnings:
                    new_analysis["warnings"] = combined_warnings
                return new_analysis
        except Exception as exc:
            logger.warning("[SLASH SLACK] Search fallback failed: %s", exc)

        return analysis

    def _graph_context_dict(self, answer: DocDriftAnswer) -> Dict[str, Any]:
        return {
            "api": answer.graph_summary.api,
            "services": answer.graph_summary.services,
            "components": answer.graph_summary.components,
            "docs": answer.graph_summary.docs,
            "git_events": answer.graph_summary.git_events,
            "slack_events": answer.graph_summary.slack_events,
        }

    def _graph_payload_from_reasoner(self, answer: DocDriftAnswer) -> Optional[Dict[str, Any]]:
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        seen: set[str] = set()

        def add_node(node_id: Optional[str], node_type: str, props: Dict[str, Any]) -> None:
            if not node_id or node_id in seen:
                return
            nodes.append({"id": node_id, "type": node_type, "props": props})
            seen.add(node_id)

        api_id = f"api::{answer.scenario.api}"
        add_node(api_id, "APIEndpoint", {"api": answer.scenario.api})

        for service in answer.impacted.get("services", []):
            node_id = f"service::{service}"
            add_node(node_id, "Service", {"service_id": service})
            edges.append({"from": node_id, "to": api_id, "type": "IMPACTS_API"})

        for component in answer.impacted.get("components", []):
            node_id = f"component::{component}"
            add_node(node_id, "Component", {"component_id": component})
            edges.append({"from": node_id, "to": api_id, "type": "EXPOSES_API"})

        for doc in answer.impacted.get("docs", []):
            node_id = f"doc::{doc}"
            add_node(node_id, "DocSection", {"doc": doc})
            edges.append({"from": node_id, "to": api_id, "type": "DOCUMENTS"})

        for drift in answer.doc_drift:
            drift_id = f"doc_drift::{drift.get('doc') or drift.get('issue')}"
            add_node(drift_id, "DocDrift", drift)
            edges.append({"from": drift_id, "to": api_id, "type": "DRIFT_ALERT"})

        for ev in answer.evidence:
            ev_id = ev.get("id")
            add_node(ev_id, "Evidence", ev)
            edges.append({"from": ev_id, "to": api_id, "type": "HAS_EVIDENCE"})

        if not nodes:
            return None
        return {"nodes": nodes, "edges": edges}

    def _entities_from_reasoner(self, answer: DocDriftAnswer) -> List[Dict[str, Any]]:
        entities: List[Dict[str, Any]] = []
        impacted = answer.impacted

        for api in impacted.get("apis", []):
            entities.append(
                {
                    "name": api,
                    "type": "api",
                    "apis": [api],
                    "services": impacted.get("services", []),
                    "components": impacted.get("components", []),
                    "labels": ["api_endpoint"],
                    "evidence_ids": [],
                }
            )

        for service in impacted.get("services", []):
            entities.append(
                {
                    "name": service,
                    "type": "service",
                    "services": [service],
                    "components": [],
                    "apis": impacted.get("apis", []),
                    "labels": [],
                    "evidence_ids": [],
                }
            )

        for component in impacted.get("components", []):
            entities.append(
                {
                    "name": component,
                    "type": "component",
                    "services": impacted.get("services", []),
                    "components": [component],
                    "apis": impacted.get("apis", []),
                    "labels": [],
                    "evidence_ids": [],
                }
            )

        for doc in impacted.get("docs", []):
            entities.append(
                {
                    "name": doc,
                    "type": "doc",
                    "services": impacted.get("services", []),
                    "components": impacted.get("components", []),
                    "apis": impacted.get("apis", []),
                    "labels": ["doc_section"],
                    "evidence_ids": [],
                }
            )

        return entities

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

    def _enqueue_slack_impact(
        self,
        command: str,
        analysis: Dict[str, Any],
        final_result: Dict[str, Any],
    ) -> None:
        if not self.impact_endpoint_base:
            return
        payload = self._build_slack_impact_payload(command, analysis, final_result)
        if not payload:
            return
        logger.info(
            "[SLASH SLACK] Enqueuing auto-impact slack-complaint for channel=%s thread=%s",
            payload.get("channel"),
            payload.get("timestamp"),
        )
        thread = threading.Thread(
            target=self._post_slack_impact_payload,
            args=(payload,),
            daemon=True,
        )
        thread.start()

    def _build_slack_impact_payload(
        self,
        command: str,
        analysis: Dict[str, Any],
        final_result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        context = analysis.get("context") or {}
        messages = analysis.get("messages") or []
        timestamp = None
        if messages:
            timestamp = messages[-1].get("ts") or messages[-1].get("timestamp")
        if not timestamp:
            timestamp = datetime.now(tz=timezone.utc).isoformat()

        channel = context.get("channel_label") or context.get("channel_name") or context.get("channel_id")
        if not channel:
            return None

        message_text = final_result.get("message") or command.strip()
        if not message_text:
            return None

        component_ids: List[str] = []
        api_ids: List[str] = []
        for entity in final_result.get("entities") or []:
            entity_type = (entity.get("type") or "").lower()
            if entity_type == "component":
                comp_values = entity.get("components") or []
                if not comp_values and entity.get("name"):
                    comp_values = [entity["name"]]
                component_ids.extend(comp_values)
            if entity_type == "api":
                api_values = entity.get("apis") or []
                if not api_values and entity.get("name"):
                    api_values = [entity["name"]]
                api_ids.extend(api_values)

        component_ids = sorted({value for value in component_ids if value})
        api_ids = sorted({value for value in api_ids if value})

        context_payload = {
            "component_ids": component_ids or None,
            "api_ids": api_ids or None,
        }
        cleaned_context = {key: value for key, value in context_payload.items() if value}
        payload: Dict[str, Any] = {
            "channel": channel,
            "message": message_text,
            "timestamp": str(timestamp),
            "context": cleaned_context,
        }
        return payload

    def _post_slack_impact_payload(self, payload: Dict[str, Any]) -> None:
        endpoint = f"{self.impact_endpoint_base.rstrip('/')}/impact/slack-complaint"
        try:
            response = httpx.post(endpoint, json=payload, timeout=2.5)
            if response.status_code >= 400:
                logger.debug(
                    "[SLASH SLACK] Auto impact request failed (status=%s): %s",
                    response.status_code,
                    response.text[:200],
                )
            else:
                logger.info(
                    "[SLASH SLACK] Auto-impact slack-complaint recorded for channel=%s",
                    payload.get("channel"),
                )
        except Exception as exc:
            logger.debug("[SLASH SLACK] Auto impact request error: %s", exc)

    @staticmethod
    def _serialize_query(query: SlashSlackQuery) -> Dict[str, Any]:
        return {
            "raw": query.raw,
            "mode": query.mode,
            "channel_id": query.channel_id,
            "channel_name": query.channel_name,
            "thread_ts": query.thread_ts,
            "keywords": query.keywords,
            "entity": query.entity,
            "time_range": query.time_range.to_dict(),
            "limit": query.limit,
        }

    def _build_final_payload(
        self,
        *,
        command: str,
        session_id: Optional[str],
        query: SlashSlackQuery,
        analysis: Dict[str, Any],
        llm_payload: Optional[Dict[str, Any]],
        llm_error: Optional[str],
    ) -> Dict[str, Any]:
        fallback_summary = analysis.get("summary") or "Slack summary unavailable."
        final_summary = (llm_payload or {}).get("summary") or fallback_summary
        final_sections = (llm_payload or {}).get("sections") or analysis.get("sections", {})
        final_graph = analysis.get("graph")
        llm_graph = self._graph_from_llm_payload(llm_payload, analysis.get("context", {}))
        final_graph = self._merge_graphs(final_graph, llm_graph)

        messages = analysis.get("messages") or []
        sources = self._build_sources(messages, query)

        result = {
            "type": "slash_slack_summary",
            "message": final_summary,
            "sections": final_sections,
            "context": analysis.get("context"),
            "graph": final_graph,
            "messages_preview": analysis.get("messages_preview"),
            "entities": (llm_payload or {}).get("entities"),
            "doc_drift": (llm_payload or {}).get("doc_drift"),
            "evidence": (llm_payload or {}).get("evidence"),
            "llm_payload": llm_payload,
            "sources": sources,
        }
        result["key_decisions"] = (llm_payload or {}).get("key_decisions") or []
        result["next_actions"] = (llm_payload or {}).get("next_actions") or []
        result["open_questions"] = (llm_payload or {}).get("open_questions") or []
        result["references"] = (llm_payload or {}).get("references") or []
        result["debug_metadata"] = (llm_payload or {}).get("debug_metadata") or {}

        metadata = result.setdefault("metadata", {})
        metadata.update({
            "raw_command": command.strip(),
            "mode": query.mode,
            "session_id": session_id,
            "llm_used": bool(llm_payload),
            "llm_error": llm_error,
            "message_count": len(messages),
            "source_count": len(sources),
        })
        warnings = list(dict.fromkeys(analysis.get("warnings") or []))
        if warnings:
            metadata["retrieval_warnings"] = warnings
        context = analysis.get("context") or {}
        channel_id = context.get("channel_id") or query.channel_id
        if channel_id:
            metadata["channel_id"] = channel_id
        if context.get("channel_name"):
            metadata["channel_name"] = context.get("channel_name")
        scope_labels = list(dict.fromkeys(query.channel_scope_labels))
        channel_label = context.get("channel_label")
        if channel_label:
            if not scope_labels:
                scope_labels = [channel_label]
            elif len(scope_labels) == 1:
                scope_labels = [channel_label]
            elif channel_label not in scope_labels:
                scope_labels.append(channel_label)
        if scope_labels:
            metadata["channel_scope"] = scope_labels
        if query.unresolved_channel_tokens:
            metadata["channel_resolution_warnings"] = list(dict.fromkeys(query.unresolved_channel_tokens))

        if not result.get("message"):
            result["message"] = fallback_summary
        if not messages:
            result["message"] = self._empty_summary_text(query)

        self._maybe_attach_debug_block(result, analysis, query)
        return result

    def _maybe_attach_debug_block(
        self,
        result: Dict[str, Any],
        analysis: Dict[str, Any],
        query: SlashSlackQuery,
    ) -> None:
        if not self.debug_block_enabled:
            return
        debug_block = self._build_debug_block(analysis, query)
        if not debug_block:
            return
        result["debug"] = debug_block
        result.setdefault("metadata", {})["debug_block"] = debug_block

    def _build_sources(self, messages: List[Dict[str, Any]], query: SlashSlackQuery) -> List[Dict[str, Any]]:
        if not messages:
            return []
        allowed_channel_ids = {cid.upper() for cid in query.channel_scope_ids or [] if cid}
        allowed_channel_names = {
            label.lstrip("#").lower() for label in query.channel_scope_labels or [] if label
        }
        sources: List[Dict[str, Any]] = []
        for idx, message in enumerate(messages):
            channel_id = message.get("channel_id") or message.get("channel")
            channel_name = message.get("channel_name")
            name_token = (channel_name or "").lstrip("#").lower()
            matches_id = not allowed_channel_ids or (channel_id and channel_id.upper() in allowed_channel_ids)
            matches_name = not allowed_channel_names or (name_token and name_token in allowed_channel_names)
            if not matches_id and not matches_name:
                continue
            text = (
                message.get("text")
                or message.get("message")
                or message.get("summary")
                or message.get("snippet")
                or ""
            )
            snippet = self._clean_snippet(text)
            if not snippet:
                continue
            iso_time = message.get("iso_time") or self._ts_to_iso(message.get("ts"))
            channel_label = self._format_channel_label(channel_name, channel_id)
            source_entry = {
                "id": message.get("id") or message.get("ts") or f"source-{idx}",
                "channel": channel_label,
                "channel_id": channel_id,
                "author": message.get("user_name") or message.get("user") or message.get("user_id"),
                "ts": message.get("ts"),
                "iso_time": iso_time,
                "permalink": message.get("permalink"),
                "deep_link": message.get("deep_link"),
                "snippet": snippet,
                "rank": idx + 1,
                "thread_ts": message.get("thread_ts"),
            }
            sources.append(source_entry)
            if len(sources) >= 12:
                break
        return sources

    def _empty_summary_text(self, query: SlashSlackQuery) -> str:
        if query.channel_scope_labels:
            scope = ", ".join(query.channel_scope_labels)
            return f"I couldn't find recent Slack messages in {scope} for that request."
        return "I couldn't find relevant Slack messages in Slack for that request."

    def _build_debug_block(self, analysis: Dict[str, Any], query: SlashSlackQuery) -> Optional[Dict[str, Any]]:
        messages = analysis.get("messages") or []
        retrieved_count = len(messages)
        context = analysis.get("context") or {}
        channel_label = (
            context.get("channel_label")
            or context.get("channel_name")
            or query.channel_name
            or query.channel_id
            or "Slack"
        )
        sample_evidence: List[Dict[str, Any]] = []
        snippet_message = next((msg for msg in messages if msg.get("text")), messages[0] if messages else None)
        if snippet_message:
            snippet_text = self._clean_snippet(
                snippet_message.get("text")
                or snippet_message.get("message")
                or snippet_message.get("summary")
                or ""
            )
            if snippet_text:
                sample_evidence.append(
                    {
                        "channel": snippet_message.get("channel") or snippet_message.get("channel_name") or channel_label,
                        "snippet": snippet_text,
                    }
                )

        return {
            "source": self.debug_source_label,
            "retrieved_count": retrieved_count,
            "sample_evidence": sample_evidence,
            "status": "PASS" if retrieved_count > 0 else "WARN",
        }

    @staticmethod
    def _clean_snippet(text: str, *, max_length: int = 160) -> str:
        snippet = " ".join(text.strip().split())
        if len(snippet) <= max_length:
            return snippet
        return snippet[: max_length - 3].rstrip() + "..."

    @staticmethod
    def _format_channel_label(channel_name: Optional[str], channel_id: Optional[str]) -> Optional[str]:
        if channel_name:
            cleaned = channel_name.lstrip("#")
            return f"#{cleaned}" if cleaned else channel_name
        if channel_id:
            return f"#{channel_id}"
        return None

    @staticmethod
    def _ts_to_iso(ts: Optional[str]) -> Optional[str]:
        if not ts:
            return None
        try:
            return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
        except (ValueError, OSError):
            return None

    def _graph_from_llm_payload(
        self,
        llm_payload: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not llm_payload:
            return None

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        conversation_id = (context or {}).get("conversation_id")

        entities = llm_payload.get("entities") or []
        for entity in entities:
            entity_id = entity.get("id") or self._stable_id(entity.get("name"), entity.get("type"), entity.get("permalink"))
            nodes.append({"id": entity_id, "type": "Entity", "props": entity})
            if conversation_id:
                edges.append({"from": conversation_id, "to": entity_id, "type": "MENTIONS_ENTITY"})

        doc_drifts = llm_payload.get("doc_drift") or []
        for doc in doc_drifts:
            doc_id = doc.get("permalink") or doc.get("doc") or self._stable_id(doc.get("doc"), doc.get("issue"))
            nodes.append({"id": doc_id, "type": "DocDrift", "props": doc})
            if conversation_id:
                edges.append({"from": conversation_id, "to": doc_id, "type": "DOC_DRIFT"})

        evidences = llm_payload.get("evidence") or []
        for ev in evidences:
            ev_id = ev.get("id") or ev.get("permalink") or self._stable_id(ev.get("channel"), ev.get("ts"))
            nodes.append({"id": ev_id, "type": "Evidence", "props": ev})
            if conversation_id:
                edges.append({"from": conversation_id, "to": ev_id, "type": "HAS_EVIDENCE"})

        if not nodes and not edges:
            return None

        return {"nodes": nodes, "edges": edges}

    def _maybe_assign_channel_hint(self, query: SlashSlackQuery, command: str) -> SlashSlackQuery:
        if query.channel_id:
            return query
        hints = []
        try:
            hints = self.parser.extract_channel_hints(command)
        except AttributeError:
            return query
        for hint in hints:
            channel_id = self.tooling.resolve_channel_id(hint)
            if channel_id:
                updated = replace(query, channel_id=channel_id, channel_name=hint)
                return self._record_scope(updated, channel_id, hint)
        return query

    def _apply_plan_to_query(self, query: SlashSlackQuery, plan: "SlashQueryPlan") -> SlashSlackQuery:
        updated = query
        time_range = self._time_range_from_plan(plan)
        if time_range:
            updated = replace(updated, time_range=time_range)
        scope_ids = list(updated.channel_scope_ids)
        scope_labels = list(updated.channel_scope_labels)
        unresolved_tokens = list(updated.unresolved_channel_tokens)
        if plan.targets:
            for target in plan.targets:
                if target.target_type != "slack_channel":
                    continue
                identifier = target.metadata.get("channel_id") if target.metadata else None
                if not identifier:
                    identifier = target.identifier or target.label or target.raw
                if not identifier:
                    continue
                channel_id = self.tooling.resolve_channel_id(identifier)
                normalized_label = self._normalize_scope_label(target.label or identifier)
                if channel_id:
                    if channel_id not in scope_ids:
                        scope_ids.append(channel_id)
                    if normalized_label and normalized_label not in scope_labels:
                        scope_labels.append(normalized_label)
                    if not updated.channel_id:
                        updated = replace(
                            updated,
                            channel_id=channel_id,
                            channel_name=normalized_label.lstrip("#") if normalized_label else target.label,
                        )
                else:
                    unresolved_tokens.append(target.raw or identifier)
        if scope_ids or scope_labels or unresolved_tokens:
            updated = replace(
                updated,
                channel_scope_ids=scope_ids,
                channel_scope_labels=scope_labels,
                unresolved_channel_tokens=unresolved_tokens,
            )
        plan_keywords = list(dict.fromkeys(plan.keywords))
        if plan_keywords:
            keywords = list(dict.fromkeys(updated.keywords + plan_keywords))
            updated = replace(updated, keywords=keywords)
        return updated

    def _record_scope(
        self,
        query: SlashSlackQuery,
        channel_id: Optional[str],
        channel_label: Optional[str],
    ) -> SlashSlackQuery:
        scope_ids = list(query.channel_scope_ids)
        scope_labels = list(query.channel_scope_labels)
        normalized_label = self._normalize_scope_label(channel_label or channel_id)
        if channel_id and channel_id not in scope_ids:
            scope_ids.append(channel_id)
        if normalized_label and normalized_label not in scope_labels:
            scope_labels.append(normalized_label)
        if scope_ids == query.channel_scope_ids and scope_labels == query.channel_scope_labels:
            return query
        return replace(query, channel_scope_ids=scope_ids, channel_scope_labels=scope_labels)

    def _ensure_scope_metadata(self, query: SlashSlackQuery) -> SlashSlackQuery:
        updated = query
        if not query.channel_id and query.channel_name:
            resolved = self.tooling.resolve_channel_id(query.channel_name)
            if resolved:
                channel_display = query.channel_name
                if self.metadata_service:
                    channel_meta = self.metadata_service.get_channel(resolved)
                    if channel_meta and channel_meta.name:
                        channel_display = channel_meta.name
                updated = replace(updated, channel_id=resolved, channel_name=channel_display)
        if updated.channel_id and self.metadata_service:
            channel_meta = self.metadata_service.get_channel(updated.channel_id)
            if channel_meta and channel_meta.name and channel_meta.name != updated.channel_name:
                updated = replace(updated, channel_name=channel_meta.name)
        if not (updated.channel_id or updated.channel_name):
            return updated
        return self._record_scope(updated, updated.channel_id, updated.channel_name)

    @staticmethod
    def _normalize_scope_label(label: Optional[str]) -> Optional[str]:
        if not label:
            return None
        cleaned = label.strip()
        if not cleaned:
            return None
        if cleaned.startswith("#"):
            cleaned = cleaned.lstrip("#")
        return f"#{cleaned}" if cleaned else None

    def _time_range_from_plan(self, plan: "SlashQueryPlan") -> Optional[TimeRange]:
        scope = plan.time_scope
        if not scope:
            return None
        return TimeRange(start=scope.start, end=scope.end)

    def _build_semantic_analysis(
        self,
        plan: "SlashQueryPlan",
        query: SlashSlackQuery,
    ) -> Optional[Dict[str, Any]]:
        if not self.context_service:
            return None
        channel_names = [label.lstrip("#") for label in query.channel_scope_labels or []]
        messages = self.context_service.search(
            plan,
            limit=query.limit,
            channel_ids=query.channel_scope_ids or None,
            channel_names=channel_names or None,
        )
        if not messages:
            return None
        context = {
            "mode": "semantic_search",
            "plan_targets": [target.to_dict() for target in plan.targets],
            "time_window": plan.time_scope.to_dict() if plan.time_scope else None,
            "conversation_id": self._conversation_id("semantic", plan.raw),
            "vector_source": "qdrant",
        }
        if query.channel_scope_labels:
            context["channel_scope_labels"] = list(dict.fromkeys(query.channel_scope_labels))
        return self.executors["channel_recap"]._build_analysis(
            messages=messages,
            context=context,
            keywords=query.keywords,
        )

    @staticmethod
    def _attach_plan_context(context: Dict[str, Any], plan: "SlashQueryPlan") -> None:
        context.setdefault("query_plan", plan.to_dict())

    @staticmethod
    def _merge_graphs(
        base: Optional[Dict[str, Any]],
        addition: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not addition:
            return base
        if not base:
            return addition
        base.setdefault("nodes", []).extend(addition.get("nodes", []))
        base.setdefault("edges", []).extend(addition.get("edges", []))
        return base

    @staticmethod
    def _stable_id(*parts: Optional[str]) -> str:
        combined = "|".join([part for part in parts if part])
        if not combined:
            combined = f"slash-slack-{datetime.now(tz=timezone.utc).isoformat()}"
        return hashlib.sha1(combined.encode("utf-8")).hexdigest()[:20]

    @staticmethod
    def _conversation_id(*parts: Optional[str]) -> str:
        combined = "|".join([part for part in parts if part])
        if not combined:
            combined = "slash-slack"
        return hashlib.sha1(combined.encode("utf-8")).hexdigest()[:20]

