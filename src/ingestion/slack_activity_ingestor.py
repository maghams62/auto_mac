"""
Slack ingestion pipeline for the activity graph/vector index.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
import time
import os

from ..graph import GraphIngestor, GraphService
from ..graph.universal_nodes import UniversalNodeWriter
from ..vector import ContextChunk, get_vector_search_service
from ..vector.context_chunk import generate_slack_entity_id
from ..integrations.slack_client import SlackAPIClient, SlackAPIError
from ..utils.component_ids import normalize_component_ids, resolve_component_id
from ..utils.slack_links import build_slack_permalink
from .loggers import SignalLogWriter
from .state import ActivityIngestState

logger = logging.getLogger(__name__)


class SlackActivityIngestor:
    """
    Pulls Slack messages and writes them into the Activity Graph + Qdrant.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        graph_service: Optional[GraphService] = None,
        vector_service=None,
    ):
        activity_cfg = config.get("activity_ingest", {})
        self.slack_cfg = activity_cfg.get("slack") or {}
        self.enabled = bool(self.slack_cfg.get("enabled", False))
        self.batch_limit = max(1, min(self.slack_cfg.get("batch_limit", 200), 1000))
        self.state_store = ActivityIngestState(activity_cfg.get("state_dir", "data/state/activity_ingest"))
        self.workspace_url = self._resolve_workspace_url(self.slack_cfg, config)
        self.team_id = self._resolve_team_id(self.slack_cfg, config)
        self.default_keywords = [
            kw.lower()
            for kw in self.slack_cfg.get("dissatisfaction_keywords", ["fail", "error", "broken", "down"])
        ]
        self.negative_reactions = set(
            self.slack_cfg.get("negative_reactions", ["thumbsdown", "rage", "angry", "frowning"])
        )

        self.graph_service = graph_service or GraphService(config)
        self.graph_ingestor = GraphIngestor(self.graph_service)
        self.universal_writer = UniversalNodeWriter(self.graph_service)
        self.vector_service = vector_service or get_vector_search_service(config)
        self.vector_collection = getattr(self.vector_service, "collection", None) if self.vector_service else None
        ag_cfg = config.get("activity_graph") or {}
        slack_log_path = (
            self.slack_cfg.get("graph_log_path")
            or ag_cfg.get("slack_graph_path")
            or "data/logs/slash/slack_graph.jsonl"
        )
        self.signal_logger = SignalLogWriter(slack_log_path)

        token_override = self.slack_cfg.get("bot_token")
        try:
            self.client = SlackAPIClient(bot_token=token_override) if self.enabled else None
        except SlackAPIError as exc:
            logger.warning("Slack ingestion disabled (client error): %s", exc)
            self.client = None
            self.enabled = False

    def ingest(self) -> Dict[str, Any]:
        """
        Run ingestion for all configured channels.
        """
        if not self.enabled:
            logger.info("[SLACK INGEST] Slack ingestion disabled via config.")
            return {"ingested": 0}
        if not self.client:
            logger.warning("[SLACK INGEST] Slack client unavailable, skipping ingestion.")
            return {"ingested": 0}

        total_messages = 0
        channels = self.slack_cfg.get("channels", [])
        for channel_cfg in channels:
            try:
                ingested = self._ingest_channel(channel_cfg)
                total_messages += ingested
            except SlackAPIError as exc:
                logger.error("[SLACK INGEST] Failed channel %s: %s", channel_cfg.get("id"), exc)
            except Exception as exc:
                logger.exception("[SLACK INGEST] Unexpected error for channel %s", channel_cfg.get("id"))

        logger.info("[SLACK INGEST] Completed ingestion (%s messages)", total_messages)
        return {"ingested": total_messages}

    def ingest_fixture_messages(self, fixtures: Dict[str, Any]) -> Dict[str, int]:
        """
        Ingest synthetic Slack messages from a fixture dictionary.
        """
        messages = fixtures.get("messages") or []
        if not messages:
            return {"ingested": 0}

        vector_chunks: List[ContextChunk] = []
        processed = 0

        for entry in messages:
            channel_cfg = self._find_channel_config(
                channel_id=entry.get("channel_id"),
                channel_name=entry.get("channel_name"),
            )
            if not channel_cfg:
                logger.warning(
                    "[SLACK INGEST] No channel config for fixture message: %s",
                    entry.get("channel_id") or entry.get("channel_name"),
                )
                continue

            slack_message = {
                "text": entry.get("text", ""),
                "ts": str(entry.get("ts") or self._generate_fixture_ts(processed)),
                "user": entry.get("user", "fixture-user"),
                "reactions": entry.get("reactions", []),
                "thread_ts": entry.get("thread_ts"),
            }

            chunk = self._build_chunk(slack_message, channel_cfg)
            if chunk:
                vector_chunks.append(chunk)

            self._write_activity_signal(slack_message, channel_cfg)
            processed += 1

        if vector_chunks:
            self._index_chunks(vector_chunks)

        logger.info("[SLACK INGEST] Fixture ingestion complete (%s messages)", processed)
        return {"ingested": processed}

    def close(self) -> None:
        if self.graph_service:
            self.graph_service.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ingest_channel(self, channel_cfg: Dict[str, Any]) -> int:
        channel_id = channel_cfg.get("id")
        if not channel_id:
            logger.warning("[SLACK INGEST] Skipping channel config without 'id': %s", channel_cfg)
            return 0

        state_key = f"slack_{channel_id}"
        state = self.state_store.load(state_key)
        last_ts = state.get("last_ts")

        history = self.client.fetch_messages(channel_id, limit=self.batch_limit, oldest=last_ts)
        messages = history.get("messages", [])
        if not messages:
            logger.debug("[SLACK INGEST] No new messages for %s", channel_id)
            return 0

        # Process oldest -> newest to preserve cursor semantics
        messages = [
            msg for msg in messages if not msg.get("subtype")  # Skip bot/system events for now
        ]
        messages.sort(key=lambda msg: float(msg.get("ts", "0")))

        vector_chunks: List[ContextChunk] = []
        processed = 0
        latest_ts = last_ts

        for msg in messages:
            ts = msg.get("ts")
            if not ts:
                continue
            if last_ts and ts <= last_ts:
                continue

            chunk = self._build_chunk(msg, channel_cfg)
            if chunk:
                vector_chunks.append(chunk)

            self._write_activity_signal(msg, channel_cfg)
            processed += 1
            latest_ts = ts

        if vector_chunks:
            self._index_chunks(vector_chunks)

        if latest_ts and latest_ts != last_ts:
            self.state_store.save(state_key, {"last_ts": latest_ts})

        logger.info("[SLACK INGEST] Channel %s ingested %s messages", channel_id, processed)
        return processed

    def _build_chunk(self, message: Dict[str, Any], channel_cfg: Dict[str, Any]) -> Optional[ContextChunk]:
        text = message.get("text", "").strip()
        if not text:
            return None

        channel_id = channel_cfg.get("id")
        channel_name = channel_cfg.get("name") or channel_id
        ts = message.get("ts", "0")
        ts_dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        ts_iso = ts_dt.isoformat()

        user = message.get("user") or message.get("username") or "unknown"
        permalink = self._build_permalink(channel_id, ts)
        chunk_text = "\n".join([
            f"Slack message in {channel_name}",
            f"Author: {user}",
            f"Timestamp: {ts_iso}",
            "",
            text,
        ])

        entity_id = generate_slack_entity_id(channel_id, ts)
        tags = ["slack", channel_id] + channel_cfg.get("tags", [])
        graph_node_id = entity_id
        metadata = {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "user": user,
            "permalink": permalink,
            "thread_ts": message.get("thread_ts"),
            "reply_count": message.get("reply_count"),
            "source_modality": "slack",
            "source_id": graph_node_id,
            "graph_node_id": graph_node_id,
        }
        chunk = ContextChunk(
            chunk_id=entity_id,
            entity_id=entity_id,
            source_type="slack",
            text=chunk_text,
            component=self._primary_component(channel_cfg),
            service=None,
            timestamp=ts_dt,
            tags=tags,
            metadata=metadata,
            collection=self.vector_collection,
        )
        return chunk

    def _write_activity_signal(self, message: Dict[str, Any], channel_cfg: Dict[str, Any]) -> None:
        if not self.graph_ingestor.available():
            return

        ts = message.get("ts", "0")
        ts_dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        signal_id = f"signal:slack:{channel_cfg.get('id')}:{ts}"
        component_ids = normalize_component_ids(channel_cfg.get("components", []))
        endpoint_ids = channel_cfg.get("endpoint_ids", [])
        weight = self._compute_signal_weight(message, channel_cfg, ts_dt)

        properties = {
            "source": "slack",
            "channel_id": channel_cfg.get("id"),
            "channel_name": channel_cfg.get("name"),
            "thread_ts": message.get("thread_ts"),
        }

        self.graph_ingestor.upsert_activity_signal(
            signal_id=signal_id,
            component_ids=component_ids,
            endpoint_ids=endpoint_ids,
            properties=properties,
            signal_weight=weight,
            last_seen=ts_dt.isoformat(),
        )
        self._log_slack_signal(message, channel_cfg, component_ids, ts_dt)

    def _compute_signal_weight(
        self,
        message: Dict[str, Any],
        channel_cfg: Dict[str, Any],
        ts_dt: datetime,
    ) -> float:
        weight = float(channel_cfg.get("base_weight", self.slack_cfg.get("base_weight", 1.0)))
        keywords = [
            kw.lower() for kw in channel_cfg.get("dissatisfaction_keywords", self.default_keywords)
        ]
        text = message.get("text", "").lower()
        if any(keyword in text for keyword in keywords):
            weight += channel_cfg.get("keyword_weight", 0.5)

        reactions = message.get("reactions", []) or []
        for reaction in reactions:
            if reaction.get("name") in self.negative_reactions:
                weight += 0.1 * reaction.get("count", 1)

        half_life = channel_cfg.get("recency_half_life_hours", 72)
        if half_life > 0:
            age_hours = max(0.0, (datetime.now(timezone.utc) - ts_dt).total_seconds() / 3600.0)
            decay = math.exp(-age_hours / half_life)
            weight *= max(0.2, decay)

        return round(weight, 4)

    def _index_chunks(self, chunks: List[ContextChunk]) -> None:
        if not chunks:
            logger.debug("[SLACK INGEST] No vector chunks to index for this batch")
            return
        if not self.vector_service:
            logger.info(
                "[SLACK INGEST] Vector service unavailable; skipped indexing %s chunks",
                len(chunks),
            )
            return
        collection = self.vector_collection or getattr(self.vector_service, "collection", "unknown")
        chunk_count = len(chunks)
        start = time.perf_counter()
        success = self.vector_service.index_chunks(chunks)
        duration_ms = (time.perf_counter() - start) * 1000
        if not success:
            logger.warning(
                "[SLACK INGEST] Vector indexing failed",
                extra={
                    "collection": collection,
                    "chunk_count": chunk_count,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return

        logger.info(
            "[SLACK INGEST] Indexed slack chunks into Qdrant",
            extra={
                "collection": collection,
                "chunk_count": chunk_count,
                "duration_ms": round(duration_ms, 2),
            },
        )
        self.universal_writer.ingest_chunks(chunks)

    def _build_permalink(self, channel_id: str, ts: str) -> str:
        permalink = build_slack_permalink(
            channel_id,
            ts,
            workspace_url=self.workspace_url,
            team_id=self.team_id,
        )
        return permalink or ""

    def _resolve_workspace_url(self, slack_cfg: Dict[str, Any], config: Dict[str, Any]) -> str:
        """
        Determine the Slack workspace base URL from config or environment variables.
        """
        workspace_url: str = (
            slack_cfg.get("workspace_url")
            or (config.get("slack") or {}).get("workspace_url")
            or ""
        )
        if "${" in workspace_url:
            workspace_url = ""
        env_url = os.environ.get("SLACK_WORKSPACE_URL") or os.environ.get("SLACK_WORKSPACE")
        if not workspace_url and env_url:
            workspace_url = env_url
        if workspace_url and not workspace_url.startswith("http"):
            workspace_url = f"https://{workspace_url.lstrip('/')}"
        return workspace_url.rstrip("/")

    def _resolve_team_id(self, slack_cfg: Dict[str, Any], config: Dict[str, Any]) -> Optional[str]:
        team_id = (
            slack_cfg.get("workspace_id")
            or slack_cfg.get("team_id")
            or (config.get("slash_slack") or {}).get("workspace_id")
            or (config.get("slash_slack") or {}).get("team_id")
            or (config.get("slack") or {}).get("workspace_id")
            or (config.get("slack") or {}).get("team_id")
            or os.environ.get("SLACK_TEAM_ID")
            or os.environ.get("SLACK_WORKSPACE_ID")
        )
        if isinstance(team_id, str):
            return team_id.strip() or None
        return None

    def _log_slack_signal(
        self,
        message: Dict[str, Any],
        channel_cfg: Dict[str, Any],
        component_ids: List[str],
        ts_dt: datetime,
    ) -> None:
        if not component_ids:
            return
        labels: List[str] = []
        is_complaint = self._is_complaint(message, channel_cfg)
        if is_complaint:
            labels.append("complaint")
        channel_id = channel_cfg.get("id")
        permalink = self._build_permalink(channel_id, message.get("ts", ""))
        text_value = (message.get("text") or "").strip()
        record = {
            "source": "slack",
            "component_ids": component_ids,
            "properties": {
                "timestamp": ts_dt.isoformat(),
                "channel_id": channel_id,
                "channel_name": channel_cfg.get("name"),
                "labels": labels,
                "permalink": permalink or None,
                "text": text_value or None,
                "user": message.get("user") or message.get("username"),
                "sentiment": "negative" if is_complaint else "neutral",
            },
        }
        self.signal_logger.write(record)

    def _is_complaint(self, message: Dict[str, Any], channel_cfg: Dict[str, Any]) -> bool:
        keywords = [
            kw.lower() for kw in channel_cfg.get("dissatisfaction_keywords", self.default_keywords)
        ]
        text = (message.get("text") or "").lower()
        if any(keyword and keyword in text for keyword in keywords):
            return True
        reactions = message.get("reactions", []) or []
        for reaction in reactions:
            if reaction.get("name") in self.negative_reactions:
                return True
        return False

    @staticmethod
    def _primary_component(channel_cfg: Dict[str, Any]) -> Optional[str]:
        components: Iterable[str] = channel_cfg.get("components") or []
        for comp in components:
            if not comp:
                continue
            canonical = resolve_component_id(comp)
            if canonical:
                return canonical
        return None

    def _find_channel_config(
        self,
        channel_id: Optional[str],
        channel_name: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        for cfg in self.slack_cfg.get("channels", []):
            if channel_id and cfg.get("id") == channel_id:
                return cfg
            if channel_name and cfg.get("name") == channel_name:
                return cfg
        return None

    @staticmethod
    def _generate_fixture_ts(offset: int) -> str:
        base_ts = datetime.now(timezone.utc).timestamp()
        return f"{base_ts + offset:.6f}"

