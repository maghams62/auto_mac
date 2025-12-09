from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ..canonical_ids import CanonicalIdRegistry
from ..embedding_provider import EmbeddingProvider
from ..vector_event import VectorEvent
from ..vector_store_factory import create_vector_store
from ...utils.slack_links import build_slack_permalink

logger = logging.getLogger(__name__)


class SlackVectorIndexer:
    """Builds vector events from the synthetic Slack ledger."""

    def __init__(
        self,
        config,
        *,
        data_path: Optional[Path] = None,
        output_path: Optional[Path] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        vector_store=None,
        canonical_registry: Optional[CanonicalIdRegistry] = None,
    ):
        self.config = config
        self.data_path = data_path or Path("data/synthetic_slack/slack_events.json")
        self.output_path = output_path or Path("data/vector_index/slack_index.json")
        self.embedding_provider = embedding_provider or EmbeddingProvider(config)
        self.vector_store = vector_store or create_vector_store(
            "slack",
            local_path=self.output_path,
            config=config,
        )
        self.registry = canonical_registry or CanonicalIdRegistry.from_file()
        slash_slack_cfg = (config.get("slash_slack") or {})
        self._workspace_url = slash_slack_cfg.get("workspace_url") or os.getenv("SLACK_WORKSPACE_URL")
        self._team_id = os.getenv("SLACK_TEAM_ID") or slash_slack_cfg.get("team_id")
        backend = os.getenv("VECTOR_BACKEND") or (config.get("vectordb") or {}).get("backend") or "local"
        backend = backend.strip().lower()
        target = getattr(self.vector_store, "collection", str(self.output_path))
        logger.info("[SLACK INDEXER] Using vector backend='%s' target='%s'", backend, target)

    def build(self) -> Dict[str, int]:
        events = self._load_events()
        if not events:
            logger.warning("[SLACK INDEXER] No synthetic slack events found at %s", self.data_path)
            return {"indexed": 0}

        vector_events = [self._build_vector_event(event) for event in events]
        texts = [event.text for event in vector_events]
        embeddings = self.embedding_provider.embed_batch(texts, batch_size=32)

        for event, embedding in zip(vector_events, embeddings):
            if not embedding:
                logger.warning("[SLACK INDEXER] Missing embedding for event %s; skipping", event.event_id)
                continue
            event.embedding = embedding

        ready_events = [event for event in vector_events if event.embedding]
        if not ready_events:
            logger.error("[SLACK INDEXER] No events ready for storage.")
            return {"indexed": 0}

        self.vector_store.upsert(ready_events)
        logger.info("[SLACK INDEXER] Indexed %s slack events", len(ready_events))
        return {"indexed": len(ready_events)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _load_events(self) -> List[Dict]:
        if not self.data_path.exists():
            logger.error("[SLACK INDEXER] Synthetic Slack file missing: %s", self.data_path)
            return []
        try:
            return json.loads(self.data_path.read_text())
        except json.JSONDecodeError as exc:
            logger.error("[SLACK INDEXER] Failed to parse %s: %s", self.data_path, exc)
            return []

    def _build_vector_event(self, raw: Dict) -> VectorEvent:
        event_id = raw.get("id") or self._fallback_id(raw)
        source_type = raw.get("source_type", "slack")
        text = raw.get("text_raw") or raw.get("text") or ""
        timestamp = self._parse_timestamp(raw.get("timestamp"))

        service_ids = raw.get("service_ids") or []
        component_ids = raw.get("component_ids") or []
        apis = raw.get("related_apis") or []
        labels = raw.get("labels") or []

        self.registry.assert_valid(
            services=service_ids,
            components=component_ids,
            apis=apis,
            context=event_id,
        )

        metadata = {
            "channel": raw.get("channel"),
            "channel_id": raw.get("channel_id"),
            "workspace": raw.get("workspace"),
            "thread_ts": raw.get("thread_ts"),
            "message_ts": raw.get("message_ts"),
            "service_ids": service_ids,
            "component_ids": component_ids,
            "apis": apis,
            "labels": labels,
            "permalink": raw.get("permalink") or self._build_permalink(raw),
        }

        human_header = self._human_context(raw)
        lines = [
            human_header,
            "",
            text.strip(),
        ]
        event_text = "\n".join(line for line in lines if line is not None)

        vector_event = VectorEvent(
            event_id=event_id,
            source_type=source_type,
            text=event_text,
            timestamp=timestamp,
            service_ids=service_ids,
            component_ids=component_ids,
            apis=apis,
            labels=labels,
            metadata=metadata,
        )
        return vector_event

    @staticmethod
    def _fallback_id(raw: Dict) -> str:
        channel = raw.get("channel_id") or raw.get("channel") or "unknown"
        message_ts = raw.get("message_ts") or raw.get("thread_ts") or "0"
        return f"slack:{channel}:{message_ts}"

    @staticmethod
    def _parse_timestamp(ts: Optional[str]) -> datetime:
        if ts:
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    @staticmethod
    def _human_context(raw: Dict) -> str:
        channel = raw.get("channel") or raw.get("channel_id")
        user = raw.get("user") or raw.get("user_name") or ""
        ts = raw.get("timestamp") or raw.get("message_ts") or ""
        return f"[Slack] {channel} :: {user} @ {ts}"

    def _build_permalink(self, raw: Dict) -> Optional[str]:
        channel_id = raw.get("channel_id") or raw.get("channel")
        message_ts = raw.get("message_ts") or raw.get("thread_ts")
        if not channel_id or not message_ts:
            return None
        return build_slack_permalink(
            channel_id,
            str(message_ts),
            workspace_url=self._workspace_url,
            team_id=self._team_id,
        )

