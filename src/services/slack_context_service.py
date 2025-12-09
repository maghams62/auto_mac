from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence

from ..vector import VectorSearchOptions, get_vector_search_service
from ..utils.slack import normalize_channel_name

if TYPE_CHECKING:
    from .slash_query_plan import SlashQueryPlan
    from ..vector.context_chunk import ContextChunk


class SlackContextService:
    """
    Helper that projects plan metadata into vector / graph lookups for Slack content.

    The service currently focuses on Qdrant-backed semantic retrieval. It degrades
    gracefully when the vector backend is disabled.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        try:
            self.vector_service = get_vector_search_service(self.config)
        except Exception:
            self.vector_service = None

    def search(
        self,
        plan: Optional["SlashQueryPlan"],
        *,
        limit: int = 40,
        channel_ids: Optional[Sequence[str]] = None,
        channel_names: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not plan or not self.vector_service:
            return []
        query_text = self._build_query_text(plan)
        if not query_text:
            return []
        options = VectorSearchOptions(top_k=max(5, min(limit, 100)), source_types=["slack"])
        try:
            chunks = self.vector_service.semantic_search(query_text, options)
        except Exception:
            return []
        messages: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        allowed_ids = {cid.upper() for cid in channel_ids or [] if cid}
        allowed_names = {
            self._channel_name_token(name) for name in channel_names or [] if name
        }
        for chunk in chunks:
            message = self._chunk_to_message(chunk)
            if not message:
                continue
            message_id = message.get("ts") or message.get("id")
            if message_id and message_id in seen_ids:
                continue
            if message_id:
                seen_ids.add(message_id)
            channel_id = (message.get("channel_id") or "").upper()
            token = self._channel_name_token(message.get("channel_name"))
            matches_id = not allowed_ids or (channel_id and channel_id in allowed_ids)
            matches_name = not allowed_names or (token and token in allowed_names)
            if not matches_id and not matches_name:
                continue
            messages.append(message)
        return messages

    def _build_query_text(self, plan: "SlashQueryPlan") -> str:
        tokens: List[str] = []
        for target in plan.targets:
            if target.label:
                tokens.append(target.label)
            elif target.identifier:
                tokens.append(str(target.identifier))
        tokens.extend(plan.keywords)
        tokens = [token for token in tokens if token]
        if plan.required_outputs:
            tokens.extend(plan.required_outputs)
        if not tokens:
            return plan.raw or ""
        # Preserve insertion order while deduplicating
        seen: set[str] = set()
        ordered: List[str] = []
        for token in tokens:
            lowered = token.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            ordered.append(token)
        return " ".join(ordered)

    def _chunk_to_message(self, chunk: "ContextChunk") -> Optional[Dict[str, Any]]:
        metadata = chunk.metadata or {}
        ts_value = metadata.get("ts") or metadata.get("timestamp")
        if not ts_value and chunk.timestamp:
            ts_value = f"{chunk.timestamp.timestamp():.6f}"
        channel_id = metadata.get("channel_id")
        channel_name = metadata.get("channel_name") or channel_id
        permalink = metadata.get("permalink") or metadata.get("url")
        user = metadata.get("user") or metadata.get("author")
        text = chunk.text or metadata.get("snippet")
        if not text:
            return None
        return {
            "id": metadata.get("entity_id") or chunk.entity_id,
            "text": text,
            "ts": ts_value,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "permalink": permalink,
            "user": user,
            "workspace_id": metadata.get("workspace_id"),
            "thread_ts": metadata.get("thread_ts"),
            "reply_count": metadata.get("reply_count"),
        }

    @staticmethod
    def _channel_name_token(name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        normalized = normalize_channel_name(name)
        if not normalized:
            return None
        return normalized.lstrip("#")

