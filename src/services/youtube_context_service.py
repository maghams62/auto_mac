from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..memory import SessionManager
from ..memory.session_memory import SessionMemory
from ..youtube.models import VideoContext, deserialize_video_contexts, serialize_video_contexts
from ..youtube.history_store import HistoryEntry, YouTubeHistoryStore


SESSION_KEY = "slash_youtube_video_contexts"


class YouTubeContextService:
    """Persist and retrieve session-scoped video contexts."""

    def __init__(
        self,
        session_manager: SessionManager,
        history_store: YouTubeHistoryStore,
        config: Dict[str, any],
    ):
        self.session_manager = session_manager
        self.history_store = history_store
        workspace_cfg = config.get("workspace") or {}
        self.workspace_id = workspace_cfg.get("id", "default_workspace")

    # ------------------------------------------------------------------ #
    # Session helpers
    # ------------------------------------------------------------------ #
    def list_contexts(self, session_id: Optional[str]) -> List[VideoContext]:
        memory = self._get_session(session_id)
        data = self._load_state(memory)
        return deserialize_video_contexts(data.get("videos", []))

    def get_active_video(self, session_id: Optional[str]) -> Optional[VideoContext]:
        contexts = self.list_contexts(session_id)
        active_id = self._load_state(self._get_session(session_id)).get("active_video_id")
        if active_id:
            for ctx in contexts:
                if ctx.video_id == active_id:
                    return ctx
        return contexts[0] if contexts else None

    def save_context(
        self,
        session_id: Optional[str],
        context: VideoContext,
        *,
        make_active: bool = True,
    ) -> VideoContext:
        memory = self._get_session(session_id)
        state = self._load_state(memory)
        contexts = deserialize_video_contexts(state.get("videos", []))

        existing = next((ctx for ctx in contexts if ctx.video_id == context.video_id), None)
        if existing:
            idx = contexts.index(existing)
            contexts[idx] = context
        else:
            contexts.insert(0, context)

        serialized = serialize_video_contexts(contexts)
        active_id = context.video_id if make_active else state.get("active_video_id")
        self._save_state(memory, serialized, active_id)

        self.history_store.record(
            HistoryEntry(
                url=context.url,
                video_id=context.video_id,
                title=context.title,
                last_used_at=context.last_used_at,
                channel_title=context.channel_title,
                description=context.description,
                thumbnail_url=context.thumbnail_url,
            )
        )
        return context

    def set_active_video(self, session_id: Optional[str], video_id: str) -> None:
        memory = self._get_session(session_id)
        state = self._load_state(memory)
        state["active_video_id"] = video_id
        memory.set_context(SESSION_KEY, state)

    def touch_video(self, session_id: Optional[str], video_id: str) -> Optional[VideoContext]:
        contexts = self.list_contexts(session_id)
        memory = self._get_session(session_id)
        for ctx in contexts:
            if ctx.video_id == video_id:
                ctx.touch()
                self.save_context(session_id, ctx, make_active=True)
                return ctx
        return None

    def get_workspace_id(self) -> str:
        return self.workspace_id

    def get_suggestions(
        self,
        session_id: Optional[str],
        *,
        limit: int = 5,
        include_clipboard: bool = True,
    ) -> Dict[str, List[Dict[str, str]]]:
        contexts = self.list_contexts(session_id)
        cards = [ctx.summary_card() for ctx in contexts[:limit]]
        history = self.history_store.get_suggestions(limit, include_clipboard=include_clipboard)
        history["session"] = cards
        return history

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _get_session(self, session_id: Optional[str]) -> SessionMemory:
        return self.session_manager.get_or_create_session(session_id)

    def _load_state(self, memory: SessionMemory) -> Dict[str, any]:
        return memory.get_context(SESSION_KEY, {"videos": [], "active_video_id": None})

    def _save_state(self, memory: SessionMemory, videos: List[Dict[str, any]], active_id: Optional[str]) -> None:
        payload = {"videos": videos, "active_video_id": active_id}
        memory.set_context(SESSION_KEY, payload)

