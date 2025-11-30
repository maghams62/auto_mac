"""
FastAPI server that provides REST and WebSocket endpoints for the UI.
Connects to the existing AutomationAgent orchestrator.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from threading import Event, Lock

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import tempfile
import httpx

from pathlib import Path
from dotenv import load_dotenv
import sys

# Load .env file explicitly before importing anything that needs config
project_root = Path(__file__).resolve().parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
else:
    # Fallback to find_dotenv() behavior
    load_dotenv(override=False)

# Ensure project root is in Python path for absolute imports
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.agent.agent import AutomationAgent
from src.agent.agent_registry import AgentRegistry
from src.memory import SessionManager
from src.memory.local_chat_cache import LocalChatCache
from src.utils import load_config, save_config
from src.workflow import WorkflowOrchestrator
from src.services.feedback_logger import get_feedback_logger
from src.services.context_resolution_service import ContextResolutionService
from src.services.chat_storage import MongoChatStorage
from src.utils.performance_monitor import get_performance_monitor
from src.utils.startup_profiler import get_startup_profiler
from src.utils.trajectory_logger import get_trajectory_logger
from src.utils.error_logger import log_error_with_context
from src.utils.api_logging import log_api_request, log_websocket_event, sanitize_payload
from src.graph import ActivityService, GraphAnalyticsService, GraphService
from src.graph.validation import GraphValidator
from telemetry.config import get_tracer, sanitize_value, set_span_error
from src.automation.background_jobs import ChatPersistenceWorker
from src.vector.service_factory import validate_vectordb_config, VectorServiceConfigError
import time

# Initialize telemetry
from telemetry import init_telemetry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
startup_profiler = get_startup_profiler()
startup_profiler.mark("module_imported")

def _configure_otel_logging():
    """Downgrade OTLP exporter spam into a single actionable warning."""

    class _OncePerRunHandler(logging.Handler):
        def __init__(self):
            super().__init__(level=logging.ERROR)
            self._emitted = False

        def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
            if self._emitted:
                return
            self._emitted = True
            logger.warning(
                "[TELEMETRY] OTLP exporter unavailable – traces will remain local",
                {"message": record.getMessage()},
            )

    exporter_logger = logging.getLogger("opentelemetry.exporter.otlp.proto.grpc.exporter")
    exporter_logger.handlers.clear()
    exporter_logger.addHandler(_OncePerRunHandler())
    exporter_logger.setLevel(logging.ERROR)
    exporter_logger.propagate = False


# Initialize FastAPI app
app = FastAPI(title="Cerebro OS API")

# Initialize telemetry (must happen before FastAPI instrumentation)
init_telemetry()
_configure_otel_logging()

# Add OpenTelemetry FastAPI instrumentation
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)
    logger.info("[TELEMETRY] FastAPI instrumentation enabled")
except ImportError:
    logger.warning("[TELEMETRY] OpenTelemetry FastAPI instrumentation not available")

# Configure CORS for frontend (allow configurable origins with sensible defaults)
default_allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://localhost:3000",
    "https://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

allowed_origins_env = os.getenv("API_ALLOWED_ORIGINS")
if allowed_origins_env:
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
else:
    allowed_origins = default_allowed_origins

allowed_origin_regex = os.getenv("API_ALLOWED_ORIGIN_REGEX", r"https?://(localhost|127\.0\.0\.1)(:\d+)?$")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Import global ConfigManager
from src.config_manager import get_global_config_manager, set_global_config_manager, ConfigManager
from src.cache import StartupCacheManager

# Initialize global config manager
config_manager = get_global_config_manager()
startup_profiler.mark("config_manager_ready")

# Startup cache hydrates heavy artifacts (prompts, manifests) between launches
startup_cache_manager = StartupCacheManager(
    cache_path=os.getenv(
        "STARTUP_CACHE_PATH",
        str(project_root / "data" / "cache" / "startup_bootstrap.json"),
    ),
    fingerprint_sources=[
        config_manager.get_config_path(),
        project_root / "prompts",
        project_root / "prompts" / "examples",
    ],
)
automation_bootstrap = startup_cache_manager.load_section("automation_bootstrap")
preloaded_prompts = automation_bootstrap.get("prompts") if automation_bootstrap else None
startup_profiler.mark("startup_cache_ready", {"cache_hit": bool(preloaded_prompts)})

# Initialize session manager
session_manager = SessionManager(storage_dir="data/sessions", config=config_manager.get_config())

# Initialize agent registry with session support
agent_registry = AgentRegistry(config_manager.get_config(), session_manager=session_manager)

# Initialize automation agent with session support (prefer startup cache prompts)
agent = AutomationAgent(
    config_manager.get_config(),
    session_manager=session_manager,
    preloaded_prompts=preloaded_prompts,
)
startup_profiler.mark("automation_agent_ready", {"from_cache": bool(preloaded_prompts)})

# Persist prompt bundle if cache miss (write once per invalidation)
if not automation_bootstrap or not automation_bootstrap.get("prompts"):
    startup_cache_manager.save_section(
        "automation_bootstrap",
        {
            "prompts": agent.prompts,
            "prompt_keys": sorted(agent.prompts.keys()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    startup_profiler.mark("startup_cache_populated", {"cache_written": True})
else:
    startup_profiler.mark("startup_cache_populated", {"cache_written": False})

# Conversation persistence
_mongo_cfg = config_manager.get_config().get("mongo", {})
_cache_cfg = _mongo_cfg.get("cache", {})
chat_storage = MongoChatStorage(config_manager.get_config())
chat_cache = LocalChatCache(
    max_messages_per_session=_cache_cfg.get("max_messages_per_session", 75),
    disk_path=_cache_cfg.get("disk_path", "data/cache/chat_sessions"),
    flush_enabled=chat_storage.enabled,
)
chat_worker = ChatPersistenceWorker(chat_cache, chat_storage)

# Lazy-load workflow orchestrator for indexing (only initialize when needed)
_orchestrator = None
_orchestrator_lock = Lock()

# Feedback logger (singleton)
feedback_logger = get_feedback_logger()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_chat_event(
    session_id: str,
    role: str,
    text: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    vector_ids: Optional[List[str]] = None,
) -> None:
    """Persist chat event to cache and signal worker."""
    if not text:
        return
    entry = {
        "session_id": session_id or "default",
        "role": role,
        "text": text,
        "metadata": metadata or {},
        "vector_ids": vector_ids or [],
        "created_at": _now_iso(),
    }
    chat_cache.append_message(entry)
    chat_worker.notify_new_message()


def _history_identity(payload: Dict[str, Any]) -> str:
    raw_id = payload.get("_id")
    if raw_id is not None:
        return f"id:{raw_id}"
    created = payload.get("created_at")
    role = payload.get("role")
    text = payload.get("text")
    return f"ts:{created}|role:{role}|text:{text}"


def _coerce_metadata(metadata: Any) -> Dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    try:
        import json as _json
        return _json.loads(_json.dumps(metadata, default=str))
    except Exception:
        return metadata


def _normalize_history_item(payload: Dict[str, Any], source: str) -> Dict[str, Any]:
    created_at = payload.get("created_at")
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    elif not isinstance(created_at, str) or not created_at:
        created_at = _now_iso()
    text = (payload.get("text") or "").strip()
    return {
        "session_id": payload.get("session_id") or "default",
        "role": payload.get("role") or "assistant",
        "text": text,
        "created_at": created_at,
        "metadata": _coerce_metadata(payload.get("metadata") or {}),
        "source": source,
    }


def _history_sort_key(entry: Dict[str, Any]) -> datetime:
    value = entry.get("created_at")
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        cleaned = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(cleaned)
        except ValueError:
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


async def _build_chat_history_payload(session_id: str, limit: int) -> Dict[str, Any]:
    cache_entries = chat_cache.list_recent(session_id, limit)
    mongo_entries: List[Dict[str, Any]] = []
    if chat_storage.enabled:
        mongo_entries = await chat_storage.fetch_recent(session_id, limit)

    seen = set()
    combined: List[Dict[str, Any]] = []
    for source, batch in (("cache", cache_entries), ("mongo", mongo_entries)):
        for item in batch:
            identity = _history_identity(item)
            if identity in seen:
                continue
            seen.add(identity)
            combined.append(_normalize_history_item(item, source))

    combined.sort(key=_history_sort_key)
    combined = combined[-limit:]

    counts = {
        "cache": sum(1 for entry in combined if entry["source"] == "cache"),
        "mongo": sum(1 for entry in combined if entry["source"] == "mongo"),
    }
    last_persisted = next(
        (entry["created_at"] for entry in reversed(combined) if entry["source"] == "mongo"),
        None,
    )
    return {
        "session_id": session_id,
        "messages": combined,
        "counts": counts,
        "last_persisted_at": last_persisted,
    }


def get_orchestrator():
    """Lazy-load WorkflowOrchestrator on first access to improve startup time."""
    global _orchestrator
    if _orchestrator is None:
        with _orchestrator_lock:
            # Double-check pattern to avoid race conditions
            if _orchestrator is None:
                logger.info("[PERF] Initializing WorkflowOrchestrator (lazy load)")
                _orchestrator = WorkflowOrchestrator(config_manager.get_config())
                logger.info("[PERF] WorkflowOrchestrator initialized")
    return _orchestrator

# Initialize recurring task scheduler
from src.automation.recurring_scheduler import RecurringTaskScheduler
recurring_scheduler = RecurringTaskScheduler(
    agent_registry=agent_registry,
    agent=agent,
    session_manager=session_manager
)

# Store references for hot-reload (orchestrator will be lazy-loaded)
config_manager.update_components(agent_registry, agent, None)  # Will be set when orchestrator is first accessed

# Graph analytics/context services (optional)
_graph_config = config_manager.get_config()
graph_service = GraphService(_graph_config)
graph_analytics_service = GraphAnalyticsService(graph_service)
activity_service = ActivityService(_graph_config, graph_service=graph_service)
context_resolution_cfg = _graph_config.get("context_resolution", {}) or {}
impact_settings = context_resolution_cfg.get("impact", {}) or {}
context_resolution_service = ContextResolutionService(
    graph_service,
    default_max_depth=impact_settings.get("default_max_depth", 2),
    context_config=context_resolution_cfg,
)
graph_validator = GraphValidator(graph_service)


def _require_graph_analytics() -> None:
    if not graph_analytics_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Graph analytics service is not available. Enable Neo4j in config.yaml.",
        )


def _require_context_resolution() -> None:
    if not context_resolution_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Context resolution service is not available. Enable Neo4j in config.yaml.",
        )


def _require_activity_service() -> None:
    if not activity_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Activity service is not available. Enable Neo4j in config.yaml.",
        )


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # session_id -> websocket
        self.websocket_to_session: Dict[WebSocket, str] = {}
        # Async lock for thread-safe access to connection dictionaries
        self._lock = asyncio.Lock()
        # Message queue for failed sends (session_id -> list of messages)
        self._failed_messages: Dict[str, List[Dict[str, Any]]] = {}
        # Maximum retry attempts
        self._max_retries = 3
        # Retry delays in seconds (exponential backoff)
        self._retry_delays = [0.1, 0.5, 2.0]

    async def connect(self, websocket: WebSocket, session_id: str):
        try:
            await websocket.accept()
            async with self._lock:
                self.active_connections[session_id] = websocket
                self.websocket_to_session[websocket] = session_id
                logger.info(f"Client connected with session {session_id}. Total connections: {len(self.active_connections)}")
            
            # Log WebSocket connection
            log_websocket_event(
                event_type="connect",
                session_id=session_id,
                config=None  # TODO: Get config from app state
            )
            # Try to send any queued messages for this session
            if session_id in self._failed_messages:
                    queued = self._failed_messages.pop(session_id, [])
                    if queued:
                        logger.info(f"[CONNECTION MANAGER] 🔄 Sending {len(queued)} queued messages for session {session_id} on reconnect")
                        for i, msg in enumerate(queued):
                            msg_type = msg.get('type', 'unknown')
                            has_files = 'files' in msg
                            logger.info(f"[CONNECTION MANAGER] Flushing queued message {i+1}/{len(queued)}: type={msg_type}, has_files={has_files}")
                            success = await self.send_message(msg, websocket)
                            if not success:
                                logger.warning(f"[CONNECTION MANAGER] Failed to send queued message {i+1}, re-queuing")
                                if session_id not in self._failed_messages:
                                    self._failed_messages[session_id] = []
                                self._failed_messages[session_id].append(msg)
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection for session {session_id}: {e}", exc_info=True)
            raise

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            session_id = self.websocket_to_session.get(websocket)
            if session_id:
                self.active_connections.pop(session_id, None)
                self.websocket_to_session.pop(websocket, None)
                # Clear failed messages for this session
                self._failed_messages.pop(session_id, None)
                logger.info(f"Client disconnected (session: {session_id}). Total connections: {len(self.active_connections)}")
                
                # Log WebSocket disconnection
                log_websocket_event(
                    event_type="disconnect",
                    session_id=session_id,
                    config=None  # TODO: Get config from app state
                )

    def _is_websocket_healthy(self, websocket: WebSocket) -> bool:
        """Check if WebSocket is in a valid state for sending."""
        try:
            # FastAPI WebSocket doesn't expose readyState directly, but we can check client_state
            # If the connection is closed, accessing it will raise an exception
            return websocket.client_state.name == "CONNECTED"
        except Exception:
            return False

    async def send_message(self, message: dict, websocket: WebSocket, retry_count: int = 0) -> bool:
        """
        Send a message with retry logic and guaranteed delivery.
        
        Args:
            message: Message dict to send
            websocket: WebSocket connection
            retry_count: Current retry attempt (internal use)
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        # Check WebSocket health before attempting to send
        if not self._is_websocket_healthy(websocket):
            # Get session_id for queueing
            async with self._lock:
                session_id = self.websocket_to_session.get(websocket)
            
            if session_id:
                # Queue message for later delivery
                if session_id not in self._failed_messages:
                    self._failed_messages[session_id] = []
                self._failed_messages[session_id].append(message)
                logger.warning(f"[CONNECTION MANAGER] WebSocket unhealthy for session {session_id}, queued message for later delivery (queue size: {len(self._failed_messages[session_id])})")
                logger.debug(f"[CONNECTION MANAGER] Queued message type: {message.get('type', 'unknown')}, has_files: {'files' in message}")
            else:
                logger.error("[CONNECTION MANAGER] WebSocket unhealthy and no session_id found, message lost")
            return False
        
        try:
            await websocket.send_json(message)
            logger.debug(f"[CONNECTION MANAGER] Message sent successfully (retry: {retry_count})")
            
            # Log WebSocket message
            async with self._lock:
                session_id = self.websocket_to_session.get(websocket)
            if session_id:
                log_websocket_event(
                    event_type="message",
                    session_id=session_id,
                    message_type=message.get("type"),
                    payload=message,
                    config=None  # TODO: Get config from app state
                )
            
            return True
        except Exception as e:
            logger.warning(f"[CONNECTION MANAGER] Error sending message (attempt {retry_count + 1}/{self._max_retries}): {e}")
            
            # Retry with exponential backoff
            if retry_count < self._max_retries - 1:
                delay = self._retry_delays[min(retry_count, len(self._retry_delays) - 1)]
                await asyncio.sleep(delay)
                
                # Check if WebSocket is still healthy before retry
                if self._is_websocket_healthy(websocket):
                    return await self.send_message(message, websocket, retry_count + 1)
                else:
                    logger.warning(f"[CONNECTION MANAGER] WebSocket became unhealthy during retry, queueing message")
                    # Queue for later delivery
                    async with self._lock:
                        session_id = self.websocket_to_session.get(websocket)
                        if session_id:
                            if session_id not in self._failed_messages:
                                self._failed_messages[session_id] = []
                            self._failed_messages[session_id].append(message)
                    return False
            else:
                # Max retries exceeded, queue message
                logger.error(f"[CONNECTION MANAGER] Max retries exceeded for message, queueing for later delivery")
                async with self._lock:
                    session_id = self.websocket_to_session.get(websocket)
                    if session_id:
                        if session_id not in self._failed_messages:
                            self._failed_messages[session_id] = []
                        self._failed_messages[session_id].append(message)
                return False

    async def broadcast(self, message: dict):
        async with self._lock:
            # Create a copy of connections to avoid modification during iteration
            connections = list(self.active_connections.values())
        
        for connection in connections:
            try:
                await self.send_message(message, connection)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")

manager = ConnectionManager()

# Initialize Bluesky notification service (after manager is created)
from src.orchestrator.bluesky_notification_service import BlueskyNotificationService
bluesky_notifications = BlueskyNotificationService(
    connection_manager=manager,
    config=config_manager.get_config()
)

# Initialize Branch Watcher service for Oqoqo self-evolving docs
from src.services.branch_watcher_service import BranchWatcherService, get_branch_watcher_service
branch_watcher = BranchWatcherService(
    connection_manager=manager,
    config=config_manager.get_config()
)

def _coerce_delay(value: Any, default: float = 8.0) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default

branch_watcher_settings = config_manager.get_config().get("branch_watcher", {}) or {}
branch_watcher_enabled = branch_watcher_settings.get("enabled", True)
branch_watcher_startup_delay = _coerce_delay(
    branch_watcher_settings.get("startup_delay_seconds", 8.0)
)

branch_watcher_runtime: Dict[str, Any] = {
    "lifecycle": "disabled" if not branch_watcher_enabled else "idle",
    "last_start_attempt": None,
    "last_started_at": None,
    "last_error": None,
    "startup_delay_seconds": branch_watcher_startup_delay,
}
branch_watcher_start_lock = asyncio.Lock()
branch_watcher_start_task: Optional[asyncio.Task] = None


def _update_branch_watcher_runtime(**updates: Any) -> None:
    branch_watcher_runtime.update(updates)


async def _deferred_branch_watcher_start(delay_override: Optional[float] = None) -> None:
    if not branch_watcher_enabled:
        logger.info("[BRANCH WATCHER] Disabled via config; skipping deferred start")
        return

    delay_seconds = branch_watcher_startup_delay if delay_override is None else max(0.0, delay_override)

    async with branch_watcher_start_lock:
        lifecycle = branch_watcher_runtime.get("lifecycle")
        if lifecycle in {"scheduled", "starting", "running"}:
            logger.debug("[BRANCH WATCHER] Start already in progress (%s)", lifecycle)
            return
        _update_branch_watcher_runtime(lifecycle="scheduled")

    if delay_seconds > 0:
        logger.info("[BRANCH WATCHER] Deferred start scheduled in %.1fs", delay_seconds)
        try:
            await asyncio.sleep(delay_seconds)
        except asyncio.CancelledError:
            _update_branch_watcher_runtime(lifecycle="cancelled")
            raise

    async with branch_watcher_start_lock:
        # Stop if another task already transitioned us to running
        if branch_watcher_runtime.get("lifecycle") == "running":
            return
        _update_branch_watcher_runtime(lifecycle="starting", last_start_attempt=_now_iso())

    try:
        await branch_watcher.start()
        _update_branch_watcher_runtime(
            lifecycle="running",
            last_started_at=_now_iso(),
            last_error=None,
        )
        logger.info("[BRANCH WATCHER] Background polling started")
    except asyncio.CancelledError:
        _update_branch_watcher_runtime(lifecycle="cancelled")
        raise
    except Exception as exc:
        _update_branch_watcher_runtime(
            lifecycle="error",
            last_error=str(exc),
        )
        logger.exception("[BRANCH WATCHER] Failed to start deferred service")


def schedule_branch_watcher_start(delay_override: Optional[float] = None) -> None:
    global branch_watcher_start_task

    if not branch_watcher_enabled:
        _update_branch_watcher_runtime(lifecycle="disabled")
        return

    if branch_watcher_start_task and not branch_watcher_start_task.done():
        logger.debug("[BRANCH WATCHER] Deferred start already scheduled")
        return

    branch_watcher_start_task = asyncio.create_task(_deferred_branch_watcher_start(delay_override))


async def _cancel_branch_watcher_start_task() -> None:
    global branch_watcher_start_task

    if branch_watcher_start_task and not branch_watcher_start_task.done():
        branch_watcher_start_task.cancel()
        try:
            await branch_watcher_start_task
        except asyncio.CancelledError:
            pass

    branch_watcher_start_task = None


def _build_branch_watcher_status() -> Dict[str, Any]:
    status = branch_watcher.get_status()
    status.update({
        "enabled": branch_watcher_enabled,
        "lifecycle": branch_watcher_runtime.get("lifecycle"),
        "last_start_attempt": branch_watcher_runtime.get("last_start_attempt"),
        "last_started_at": branch_watcher_runtime.get("last_started_at"),
        "last_error": branch_watcher_runtime.get("last_error"),
        "startup_delay_seconds": branch_watcher_runtime.get("startup_delay_seconds"),
        "pending_start": bool(branch_watcher_start_task and not branch_watcher_start_task.done()),
    })
    return status

# Track active agent tasks so we can support safe cancellation per session
# Use async lock for thread-safe access
_session_tasks_lock = asyncio.Lock()
session_tasks: Dict[str, asyncio.Task] = {}
session_cancel_events: Dict[str, Event] = {}

# Per-session execution queues to ensure sequential processing
# Each session has a queue that processes one request at a time
# and waits for the response to be fully delivered before accepting the next
_session_queues: Dict[str, asyncio.Queue] = {}
_session_queue_locks: Dict[str, asyncio.Lock] = {}
_session_response_acks: Dict[str, asyncio.Event] = {}  # Tracks when response is delivered

# Pydantic models for API
class ChatMessage(BaseModel):
    message: str
    timestamp: Optional[str] = None
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    status: str
    timestamp: str

class ChatHistoryEntry(BaseModel):
    session_id: str
    role: str
    text: str
    created_at: str
    metadata: Dict[str, Any] = {}
    source: str


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[ChatHistoryEntry]
    counts: Dict[str, int]
    last_persisted_at: Optional[str]

class SystemStats(BaseModel):
    indexed_documents: int
    total_chunks: int
    available_agents: List[str]
    uptime: str


class FeedbackPayload(BaseModel):
    plan_id: str
    goal: str
    feedback_type: str  # "positive" | "negative"
    plan_status: str
    duration_ms: Optional[int] = None
    analytics: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    session_id: Optional[str] = None
    plan_started_at: Optional[str] = None
    plan_completed_at: Optional[str] = None
    step_statuses: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


async def has_active_task(session_id: str) -> bool:
    """Check if a session already has an in-flight agent execution."""
    async with _session_tasks_lock:
        task = session_tasks.get(session_id)
        return bool(task and not task.done())


def format_result_message(result: Dict[str, Any]) -> str:
    """Format agent result into a readable message string."""
    if not isinstance(result, dict):
        return str(result)
    
    # Check for Maps result - return simple, clean message
    if "maps_url" in result:
        maps_url = result.get("maps_url", "")
        # Use the message if provided, otherwise create simple one
        if "message" in result:
            return result["message"]
        else:
            return f"Here's your trip, enjoy: {maps_url}"
    
    # Check for other structured results
    if result.get("error"):
        # Try error_message first, fall back to message or the error value itself
        error_value = result.get("error")
        error_text = result.get('error_message') or result.get('message')
        if not error_text and isinstance(error_value, str):
            error_text = error_value
        if not error_text:
            error_text = 'Unknown error'
        return f"❌ **Error:** {error_text}"
    
    # Handle reply type results (from reply_to_user tool) - combine message and details
    # Check if this is a reply type OR if it has details field (which indicates reply structure)
    is_reply_type = result.get("type") == "reply"
    has_details = "details" in result
    
    if is_reply_type or has_details:
        message = result.get("message", "")
        details = result.get("details", "")
        
        # Combine message and details if both exist
        if message and details:
            # Check for duplicate content - if details contains the same text as message, skip details
            message_clean = message.strip()
            details_clean = details.strip()
            
            # Check if details is a duplicate or subset of message
            if message_clean and details_clean:
                # If details is identical to message, skip it
                if details_clean == message_clean:
                    return message
                # If details starts with the same text as message, skip the duplicate part
                if details_clean.startswith(message_clean):
                    # Extract only the additional content
                    additional = details_clean[len(message_clean):].strip()
                    if additional:
                        separator = "\n\n" if message.rstrip().endswith((".", "!", "?")) else "\n\n"
                        return f"{message}{separator}{additional}"
                    else:
                        return message
                # If message is a subset of details, use details only
                if message_clean in details_clean and len(details_clean) > len(message_clean) * 1.5:
                    return details
            
            # If message ends with punctuation, add space; otherwise add newline
            separator = "\n\n" if message.rstrip().endswith((".", "!", "?")) else "\n\n"
            return f"{message}{separator}{details}"
        elif message:
            return message
        elif details:
            return details
    
    # Default formatting - check for message field
    if "message" in result:
        return result["message"]
    
    # Format as JSON if it's a complex dict
    import json
    return json.dumps(result, indent=2)


async def process_agent_request(
    session_id: str,
    user_message: str,
    websocket: WebSocket,
    cancel_event: Event
):
    """Run the automation agent in a background task and stream the result."""
    # Safety check: reject /clear commands (should be handled by WebSocket handler)
    normalized_msg = user_message.strip().lower() if user_message else ""
    if normalized_msg == "/clear" or normalized_msg == "clear":
        logger.warning(f"/clear command reached process_agent_request - this should not happen. Session: {session_id}")
        await manager.send_message({
            "type": "error",
            "message": "Error: /clear command should be handled by the WebSocket handler. Please try again.",
            "timestamp": datetime.now().isoformat()
        }, websocket)
        return
    
    # Check for API docs sync approval responses
    # Triggered by user saying "yes", "sync", "update docs", etc. after a drift notification
    approval_keywords = {"yes", "sync", "update", "approve", "apply", "sync docs", "update docs", "sync api docs"}
    if normalized_msg in approval_keywords or normalized_msg.startswith("yes"):
        # Check if there's a pending drift report
        pending_report = branch_watcher.get_pending_report()
        if pending_report:
            logger.info(f"[API SERVER] User approved drift fix for branch '{pending_report.branch}'")
            try:
                from src.agent.apidocs_agent import write_api_spec
                
                if not pending_report.proposed_spec:
                    await manager.send_message({
                        "type": "error",
                        "message": f"No proposed spec available for branch '{pending_report.branch}'. Cannot apply update.",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    return
                
                # Apply the update
                result = write_api_spec.invoke({
                    "content": pending_report.proposed_spec,
                    "backup": True
                })
                
                if not result.get("success"):
                    await manager.send_message({
                        "type": "error",
                        "message": f"Failed to apply spec update: {result.get('error', 'Unknown error')}",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    return
                
                branch_name = pending_report.branch
                branch_watcher.clear_pending_report(branch_name)
                
                # Send success confirmation with Swagger link
                await manager.send_message({
                    "type": "apidocs_sync",
                    "message": f"✅ **API documentation updated successfully!**\n\n"
                              f"The API spec has been synced with changes from branch `{branch_name}`.\n\n"
                              f"📄 **View updated docs:** [Swagger UI](http://localhost:8000/docs) | [ReDoc](http://localhost:8000/redoc)",
                    "timestamp": datetime.now().isoformat(),
                    "apidocs_sync": {
                        "branch": branch_name,
                        "spec_path": result.get("path"),
                        "backup_path": result.get("backup_path"),
                        "swagger_url": "http://localhost:8000/docs",
                        "redoc_url": "http://localhost:8000/redoc",
                    }
                }, websocket)
                return
                
            except Exception as e:
                logger.error(f"[API SERVER] Error applying drift fix: {e}", exc_info=True)
                await manager.send_message({
                    "type": "error",
                    "message": f"Error applying API spec update: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                return

    # Get the current event loop
    loop = asyncio.get_event_loop()

    # Define callback to send plan to UI
    def send_plan_to_ui(plan_data: Dict[str, Any]):
        """Send plan steps to UI for task disambiguation display."""
        try:
            # Schedule the async send in the main event loop from the worker thread
            asyncio.run_coroutine_threadsafe(
                manager.send_message({
                    "type": "plan",
                    "message": "",  # Required by Message interface but not displayed for plan type
                    "goal": plan_data.get("goal", ""),
                    "steps": plan_data.get("steps", []),
                    "timestamp": datetime.now().isoformat()
                }, websocket),
                loop
            )
        except Exception as e:
            logger.error(f"Failed to send plan to UI: {e}")

    # Define callbacks for live plan progress tracking
    def send_step_started(data: Dict[str, Any]):
        """Send step started event to UI."""
        try:
            asyncio.run_coroutine_threadsafe(
                manager.send_message({
                    "type": "plan_update",
                    "step_id": data["step_id"],
                    "status": "running",
                    "sequence_number": data["sequence_number"],
                    "timestamp": data["timestamp"]
                }, websocket),
                loop
            )
        except Exception as e:
            logger.error(f"Failed to send step started event: {e}")

    def send_step_succeeded(data: Dict[str, Any]):
        """Send step succeeded event to UI."""
        try:
            asyncio.run_coroutine_threadsafe(
                manager.send_message({
                    "type": "plan_update",
                    "step_id": data["step_id"],
                    "status": "completed",
                    "sequence_number": data["sequence_number"],
                    "output_preview": data.get("output_preview"),
                    "timestamp": data["timestamp"]
                }, websocket),
                loop
            )
        except Exception as e:
            logger.error(f"Failed to send step succeeded event: {e}")

    def send_step_failed(data: Dict[str, Any]):
        """Send step failed event to UI."""
        try:
            asyncio.run_coroutine_threadsafe(
                manager.send_message({
                    "type": "plan_update",
                    "step_id": data["step_id"],
                    "status": "failed",
                    "sequence_number": data["sequence_number"],
                    "error": data.get("error"),
                    "can_retry": data.get("can_retry", False),
                    "timestamp": data["timestamp"]
                }, websocket),
                loop
            )
        except Exception as e:
            logger.error(f"Failed to send step failed event: {e}")

    # CRITICAL: Log start of agent execution to track flow
    import time
    execution_start_time = time.time()
    logger.info(f"[API SERVER] Starting agent execution for session {session_id}: {user_message[:100]}...")
    
    # Pass callbacks through run() method instead of setting on agent instance to avoid cross-talk
    # No timeout wrapper - agent.run() now self-limits via ResultCapture mechanism
    # Agentic tasks can run for extended periods, so we rely on manual cancellation if needed
    try:
        result = await asyncio.to_thread(
            agent.run,
            user_message,
            session_id,
            cancel_event,
            None,  # context
            send_plan_to_ui,
            send_step_started,
            send_step_succeeded,
            send_step_failed
        )
        
        execution_duration = time.time() - execution_start_time
        logger.info(f"[API SERVER] Agent execution completed in {execution_duration:.2f}s for session {session_id}")
        
        result_dict = result if isinstance(result, dict) else {"message": str(result)}
        logger.info(f"[API SERVER] Agent execution completed for session {session_id}, result keys: {list(result_dict.keys())}")
        
        # CRITICAL: Log step_results structure for debugging file extraction and Bluesky posts
        if "step_results" in result_dict:
            step_results = result_dict["step_results"]
            logger.info(f"[API SERVER] step_results type: {type(step_results)}, keys: {list(step_results.keys()) if isinstance(step_results, dict) else 'not a dict'}")
            for step_id, step_result in (step_results.items() if isinstance(step_results, dict) else []):
                if isinstance(step_result, dict):
                    step_type = step_result.get("type", "no_type")
                    tool_name = step_result.get("tool", "no_tool")
                    logger.info(f"[API SERVER] Step {step_id}: type='{step_type}', tool='{tool_name}', has_files={'files' in step_result}, has_results={'results' in step_result}")
                    
                    # Check for Bluesky post results
                    if tool_name == "post_bluesky_update" or "bluesky" in tool_name.lower():
                        logger.info(f"[API SERVER] 🔵 BLUESKY POST detected in step {step_id}")
                        logger.info(f"[API SERVER] Bluesky result keys: {list(step_result.keys())}")
                        logger.info(f"[API SERVER] Bluesky success: {step_result.get('success')}, error: {step_result.get('error')}")
                        logger.info(f"[API SERVER] Bluesky message: {step_result.get('message', 'N/A')[:100]}")
                        logger.info(f"[API SERVER] Bluesky URL: {step_result.get('url', 'N/A')}")
                    
                    # Check for file_list
                    if step_type == "file_list":
                        files_count = len(step_result.get("files", [])) if isinstance(step_result.get("files"), list) else 0
                        logger.info(f"[API SERVER] ⚠️ FILE_LIST FOUND in step {step_id} with {files_count} files!")
                    
                    # Check for reply_to_user
                    if step_type == "reply" or tool_name == "reply_to_user":
                        logger.info(f"[API SERVER] 📝 REPLY_TO_USER found in step {step_id}")
                        logger.info(f"[API SERVER] Reply message: {step_result.get('message', 'N/A')[:100]}")
                        logger.info(f"[API SERVER] Reply details: {step_result.get('details', 'N/A')[:100] if step_result.get('details') else 'N/A'}")
        elif "results" in result_dict:
            results = result_dict["results"]
            logger.info(f"[API SERVER] results type: {type(results)}, keys: {list(results.keys()) if isinstance(results, dict) else 'not a dict'}")
        
        # Check if this is a retry_with_orchestrator result from slash command
        if isinstance(result_dict, dict) and result_dict.get("type") == "retry_with_orchestrator":
            original_message = result_dict.get("original_message", user_message)
            retry_message = result_dict.get("content", "Retrying via main assistant...")
            context = result_dict.get("context", None)

            # Send retry notification
            await manager.send_message({
                "type": "status",
                "status": "processing",
                "message": retry_message,
                "timestamp": datetime.now().isoformat()
            }, websocket)

            # Log context if present (for debugging)
            if context:
                logger.info(f"[API SERVER] [EMAIL WORKFLOW] Retrying with context: {context}")

            # Retry via orchestrator (agent.run will handle it as natural language)
            # Pass context to orchestrator for email summarization hints
            # Also pass callback to avoid cross-talk
            retry_start_time = time.time()
            result = await asyncio.to_thread(agent.run, original_message, session_id, cancel_event, context, send_plan_to_ui)
            retry_duration = time.time() - retry_start_time
            logger.info(f"[API SERVER] Retry execution completed in {retry_duration:.2f}s for session {session_id}")
            result_dict = result if isinstance(result, dict) else {"message": str(result)}
        
        result_status = result_dict.get("status", "completed")

        # Send plan_finalize event to close out the plan streaming
        await manager.send_message({
            "type": "plan_finalize",
            "status": result_status,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_steps": len(result_dict.get("step_results", {})),
                "completed_steps": sum(1 for step in result_dict.get("step_results", {}).values() if not step.get("error")),
                "failed_steps": sum(1 for step in result_dict.get("step_results", {}).values() if step.get("error")),
                "duration": result_dict.get("duration", None)
            }
        }, websocket)

        session_memory = session_manager.get_or_create_session(session_id)

        # Format the result message - prioritize Maps URLs (check top level first, then nested)
        formatted_message = format_result_message(result_dict)
        
        # Check for Maps URL at top level (from orchestrator extraction)
        if "maps_url" in result_dict:
            formatted_message = format_result_message(result_dict)
        # Check step_results for Maps URLs (in case it's nested)
        elif "step_results" in result_dict:
            for step_result in result_dict["step_results"].values():
                if isinstance(step_result, dict) and "maps_url" in step_result:
                    formatted_message = format_result_message(step_result)
                    break
        elif "results" in result_dict:
            for step_result in result_dict["results"].values():
                if isinstance(step_result, dict) and "maps_url" in step_result:
                    formatted_message = format_result_message(step_result)
                    break
        
        # If no Maps URL found, check for reply type results in step_results/results
        if not formatted_message or formatted_message == json.dumps(result_dict, indent=2):
            # Extract reply_to_user message with defensive checks for both possible keys
            reply_result = None
            step_results_source = result_dict.get("step_results") or result_dict.get("results")
            
            if step_results_source:
                for step_id, step_result in step_results_source.items():
                    if isinstance(step_result, dict) and step_result.get("type") == "reply":
                        reply_result = step_result
                        logger.info(f"[API SERVER] Found reply_to_user result in step {step_id}")
                        break
            
            if not reply_result:
                logger.warning("[API SERVER] No reply_to_user found in step results")
            
            if reply_result:
                # Use format_result_message to combine message and details
                formatted_message = format_result_message(reply_result)
                logger.info(f"[API SERVER] Using reply_to_user message: {formatted_message[:100]}...")
            else:
                # Fallback: Try to extract meaningful message from result structure
                # First check for Bluesky post results
                bluesky_post_result = None
                if step_results_source:
                    for step_id, step_result in step_results_source.items():
                        if isinstance(step_result, dict):
                            tool_name = step_result.get("tool", "")
                            # Check if this is a Bluesky post result
                            if tool_name == "post_bluesky_update" or (step_result.get("success") and step_result.get("url") and "bsky.app" in str(step_result.get("url", ""))):
                                bluesky_post_result = step_result
                                logger.info(f"[API SERVER] Found Bluesky post result in step {step_id}")
                                break
                
                if bluesky_post_result:
                    # Format Bluesky post result
                    if bluesky_post_result.get("success"):
                        url = bluesky_post_result.get("url", "")
                        message_text = bluesky_post_result.get("message", "")
                        if url:
                            formatted_message = f"{message_text}\n\nPost URL: {url}" if message_text else f"Posted to Bluesky: {url}"
                        else:
                            formatted_message = message_text or "Posted to Bluesky successfully"
                        logger.info(f"[API SERVER] Using Bluesky post result message: {formatted_message[:100]}...")
                    elif bluesky_post_result.get("error"):
                        error_msg = bluesky_post_result.get("error_message", "Unknown error")
                        formatted_message = f"Failed to post to Bluesky: {error_msg}"
                        logger.info(f"[API SERVER] Using Bluesky post error message: {formatted_message[:100]}...")
                
                # If no Bluesky result, try other fallbacks
                if not formatted_message or formatted_message == json.dumps(result_dict, indent=2):
                    if step_results_source:
                        # Get the first result's message if available
                        first_result = list(step_results_source.values())[0]
                        if isinstance(first_result, dict) and "message" in first_result:
                            formatted_message = format_result_message(first_result)
                            logger.info(f"[API SERVER] Using fallback message from first step result")
                        elif isinstance(first_result, dict) and "maps_url" in first_result:
                            formatted_message = format_result_message(first_result)
                            logger.info(f"[API SERVER] Using maps_url from first step result")
        
        # CRITICAL: Ensure formatted_message is never empty before sending response
        # This guarantees a response is always sent, preventing stuck "processing" state
        if not formatted_message or formatted_message.strip() == "" or formatted_message == json.dumps(result_dict, indent=2):
            # Generate a fallback message from available data
            goal = result_dict.get("goal", "Task")
            status = result_dict.get("status", "completed")
            step_results_source = result_dict.get("step_results") or result_dict.get("results") or {}
            
            # Try to extract any meaningful message from step results
            extracted_messages = []
            for step_id, step_result in step_results_source.items():
                if isinstance(step_result, dict):
                    msg = (
                        step_result.get("message") or
                        step_result.get("summary") or
                        step_result.get("content") or
                        step_result.get("response")
                    )
                    if msg and msg.strip():
                        extracted_messages.append(msg)
            
            if extracted_messages:
                formatted_message = "\n".join(extracted_messages[:3])  # Limit to first 3 messages
                logger.info(f"[API SERVER] Generated fallback message from {len(extracted_messages)} step results")
            elif result_dict.get("message"):
                formatted_message = result_dict.get("message")
                logger.info("[API SERVER] Using top-level message from result_dict")
            else:
                # Ultimate fallback: create a generic message based on status
                if status == "error":
                    formatted_message = f"❌ {goal} encountered an error. Please check the details."
                elif status == "cancelled":
                    formatted_message = f"⏸️ {goal} was cancelled."
                else:
                    steps_count = len(step_results_source)
                    if steps_count > 0:
                        completed = sum(1 for r in step_results_source.values() 
                                      if isinstance(r, dict) and not r.get("error"))
                        formatted_message = f"✅ {goal} completed ({completed}/{steps_count} steps)."
                    else:
                        formatted_message = f"✅ {goal} completed."
                logger.warning(f"[API SERVER] Generated ultimate fallback message: {formatted_message[:100]}...")

        # Extract files/documents array from result if present (for file_list and document_list type responses)
        # Also check for files array from explain pipeline results
        # CRITICAL: Extract file_list from ALL steps, not just the first match, to ensure files are displayed
        # even when reply_to_user fails
        files_array = None
        documents_array = None
        
        # Helper function to validate and sanitize files array
        def validate_files_array(files: Any) -> Optional[List[Dict[str, Any]]]:
            """Validate and sanitize files array, return None if invalid."""
            if files is None:
                return None
            if not isinstance(files, list):
                logger.warning(f"[API SERVER] Files array is not a list: {type(files)}")
                return None
            if len(files) == 0:
                return None
            
            # Validate each file entry
            validated_files = []
            for i, file_entry in enumerate(files):
                try:
                    if not isinstance(file_entry, dict):
                        logger.warning(f"[API SERVER] File entry {i} is not a dict, skipping")
                        continue
                    
                    # Ensure required fields exist
                    if "path" not in file_entry and "name" not in file_entry:
                        logger.warning(f"[API SERVER] File entry {i} missing path/name, skipping")
                        continue
                    
                    # Sanitize file entry
                    sanitized = {
                        "name": file_entry.get("name") or Path(file_entry.get("path", "")).name or "Unknown",
                        "path": file_entry.get("path", ""),
                        "score": file_entry.get("score", 0.0),
                    }
                    
                    # Copy optional fields
                    for key in ["result_type", "thumbnail_url", "preview_url", "meta"]:
                        if key in file_entry:
                            sanitized[key] = file_entry[key]
                    
                    validated_files.append(sanitized)
                except Exception as e:
                    logger.warning(f"[API SERVER] Error validating file entry {i}: {e}, skipping")
                    continue
            
            if len(validated_files) == 0:
                logger.warning(f"[API SERVER] No valid files after validation")
                return None
            
            return validated_files
        
        # Wrap entire file extraction in error boundary
        try:
            logger.info(f"[API SERVER] Starting file_list extraction from result_dict keys: {list(result_dict.keys())}")
            
            # Check for files array in explain pipeline results (from explain command)
            try:
                if "final_result" in result_dict:
                    final_result = result_dict["final_result"]
                    if isinstance(final_result, dict) and "files" in final_result:
                        validated = validate_files_array(final_result["files"])
                        if validated:
                            files_array = validated
                            logger.info(f"[API SERVER] Found files array in final_result: {len(files_array)} files")
            except Exception as e:
                logger.warning(f"[API SERVER] Error extracting files from final_result: {e}", exc_info=True)
        
            # CRITICAL: Check ALL step_results for file_list, don't break on first match
            # This ensures we find file_list even if it's in an earlier step and reply_to_user fails
            # Check both "step_results" and "results" (legacy key)
            step_results_source = result_dict.get("step_results") or result_dict.get("results") or {}
            
            logger.info(f"[API SERVER] step_results_source type: {type(step_results_source)}, is_dict: {isinstance(step_results_source, dict)}, length: {len(step_results_source) if isinstance(step_results_source, dict) else 'N/A'}")
            
            # Also check if step_results is nested in final_result
            if not step_results_source and "final_result" in result_dict:
                final_result = result_dict["final_result"]
                if isinstance(final_result, dict):
                    step_results_source = final_result.get("step_results") or final_result.get("results") or {}
                    if step_results_source:
                        logger.info(f"[API SERVER] Found step_results in final_result")
            
            if step_results_source:
                try:
                    logger.info(f"[API SERVER] Checking {len(step_results_source)} step results for file_list/document_list")
                    logger.info(f"[API SERVER] Step results keys (step_ids): {list(step_results_source.keys())}")
                    
                    # Log structure of each step_result for debugging
                    for step_id, step_result in step_results_source.items():
                        try:
                            if isinstance(step_result, dict):
                                step_type = step_result.get("type", "no_type_field")
                                step_keys = list(step_result.keys())
                                logger.info(f"[API SERVER] Step {step_id}: type='{step_type}', keys={step_keys}")
                                if step_type == "file_list":
                                    files_in_step = step_result.get("files", [])
                                    logger.info(f"[API SERVER] Step {step_id} is file_list with {len(files_in_step) if isinstance(files_in_step, list) else 'non-list'} files")
                            else:
                                logger.info(f"[API SERVER] Step {step_id}: not a dict, type={type(step_result)}")
                        except Exception as e:
                            logger.warning(f"[API SERVER] Error logging step {step_id}: {e}")
                    
                    # First pass: Look for file_list in ALL steps (prioritize file_list over document_list)
                    for step_id, step_result in step_results_source.items():
                        try:
                            if not isinstance(step_result, dict):
                                logger.debug(f"[API SERVER] Skipping step {step_id} - not a dict")
                                continue
                            
                            # Check for file_list type (highest priority)
                            if step_result.get("type") == "file_list" and "files" in step_result:
                                found_files = step_result["files"]
                                logger.info(f"[API SERVER] 🔍 Found file_list in step {step_id}, files type: {type(found_files)}, length: {len(found_files) if isinstance(found_files, list) else 'N/A'}")
                                validated = validate_files_array(found_files)
                                if validated:
                                    files_array = validated
                                    logger.info(f"[API SERVER] ✅ Found file_list in step_results[{step_id}]: {len(files_array)} files")
                                    logger.info(f"[API SERVER] First file in array: {list(files_array[0].keys()) if files_array else 'empty'}")
                                    # Don't break - continue checking to see if there are multiple file_list results
                                else:
                                    logger.warning(f"[API SERVER] Step {step_id} has file_list type but validation failed")
                                    logger.warning(f"[API SERVER] Files array details: type={type(found_files)}, is_list={isinstance(found_files, list)}, length={len(found_files) if isinstance(found_files, list) else 'N/A'}")
                                    if isinstance(found_files, list) and len(found_files) > 0:
                                        logger.warning(f"[API SERVER] First file entry: {found_files[0] if found_files else 'empty'}")
                            
                            # Check for document_list type (only if files_array not found yet)
                            elif files_array is None and step_result.get("type") == "document_list" and "documents" in step_result:
                                found_docs = step_result["documents"]
                                if isinstance(found_docs, list) and len(found_docs) > 0:
                                    documents_array = found_docs
                                    logger.info(f"[API SERVER] ✅ Found document_list in step_results[{step_id}]: {len(documents_array)} documents")
                            
                            # Also check for files array directly in explain pipeline results
                            elif step_result.get("rag_pipeline") and "files" in step_result:
                                found_files = step_result["files"]
                                validated = validate_files_array(found_files)
                                if validated:
                                    files_array = validated
                                    logger.info(f"[API SERVER] ✅ Found files array in explain pipeline result (step {step_id}): {len(files_array)} files")
                        except Exception as e:
                            logger.warning(f"[API SERVER] Error processing step {step_id} for file extraction: {e}", exc_info=True)
                            continue
                except Exception as e:
                    logger.error(f"[API SERVER] Error in step_results file extraction: {e}", exc_info=True)
            
            # Fallback: Check top-level result_dict
            try:
                if files_array is None:
                    if result_dict.get("type") == "file_list" and "files" in result_dict:
                        validated = validate_files_array(result_dict["files"])
                        if validated:
                            files_array = validated
                            logger.info(f"[API SERVER] ✅ Found file_list at top level: {len(files_array)} files")
                    elif result_dict.get("type") == "document_list" and "documents" in result_dict:
                        documents_array = result_dict["documents"]
                        logger.info(f"[API SERVER] ✅ Found document_list at top level: {len(documents_array)} documents")
                    # Check top-level files array from explain pipeline
                    elif "files" in result_dict and result_dict.get("rag_pipeline"):
                        validated = validate_files_array(result_dict["files"])
                        if validated:
                            files_array = validated
                            logger.info(f"[API SERVER] ✅ Found files array at top level from explain pipeline: {len(files_array)} files")
            except Exception as e:
                logger.warning(f"[API SERVER] Error in top-level file extraction: {e}", exc_info=True)
            
            if files_array is None and documents_array is None:
                logger.warning(f"[API SERVER] ⚠️ No file_list or document_list found in result_dict. Step results keys: {list(step_results_source.keys()) if step_results_source else 'none'}")
            
            # CRITICAL: Extract image results from search_documents tool output
            # search_documents returns a "results" array with result_type: "image" that needs to be converted to files array format
            if files_array is None:
                try:
                    step_results_source = result_dict.get("step_results") or result_dict.get("results") or {}
                    
                    for step_id, step_result in step_results_source.items():
                        try:
                            if not isinstance(step_result, dict):
                                continue
                            
                            # Check if this is a search_documents result (has "results" array)
                            if "results" in step_result and isinstance(step_result["results"], list):
                                search_results = step_result["results"]
                                logger.info(f"[API SERVER] Found search_documents results in step {step_id}: {len(search_results)} results")
                                
                                # Filter for images and convert to FileList format
                                image_files = []
                                for result in search_results:
                                    try:
                                        if isinstance(result, dict) and result.get("result_type") == "image":
                                            doc_path = result.get("doc_path", "")
                                            doc_title = result.get("doc_title", "")
                                            metadata = result.get("metadata", {})
                                            
                                            # Get file name - prefer doc_title, fallback to filename from path
                                            if doc_title:
                                                file_name = doc_title
                                            elif doc_path:
                                                try:
                                                    file_name = Path(doc_path).name
                                                except Exception:
                                                    file_name = "Unknown"
                                            else:
                                                file_name = "Unknown"
                                            
                                            # Get file type from metadata or path extension
                                            file_type = metadata.get("file_type", "")
                                            if not file_type and doc_path:
                                                try:
                                                    suffix = Path(doc_path).suffix
                                                    file_type = suffix[1:] if suffix else "image"
                                                except Exception:
                                                    file_type = "image"
                                            if not file_type:
                                                file_type = "image"
                                            
                                            # Convert search_documents format to FileList format
                                            converted_file = {
                                                "name": file_name,
                                                "path": doc_path,
                                                "score": result.get("relevance_score", 0.0),
                                                "result_type": "image",
                                                "thumbnail_url": result.get("thumbnail_url"),
                                                "preview_url": result.get("preview_url"),
                                                "meta": {
                                                    "file_type": file_type,
                                                    "width": metadata.get("width"),
                                                    "height": metadata.get("height")
                                                }
                                            }
                                            image_files.append(converted_file)
                                    except Exception as e:
                                        logger.warning(f"[API SERVER] Error converting image result: {e}, skipping")
                                        continue
                                
                                if image_files:
                                    validated = validate_files_array(image_files)
                                    if validated:
                                        files_array = validated
                                        logger.info(f"[API SERVER] Extracted {len(image_files)} image results from search_documents and converted to files array format")
                                        break
                        except Exception as e:
                            logger.warning(f"[API SERVER] Error processing search_documents step {step_id}: {e}", exc_info=True)
                            continue
                except Exception as e:
                    logger.warning(f"[API SERVER] Error in search_documents image extraction: {e}", exc_info=True)
        
            # CRITICAL: Last resort - try to extract files from reply details (JSON string)
            # Sometimes the LLM puts file_list data in reply details as JSON
            if files_array is None:
                try:
                    step_results_source = result_dict.get("step_results") or result_dict.get("results") or {}
                    for step_id, step_result in step_results_source.items():
                        if isinstance(step_result, dict) and step_result.get("type") == "reply":
                            details = step_result.get("details", "")
                            if details and isinstance(details, str):
                                try:
                                    # Try to parse details as JSON
                                    parsed_details = json.loads(details)
                                    if isinstance(parsed_details, list) and len(parsed_details) > 0:
                                        # Check if it looks like a files array
                                        first_item = parsed_details[0]
                                        if isinstance(first_item, dict) and ("name" in first_item or "path" in first_item):
                                            validated = validate_files_array(parsed_details)
                                            if validated:
                                                files_array = validated
                                                logger.info(f"[API SERVER] ✅ Extracted {len(files_array)} files from reply details JSON in step {step_id}")
                                                break
                                except (json.JSONDecodeError, Exception) as e:
                                    logger.debug(f"[API SERVER] Could not parse reply details as JSON in step {step_id}: {e}")
                                    continue
                except Exception as e:
                    logger.warning(f"[API SERVER] Error extracting files from reply details: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"[API SERVER] CRITICAL: Error in file extraction logic: {e}", exc_info=True)
            # Continue with response even if file extraction failed
            files_array = None
            documents_array = None

        # Extract completion_event from reply results if present
        completion_event = None
        if "step_results" in result_dict and result_dict["step_results"]:
            for step_result in result_dict["step_results"].values():
                if isinstance(step_result, dict) and step_result.get("type") == "reply" and "completion_event" in step_result:
                    completion_event = step_result["completion_event"]
                    break
        elif "results" in result_dict and result_dict["results"]:
            for step_result in result_dict["results"].values():
                if isinstance(step_result, dict) and step_result.get("type") == "reply" and "completion_event" in step_result:
                    completion_event = step_result["completion_event"]
                    break
        elif result_dict.get("type") == "reply" and "completion_event" in result_dict:
            completion_event = result_dict["completion_event"]

        # Check for special response types that need custom handling
        # API Docs Drift (Oqoqo pattern) - send as apidocs_drift type for frontend drift card
        apidocs_drift_result = None
        apidocs_sync_result = None
        if result_dict.get("type") == "result" and result_dict.get("agent") == "apidocs":
            inner_result = result_dict.get("result", {})
            if inner_result.get("type") == "apidocs_drift":
                apidocs_drift_result = inner_result
                logger.info(f"[API SERVER] 📄 Detected apidocs_drift result, will send as apidocs_drift type")
            elif inner_result.get("type") == "apidocs_sync":
                apidocs_sync_result = inner_result
                logger.info(f"[API SERVER] ✅ Detected apidocs_sync result (no drift)")
        
        # Build response payload
        if apidocs_drift_result:
            # Send as apidocs_drift type for the frontend drift card
            response_payload = {
                "type": "apidocs_drift",
                "message": apidocs_drift_result.get("message", "API Documentation Drift Detected"),
                "status": "completed",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "apidocs_drift": {
                    "has_drift": apidocs_drift_result.get("has_drift", True),
                    "changes": apidocs_drift_result.get("changes", []),
                    "summary": apidocs_drift_result.get("summary", ""),
                    "proposed_spec": apidocs_drift_result.get("proposed_spec"),
                    "change_count": apidocs_drift_result.get("change_count", 0),
                    "breaking_changes": apidocs_drift_result.get("breaking_changes", 0),
                }
            }
            logger.info(f"[API SERVER] Built apidocs_drift response payload with {apidocs_drift_result.get('change_count', 0)} changes")
        elif apidocs_sync_result:
            # No drift - send as system message
            response_payload = {
                "type": "system",
                "message": apidocs_sync_result.get("message", "✅ API documentation is in sync with code."),
                "status": "completed",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }
            logger.info(f"[API SERVER] Built apidocs_sync response payload (no drift)")
        else:
            response_payload = {
                "type": "response",
                "message": formatted_message,
                "status": result_status,
                "session_id": session_id,
                "interaction_count": len(session_memory.interactions),
                "timestamp": datetime.now().isoformat()
            }
            result_payload = None
            if isinstance(result_dict, dict):
                final_result = result_dict.get("final_result")
                nested_result = result_dict.get("result") if isinstance(result_dict.get("result"), dict) else None
                if isinstance(final_result, dict):
                    result_payload = final_result
                elif isinstance(nested_result, dict):
                    result_payload = nested_result
                elif result_dict.get("type") in {"slash_slack_summary", "slash_git_summary"}:
                    result_payload = result_dict

            if result_payload:
                response_payload["result"] = result_payload
                if result_payload.get("type") == "slash_slack_summary":
                    logger.info("[API SERVER] Included slash_slack_summary payload in response for frontend consumption")
        
        # Add files array if present
        if files_array is not None:
            response_payload["files"] = files_array
            logger.info(f"[API SERVER] ✅ Added {len(files_array)} files to response payload")
            if files_array:
                logger.info(f"[API SERVER] First file in payload: {list(files_array[0].keys()) if files_array else 'empty'}")
        else:
            logger.info(f"[API SERVER] No files_array to add to response payload")

        # Add documents array if present
        if documents_array is not None:
            response_payload["documents"] = documents_array
            logger.info(f"[API SERVER] ✅ Added {len(documents_array)} documents to response payload")
        else:
            logger.info(f"[API SERVER] No documents_array to add to response payload")

        # Add completion_event if present (for rich UI feedback)
        if completion_event is not None:
            response_payload["completion_event"] = completion_event
            logger.info(f"[API SERVER] Including completion_event: {completion_event.get('action_type')}")

        record_chat_event(
            session_id,
            "assistant",
            formatted_message,
            metadata={"transport": "websocket", "status": result_status},
        )

        # CRITICAL: Validate response payload before sending
        def validate_response_payload(payload: dict) -> tuple:
            """Validate response payload structure and return (is_valid, error_message)."""
            if not isinstance(payload, dict):
                return False, "Payload is not a dictionary"
            
            # Required fields
            if "type" not in payload:
                return False, "Missing required field: type"
            if "message" not in payload:
                return False, "Missing required field: message"
            if "timestamp" not in payload:
                return False, "Missing required field: timestamp"
            
            # Validate message is not empty
            if not payload.get("message") or not str(payload["message"]).strip():
                return False, "Message field is empty"
            
            # Validate files array if present
            if "files" in payload:
                files = payload["files"]
                if not isinstance(files, list):
                    return False, "Files field must be a list"
                # Validate each file entry
                for i, file_entry in enumerate(files):
                    if not isinstance(file_entry, dict):
                        return False, f"File entry {i} is not a dictionary"
                    if "path" not in file_entry and "name" not in file_entry:
                        return False, f"File entry {i} missing required fields (path or name)"
            
            # Validate documents array if present
            if "documents" in payload:
                docs = payload["documents"]
                if not isinstance(docs, list):
                    return False, "Documents field must be a list"
            
            return True, ""
        
        # Validate payload
        is_valid, validation_error = validate_response_payload(response_payload)
        if not is_valid:
            logger.error(f"[API SERVER] ❌ Response payload validation failed: {validation_error}")
            logger.error(f"[API SERVER] Payload structure: {json.dumps(response_payload, indent=2, default=str)}")
            # Create a minimal valid payload as fallback
            response_payload = {
                "type": "response",
                "message": formatted_message or "Task completed, but response formatting encountered an error.",
                "status": result_status,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "validation_error": validation_error
            }
            logger.warning(f"[API SERVER] Using fallback payload after validation failure")
        
        # CRITICAL: Log complete response payload structure before sending
        logger.info(f"[API SERVER] ========== RESPONSE PAYLOAD STRUCTURE ==========")
        logger.info(f"[API SERVER] Response payload keys: {list(response_payload.keys())}")
        logger.info(f"[API SERVER] Response type: {response_payload.get('type')}")
        logger.info(f"[API SERVER] Response status: {response_payload.get('status')}")
        logger.info(f"[API SERVER] Has files: {'files' in response_payload}")
        if "files" in response_payload:
            files_in_payload = response_payload["files"]
            logger.info(f"[API SERVER] Files in payload: count={len(files_in_payload) if isinstance(files_in_payload, list) else 'non-list'}, type={type(files_in_payload)}")
            if isinstance(files_in_payload, list) and len(files_in_payload) > 0:
                logger.info(f"[API SERVER] First file: name={files_in_payload[0].get('name', 'N/A')}, path={files_in_payload[0].get('path', 'N/A')[:50]}")
        logger.info(f"[API SERVER] Has documents: {'documents' in response_payload}")
        logger.info(f"[API SERVER] Message length: {len(formatted_message)}")
        logger.info(f"[API SERVER] Message preview: {formatted_message[:200] if formatted_message else 'EMPTY'}")
        logger.info(f"[API SERVER] =================================================")
        
        # CRITICAL: Log before sending response to track response flow
        logger.info(f"[API SERVER] Sending response to user (session: {session_id}, status: {result_status}, message length: {len(formatted_message)})")
        
        # Send response with guaranteed delivery
        send_success = await manager.send_message(response_payload, websocket)
        if send_success:
            logger.info(f"[API SERVER] ✅ Response sent successfully to session {session_id}")
        else:
            logger.error(f"[API SERVER] ❌ Failed to send response to session {session_id} (message queued for retry)")
            # Try to send a minimal error notification as immediate fallback
            try:
                minimal_payload = {
                    "type": "status",
                    "message": "Response is being prepared, please wait...",
                    "status": "processing",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat()
                }
                await manager.send_message(minimal_payload, websocket)
            except Exception as fallback_error:
                logger.error(f"[API SERVER] ❌ Failed to send fallback status message: {fallback_error}", exc_info=True)
        
        # Signal that response has been delivered - allows next request to be processed
        async with _session_tasks_lock:
            if session_id in _session_response_acks:
                _session_response_acks[session_id].set()
                logger.info(f"[API SERVER] Response delivery acknowledged for session {session_id}")

        # Always emit a completion status so the launcher clears the processing banner
        normalized_result_status = (result_status or "").lower()
        if normalized_result_status not in {"cancelled", "error", "failed"}:
            await manager.send_message({
                "type": "status",
                "status": "complete",
                "message": "",
                "timestamp": datetime.now().isoformat()
            }, websocket)

        if result_status == "cancelled":
            await manager.send_message({
                "type": "status",
                "status": "cancelled",
                "message": result_dict.get("message", "Execution cancelled."),
                "timestamp": datetime.now().isoformat()
            }, websocket)
            
            # Signal response delivered for cancellation
            async with _session_tasks_lock:
                if session_id in _session_response_acks:
                    _session_response_acks[session_id].set()
                    logger.info(f"[API SERVER] Cancellation response acknowledged for session {session_id}")

    except asyncio.CancelledError:
        logger.info(f"[API SERVER] Agent task cancelled for session {session_id}")
        # CRITICAL: Always send cancellation response before cleanup
        try:
            # Send plan_finalize event for cancellation
            await manager.send_message({
                "type": "plan_finalize",
                "status": "cancelled",
                "timestamp": datetime.now().isoformat(),
                "summary": {"reason": "user_cancelled"}
            }, websocket)
            await manager.send_message({
                "type": "status",
                "status": "cancelled",
                "message": "Execution cancelled.",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }, websocket)
            record_chat_event(
                session_id,
                "assistant",
                "Execution cancelled.",
                metadata={"transport": "websocket", "status": "cancelled"},
            )
            logger.info(f"[API SERVER] ✅ Cancellation response sent to session {session_id}")
            
            # Signal response delivered for cancellation
            async with _session_tasks_lock:
                if session_id in _session_response_acks:
                    _session_response_acks[session_id].set()
                    logger.info(f"[API SERVER] Cancellation response acknowledged for session {session_id}")
        except Exception as send_error:
            logger.error(f"[API SERVER] ❌ Failed to send cancellation response to session {session_id}: {send_error}", exc_info=True)
            # Still signal ack to prevent deadlock
            async with _session_tasks_lock:
                if session_id in _session_response_acks:
                    _session_response_acks[session_id].set()
    except Exception as e:
        logger.error(f"[API SERVER] Error executing task for session {session_id}: {e}", exc_info=True)
        # CRITICAL: Always send error response before cleanup to prevent stuck state
        try:
            # Send plan_finalize event for errors
            await manager.send_message({
                "type": "plan_finalize",
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "summary": {"error": str(e)}
            }, websocket)
            
            # Send error response message
            await manager.send_message({
                "type": "error",
                "message": f"Error: {str(e)}",
                "status": "error",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }, websocket)
            record_chat_event(
                session_id,
                "assistant",
                f"Error: {str(e)}",
                metadata={"transport": "websocket", "status": "error"},
            )
            logger.info(f"[API SERVER] ✅ Error response sent to session {session_id}")
            
            # Signal response delivered for error
            async with _session_tasks_lock:
                if session_id in _session_response_acks:
                    _session_response_acks[session_id].set()
                    logger.info(f"[API SERVER] Error response acknowledged for session {session_id}")
        except Exception as send_error:
            logger.error(f"[API SERVER] ❌ Failed to send error response to session {session_id}: {send_error}", exc_info=True)
            # Still signal ack to prevent deadlock
            async with _session_tasks_lock:
                if session_id in _session_response_acks:
                    _session_response_acks[session_id].set()
    finally:
        async with _session_tasks_lock:
            session_tasks.pop(session_id, None)
            session_cancel_events.pop(session_id, None)


async def handle_stop_request(session_id: str, websocket: WebSocket):
    """Handle a stop command by signalling the active task to cancel."""
    async with _session_tasks_lock:
        task = session_tasks.get(session_id)
        cancel_event = session_cancel_events.get(session_id)

    if not task or task.done():
        await manager.send_message({
            "type": "status",
            "status": "idle",
            "message": "No active task to stop.",
            "timestamp": datetime.now().isoformat()
        }, websocket)
        return

    if cancel_event and not cancel_event.is_set():
        cancel_event.set()
        logger.info(f"Cancellation requested for session {session_id}")

    await manager.send_message({
        "type": "status",
        "status": "cancelling",
        "message": "Stop requested. Attempting to cancel safely...",
        "timestamp": datetime.now().isoformat()
    }, websocket)

# REST Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Cerebro OS API",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for Electron launcher"""
    return {
        "status": "ok",
        "service": "Cerebro OS API",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/stats", response_model=SystemStats)
async def get_stats():
    """Get system statistics"""
    try:
        # Get document indexer stats (if available)
        indexed_docs = 0
        total_chunks = 0

        # The agent doesn't have document_indexer, so we'll use default values
        # In a real implementation, you would get these from a document indexer service

        # Get available agents
        from src.agent.agent_registry import AgentRegistry
        registry = AgentRegistry(config_manager.get_config())
        available_agents = list(registry.agents.keys())

        return SystemStats(
            indexed_documents=indexed_docs,
            total_chunks=total_chunks,
            available_agents=available_agents,
            uptime="Running"
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/storage/status")
async def storage_status():
    """Report health for chat persistence layers."""
    mongo_status = await chat_storage.health()
    cache_status = chat_cache.describe()
    startup_cache_status = startup_cache_manager.describe()
    return {
        "mongo": mongo_status,
        "cache": cache_status,
        "startup_cache": startup_cache_status,
    }


@app.get("/api/vector/health")
async def vector_health():
    """Return connectivity details for the configured Qdrant instance."""
    try:
        vectordb_config = validate_vectordb_config(config_manager.get_config())
    except VectorServiceConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    headers = {"Content-Type": "application/json"}
    api_key = vectordb_config.get("api_key")
    if api_key:
        headers["api-key"] = api_key
    base_url = vectordb_config["url"].rstrip("/")
    timeout = vectordb_config.get("timeout_seconds", 6.0)

    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=timeout) as client:
        start = time.perf_counter()
        try:
            response = await client.get("/collections")
            response.raise_for_status()
        except Exception as exc:
            logger.error("[VECTOR HEALTH] Failed to query Qdrant: %s", exc)
            raise HTTPException(status_code=502, detail=f"Failed to query Qdrant: {exc}") from exc

        latency_ms = (time.perf_counter() - start) * 1000
        collections = response.json().get("result", {}).get("collections", [])
        return {
            "status": "ok",
            "url": str(client.base_url),
            "collection": vectordb_config["collection"],
            "collections_visible": len(collections),
            "latency_ms": round(latency_ms, 2),
        }


@app.get("/api/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str, limit: int = 50):
    """Return cached + persisted chat history for a session."""
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    limit = max(1, min(limit, 500))
    payload = await _build_chat_history_payload(session_id, limit)
    return payload


@app.get("/api/activity-graph/activity-level")
async def get_activity_graph_activity_level(
    component_id: str,
    window_hours: int = 168,
    limit: int = 15,
):
    """
    Return aggregated activity score and recent signals for a component.
    """
    if not component_id:
        raise HTTPException(status_code=400, detail="component_id is required")

    _require_graph_analytics()
    limit = max(1, min(limit, 50))
    window_hours = max(0, window_hours)
    result = graph_analytics_service.get_component_activity(
        component_id=component_id,
        window_hours=window_hours,
        limit=limit,
    )
    return result


@app.get("/api/activity-graph/dissatisfaction")
async def get_activity_graph_dissatisfaction(
    window_hours: int = 168,
    limit: int = 5,
    components: Optional[List[str]] = None,
):
    """
    Return leaderboard of components ranked by dissatisfaction signals.
    """
    _require_graph_analytics()
    limit = max(1, min(limit, 25))
    window_hours = max(0, window_hours)
    results = graph_analytics_service.get_dissatisfaction_leaderboard(
        window_hours=window_hours,
        limit=limit,
        components=components,
    )
    return {
        "window_hours": window_hours,
        "limit": limit,
        "results": results,
    }


@app.get("/api/activity/component/{component_id}")
async def get_activity_component(component_id: str, window_days: int = 14):
    """
    Return aggregated Git/Slack/doc-drift metrics for a component.
    """
    if not component_id:
        raise HTTPException(status_code=400, detail="component_id is required")
    _require_activity_service()
    window_days = max(0, window_days)
    return activity_service.get_activity_for_component(component_id, window_days=window_days)


@app.get("/api/activity/top-components")
async def get_activity_top_components(limit: int = 5, window_days: int = 14):
    """
    Return the noisiest components ranked by doc-drift intensity.
    """
    _require_activity_service()
    limit = max(1, min(limit, 25))
    window_days = max(0, window_days)
    results = activity_service.get_top_components_by_doc_drift(limit=limit, window_days=window_days)
    return {
        "window_days": window_days,
        "limit": limit,
        "results": results,
    }


@app.get("/api/context-resolution/impacts")
async def get_context_resolution_impacts(
    api_id: Optional[str] = None,
    component_id: Optional[str] = None,
    max_depth: Optional[int] = None,
    include_docs: Optional[bool] = None,
    include_services: Optional[bool] = None,
):
    """
    Return docs/services/components impacted by a component/API change.
    """
    if not api_id and not component_id:
        raise HTTPException(status_code=400, detail="api_id or component_id is required")

    _require_context_resolution()
    include_docs = (
        include_docs
        if include_docs is not None
        else impact_settings.get("include_docs", True)
    )
    include_services = (
        include_services
        if include_services is not None
        else impact_settings.get("include_services", True)
    )

    result = context_resolution_service.resolve_impacts(
        api_id=api_id,
        component_id=component_id,
        max_depth=max_depth,
        include_docs=include_docs,
        include_services=include_services,
    )
    return result


@app.post("/api/context-resolution/changes")
async def post_context_resolution_changes(request: ContextChangeRequest):
    """
    Given changed code artifacts (and optional component), return docs/components to update.
    """
    if not request.component_id and not request.artifact_ids:
        raise HTTPException(status_code=400, detail="component_id or artifact_ids is required")

    _require_context_resolution()
    result = context_resolution_service.resolve_change_impacts(
        component_id=request.component_id,
        artifact_ids=request.artifact_ids,
        max_depth=request.max_depth,
        include_docs=request.include_docs,
        include_activity=request.include_activity,
        include_cross_repo=request.include_cross_repo,
        activity_window_hours=request.activity_window_hours,
    )
    return result


@app.get("/api/graph/validation")
async def get_graph_validation():
    """
    Run lightweight graph validation checks.
    """
    if not graph_validator.is_available():
        raise HTTPException(
            status_code=503,
            detail="Graph validator unavailable. Enable Neo4j in config.yaml.",
        )
    return graph_validator.run_checks()


@app.post("/api/telemetry/slash-command")
async def record_slash_command_telemetry(data: Dict[str, Any] = Body(...)):
    """Record slash command usage telemetry from frontend."""
    try:
        command_name = data.get("command_name", "unknown")
        invocation_source = data.get("invocation_source", "unknown")
        timestamp = data.get("timestamp")
        
        # Record via performance monitor (same as backend does)
        try:
            get_performance_monitor().record_batch_operation("slash_command_usage", 1)
        except Exception as e:
            logger.warning(f"[TELEMETRY] Failed to record batch operation: {e}")
        
        # Log structured entry
        logger.info(
            "[SLASH COMMANDS] Command invoked",
            extra={
                "command": command_name,
                "invocation_source": invocation_source,
                "timestamp": timestamp,
            },
        )
        
        return {"status": "recorded", "command": command_name}
    except Exception as e:
        # Don't break user flow if telemetry fails
        logger.warning(f"[TELEMETRY] Error recording slash command telemetry: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/feedback")
async def record_user_feedback(payload: FeedbackPayload):
    """Persist thumbs-up/down feedback for completed plans."""
    feedback_type = (payload.feedback_type or "").strip().lower()
    if feedback_type not in {"positive", "negative"}:
        raise HTTPException(status_code=400, detail="feedback_type must be 'positive' or 'negative'")

    entry = payload.dict(exclude_none=True)
    entry.pop("feedback_type", None)

    try:
        await feedback_logger.log_async(feedback_type, entry)
        log_fn = logger.warning if feedback_type == "negative" else logger.info
        log_fn(
            "[USER FEEDBACK] Recorded feedback entry",
            extra={
                "feedback_type": feedback_type,
                "plan_id": payload.plan_id,
                "goal": payload.goal,
                "plan_status": payload.plan_status,
            },
        )
        return {"status": "recorded", "feedback_type": feedback_type}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"[USER FEEDBACK] Failed to record feedback: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to record feedback")


class FrontendLogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    context: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class ContextChangeRequest(BaseModel):
    component_id: Optional[str] = None
    artifact_ids: Optional[List[str]] = None
    max_depth: Optional[int] = None
    include_docs: bool = True
    include_activity: bool = True
    include_cross_repo: Optional[bool] = None
    activity_window_hours: Optional[int] = None


@app.post("/api/logs")
async def receive_frontend_log(log_entry: FrontendLogEntry):
    """Receive and store frontend logs for unified logging"""
    try:
        # Sanitize log entry
        sanitized_context = sanitize_value(log_entry.context or {}) if log_entry.context else {}
        sanitized_error = sanitize_value(log_entry.error or {}) if log_entry.error else None
        
        # Write to unified log file
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"frontend-{datetime.now().strftime('%Y-%m-%d')}.log"
        
        log_line = {
            "timestamp": log_entry.timestamp,
            "level": log_entry.level,
            "message": log_entry.message,
            "context": sanitized_context,
        }
        if sanitized_error:
            log_line["error"] = sanitized_error
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_line) + "\n")
        
        # Also log to backend logger with appropriate level
        log_message = f"[FRONTEND] {log_entry.message}"
        extra = {"context": sanitized_context}
        if sanitized_error:
            extra["error"] = sanitized_error
        
        if log_entry.level.upper() == "ERROR":
            logger.error(log_message, extra=extra)
        elif log_entry.level.upper() == "WARN":
            logger.warning(log_message, extra=extra)
        elif log_entry.level.upper() == "DEBUG":
            logger.debug(log_message, extra=extra)
        else:
            logger.info(log_message, extra=extra)
        
        return {"status": "logged"}
    except Exception as exc:
        logger.error(f"[LOGS] Failed to store frontend log: {exc}", exc_info=True)
        # Don't raise error - logging failures shouldn't break the app
        return {"status": "error", "message": str(exc)}


@app.post("/webhooks/github")
async def github_webhook(request: Request):
    """
    Handle GitHub webhook events for PR notifications.

    Processes pull_request events, validates signatures, and stores PR metadata
    for the Git agent to query.
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # Get signature from header
        signature = request.headers.get("X-Hub-Signature-256", "")

        # Get event type
        event_type = request.headers.get("X-GitHub-Event", "")

        # Parse JSON payload
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.error("[GITHUB WEBHOOK] Invalid JSON payload")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        # Initialize webhook service
        from src.services.github_webhook_service import GitHubWebhookService
        webhook_service = GitHubWebhookService(config_manager.get_config())

        # Verify signature
        if not webhook_service.verify_signature(body, signature):
            logger.error("[GITHUB WEBHOOK] Signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Process PR event
        pr_metadata = webhook_service.process_pr_event(event_type, payload)

        # If event was ignored, return success but note it
        if pr_metadata.get("ignored"):
            logger.info(f"[GITHUB WEBHOOK] Event ignored: {pr_metadata.get('reason')}")
            return {
                "status": "ignored",
                "reason": pr_metadata.get("reason"),
            }

        # Broadcast WebSocket notification for PR events
        if event_type == "pull_request" and not pr_metadata.get("ignored"):
            action = pr_metadata.get("action", "unknown")
            pr_number = pr_metadata.get("pr_number")
            title = pr_metadata.get("title", "")
            repo = pr_metadata.get("repo", "")
            branch = pr_metadata.get("base_branch", "")
            author = pr_metadata.get("author", "")
            url = pr_metadata.get("url", "")

            # Create notification message based on action
            notification_messages = {
                "opened": f"New PR opened: #{pr_number} - {title}",
                "ready_for_review": f"PR #{pr_number} ready for review: {title}",
                "closed": f"PR #{pr_number} {'merged' if pr_metadata.get('merged_at') else 'closed'}: {title}",
                "synchronize": f"PR #{pr_number} updated with new commits: {title}",
                "reopened": f"PR #{pr_number} reopened: {title}",
            }

            notification_message = notification_messages.get(
                action,
                f"PR #{pr_number} {action} on {repo}/{branch}: {title}"
            )

            # Broadcast to all connected WebSocket clients
            websocket_message = {
                "type": "github_pr",
                "message": notification_message,
                "github_pr": {
                    "repo": repo,
                    "branch": branch,
                    "number": pr_number,
                    "title": title,
                    "author": author,
                    "url": url,
                    "action": action,
                },
                "timestamp": datetime.now().isoformat(),
            }

            # Send to all connected clients
            for websocket in manager.active_connections:
                try:
                    await websocket.send_json(websocket_message)
                    logger.info(f"[GITHUB WEBHOOK] Sent PR notification to WebSocket client")
                except Exception as e:
                    logger.warning(f"[GITHUB WEBHOOK] Failed to send to WebSocket: {e}")

            # Send system notification (optional - using notifications agent)
            try:
                from src.agent.notifications_agent import send_system_notification
                send_system_notification(
                    title="GitHub PR Event",
                    message=notification_message,
                    sound="Glass",
                )
                logger.info(f"[GITHUB WEBHOOK] Sent system notification")
            except Exception as e:
                logger.warning(f"[GITHUB WEBHOOK] Failed to send system notification: {e}")

        logger.info(f"[GITHUB WEBHOOK] Successfully processed {event_type} event")
        return {
            "status": "success",
            "event_type": event_type,
            "pr_metadata": pr_metadata,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"[GITHUB WEBHOOK] Error processing webhook: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """Synchronous chat endpoint (for simple requests)"""
    try:
        logger.info(f"Received chat message: {message.message}")
        
        # Get session ID from request if available, otherwise use default
        session_id = message.session_id or "default"
        record_chat_event(
            session_id,
            "user",
            message.message,
            metadata={"transport": "rest"},
        )
        
        # Handle /clear command
        normalized_msg = message.message.strip().lower() if message.message else ""
        if normalized_msg == "/clear" or normalized_msg == "clear":
            session_manager.clear_session(session_id)
            record_chat_event(
                session_id,
                "assistant",
                "✨ Context cleared. Starting a new session.",
                metadata={"transport": "rest", "status": "completed"},
            )
            return ChatResponse(
                response="✨ Context cleared. Starting a new session.",
                status="completed",
                timestamp=datetime.now().isoformat()
            )

        # Execute the task using the automation agent
        result = agent.run(message.message, session_id=session_id)
        
        # Handle different return types
        if isinstance(result, dict):
            result_dict = result
        elif isinstance(result, str):
            # Try to parse if it's a string representation of a dict
            try:
                import ast
                result_dict = ast.literal_eval(result)
            except:
                result_dict = {"message": result}
        else:
            result_dict = {"message": str(result)}
        
        # Check if this is a retry_with_orchestrator result from slash command
        if isinstance(result_dict, dict) and result_dict.get("type") == "retry_with_orchestrator":
            original_message = result_dict.get("original_message", message.message)
            context = result_dict.get("context", None)
            
            # Log context if present (for debugging)
            if context:
                logger.info(f"[API SERVER] [REST] Retrying with context: {context}")
            
            # Convert slash command to natural language for orchestrator
            # Strip the slash command prefix (e.g., "/email summarize..." -> "summarize...")
            if original_message.strip().startswith('/'):
                # Extract the command and task
                parts = original_message.strip().split(None, 1)
                if len(parts) > 1:
                    # Remove the slash and command, keep the task
                    natural_language = parts[1]
                else:
                    natural_language = original_message.replace('/', '').strip()
            else:
                natural_language = original_message
            
            # Retry via orchestrator (agent.run will handle it as natural language)
            result = agent.run(natural_language, session_id=session_id, context=context)
            result_dict = result if isinstance(result, dict) else {"message": str(result)}
        
        # Format the response
        if isinstance(result_dict, dict):
            # Check again if retry happened (in case retry also returned retry)
            if result_dict.get("type") == "retry_with_orchestrator":
                # This shouldn't happen, but if it does, return a helpful message
                response_text = f"Request was delegated to orchestrator but did not complete. Original message: {result_dict.get('original_message', message.message)}"
                status = "error"
            else:
                # Extract message from orchestrator result structure
                # Orchestrator returns: {"status": "...", "message": "...", "final_result": {...}, "results": {...}}
                if "final_result" in result_dict:
                    # Prefer the message field, fall back to final_result content
                    response_text = (
                        result_dict.get("message") or 
                        result_dict.get("response") or
                        (result_dict.get("final_result", {}).get("message") if isinstance(result_dict.get("final_result"), dict) else None) or
                        str(result_dict)
                    )
                else:
                    response_text = result_dict.get("message") or result_dict.get("response") or str(result_dict)
                status = result_dict.get("status", "completed")
        else:
            response_text = str(result_dict)
            status = "completed"

        record_chat_event(
            session_id,
            "assistant",
            response_text,
            metadata={"transport": "rest", "status": status},
        )
        return ChatResponse(
            response=response_text,
            status=status,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agents")
async def list_agents():
    """List all available agents and their capabilities"""
    try:
        from src.agent.agent_registry import AgentRegistry
        registry = AgentRegistry(config_manager.get_config())

        agents_info = {}
        for agent_name, agent_instance in registry.agents.items():
            tools = agent_instance.get_tools()
            agents_info[agent_name] = {
                "name": agent_name,
                "tools": [tool.__name__ if hasattr(tool, '__name__') else str(tool) for tool in tools],
                "tool_count": len(tools)
            }

        return agents_info
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/commands")
async def list_commands():
    """List all available commands/actions for the launcher"""
    try:
        from src.agent.agent_registry import AgentRegistry
        registry = AgentRegistry(config_manager.get_config())

        # Map agent names to categories and icons
        agent_metadata = {
            "file_agent": {"title": "Search Files", "category": "Files", "icon": "📄", "description": "Search and manage documents", "keywords": ["file", "document", "search", "pdf", "doc"]},
            "folder_agent": {"title": "Browse Folders", "category": "Files", "icon": "📁", "description": "Navigate and organize folders", "keywords": ["folder", "directory", "browse", "organize"]},
            "email_agent": {"title": "Email", "category": "Communication", "icon": "📧", "description": "Compose and send emails", "keywords": ["email", "mail", "send", "compose"]},
            "imessage_agent": {"title": "iMessage", "category": "Communication", "icon": "💬", "description": "Send iMessages", "keywords": ["imessage", "message", "text", "sms"]},
            "browser_agent": {"title": "Web Search", "category": "Web", "icon": "🌐", "description": "Search the web", "keywords": ["web", "search", "google", "browser"]},
            "google_agent": {"title": "Google", "category": "Web", "icon": "🔍", "description": "Search with Google", "keywords": ["google", "search"]},
            "presentation_agent": {"title": "Presentations", "category": "Productivity", "icon": "📊", "description": "Create Keynote presentations", "keywords": ["keynote", "presentation", "slides", "deck"]},
            "writing_agent": {"title": "Writing", "category": "Productivity", "icon": "✍️", "description": "Generate documents and content", "keywords": ["write", "document", "pages", "content"]},
            "spotify_agent": {"title": "Spotify", "category": "Media", "icon": "🎵", "description": "Control Spotify playback", "keywords": ["spotify", "music", "play", "song"]},
            "calendar_agent": {"title": "Calendar", "category": "Productivity", "icon": "📅", "description": "Manage calendar events", "keywords": ["calendar", "event", "schedule", "meeting"]},
            "notes_agent": {"title": "Notes", "category": "Productivity", "icon": "📝", "description": "Create and manage notes", "keywords": ["note", "notes", "write"]},
            "reminders_agent": {"title": "Reminders", "category": "Productivity", "icon": "⏰", "description": "Set reminders", "keywords": ["reminder", "todo", "task"]},
            "maps_agent": {"title": "Maps", "category": "Navigation", "icon": "🗺️", "description": "Plan routes and trips", "keywords": ["maps", "directions", "route", "travel"]},
            "weather_agent": {"title": "Weather", "category": "Information", "icon": "🌤️", "description": "Get weather information", "keywords": ["weather", "forecast", "temperature"]},
            "discord_agent": {"title": "Discord", "category": "Communication", "icon": "💬", "description": "Send Discord messages", "keywords": ["discord", "message", "chat"]},
            "whatsapp_agent": {"title": "WhatsApp", "category": "Communication", "icon": "💬", "description": "Send WhatsApp messages", "keywords": ["whatsapp", "message", "chat"]},
            "bluesky_agent": {"title": "Bluesky", "category": "Social", "icon": "🦋", "description": "Post to Bluesky", "keywords": ["bluesky", "social", "post"]},
            "twitter_agent": {"title": "Twitter", "category": "Social", "icon": "🐦", "description": "Post to Twitter", "keywords": ["twitter", "tweet", "social"]},
            "reddit_agent": {"title": "Reddit", "category": "Social", "icon": "🤖", "description": "Browse Reddit", "keywords": ["reddit", "browse"]},
            "knowledge_agent": {"title": "Knowledge", "category": "Information", "icon": "📚", "description": "Look up information", "keywords": ["knowledge", "wiki", "information", "learn"]},
            "voice_agent": {"title": "Voice", "category": "Accessibility", "icon": "🎤", "description": "Text-to-speech and transcription", "keywords": ["voice", "speak", "tts", "transcribe"]},
            "shortcuts_agent": {"title": "Shortcuts", "category": "Automation", "icon": "⚡", "description": "Run Shortcuts", "keywords": ["shortcut", "automation", "workflow"]},
            "system_control_agent": {"title": "System Control", "category": "System", "icon": "⚙️", "description": "Control system settings", "keywords": ["system", "settings", "control"]},
        }

        commands = []
        for agent_name, agent_instance in registry.agents.items():
            # Get metadata or use defaults
            metadata = agent_metadata.get(agent_name, {
                "title": agent_name.replace("_", " ").title(),
                "category": "General",
                "icon": "⚙️",
                "description": f"{agent_name} operations",
                "keywords": [agent_name.replace("_agent", "")]
            })

            commands.append({
                "id": agent_name,
                "title": metadata["title"],
                "description": metadata["description"],
                "category": metadata["category"],
                "icon": metadata["icon"],
                "keywords": metadata["keywords"],
                "handler_type": "agent"
            })

        # Add Spotify control commands (direct API calls)
        spotify_controls = [
            {
                "id": "spotify_play_pause",
                "title": "Play/Pause",
                "description": "Toggle Spotify playback",
                "category": "Spotify",
                "icon": "⏯️",
                "keywords": ["spotify", "play", "pause", "toggle", "music"],
                "handler_type": "spotify_control",
                "endpoint": "/api/spotify/toggle"  # Will implement toggle endpoint
            },
            {
                "id": "spotify_next",
                "title": "Next Track",
                "description": "Skip to next Spotify track",
                "category": "Spotify",
                "icon": "⏭️",
                "keywords": ["spotify", "next", "skip", "forward"],
                "handler_type": "spotify_control",
                "endpoint": "/api/spotify/next"
            },
            {
                "id": "spotify_previous",
                "title": "Previous Track",
                "description": "Go to previous Spotify track",
                "category": "Spotify",
                "icon": "⏮️",
                "keywords": ["spotify", "previous", "back", "rewind"],
                "handler_type": "spotify_control",
                "endpoint": "/api/spotify/previous"
            }
        ]
        commands.extend(spotify_controls)

        # Add all slash commands from slash_commands.py
        # Commands that need input (with_input) vs immediate execution (immediate)
        slash_commands = [
            # Files & Folders
            {"id": "files", "title": "Files", "icon": "📄", "type": "with_input", "placeholder": "What to do with files...", "category": "Files", "description": "Talk directly to File Agent", "keywords": ["file", "files", "document", "search"]},
            {"id": "folder", "title": "Folder", "icon": "📁", "type": "with_input", "placeholder": "What to do with folders...", "category": "Files", "description": "Browse and organize folders", "keywords": ["folder", "directory", "browse"]},
            {"id": "browse", "title": "Browse", "icon": "🌐", "type": "with_input", "placeholder": "What to browse...", "category": "Web", "description": "Talk directly to Browser Agent", "keywords": ["browse", "web", "browser"]},
            
            # Communication
            {"id": "email", "title": "Email", "icon": "📧", "type": "with_input", "placeholder": "What to email...", "category": "Communication", "description": "Compose and send emails", "keywords": ["email", "mail", "send"]},
            {"id": "message", "title": "iMessage", "icon": "💬", "type": "with_input", "placeholder": "What to message...", "category": "Communication", "description": "Send iMessages", "keywords": ["message", "imessage", "text", "sms"]},
            {"id": "whatsapp", "title": "WhatsApp", "icon": "💬", "type": "with_input", "placeholder": "What to do with WhatsApp...", "category": "Communication", "description": "Read and analyze WhatsApp messages", "keywords": ["whatsapp", "wa"]},
            {"id": "wa", "title": "WA", "icon": "💬", "type": "with_input", "placeholder": "What to do with WhatsApp...", "category": "Communication", "description": "WhatsApp (alias)", "keywords": ["whatsapp", "wa"]},
            {"id": "discord", "title": "Discord", "icon": "💬", "type": "with_input", "placeholder": "What to do with Discord...", "category": "Communication", "description": "Send Discord messages", "keywords": ["discord", "message"]},
            {"id": "slack", "title": "Slack", "icon": "💬", "type": "with_input", "placeholder": "e.g. search #incidents for errors...", "category": "Communication", "description": "Fetch and summarize Slack discussions", "keywords": ["slack", "channel", "chat", "search"]},
            
            # Social Media
            {"id": "bluesky", "title": "Bluesky", "icon": "🦋", "type": "with_input", "placeholder": "What to post...", "category": "Social", "description": "Post to Bluesky", "keywords": ["bluesky", "post", "social"]},
            {"id": "twitter", "title": "Twitter", "icon": "🐦", "type": "with_input", "placeholder": "What to tweet...", "category": "Social", "description": "Post to Twitter", "keywords": ["twitter", "tweet"]},
            {"id": "reddit", "title": "Reddit", "icon": "🤖", "type": "with_input", "placeholder": "What to do on Reddit...", "category": "Social", "description": "Browse Reddit", "keywords": ["reddit", "browse"]},
            
            # Productivity
            {"id": "present", "title": "Present", "icon": "📊", "type": "with_input", "placeholder": "What presentation to create...", "category": "Productivity", "description": "Create Keynote presentations", "keywords": ["present", "keynote", "presentation", "slides"]},
            {"id": "write", "title": "Write", "icon": "✍️", "type": "with_input", "placeholder": "What to write...", "category": "Productivity", "description": "Generate documents and content", "keywords": ["write", "document", "content"]},
            {"id": "calendar", "title": "Calendar", "icon": "📅", "type": "with_input", "placeholder": "What calendar action...", "category": "Productivity", "description": "List events & prepare meeting briefs", "keywords": ["calendar", "event", "schedule", "meeting"]},
            {"id": "day", "title": "Day", "icon": "📅", "type": "with_input", "placeholder": "Generate daily briefing...", "category": "Productivity", "description": "Generate comprehensive daily briefings", "keywords": ["day", "daily", "briefing", "overview"]},
            {"id": "report", "title": "Report", "icon": "📄", "type": "with_input", "placeholder": "What report to generate...", "category": "Productivity", "description": "Generate PDF reports from local files", "keywords": ["report", "pdf", "generate"]},
            {"id": "recurring", "title": "Recurring", "icon": "🔄", "type": "with_input", "placeholder": "Schedule recurring task...", "category": "Productivity", "description": "Schedule recurring tasks", "keywords": ["recurring", "schedule", "repeat"]},
            {"id": "git", "title": "GitHub PRs", "icon": "🐙", "type": "with_input", "placeholder": "e.g. PR #42 or open PRs on main...", "category": "Development", "description": "Inspect GitHub pull requests", "keywords": ["git", "github", "pr", "pull request"]},
            {"id": "pr", "title": "PR Lookup", "icon": "🐙", "type": "with_input", "placeholder": "Inspect PR #123...", "category": "Development", "description": "Alias for GitHub PR summaries", "keywords": ["pr", "pull request", "github"]},
            {"id": "oq", "title": "Activity Intelligence", "icon": "🧭", "type": "with_input", "placeholder": "Ask about recent activity...", "category": "Intelligence", "description": "Combine Slack + Git signals for status updates", "keywords": ["oq", "activity", "status", "recent work"]},
            {"id": "activity", "title": "Activity Query", "icon": "🧭", "type": "with_input", "placeholder": "e.g. What's happening with onboarding?", "category": "Intelligence", "description": "Alias for Oqoqo reasoning", "keywords": ["activity", "oqoqo", "status"]},
            
            # Media
            {"id": "spotify", "title": "Spotify", "icon": "🎵", "type": "with_input", "placeholder": "Control Spotify...", "category": "Media", "description": "Control Spotify playback", "keywords": ["spotify", "music", "play"]},
            {"id": "music", "title": "Music", "icon": "🎵", "type": "with_input", "placeholder": "Control music...", "category": "Media", "description": "Control Spotify playback (alias)", "keywords": ["music", "spotify", "play"]},
            
            # Navigation & Information
            {"id": "maps", "title": "Maps", "icon": "🗺️", "type": "with_input", "placeholder": "Where to go...", "category": "Navigation", "description": "Plan routes and trips", "keywords": ["maps", "directions", "route", "travel"]},
            {"id": "stock", "title": "Stock", "icon": "📈", "type": "with_input", "placeholder": "Stock ticker or query...", "category": "Finance", "description": "Stock/Finance Agent", "keywords": ["stock", "finance", "ticker", "market"]},
            
            # System & Utilities
            {"id": "notify", "title": "Notify", "icon": "🔔", "type": "with_input", "placeholder": "Notification message...", "category": "System", "description": "Send system notifications", "keywords": ["notify", "notification", "alert"]},
            {"id": "explain", "title": "Explain", "icon": "💡", "type": "with_input", "placeholder": "What to explain...", "category": "Information", "description": "Explain commands or concepts", "keywords": ["explain", "help", "how"]},
            {"id": "help", "title": "Help", "icon": "❓", "type": "with_input", "placeholder": "Command or topic...", "category": "Information", "description": "Show help for commands", "keywords": ["help", "?", "assistance"]},
            {"id": "agents", "title": "Agents", "icon": "🤖", "type": "immediate", "category": "Information", "description": "List all available agents", "keywords": ["agents", "list", "available"]},
            {"id": "clear", "title": "Clear", "icon": "🗑️", "type": "immediate", "category": "System", "description": "Clear chat history", "keywords": ["clear", "reset"]},
            {"id": "confetti", "title": "Confetti", "icon": "🎉", "type": "immediate", "category": "Fun", "description": "Trigger celebratory confetti effects", "keywords": ["confetti", "celebrate", "party"]},
        ]

        # Convert slash commands to command format
        for slash_cmd in slash_commands:
            commands.append({
                "id": slash_cmd["id"],
                "title": slash_cmd["title"],
                "description": slash_cmd["description"],
                "category": slash_cmd["category"],
                "icon": slash_cmd["icon"],
                "keywords": slash_cmd["keywords"],
                "handler_type": "slash_command",
                "command_type": slash_cmd["type"],  # "immediate" or "with_input"
                "placeholder": slash_cmd.get("placeholder", ""),
            })

        # System commands (handled by Electron, not agents)
        system_commands = [
            {
                "id": "open_app",
                "title": "Open Application",
                "description": "Launch any macOS app (e.g., 'open Safari')",
                "category": "System",
                "icon": "🚀",
                "keywords": ["open", "launch", "start", "app", "application"],
                "handler_type": "system_open_app"
            },
            {
                "id": "settings",
                "title": "Settings",
                "description": "Open Cerebros preferences",
                "category": "System",
                "icon": "⚙️",
                "keywords": ["settings", "preferences", "config", "options", "prefs"],
                "handler_type": "system_settings"
            },
            {
                "id": "quit_cerebros",
                "title": "Quit Cerebros",
                "description": "Close the Cerebros application",
                "category": "System",
                "icon": "🚪",
                "keywords": ["quit", "exit", "close"],
                "handler_type": "system_quit"
            },
        ]
        commands.extend(system_commands)

        return {"commands": commands}
    except Exception as e:
        logger.error(f"Error listing commands: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/help")
async def get_help_data():
    """Get complete help data for all commands, agents, and tools"""
    try:
        from src.ui.help_registry import HelpRegistry
        help_registry = HelpRegistry(agent_registry)
        return help_registry.to_dict()
    except Exception as e:
        logger.error(f"Error getting help data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/help/search")
async def search_help(q: str, limit: int = 10):
    """Search help entries by query"""
    try:
        from src.ui.help_registry import HelpRegistry
        help_registry = HelpRegistry(agent_registry)
        results = help_registry.search(q, limit=limit)
        return {
            "query": q,
            "count": len(results),
            "results": [r.to_dict() for r in results]
        }
    except Exception as e:
        logger.error(f"Error searching help: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/universal-search")
async def universal_search(q: str, limit: int = 10, types: str = "document,image"):
    """Universal semantic search across indexed documents and images with highlighting"""
    import time
    from telemetry.config import get_tracer
    
    start_time = time.time()
    tracer = get_tracer("api_server")
    span = tracer.start_span("universal_search")
    
    try:
        span.set_attribute("query", sanitize_value(q[:100]))  # Limit query length in telemetry
        span.set_attribute("limit", limit)
        span.set_attribute("types", types)
        
        logger.info(f"[UNIVERSAL_SEARCH] Starting search", {
            "query": q[:100],  # Log first 100 chars
            "limit": limit,
            "types": types
        })
        
        # Validate input
        if not q or not q.strip():
            span.set_status({"code": 400, "message": "Empty query"})
            span.end()
            raise HTTPException(status_code=400, detail="Query parameter 'q' is required and cannot be empty")

        # Sanitize and limit query length
        query = q.strip()[:200]  # Limit query length for security
        if not query:
            span.set_status({"code": 400, "message": "Query empty after trimming"})
            span.end()
            raise HTTPException(status_code=400, detail="Query cannot be empty after trimming")

        # Parse types filter
        requested_types = set(t.strip().lower() for t in types.split(',') if t.strip())
        if not requested_types:
            requested_types = {"document", "image"}

        # Search results from different sources
        all_results = []
        doc_search_time = 0
        image_search_time = 0

        # Document search
        if "document" in requested_types:
            try:
                doc_start = time.time()
                grouped_results = get_orchestrator().search.search_and_group(query)
                doc_limit = limit if len(requested_types) == 1 else limit // 2
                doc_search_time = time.time() - doc_start
                
                logger.debug(f"[UNIVERSAL_SEARCH] Document search completed", {
                    "query": query[:50],
                    "results_found": len(grouped_results),
                    "time_ms": round(doc_search_time * 1000, 2)
                })
                
                span.set_attribute("document_results_count", len(grouped_results))
                span.set_attribute("document_search_time_ms", round(doc_search_time * 1000, 2))

                for result in grouped_results[:doc_limit]:
                    # Get the best chunk for snippet generation
                    best_chunk = max(result['chunks'], key=lambda x: x['similarity'])

                    # Generate highlighted snippet
                    snippet, highlight_offsets = _generate_highlighted_snippet(
                        best_chunk['full_content'],
                        query,
                        context_chars=150
                    )

                    all_results.append({
                        "result_type": "document",
                        "file_path": result['file_path'],
                        "file_name": result['file_name'],
                        "file_type": result['file_type'],
                        "page_number": best_chunk.get('page_number'),
                        "total_pages": result['total_pages'],
                        "similarity_score": round(result['max_similarity'], 3),
                        "snippet": snippet,
                        "highlight_offsets": highlight_offsets,
                        "breadcrumb": _generate_breadcrumb(result['file_path']),
                        "metadata": {
                            "width": None,
                            "height": None
                        }
                    })
            except Exception as e:
                logger.error(f"[UNIVERSAL_SEARCH] Error searching documents", exc_info=True, extra={
                    "query": query[:50],
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                set_span_error(span, e, {"search_type": "document"})

        # Image search
        if "image" in requested_types and get_orchestrator().indexer.image_indexer:
            try:
                image_start = time.time()
                image_results = get_orchestrator().indexer.image_indexer.search_images(query, top_k=limit // 2)
                image_search_time = time.time() - image_start
                
                logger.debug(f"[UNIVERSAL_SEARCH] Image search completed", {
                    "query": query[:50],
                    "results_found": len(image_results),
                    "time_ms": round(image_search_time * 1000, 2)
                })
                
                span.set_attribute("image_results_count", len(image_results))
                span.set_attribute("image_search_time_ms", round(image_search_time * 1000, 2))

                for result in image_results:
                    all_results.append({
                        "result_type": "image",
                        "file_path": result['file_path'],
                        "file_name": result['file_name'],
                        "file_type": result['file_type'],
                        "similarity_score": round(result['similarity_score'], 3),
                        "snippet": result['caption'],  # Caption serves as snippet for images
                        "highlight_offsets": [],  # No highlighting for images
                        "breadcrumb": result['breadcrumb'],
                        "thumbnail_url": f"/api/files/thumbnail?path={result['file_path']}&max_size=256",
                        "preview_url": f"/api/files/preview?path={result['file_path']}",
                        "metadata": {
                            "width": result.get('width'),
                            "height": result.get('height')
                        }
                    })
            except Exception as e:
                logger.error(f"[UNIVERSAL_SEARCH] Error searching images", exc_info=True, extra={
                    "query": query[:50],
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                set_span_error(span, e, {"search_type": "image"})

        # Sort all results by similarity score (descending)
        all_results.sort(key=lambda x: x['similarity_score'], reverse=True)

        # Apply final limit
        final_results = all_results[:limit]
        
        total_time = time.time() - start_time
        
        logger.info(f"[UNIVERSAL_SEARCH] Search completed", {
            "query": query[:50],
            "total_results": len(final_results),
            "document_results": len([r for r in final_results if r["result_type"] == "document"]),
            "image_results": len([r for r in final_results if r["result_type"] == "image"]),
            "total_time_ms": round(total_time * 1000, 2),
            "doc_search_time_ms": round(doc_search_time * 1000, 2),
            "image_search_time_ms": round(image_search_time * 1000, 2)
        })
        
        span.set_attribute("total_results", len(final_results))
        span.set_attribute("total_time_ms", round(total_time * 1000, 2))
        span.set_status({"code": 1})  # OK status
        span.end()

        return {
            "query": query,
            "count": len(final_results),
            "results": final_results,
            "types_searched": list(requested_types)
        }

    except HTTPException:
        span.set_status({"code": 2})  # ERROR status
        span.end()
        raise
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"[UNIVERSAL_SEARCH] Search failed", exc_info=True, extra={
            "query": q[:50] if q else None,
            "error": str(e),
            "error_type": type(e).__name__,
            "total_time_ms": round(total_time * 1000, 2)
        })
        set_span_error(span, e, {"query": sanitize_value(q[:100]) if q else None})
        span.set_status({"code": 2})  # ERROR status
        span.end()
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


def _generate_highlighted_snippet(content: str, query: str, context_chars: int = 150) -> tuple[str, list[list[int]]]:
    """Generate a highlighted snippet with character offsets for query terms"""
    import re

    if not content:
        return "", []

    # Simple keyword extraction from query (split on spaces and punctuation)
    keywords = re.findall(r'\b\w+\b', query.lower())
    if not keywords:
        # Fallback: return first part of content
        snippet = content[:context_chars * 2] + "..." if len(content) > context_chars * 2 else content
        return snippet, []

    # Find best matching section
    content_lower = content.lower()
    best_start = 0
    max_matches = 0

    # Slide through content to find section with most keyword matches
    window_size = context_chars * 2
    for i in range(0, len(content) - window_size + 1, context_chars // 2):
        window = content_lower[i:i + window_size]
        matches = sum(1 for keyword in keywords if keyword in window)
        if matches > max_matches:
            max_matches = matches
            best_start = i

    # Extract snippet around best match
    start = max(0, best_start - context_chars // 2)
    end = min(len(content), start + context_chars * 2)

    snippet = content[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."

    # Find highlight offsets within the snippet
    highlight_offsets = []
    snippet_lower = snippet.lower()

    for keyword in keywords:
        # Find all occurrences of this keyword in the snippet
        for match in re.finditer(r'\b' + re.escape(keyword) + r'\b', snippet_lower, re.IGNORECASE):
            start_offset = match.start()
            end_offset = match.end()
            # Adjust for the "..." prefix if present
            if snippet.startswith("..."):
                start_offset += 3
                end_offset += 3
            highlight_offsets.append([start_offset, end_offset])

    return snippet, highlight_offsets


def _generate_breadcrumb(file_path: str) -> str:
    """Generate a breadcrumb path for display"""
    # Get relative path from configured document directories
    config = config_manager.get_config()
    folders = config.get('documents', {}).get('folders', [])

    for folder in folders:
        try:
            folder_path = Path(folder)
            file_path_obj = Path(file_path)
            if file_path_obj.is_relative_to(folder_path):
                relative_path = file_path_obj.relative_to(folder_path)
                return str(relative_path)
        except (ValueError, OSError):
            continue

    # Fallback: return just the filename
    return Path(file_path).name


@app.get("/api/help/categories")
async def get_help_categories():
    """Get all help categories"""
    try:
        from src.ui.help_registry import HelpRegistry
        help_registry = HelpRegistry(agent_registry)
        categories = help_registry.get_all_categories()
        return {
            "categories": [c.to_dict() for c in categories]
        }
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/help/categories/{category}")
async def get_category_help(category: str):
    """Get help entries for a specific category"""
    try:
        from src.ui.help_registry import HelpRegistry
        help_registry = HelpRegistry(agent_registry)
        entries = help_registry.get_by_category(category)
        if not entries:
            raise HTTPException(status_code=404, detail=f"Category '{category}' not found")
        return {
            "category": category,
            "count": len(entries),
            "entries": [e.to_dict() for e in entries]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting category help: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/help/commands/{command}")
async def get_command_help(command: str):
    """Get detailed help for a specific command"""
    try:
        from src.ui.help_registry import HelpRegistry
        help_registry = HelpRegistry(agent_registry)

        # Try with slash prefix
        entry = help_registry.get_entry(f"/{command}")
        if not entry:
            # Try without slash
            entry = help_registry.get_entry(command)

        if not entry:
            # Get suggestions
            suggestions = help_registry.get_suggestions(f"/{command}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": f"Command '{command}' not found",
                    "suggestions": suggestions
                }
            )

        return entry.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting command help: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/help/agents/{agent}")
async def get_agent_help(agent: str):
    """Get detailed help for a specific agent"""
    try:
        from src.ui.help_registry import HelpRegistry
        help_registry = HelpRegistry(agent_registry)

        agent_help = help_registry.get_agent(agent)
        if not agent_help:
            raise HTTPException(status_code=404, detail=f"Agent '{agent}' not found")

        return agent_help.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent help: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ConfigUpdateRequest(BaseModel):
    """Request model for config updates."""
    updates: Dict[str, Any]


@app.get("/api/config")
async def get_config():
    """
    Get current configuration (sanitized - no API keys).
    
    Returns editable fields only for security.
    """
    try:
        current_config = config_manager.get_config()
        
        # Sanitize config - remove sensitive fields
        sanitized = current_config.copy()
        
        # Remove OpenAI API key
        if "openai" in sanitized and "api_key" in sanitized["openai"]:
            sanitized["openai"] = sanitized["openai"].copy()
            sanitized["openai"]["api_key"] = "***REDACTED***"
        
        # Mask Discord credentials
        if "discord" in sanitized and "credentials" in sanitized["discord"]:
            sanitized["discord"] = sanitized["discord"].copy()
            sanitized["discord"]["credentials"] = {
                "email": sanitized["discord"]["credentials"].get("email", ""),
                "password": "***REDACTED***" if sanitized["discord"]["credentials"].get("password") else "",
                "mfa_code": "***REDACTED***" if sanitized["discord"]["credentials"].get("mfa_code") else ""
            }
        
        return sanitized
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/config")
async def update_config(request: ConfigUpdateRequest):
    """
    Update configuration and hot-reload.
    
    Updates are merged with existing config, saved to config.yaml,
    and components are updated without restart.
    """
    try:
        # Update config
        updated_config = config_manager.update_config(request.updates)
        
        # Update component references
        config_manager.update_components(agent_registry, agent, _orchestrator)
        
        # Return sanitized updated config
        sanitized = updated_config.copy()
        if "openai" in sanitized and "api_key" in sanitized["openai"]:
            sanitized["openai"] = sanitized["openai"].copy()
            sanitized["openai"]["api_key"] = "***REDACTED***"
        
        if "discord" in sanitized and "credentials" in sanitized["discord"]:
            sanitized["discord"] = sanitized["discord"].copy()
            if "credentials" in sanitized["discord"]:
                sanitized["discord"]["credentials"] = {
                    "email": sanitized["discord"]["credentials"].get("email", ""),
                    "password": "***REDACTED***" if sanitized["discord"]["credentials"].get("password") else "",
                    "mfa_code": "***REDACTED***" if sanitized["discord"]["credentials"].get("mfa_code") else ""
                }
        
        logger.info("Config updated successfully via API")
        return {
            "success": True,
            "message": "Config updated and reloaded",
            "config": sanitized
        }
    except Exception as e:
        logger.error(f"Error updating config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@app.post("/api/config/reload")
async def reload_config_endpoint():
    """Force reload configuration from file."""
    try:
        config_manager.reload_config()
        config_manager.update_components(agent_registry, agent, _orchestrator)
        return {"success": True, "message": "Config reloaded from file"}
    except Exception as e:
        logger.error(f"Error reloading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket endpoint for real-time chat
@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, session_id: Optional[str] = None):
    """WebSocket endpoint for real-time bidirectional communication with session support"""
    # Generate session ID if not provided
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())

    try:
        await manager.connect(websocket, session_id)
        logger.info(f"WebSocket connection established for session {session_id}")
    except Exception as e:
        logger.error(f"Error accepting WebSocket connection: {e}", exc_info=True)
        # Try to send error message before closing
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
        return

    # Get session memory
    try:
        memory = session_manager.get_or_create_session(session_id)
        is_new_session = memory.is_new_session()
    except Exception as e:
        logger.error(f"Error getting session memory: {e}", exc_info=True)
        await manager.disconnect(websocket)
        return

    try:
        # Send welcome message with session info
        await manager.send_message({
            "type": "system",
            "message": "Connected to Cerebro OS",
            "session_id": session_id,
            "session_status": "new" if is_new_session else "resumed",
            "interactions": len(memory.interactions),
            "timestamp": datetime.now().isoformat()
        }, websocket)
        logger.info(f"Welcome message sent to session {session_id}")
    except Exception as e:
        logger.error(f"Error sending welcome message: {e}", exc_info=True)
        await manager.disconnect(websocket)
        return

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            command = (data.get("command") or "").strip().lower()
            stripped_message = message.strip() if message else ""

            # Handle stop command even if no text payload
            if command == "stop" or stripped_message.lower() == "/stop":
                await handle_stop_request(session_id, websocket)
                continue

            if not stripped_message and not command:
                continue

            logger.info(f"WebSocket received (session {session_id}): message='{message}', command='{command}'")
            if stripped_message:
                record_chat_event(
                    session_id,
                    "user",
                    stripped_message,
                    metadata={"transport": "websocket"},
                )
            elif command:
                record_chat_event(
                    session_id,
                    "user",
                    command,
                    metadata={"transport": "websocket", "input_type": "command"},
                )

            # Handle /help command - show help in sidebar (frontend handles this)
            normalized_message = stripped_message.lower().strip() if stripped_message else ""
            is_help_command = (
                normalized_message == "/help" or 
                normalized_message == "help" or
                command == "help" or
                (stripped_message and stripped_message.lower().strip() == "/help") or
                (stripped_message and stripped_message.lower().strip() == "help")
            )
            
            if is_help_command:
                logger.info(f"Detected /help command for session {session_id}")
                # Frontend handles showing help in sidebar, just acknowledge
                await manager.send_message({
                    "type": "system",
                    "message": "💡 Help panel opened in sidebar. Click any command to use it.",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                continue

            # Handle /index command - index documents from configured folders
            normalized_message = stripped_message.lower().strip() if stripped_message else ""
            is_index_command = (
                normalized_message == "/index" or 
                normalized_message == "index" or
                command == "index" or
                (stripped_message and stripped_message.lower().strip() == "/index") or
                (stripped_message and stripped_message.lower().strip() == "index")
            )
            
            if is_index_command:
                logger.info(f"Detected /index command for session {session_id}")
                await manager.send_message({
                    "type": "status",
                    "status": "processing",
                    "message": "📚 Indexing documents from configured folders... This may take a while.",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                
                try:
                    # Create cancel event for indexing
                    indexing_cancel_event = asyncio.Event()
                    
                    # Run indexing in a background task
                    async def run_indexing():
                        try:
                            # Check for cancellation before starting
                            if indexing_cancel_event.is_set():
                                await manager.send_message({
                                    "type": "status",
                                    "status": "idle",
                                    "message": "Indexing cancelled before starting.",
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)
                                return
                            
                            # Run indexing in thread pool with cancel event
                            result = await asyncio.to_thread(
                                get_orchestrator().reindex_documents,
                                cancel_event=indexing_cancel_event
                            )
                            
                            # Check if cancelled during execution
                            if indexing_cancel_event.is_set():
                                await manager.send_message({
                                    "type": "status",
                                    "status": "idle",
                                    "message": "Indexing cancelled.",
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)
                                return
                            
                            if result.get('success'):
                                indexed_count = result.get('indexed_documents', 0)
                                stats = result.get('stats', {})
                                total_chunks = stats.get('total_chunks', 0)
                                unique_files = stats.get('unique_files', 0)
                                
                                folders = config_manager.get_config().get('documents', {}).get('folders', [])
                                folders_str = ', '.join([Path(f).name for f in folders])
                                
                                # Show total documents in index (not just newly indexed)
                                # If no new documents were indexed but index exists, show total count
                                if indexed_count == 0 and unique_files > 0:
                                    message = f"✅ Indexing complete!\n\n📊 **Results:**\n- Total documents in index: {unique_files}\n- Total chunks: {total_chunks}\n- Folders: {folders_str}\n\nYour documents are now searchable and the agent can use them as context."
                                elif indexed_count > 0:
                                    message = f"✅ Indexing complete!\n\n📊 **Results:**\n- New documents indexed: {indexed_count}\n- Total documents in index: {unique_files}\n- Total chunks: {total_chunks}\n- Folders: {folders_str}\n\nYour documents are now searchable and the agent can use them as context."
                                else:
                                    message = f"✅ Indexing complete!\n\n📊 **Results:**\n- Documents indexed: {indexed_count}\n- Total chunks: {total_chunks}\n- Folders: {folders_str}\n\nYour documents are now searchable and the agent can use them as context."
                                
                                await manager.send_message({
                                    "type": "response",
                                    "message": message,
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)
                                
                                await manager.send_message({
                                    "type": "status",
                                    "status": "idle",
                                    "message": "",
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)
                            else:
                                error_msg = result.get('error', 'Unknown error')
                                await manager.send_message({
                                    "type": "error",
                                    "message": f"❌ Indexing failed: {error_msg}",
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)
                                
                                await manager.send_message({
                                    "type": "status",
                                    "status": "idle",
                                    "message": "",
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)
                        except asyncio.CancelledError:
                            logger.info("Indexing task cancelled")
                            await manager.send_message({
                                "type": "status",
                                "status": "idle",
                                "message": "Indexing cancelled.",
                                "timestamp": datetime.now().isoformat()
                            }, websocket)
                        except Exception as e:
                            logger.error(f"Error during indexing: {e}", exc_info=True)
                            await manager.send_message({
                                "type": "error",
                                "message": f"❌ Indexing error: {str(e)}",
                                "timestamp": datetime.now().isoformat()
                            }, websocket)
                            
                            await manager.send_message({
                                "type": "status",
                                "status": "idle",
                                "message": "",
                                "timestamp": datetime.now().isoformat()
                            }, websocket)
                        finally:
                            # Clean up task tracking
                            async with _session_tasks_lock:
                                session_tasks.pop(session_id, None)
                                session_cancel_events.pop(session_id, None)
                    
                    # Create and store the indexing task
                    indexing_task = asyncio.create_task(run_indexing())
                    async with _session_tasks_lock:
                        session_tasks[session_id] = indexing_task
                        session_cancel_events[session_id] = indexing_cancel_event
                except Exception as e:
                    logger.error(f"Error starting indexing: {e}", exc_info=True)
                    await manager.send_message({
                        "type": "error",
                        "message": f"❌ Failed to start indexing: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                continue
            
            # Handle /clear command FIRST - before any other processing
            # Check multiple variations to be robust (case-insensitive, with/without slash)
            normalized_message = stripped_message.lower().strip() if stripped_message else ""
            # Check if message is /clear (with or without leading slash, case-insensitive)
            is_clear_command = (
                normalized_message == "/clear" or 
                normalized_message == "clear" or
                command == "clear" or
                (stripped_message and stripped_message.lower().strip() == "/clear") or
                (stripped_message and stripped_message.lower().strip() == "clear")
            )
            
            if is_clear_command:
                logger.info(f"Detected /clear command for session {session_id}")
                # Atomic check-and-clear: check for active task and clear in one lock
                async with _session_tasks_lock:
                    has_task = session_id in session_tasks and session_tasks[session_id] and not session_tasks[session_id].done()
                    
                    if has_task:
                        # Release lock before sending message
                        pass
                    else:
                        # Cancel any pending task before clearing
                        if session_id in session_tasks:
                            task = session_tasks[session_id]
                            if task and not task.done():
                                cancel_event = session_cancel_events.get(session_id)
                                if cancel_event:
                                    cancel_event.set()
                            session_tasks.pop(session_id, None)
                        session_cancel_events.pop(session_id, None)
                
                if has_task:
                    await manager.send_message({
                        "type": "status",
                        "status": "processing",
                        "message": "Cannot clear context while a request is running. Please stop it first.",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    continue

                # Clear session memory (outside lock to avoid blocking)
                logger.info(f"Clearing session memory for session {session_id}")
                memory = session_manager.clear_session(session_id)
                
                # Send clear message to frontend
                await manager.send_message({
                    "type": "clear",
                    "message": "✨ Context cleared. Starting a new session.",
                    "session_id": session_id,
                    "session_status": "cleared",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                record_chat_event(
                    session_id,
                    "assistant",
                    "✨ Context cleared. Starting a new session.",
                    metadata={"transport": "websocket", "type": "system"},
                )
                logger.info(f"Session cleared successfully for session {session_id}")
                continue

            # Ensure sequential processing: wait for previous request to complete and response to be delivered
            async with _session_tasks_lock:
                # Initialize queue and locks for this session if needed
                if session_id not in _session_queues:
                    _session_queues[session_id] = asyncio.Queue()
                    _session_queue_locks[session_id] = asyncio.Lock()
                    _session_response_acks[session_id] = asyncio.Event()
                    _session_response_acks[session_id].set()  # Initially ready
                
                # Check if there's an active task
                if session_id in session_tasks:
                    existing_task = session_tasks[session_id]
                    if existing_task and not existing_task.done():
                        # Wait for response to be delivered before accepting new request
                        ack_event = _session_response_acks[session_id]
                        if not ack_event.is_set():
                            logger.info(f"[API SERVER] Waiting for previous response to be delivered for session {session_id}")
                            # Release lock before waiting
                            pass
                        else:
                            # Task is done but cleanup hasn't happened yet - wait a bit
                            has_active = True
                    else:
                        # Clean up done task
                        session_tasks.pop(session_id, None)
                        session_cancel_events.pop(session_id, None)
                        _session_response_acks[session_id].set()  # Ready for next request
                        has_active = False
                else:
                    has_active = False
            
            # If there's an active task, wait for it to complete and response to be delivered
            if has_active:
                ack_event = _session_response_acks.get(session_id)
                if ack_event and not ack_event.is_set():
                    # Wait for response delivery (with timeout to prevent infinite wait)
                    try:
                        await asyncio.wait_for(ack_event.wait(), timeout=300.0)  # 5 min max wait
                        logger.info(f"[API SERVER] Previous response delivered, processing new request for session {session_id}")
                    except asyncio.TimeoutError:
                        logger.warning(f"[API SERVER] Timeout waiting for response delivery for session {session_id}, proceeding anyway")
                
                # Check again if task is still active
                async with _session_tasks_lock:
                    if session_id in session_tasks:
                        existing_task = session_tasks[session_id]
                        if existing_task and not existing_task.done():
                            await manager.send_message({
                                "type": "status",
                                "status": "processing",
                                "message": "Still working on your previous request. Please wait or press Stop.",
                                "timestamp": datetime.now().isoformat()
                            }, websocket)
                            continue
                        else:
                            # Task completed while we waited - clean up
                            session_tasks.pop(session_id, None)
                            session_cancel_events.pop(session_id, None)
                            _session_response_acks[session_id].set()

            # Reset ack event for this new request
            async with _session_tasks_lock:
                if session_id in _session_response_acks:
                    _session_response_acks[session_id].clear()

            await manager.send_message({
                "type": "status",
                "status": "processing",
                "message": "Processing your request...",
                "timestamp": datetime.now().isoformat()
            }, websocket)

            # Create task and register atomically
            cancel_event = Event()
            task = asyncio.create_task(
                process_agent_request(session_id, message, websocket, cancel_event)
            )
            async with _session_tasks_lock:
                session_cancel_events[session_id] = cancel_event
                session_tasks[session_id] = task

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        logger.info(f"WebSocket client disconnected (session: {session_id})")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket)
    finally:
        # Cleanup tasks atomically
        async with _session_tasks_lock:
            cleanup_event = session_cancel_events.get(session_id)
            if cleanup_event and not cleanup_event.is_set():
                cleanup_event.set()
            session_tasks.pop(session_id, None)
            session_cancel_events.pop(session_id, None)
            # Ensure response ack is set so next request can proceed
            if session_id in _session_response_acks:
                _session_response_acks[session_id].set()

@app.post("/api/reindex")
async def reindex_documents():
    """Trigger document and image reindexing"""
    try:
        logger.info("Starting document and image reindexing")

        # Get configured folders
        config = config_manager.get_config()
        folders = config.get('documents', {}).get('folders', [])

        if not folders:
            return {"status": "error", "message": "No folders configured for indexing"}

        # Run indexing synchronously (this is a simple MVP - in production might want async)
        indexed_docs = get_orchestrator().indexer.index_documents(folders)

        # Get stats
        doc_stats = get_orchestrator().indexer.get_stats()
        image_stats = {}
        if get_orchestrator().indexer.image_indexer:
            image_stats = get_orchestrator().indexer.image_indexer.get_stats()

        total_docs = doc_stats.get('total_documents', 0)
        total_images = image_stats.get('total_images', 0)

        logger.info(f"Reindexing complete: {indexed_docs} documents indexed, {total_images} total images")

        return {
            "status": "success",
            "message": f"Indexed {indexed_docs} documents and {total_images} images",
            "stats": {
                "documents_indexed": indexed_docs,
                "total_documents": total_docs,
                "total_images": total_images,
                "folders": folders
            }
        }
    except Exception as e:
        logger.error(f"Error reindexing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class RevealFileRequest(BaseModel):
    path: str

@app.post("/api/reveal-file")
async def reveal_file(request: RevealFileRequest):
    """
    Reveal a file in Finder (macOS only).
    
    Accepts a JSON body with 'path' field.
    """
    try:
        file_path = request.path
        
        import subprocess
        import os
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        
        # Use macOS 'open' command to reveal file in Finder
        subprocess.run(["open", "-R", file_path], check=True)
        
        return {
            "success": True,
            "message": f"Revealed {file_path} in Finder"
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"Error revealing file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reveal file: {str(e)}")
    except Exception as e:
        logger.error(f"Error revealing file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class FilePreviewRequest(BaseModel):
    path: str


@app.api_route("/api/files/preview", methods=["GET", "HEAD"])
async def preview_file(path: str, request: Request):
    """
    Preview a file from whitelisted directories (data/reports, data/presentations, etc.).
    
    This endpoint enforces security by only allowing files from configured safe directories.
    It supports both HEAD (for pre-flight checks) and GET (for actual file content) methods.
    All requests are instrumented with OpenTelemetry spans and structured logging for
    debugging preview issues.
    
    Returns file content with appropriate content-type headers for preview.
    Security: Only allows files from configured safe directories.
    """
    from pathlib import Path
    from fastapi.responses import FileResponse, StreamingResponse, Response
    from telemetry.config import get_tracer
    from opentelemetry import trace
    
    # Get request method for telemetry
    method = request.method
    tracer = get_tracer("api_server")
    span = tracer.start_span("file_preview")
    
    try:
        # Log request start with structured data
        logger.info(f"[FILE PREVIEW] {method} request for path: {path}")
        
        # Set telemetry attributes (all as strings/primitives for OpenTelemetry compatibility)
        span.set_attribute("file_preview.method", method)
        span.set_attribute("file_preview.path_param", str(path))
        
        file_path = Path(path)
        
        # Resolve to absolute path
        if not file_path.is_absolute():
            # Try relative to project root
            project_root = Path(__file__).resolve().parent
            file_path = (project_root / file_path).resolve()
        
        resolved_path_str = str(file_path.resolve())
        span.set_attribute("file_preview.resolved_path", resolved_path_str)
        logger.debug(f"[FILE PREVIEW] Resolved path: {resolved_path_str}")
        
        # Security: Whitelist allowed directories
        allowed_roots = [
            Path(__file__).resolve().parent / "data" / "reports",
            Path(__file__).resolve().parent / "data" / "presentations",
            Path(__file__).resolve().parent / "data" / "screenshots",
        ]

        # Also allow files from configured document folders
        config = config_manager.get_config()
        document_folders = config.get('documents', {}).get('folders', [])
        for folder in document_folders:
            allowed_roots.append(Path(folder).resolve())
        
        # Log allowed roots on first request (debugging aid)
        if not hasattr(preview_file, '_logged_allowed_roots'):
            allowed_roots_str = [str(r) for r in allowed_roots]
            logger.info(f"[FILE PREVIEW] Allowed directories: {allowed_roots_str}")
            preview_file._logged_allowed_roots = True
        
        # Check if file is within an allowed directory
        is_allowed = False
        matched_root = None
        for allowed_root in allowed_roots:
            try:
                file_path.resolve().relative_to(allowed_root.resolve())
                is_allowed = True
                matched_root = str(allowed_root)
                break
            except ValueError:
                continue
        
        span.set_attribute("file_preview.is_allowed", str(is_allowed))
        if matched_root:
            span.set_attribute("file_preview.matched_root", matched_root)
        
        if not is_allowed:
            error_msg = f"File path not in allowed directories. Allowed: {[str(r) for r in allowed_roots]}"
            logger.warning(f"[FILE PREVIEW] Access denied for {resolved_path_str}. Allowed roots: {[str(r) for r in allowed_roots]}")
            span.set_attribute("file_preview.status_code", "403")
            span.set_attribute("file_preview.error_type", "HTTPException")
            span.set_status(trace.Status(trace.StatusCode.ERROR, "Access denied"))
            span.end()
            raise HTTPException(status_code=403, detail=error_msg)
        
        # Check if file exists
        if not file_path.exists() or not file_path.is_file():
            logger.warning(f"[FILE PREVIEW] File not found: {resolved_path_str}")
            span.set_attribute("file_preview.status_code", "404")
            span.set_attribute("file_preview.error_type", "FileNotFoundError")
            span.set_status(trace.Status(trace.StatusCode.ERROR, "File not found"))
            span.end()
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        
        # Determine content type
        ext = file_path.suffix.lower()
        content_types = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".html": "text/html",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".key": "application/vnd.apple.keynote",
            ".pages": "application/vnd.apple.pages",
        }
        
        content_type = content_types.get(ext, "application/octet-stream")
        span.set_attribute("file_preview.ext", ext)
        span.set_attribute("file_preview.content_type", content_type)
        
        # For HEAD requests, return headers only (no body)
        if method == "HEAD":
            logger.info(f"[FILE PREVIEW] HEAD request successful for {resolved_path_str} (content-type: {content_type})")
            span.set_attribute("file_preview.status_code", "200")
            span.set_status(trace.Status(trace.StatusCode.OK))
            span.end()
            return Response(
                status_code=200,
                headers={
                    "Content-Type": content_type,
                    "Content-Length": str(file_path.stat().st_size) if file_path.exists() else "0",
                }
            )
        
        # For GET requests, return file content
        logger.info(f"[FILE PREVIEW] GET request successful for {resolved_path_str} (content-type: {content_type})")
        
        # For PDFs and images, return file directly
        if ext in [".pdf", ".png", ".jpg", ".jpeg", ".gif"]:
            span.set_attribute("file_preview.status_code", "200")
            span.set_status(trace.Status(trace.StatusCode.OK))
            span.end()
            return FileResponse(
                str(file_path),
                media_type=content_type,
                filename=file_path.name
            )
        
        # For HTML/text files, read and return content
        if ext in [".html", ".txt", ".md"]:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            span.set_attribute("file_preview.status_code", "200")
            span.set_status(trace.Status(trace.StatusCode.OK))
            span.end()
            return StreamingResponse(
                iter([content]),
                media_type=content_type
            )
        
        # For other files, return as download
        span.set_attribute("file_preview.status_code", "200")
        span.set_status(trace.Status(trace.StatusCode.OK))
        span.end()
        return FileResponse(
            str(file_path),
            media_type=content_type,
            filename=file_path.name
        )
        
    except HTTPException as e:
        # HTTPException is expected for 403/404, log and re-raise
        span.set_attribute("file_preview.status_code", str(e.status_code))
        span.set_attribute("file_preview.error_type", "HTTPException")
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e.detail)))
        span.end()
        raise
    except Exception as e:
        # Unexpected errors
        error_type = type(e).__name__
        logger.error(f"[FILE PREVIEW] Unexpected error previewing file {path}: {e}", exc_info=True)
        span.set_attribute("file_preview.status_code", "500")
        span.set_attribute("file_preview.error_type", error_type)
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
        span.record_exception(e)
        span.end()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files/metadata")
async def get_file_metadata(path: str):
    """
    Get file metadata (size, modified date, etc.) for a file.
    """
    import os
    from pathlib import Path
    
    try:
        file_path = Path(path)
        
        # Security check - ensure file is in allowed directories
        allowed_dirs = [
            Path("data/reports"),
            Path("data/presentations"),
            Path("data/documents"),
            Path("data/images"),
        ]
        
        # Resolve to absolute path
        abs_path = file_path.resolve()
        
        # Check if file is in any allowed directory
        is_allowed = False
        for allowed_dir in allowed_dirs:
            allowed_abs = allowed_dir.resolve()
            try:
                if abs_path.is_relative_to(allowed_abs):
                    is_allowed = True
                    break
            except AttributeError:
                # Python < 3.9 compatibility
                try:
                    abs_path.relative_to(allowed_abs)
                    is_allowed = True
                    break
                except ValueError:
                    pass
        
        if not is_allowed:
            raise HTTPException(status_code=403, detail="File is outside allowed directories")
        
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        stat = abs_path.stat()
        
        return {
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get metadata: {str(e)}")


@app.get("/api/files/thumbnail")
async def get_thumbnail(path: str, max_size: int = 256):
    """
    Generate and serve thumbnail for image files.

    Args:
        path: Path to the image file
        max_size: Maximum dimension for thumbnail

    Returns:
        Thumbnail image as JPEG response
    """
    try:
        from pathlib import Path
        from PIL import Image
        from fastapi.responses import FileResponse
        import hashlib
        import os

        file_path = Path(path)

        # Resolve to absolute path
        if not file_path.is_absolute():
            project_root = Path(__file__).resolve().parent
            file_path = (project_root / file_path).resolve()

        # Security: Only allow thumbnails for images in configured document folders
        config = config_manager.get_config()
        allowed_roots = config.get('documents', {}).get('folders', [])

        is_allowed = False
        for allowed_root in allowed_roots:
            try:
                allowed_path = Path(allowed_root).resolve()
                file_path.resolve().relative_to(allowed_path)
                is_allowed = True
                break
            except ValueError:
                continue

        # Also allow from standard data directories for backwards compatibility
        if not is_allowed:
            standard_roots = [
                Path(__file__).resolve().parent / "data" / "reports",
                Path(__file__).resolve().parent / "data" / "presentations",
                Path(__file__).resolve().parent / "data" / "screenshots",
            ]
            for allowed_root in standard_roots:
                try:
                    file_path.resolve().relative_to(allowed_root.resolve())
                    is_allowed = True
                    break
                except ValueError:
                    continue

        if not is_allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Thumbnail not allowed for this path"
            )

        # Check if file exists and is an image
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

        ext = file_path.suffix.lower()
        supported_image_types = config.get('documents', {}).get('supported_image_types', [])
        if ext not in supported_image_types:
            raise HTTPException(status_code=400, detail=f"Not a supported image type: {ext}")

        # Thumbnail cache settings
        thumbnail_config = config.get('images', {}).get('thumbnail', {})
        cache_dir = Path(thumbnail_config.get('cache_dir', 'data/cache/thumbnails'))
        quality = thumbnail_config.get('quality', 85)

        # Create cache directory
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Generate thumbnail filename
        file_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
        thumbnail_filename = f"{file_hash}_{max_size}x{max_size}.jpg"
        thumbnail_path = cache_dir / thumbnail_filename

        # Generate thumbnail if it doesn't exist
        if not thumbnail_path.exists():
            try:
                with Image.open(file_path) as img:
                    # Create thumbnail
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

                    # Save thumbnail
                    img.save(thumbnail_path, 'JPEG', quality=quality)
            except Exception as e:
                logger.error(f"Error generating thumbnail for {file_path}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to generate thumbnail: {e}")

        # Return thumbnail
        return FileResponse(
            str(thumbnail_path),
            media_type='image/jpeg',
            filename=thumbnail_filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving thumbnail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribe audio using OpenAI Whisper API.
    
    Accepts audio files and returns transcribed text.
    """
    tmp_file_path = None
    try:
        # Log request details for debugging
        import traceback
        logger.info(f"[TRANSCRIBE] Request received from: {audio.filename}, content_type: {audio.content_type}")
        logger.info(f"[TRANSCRIBE] Request headers available: {hasattr(audio, 'headers')}")
        
        # Validate file size (max 25MB for Whisper API)
        content = await audio.read()
        file_size = len(content)
        logger.info(f"Audio file size: {file_size} bytes")
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty audio file received")
        
        if file_size > 25 * 1024 * 1024:  # 25MB limit
            raise HTTPException(status_code=400, detail=f"Audio file too large: {file_size} bytes (max 25MB)")
        
        # Get OpenAI API key from config manager (always fresh)
        api_key = config_manager.get_config().get("openai", {}).get("api_key")
        if not api_key or api_key.startswith("${"):
            # Fallback to environment variable
            api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OpenAI API key not configured")
            raise HTTPException(status_code=500, detail="OpenAI API key not configured. Please set OPENAI_API_KEY environment variable or configure it in config.yaml")
        
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # Save uploaded file temporarily
        # Use .webm extension but Whisper should handle it
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_file:
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        logger.info(f"Saved temporary file: {tmp_file_path}")
        
        try:
            # Transcribe using OpenAI Whisper
            # Whisper supports: mp3, mp4, mpeg, mpga, m4a, wav, webm
            with open(tmp_file_path, "rb") as audio_file:
                logger.info("Calling OpenAI Whisper API...")
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"  # Optional: specify language for better accuracy
                )
            
            transcript_text = transcript.text.strip()
            logger.info(f"Transcription successful: {len(transcript_text)} characters - '{transcript_text[:100]}...'")
            
            return {
                "text": transcript_text,
                "status": "success"
            }
        except Exception as whisper_error:
            logger.error(f"OpenAI Whisper API error: {whisper_error}", exc_info=True)
            error_msg = str(whisper_error)
            if "Invalid file format" in error_msg or "unsupported" in error_msg.lower():
                raise HTTPException(status_code=400, detail=f"Unsupported audio format. Error: {error_msg}")
            elif "rate limit" in error_msg.lower():
                raise HTTPException(status_code=429, detail="OpenAI API rate limit exceeded. Please try again later.")
            else:
                raise HTTPException(status_code=500, detail=f"Whisper API error: {error_msg}")
        finally:
            # Clean up temporary file
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.unlink(tmp_file_path)
                    logger.info(f"Cleaned up temporary file: {tmp_file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file: {cleanup_error}")
                
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@app.post("/api/text-to-speech")
async def text_to_speech_api(
    text: str = Body(..., embed=True),
    voice: str = Body(default="alloy", embed=True),
    speed: float = Body(default=1.0, embed=True)
):
    """
    Convert text to speech using OpenAI TTS API.
    
    Accepts text and returns audio file path or audio data.
    """
    try:
        logger.info(f"Received TTS request: text_length={len(text)}, voice={voice}, speed={speed}")
        
        # Validate inputs
        if not text or len(text.strip()) == 0:
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        MAX_TEXT_LENGTH = 4000
        if len(text) > MAX_TEXT_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Text too long (max {MAX_TEXT_LENGTH} characters). Current: {len(text)}"
            )
        
        valid_voices = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
        if voice not in valid_voices:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid voice '{voice}'. Valid voices: {', '.join(valid_voices)}"
            )
        
        if speed < 0.25 or speed > 4.0:
            raise HTTPException(
                status_code=400,
                detail=f"Speed must be between 0.25 and 4.0. Got: {speed}"
            )
        
        # Get OpenAI API key from config manager (always fresh)
        api_key = config_manager.get_config().get("openai", {}).get("api_key")
        if not api_key or api_key.startswith("${"):
            api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # Generate speech
        response = client.audio.speech.create(
            model="tts-1",  # Use "tts-1-hd" for higher quality (slower, more expensive)
            voice=voice,
            input=text,
            speed=speed
        )
        
        # Save to data/audio directory
        audio_dir = Path(__file__).parent / "data" / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = audio_dir / f"tts_{os.urandom(4).hex()}.mp3"
        
        # Save audio file
        response.stream_to_file(str(audio_path))
        
        logger.info(f"TTS successful: {audio_path}")
        
        return {
            "success": True,
            "audio_path": str(audio_path),
            "text": text,
            "voice": voice,
            "speed": speed,
            "file_size_bytes": audio_path.stat().st_size if audio_path.exists() else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating speech: {e}")
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


# Startup and shutdown handlers for recurring scheduler
@app.on_event("startup")
async def startup_event():
    """Start background services on app startup."""
    startup_profiler.mark("fastapi_startup_event")
    logger.info("Starting recurring task scheduler...")
    await recurring_scheduler.start()

    logger.info("Starting Bluesky notification service...")
    await bluesky_notifications.start()
    
    if branch_watcher_enabled:
        logger.info("Scheduling Branch Watcher service (Oqoqo API docs)...")
        schedule_branch_watcher_start()
    else:
        logger.info("Branch Watcher service disabled via config; skipping startup")

    logger.info("Starting chat persistence worker...")
    await chat_worker.start()
    
    # Background warm-up: Initialize heavy components after server is ready
    async def warm_up_orchestrator():
        # Small delay to ensure server is fully ready to accept requests
        await asyncio.sleep(2)
        try:
            logger.info("[PERF] Background: Warming up WorkflowOrchestrator...")
            # Trigger lazy initialization in background
            get_orchestrator()
            logger.info("[PERF] Background: WorkflowOrchestrator warmed up")
        except Exception as e:
            logger.warning(f"[PERF] Background warm-up failed (non-critical): {e}")
    
    # Start background task (fire and forget)
    asyncio.create_task(warm_up_orchestrator())

    startup_profiler.mark("fastapi_startup_complete")
    logger.info("[STARTUP] Backend timeline", {"events": startup_profiler.summary()})


@app.on_event("shutdown")
async def shutdown_event():
    """Stop background services on app shutdown."""
    logger.info("Stopping recurring task scheduler...")
    await recurring_scheduler.stop()

    logger.info("Stopping Bluesky notification service...")
    await bluesky_notifications.stop()
    
    logger.info("Stopping Branch Watcher service...")
    await _cancel_branch_watcher_start_task()
    await branch_watcher.stop()
    _update_branch_watcher_runtime(lifecycle="stopped")

    logger.info("Stopping chat persistence worker...")
    await chat_worker.stop()


# API endpoint for managing recurring tasks
@app.get("/api/recurring/tasks")
async def get_recurring_tasks():
    """Get all registered recurring tasks."""
    try:
        tasks = await recurring_scheduler.get_tasks()
        return {
            "success": True,
            "tasks": [task.to_dict() for task in tasks]
        }
    except Exception as e:
        logger.error(f"Error fetching recurring tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recurring/tasks")
async def create_recurring_task(spec: Dict[str, Any] = Body(...)):
    """
    Create a new recurring task.

    Body should contain:
        - name: Task name
        - command_text: Original command
        - schedule: Schedule specification (type, weekday, time, tz)
        - action: Action specification (kind, delivery, params)
    """
    try:
        from src.automation.recurring_scheduler import ScheduleSpec, ActionSpec

        # Parse specification
        name = spec.get("name")
        command_text = spec.get("command_text", "")
        schedule_data = spec.get("schedule", {})
        action_data = spec.get("action", {})

        if not name or not schedule_data or not action_data:
            raise HTTPException(status_code=400, detail="Missing required fields")

        # Create specs
        schedule = ScheduleSpec(**schedule_data)
        action = ActionSpec(**action_data)

        # Register task
        task = await recurring_scheduler.register_task(
            name=name,
            command_text=command_text,
            schedule=schedule,
            action=action
        )

        return {
            "success": True,
            "task": task.to_dict(),
            "message": f"Recurring task '{name}' created successfully. Next run: {task.next_run_at}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating recurring task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/recurring/tasks/{task_id}")
async def delete_recurring_task(task_id: str):
    """Delete a recurring task by ID."""
    try:
        await recurring_scheduler.delete_task(task_id)
        return {
            "success": True,
            "message": f"Task {task_id} deleted successfully"
        }
    except Exception as e:
        logger.error(f"Error deleting recurring task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recurring/tasks/{task_id}/pause")
async def pause_recurring_task(task_id: str):
    """Pause a recurring task."""
    try:
        await recurring_scheduler.pause_task(task_id)
        return {
            "success": True,
            "message": f"Task {task_id} paused successfully"
        }
    except Exception as e:
        logger.error(f"Error pausing recurring task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recurring/tasks/{task_id}/resume")
async def resume_recurring_task(task_id: str):
    """Resume a paused recurring task."""
    try:
        await recurring_scheduler.resume_task(task_id)
        return {
            "success": True,
            "message": f"Task {task_id} resumed successfully"
        }
    except Exception as e:
        logger.error(f"Error resuming recurring task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback."""
    code: str
    state: Optional[str] = None
    redirect_uri: str


@app.post("/api/auth/callback")
async def oauth_callback(request: OAuthCallbackRequest):
    """
    Handle OAuth callback with authorization code.

    This endpoint processes OAuth callbacks, specifically implementing Spotify OAuth flow.
    """
    try:
        logger.info(f"OAuth callback received: code={request.code[:20]}..., state={request.state}, redirect_uri={request.redirect_uri}")

        # Check if this is a Spotify callback (state contains 'spotify')
        if request.state and 'spotify' in request.state:
            return await _handle_spotify_callback(request)

        # Get OAuth configuration for other providers
        oauth_config = config_manager.get_config().get("oauth", {})
        allowed_domains = oauth_config.get("allowed_redirect_domains", ["localhost", "127.0.0.1"])

        # Validate redirect URI
        try:
            redirect_url = request.redirect_uri
            parsed_url = json.loads(json.dumps({"url": redirect_url}))  # Basic validation
            # In a real implementation, you would validate against allowed domains
        except Exception as e:
            logger.warning(f"Invalid redirect URI: {e}")

        # TODO: Implement actual OAuth token exchange for other providers
        # This is a placeholder that returns success

        return {
            "success": True,
            "message": "Authentication successful. Redirecting...",
            "redirect_to": "/",  # Default redirect destination
            "code": request.code[:10] + "..."  # Partial code for logging (don't return full code)
        }
    except Exception as e:
        logger.error(f"Error processing OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=f"OAuth callback failed: {str(e)}")


async def _handle_spotify_callback(request: OAuthCallbackRequest):
    """
    Handle Spotify OAuth callback by exchanging authorization code for tokens.
    """
    try:
        logger.info("Processing Spotify OAuth callback")
        logger.info(f"Code: {request.code[:20]}..., Redirect URI: {request.redirect_uri}")

        # Get Spotify API configuration
        from src.integrations.spotify_api import SpotifyAPIClient
        from src.config_validator import get_config_accessor
        
        config = config_manager.get_config()
        accessor = get_config_accessor(config)
        api_config = accessor.get_spotify_api_config()
        logger.info(f"Token storage path: {api_config.token_storage_path}")

        # Initialize Spotify API client
        client = SpotifyAPIClient(
            client_id=api_config.client_id,
            client_secret=api_config.client_secret,
            redirect_uri=request.redirect_uri,
            token_storage_path=api_config.token_storage_path,
        )

        # Exchange authorization code for tokens
        logger.info("Exchanging authorization code for tokens")
        token = client.exchange_code_for_token(request.code)

        if token:
            logger.info(f"Spotify authentication successful! Token saved to: {api_config.token_storage_path}")
            # Verify the token was saved
            if client.is_authenticated():
                logger.info("Token verified - client is authenticated")
            else:
                logger.warning("Token exchange succeeded but client not showing as authenticated")
            
            return {
                "success": True,
                "message": "Spotify authentication successful! You can now play music.",
                "redirect_to": "/",
                "provider": "spotify"
            }
        else:
            logger.error("Failed to exchange authorization code for tokens - token is None")
            raise HTTPException(status_code=400, detail="Failed to exchange authorization code")

    except Exception as e:
        logger.error(f"Error processing Spotify OAuth callback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Spotify authentication failed: {str(e)}")


@app.get("/api/auth/redirect-url")
async def get_redirect_url():
    """
    Get the configured redirect URL for OAuth flows.
    
    This endpoint returns the redirect URL that should be used
    when configuring OAuth providers.
    """
    try:
        oauth_config = config_manager.get_config().get("oauth", {})
        ui_config = config_manager.get_config().get("ui", {})
        
        # Get redirect URL from config or construct from base URL + path
        redirect_url = ui_config.get("redirect_url")
        if not redirect_url or redirect_url.startswith("${"):
            # Construct from base URL and path
            base_url = oauth_config.get("redirect_base_url", "http://localhost:3000")
            redirect_path = oauth_config.get("redirect_path", "/redirect")
            redirect_url = f"{base_url}{redirect_path}"
        
        # Replace environment variables if present
        if redirect_url.startswith("${"):
            import re
            # Extract default value from ${VAR:-default} format
            match = re.match(r'\$\{([^:]+):-([^}]+)\}', redirect_url)
            if match:
                redirect_url = match.group(2)
        
        return {
            "redirect_url": redirect_url,
            "base_url": oauth_config.get("redirect_base_url", "http://localhost:3000"),
            "path": oauth_config.get("redirect_path", "/redirect")
        }
    except Exception as e:
        logger.error(f"Error getting redirect URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SPOTIFY WEB PLAYBACK SDK ENDPOINTS
# ============================================================================

# Global variable to store the web player device ID
web_player_device_id: Optional[str] = None

class SpotifyDeviceRegistration(BaseModel):
    """Request model for registering Spotify web player device."""
    device_id: str


@app.get("/api/spotify/auth-status")
async def spotify_auth_status():
    """Check if user is authenticated with Spotify."""
    try:
        from src.integrations.spotify_api import SpotifyAPIClient
        from src.config_validator import get_config_accessor
        import os

        config = config_manager.get_config()
        accessor = get_config_accessor(config)
        api_config = accessor.get_spotify_api_config()

        # Check if token file exists
        token_file_exists = False
        if api_config.token_storage_path:
            token_file_exists = os.path.exists(api_config.token_storage_path)
            logger.info(f"Token file check: {api_config.token_storage_path} exists={token_file_exists}")

        client = SpotifyAPIClient(
            client_id=api_config.client_id,
            client_secret=api_config.client_secret,
            redirect_uri=api_config.redirect_uri,
            token_storage_path=api_config.token_storage_path,
        )

        is_auth = client.is_authenticated()
        logger.info(f"Spotify auth status: authenticated={is_auth}, has_token={client.token is not None}, token_file_exists={token_file_exists}")
        
        return {
            "authenticated": is_auth,
            "has_credentials": bool(api_config.client_id and api_config.client_secret),
            "token_file_exists": token_file_exists,
            "has_token_object": client.token is not None
        }
    except Exception as e:
        logger.warning(f"Spotify auth status check failed: {e}", exc_info=True)
        return {"authenticated": False, "has_credentials": False, "error": str(e)}


@app.get("/api/spotify/token")
async def get_spotify_token():
    """Get Spotify access token for Web Playback SDK."""
    try:
        from src.integrations.spotify_api import SpotifyAPIClient
        from src.config_validator import get_config_accessor

        config = config_manager.get_config()
        accessor = get_config_accessor(config)
        api_config = accessor.get_spotify_api_config()

        client = SpotifyAPIClient(
            client_id=api_config.client_id,
            client_secret=api_config.client_secret,
            redirect_uri=api_config.redirect_uri,
            token_storage_path=api_config.token_storage_path,
        )

        if not client.is_authenticated():
            raise HTTPException(status_code=401, detail="Not authenticated with Spotify")

        # Get the access token directly from the client's token object
        if not client.token or not client.token.access_token:
            raise HTTPException(status_code=401, detail="No valid token available")

        # Refresh token if it's expired
        if client.token.is_expired():
            try:
                client._refresh_token()
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                raise HTTPException(status_code=401, detail="Token expired and refresh failed")

        return {"access_token": client.token.access_token}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Spotify token: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/spotify/login")
async def spotify_login():
    """Initiate Spotify OAuth login flow."""
    try:
        from src.integrations.spotify_api import SpotifyAPIClient
        from src.config_validator import get_config_accessor
        from fastapi.responses import RedirectResponse

        config = config_manager.get_config()
        accessor = get_config_accessor(config)
        api_config = accessor.get_spotify_api_config()

        client = SpotifyAPIClient(
            client_id=api_config.client_id,
            client_secret=api_config.client_secret,
            redirect_uri=api_config.redirect_uri,
            token_storage_path=api_config.token_storage_path,
        )

        # Get authorization URL with required scopes for playback
        scopes = [
            "user-read-playback-state",
            "user-modify-playback-state",
            "user-read-currently-playing",
            "streaming",
            "user-read-email",
            "user-read-private"
        ]
        auth_url = client.get_authorization_url(scopes)
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Error initiating Spotify login: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/spotify/register-device")
async def register_spotify_device(request: SpotifyDeviceRegistration):
    """Register the web player device ID."""
    global web_player_device_id
    try:
        web_player_device_id = request.device_id
        logger.info(f"Registered Spotify web player device: {web_player_device_id}")
        return {
            "success": True,
            "device_id": web_player_device_id,
            "message": "Device registered successfully"
        }
    except Exception as e:
        logger.error(f"Error registering Spotify device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/spotify/device-id")
async def get_spotify_device_id():
    """Get the registered web player device ID."""
    global web_player_device_id
    if not web_player_device_id:
        raise HTTPException(status_code=404, detail="No web player device registered")
    return {"device_id": web_player_device_id}


@app.get("/api/spotify/devices")
async def get_spotify_devices():
    """Get available Spotify devices."""
    try:
        from src.integrations.spotify_api import SpotifyAPIClient
        from src.config_validator import get_config_accessor

        config = config_manager.get_config()
        accessor = get_config_accessor(config)
        api_config = accessor.get_spotify_api_config()

        client = SpotifyAPIClient(
            client_id=api_config.client_id,
            client_secret=api_config.client_secret,
            redirect_uri=api_config.redirect_uri,
            token_storage_path=api_config.token_storage_path,
        )

        if not client.is_authenticated():
            raise HTTPException(status_code=401, detail="Not authenticated with Spotify")

        devices = client.get_devices()
        return {"devices": devices}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Spotify devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/spotify/pause")
async def spotify_pause():
    """Pause Spotify playback."""
    try:
        from src.integrations.spotify_api import SpotifyAPIClient
        from src.config_validator import get_config_accessor

        config = config_manager.get_config()
        accessor = get_config_accessor(config)
        api_config = accessor.get_spotify_api_config()

        client = SpotifyAPIClient(
            client_id=api_config.client_id,
            client_secret=api_config.client_secret,
            redirect_uri=api_config.redirect_uri,
            token_storage_path=api_config.token_storage_path,
        )

        if not client.is_authenticated():
            raise HTTPException(status_code=401, detail="Not authenticated with Spotify")

        result = client.pause_playback()
        logger.info(f"Pause result: {result}")
        
        # Broadcast playback paused event to all WebSocket clients
        await manager.broadcast({
            "type": "spotify_playback_update",
            "action": "pause",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Handle 204 No Content responses
        if result.get("status_code") == 204:
            return {"success": True, "message": "Playback paused"}
        return {"success": True, "message": "Playback paused", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing playback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/spotify/status")
async def get_spotify_status():
    """Get current Spotify playback status."""
    try:
        from src.integrations.spotify_api import SpotifyAPIClient
        from src.config_validator import get_config_accessor

        config = config_manager.get_config()
        accessor = get_config_accessor(config)
        api_config = accessor.get_spotify_api_config()

        client = SpotifyAPIClient(
            client_id=api_config.client_id,
            client_secret=api_config.client_secret,
            redirect_uri=api_config.redirect_uri,
            token_storage_path=api_config.token_storage_path,
        )

        if not client.is_authenticated():
            raise HTTPException(status_code=401, detail="Not authenticated with Spotify")

        status = client.get_current_playback()
        return {"status": status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Spotify status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/spotify/play")
async def spotify_play():
    """Resume Spotify playback."""
    try:
        from src.integrations.spotify_api import SpotifyAPIClient
        from src.config_validator import get_config_accessor

        config = config_manager.get_config()
        accessor = get_config_accessor(config)
        api_config = accessor.get_spotify_api_config()

        client = SpotifyAPIClient(
            client_id=api_config.client_id,
            client_secret=api_config.client_secret,
            redirect_uri=api_config.redirect_uri,
            token_storage_path=api_config.token_storage_path,
        )

        if not client.is_authenticated():
            raise HTTPException(status_code=401, detail="Not authenticated with Spotify")

        result = client.resume_playback()
        
        # Broadcast playback started event to all WebSocket clients
        await manager.broadcast({
            "type": "spotify_playback_update",
            "action": "play",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Handle 204 No Content responses
        if result.get("status_code") == 204:
            return {"success": True, "message": "Playback resumed"}
        return {"success": True, "message": "Playback resumed", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming playback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/spotify/next")
async def spotify_next():
    """Skip to next track."""
    try:
        from src.integrations.spotify_api import SpotifyAPIClient
        from src.config_validator import get_config_accessor

        config = config_manager.get_config()
        accessor = get_config_accessor(config)
        api_config = accessor.get_spotify_api_config()

        client = SpotifyAPIClient(
            client_id=api_config.client_id,
            client_secret=api_config.client_secret,
            redirect_uri=api_config.redirect_uri,
            token_storage_path=api_config.token_storage_path,
        )

        if not client.is_authenticated():
            raise HTTPException(status_code=401, detail="Not authenticated with Spotify")

        # Use web player device if available
        global web_player_device_id
        result = client.skip_to_next(device_id=web_player_device_id)
        
        # Broadcast track change event to all WebSocket clients
        await manager.broadcast({
            "type": "spotify_playback_update",
            "action": "next",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return {"success": True, "message": "Skipped to next track"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error skipping to next track: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/spotify/previous")
async def spotify_previous():
    """Skip to previous track."""
    try:
        from src.integrations.spotify_api import SpotifyAPIClient
        from src.config_validator import get_config_accessor

        config = config_manager.get_config()
        accessor = get_config_accessor(config)
        api_config = accessor.get_spotify_api_config()

        client = SpotifyAPIClient(
            client_id=api_config.client_id,
            client_secret=api_config.client_secret,
            redirect_uri=api_config.redirect_uri,
            token_storage_path=api_config.token_storage_path,
        )

        if not client.is_authenticated():
            raise HTTPException(status_code=401, detail="Not authenticated with Spotify")

        # Use web player device if available
        global web_player_device_id
        result = client.skip_to_previous(device_id=web_player_device_id)
        
        # Broadcast track change event to all WebSocket clients
        await manager.broadcast({
            "type": "spotify_playback_update",
            "action": "previous",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return {"success": True, "message": "Skipped to previous track"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error skipping to previous track: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# API DOCS - SELF-EVOLVING DOCUMENTATION (OQOQO PATTERN)
# ============================================================================

@app.get("/api/apidocs/spec")
async def get_api_spec():
    """
    Get the current API specification from docs/api-spec.yaml.
    
    Returns the human-facing API documentation that may drift from code.
    """
    try:
        from src.agent.apidocs_agent import read_api_spec
        result = read_api_spec.invoke({})
        
        if not result.get("exists"):
            raise HTTPException(status_code=404, detail=result.get("error", "API spec not found"))
        
        return {
            "success": True,
            "path": result["path"],
            "content": result["content"],
            "line_count": result.get("line_count", 0)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading API spec: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/apidocs/code")
async def get_api_code():
    """
    Get extracted endpoint definitions from api_server.py.
    
    Returns the actual API as implemented in code (source of truth).
    """
    try:
        from src.agent.apidocs_agent import read_api_code
        result = read_api_code.invoke({"include_full": False})
        
        if not result.get("exists"):
            raise HTTPException(status_code=404, detail=result.get("error", "API code not found"))
        
        return {
            "success": True,
            "path": result["path"],
            "endpoint_count": result["endpoint_count"],
            "endpoints": result["endpoints"],
            "content": result["content"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading API code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ApidocsCheckRequest(BaseModel):
    """Request body for drift check."""
    include_proposed_spec: bool = True


@app.post("/api/apidocs/check-drift")
async def check_api_drift(request: ApidocsCheckRequest = ApidocsCheckRequest()):
    """
    Check for drift between API code and documentation.
    
    Uses LLM-based semantic diff to detect meaningful API changes:
    - New/removed endpoints
    - Parameter changes (added, removed, type changed)
    - Response schema changes
    - Breaking vs non-breaking changes
    
    Returns a drift report with:
    - List of changes detected
    - Human-readable summary
    - Proposed spec update (if drift found)
    """
    try:
        from src.agent.apidocs_agent import read_api_spec, read_api_code
        from src.services.api_diff_service import get_api_diff_service
        
        # Read current spec
        spec_result = read_api_spec.invoke({})
        if not spec_result.get("exists"):
            raise HTTPException(status_code=404, detail="API spec not found. Create docs/api-spec.yaml first.")
        
        # Read code endpoints (use summary, not full code - more efficient for LLM)
        code_result = read_api_code.invoke({"include_full": False})
        if not code_result.get("exists"):
            raise HTTPException(status_code=404, detail="API code not found")
        
        # Run semantic diff
        diff_service = get_api_diff_service(config_manager.get_config())
        drift_report = diff_service.check_drift(
            code_content=code_result["content"],
            spec_content=spec_result["content"]
        )
        
        result = drift_report.to_dict()
        
        # Optionally exclude proposed spec (can be large)
        if not request.include_proposed_spec:
            result.pop("proposed_spec", None)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking API drift: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class ApidocsApplyRequest(BaseModel):
    """Request body for applying spec update."""
    proposed_spec: str
    create_backup: bool = True


@app.post("/api/apidocs/apply")
async def apply_api_spec_update(request: ApidocsApplyRequest):
    """
    Apply a proposed spec update to docs/api-spec.yaml.
    
    This is called after user approves the drift fix.
    Creates a backup before overwriting.
    """
    try:
        from src.agent.apidocs_agent import write_api_spec
        
        result = write_api_spec.invoke({
            "content": request.proposed_spec,
            "backup": request.create_backup
        })
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to apply update"))
        
        return {
            "success": True,
            "message": "API spec updated successfully",
            "path": result["path"],
            "backup_path": result.get("backup_path")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying API spec update: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/apidocs/urls")
async def get_api_docs_urls():
    """
    Get URLs to view API documentation.
    
    Returns links to Swagger UI, ReDoc, and the spec file.
    """
    try:
        from src.agent.apidocs_agent import get_api_spec_url
        return get_api_spec_url.invoke({})
    except Exception as e:
        logger.error(f"Error getting API docs URLs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ApidocsBranchCheckRequest(BaseModel):
    """Request body for branch-based drift check."""
    branch_name: str
    include_proposed_spec: bool = True


@app.post("/api/apidocs/check-branch")
async def check_branch_for_drift(request: ApidocsBranchCheckRequest):
    """
    Check if a GitHub branch has API changes that cause documentation drift.
    
    Compares the specified branch against main to detect if api_server.py changed.
    If changes are detected, runs semantic diff against docs/api-spec.yaml.
    
    This is the Oqoqo pattern for PR-based self-evolving documentation.
    
    Args:
        branch_name: The feature branch to check against main
        include_proposed_spec: Whether to generate a proposed spec update
        
    Returns:
        - has_api_changes: Whether the monitored file changed in the branch
        - has_drift: Whether there's drift between code and spec
        - changes: List of detected API changes
        - proposed_spec: Updated spec YAML (if drift found and requested)
    """
    try:
        from src.services.github_pr_service import get_github_pr_service, GitHubAPIError
        from src.agent.apidocs_agent import read_api_spec
        from src.services.api_diff_service import get_api_diff_service
        
        github_service = get_github_pr_service()
        
        # Step 1: Check if the branch has changes to the monitored file
        logger.info(f"[APIDOCS] Checking branch '{request.branch_name}' for API changes")
        branch_result = github_service.check_branch_for_api_changes(request.branch_name)
        
        if branch_result.get("error"):
            raise HTTPException(
                status_code=400, 
                detail=f"GitHub API error: {branch_result['error']}"
            )
        
        if not branch_result.get("has_changes"):
            return {
                "has_api_changes": False,
                "has_drift": False,
                "branch": request.branch_name,
                "base_branch": branch_result.get("base_branch", "main"),
                "monitored_file": branch_result.get("monitored_file"),
                "message": f"No changes to {branch_result.get('monitored_file')} in branch '{request.branch_name}'"
            }
        
        # Step 2: Get current spec
        spec_result = read_api_spec.invoke({})
        if not spec_result.get("exists"):
            raise HTTPException(
                status_code=404, 
                detail="API spec not found. Create docs/api-spec.yaml first."
            )
        
        # Step 3: Run semantic diff between branch code and current spec
        branch_code = branch_result.get("branch_file_content", "")
        if not branch_code:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch file content from branch"
            )
        
        diff_service = get_api_diff_service(config_manager.get_config())
        drift_report = diff_service.check_drift(
            code_content=branch_code,
            spec_content=spec_result["content"]
        )
        
        result = {
            "has_api_changes": True,
            "has_drift": drift_report.has_drift,
            "branch": request.branch_name,
            "base_branch": branch_result.get("base_branch", "main"),
            "monitored_file": branch_result.get("monitored_file"),
            "total_files_changed": branch_result.get("total_files_changed", 0),
            "ahead_by": branch_result.get("ahead_by", 0),
            "changes": [c.to_dict() if hasattr(c, 'to_dict') else c for c in drift_report.changes],
            "change_count": len(drift_report.changes),
            "breaking_changes": sum(1 for c in drift_report.changes if hasattr(c, 'severity') and c.severity.value == "breaking"),
            "summary": drift_report.summary,
        }
        
        # Optionally include proposed spec
        if request.include_proposed_spec and drift_report.has_drift:
            result["proposed_spec"] = drift_report.proposed_spec
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking branch for drift: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/apidocs/watcher/status")
async def get_branch_watcher_status():
    """
    Get the current status of the Branch Watcher service.
    
    Returns information about watched branches, pending drift reports,
    and the service running state.
    """
    try:
        return _build_branch_watcher_status()
    except Exception as e:
        logger.error(f"Error getting branch watcher status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/apidocs/watcher/pending")
async def get_pending_drift_reports():
    """
    Get all pending drift reports awaiting user approval.
    
    Returns a list of branches with detected drift that haven't been
    approved or rejected yet.
    """
    try:
        pending = []
        for branch, report in branch_watcher.pending_drift_reports.items():
            pending.append({
                "branch": report.branch,
                "has_drift": report.has_drift,
                "change_count": report.change_count,
                "breaking_changes": report.breaking_changes,
                "summary": report.summary,
                "detected_at": report.detected_at,
                "has_proposed_spec": report.proposed_spec is not None,
            })
        return {
            "pending_count": len(pending),
            "reports": pending
        }
    except Exception as e:
        logger.error(f"Error getting pending drift reports: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ApidocsApprovalRequest(BaseModel):
    """Request body for approving/rejecting a drift fix."""
    branch: Optional[str] = None  # If None, uses most recent pending report
    approved: bool = True


@app.post("/api/apidocs/watcher/approve")
async def approve_drift_fix(request: ApidocsApprovalRequest):
    """
    Approve or reject a pending drift fix.
    
    If approved, applies the proposed spec update and sends confirmation.
    If rejected, clears the pending report without applying changes.
    
    Returns a response with the Swagger docs URL on success.
    """
    try:
        from src.agent.apidocs_agent import write_api_spec
        
        # Get the pending report
        report = branch_watcher.get_pending_report(request.branch)
        if not report:
            raise HTTPException(
                status_code=404, 
                detail="No pending drift report found" + (f" for branch '{request.branch}'" if request.branch else "")
            )
        
        branch_name = report.branch
        
        if not request.approved:
            # User rejected - just clear the pending report
            branch_watcher.clear_pending_report(branch_name)
            return {
                "success": True,
                "action": "rejected",
                "branch": branch_name,
                "message": f"Drift fix for branch '{branch_name}' was rejected. No changes made."
            }
        
        # User approved - apply the spec update
        if not report.proposed_spec:
            raise HTTPException(
                status_code=400,
                detail=f"No proposed spec available for branch '{branch_name}'"
            )
        
        # Apply the update
        result = write_api_spec.invoke({
            "content": report.proposed_spec,
            "backup": True
        })
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to apply spec update: {result.get('error', 'Unknown error')}"
            )
        
        # Clear the pending report
        branch_watcher.clear_pending_report(branch_name)
        
        # Send confirmation via WebSocket
        confirmation_message = {
            "type": "apidocs_sync",
            "message": f"✅ API documentation updated successfully!\n\n"
                      f"The API spec has been synced with changes from branch `{branch_name}`.\n\n"
                      f"**View updated docs:** http://localhost:8000/docs",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "apidocs_sync": {
                "branch": branch_name,
                "spec_path": result.get("path"),
                "backup_path": result.get("backup_path"),
                "swagger_url": "http://localhost:8000/docs",
                "redoc_url": "http://localhost:8000/redoc",
            }
        }
        
        await manager.broadcast(confirmation_message)
        
        return {
            "success": True,
            "action": "approved",
            "branch": branch_name,
            "message": f"API documentation updated successfully from branch '{branch_name}'",
            "spec_path": result.get("path"),
            "backup_path": result.get("backup_path"),
            "swagger_url": "http://localhost:8000/docs",
            "redoc_url": "http://localhost:8000/redoc"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving drift fix: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Cerebro OS API Server...")
    logger.info("API will be available at http://localhost:8000")
    logger.info("WebSocket endpoint: ws://localhost:8000/ws/chat")
    logger.info("API docs: http://localhost:8000/docs")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
