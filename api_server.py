"""
FastAPI server that provides REST and WebSocket endpoints for the UI.
Connects to the existing AutomationAgent orchestrator.
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from threading import Event

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import tempfile

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
from src.utils import load_config, save_config
from src.workflow import WorkflowOrchestrator

# Initialize telemetry
from telemetry import init_telemetry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Cerebro OS API")

# Initialize telemetry (must happen before FastAPI instrumentation)
init_telemetry()

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

# Initialize global config manager
config_manager = get_global_config_manager()

# Initialize session manager
session_manager = SessionManager(storage_dir="data/sessions", config=config_manager.get_config())

# Initialize agent registry with session support
agent_registry = AgentRegistry(config_manager.get_config(), session_manager=session_manager)

# Initialize automation agent with session support
agent = AutomationAgent(config_manager.get_config(), session_manager=session_manager)

# Initialize workflow orchestrator for indexing
orchestrator = WorkflowOrchestrator(config_manager.get_config())

# Initialize recurring task scheduler
from src.automation.recurring_scheduler import RecurringTaskScheduler
recurring_scheduler = RecurringTaskScheduler(
    agent_registry=agent_registry,
    agent=agent,
    session_manager=session_manager
)

# Store references for hot-reload
config_manager.update_components(agent_registry, agent, orchestrator)

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

class SystemStats(BaseModel):
    indexed_documents: int
    total_chunks: int
    available_agents: List[str]
    uptime: str


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
        # Try error_message first, fall back to message, then generic
        error_text = result.get('error_message') or result.get('message') or 'Unknown error'
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

        # Build response payload
        response_payload = {
            "type": "response",
            "message": formatted_message,
            "status": result_status,
            "session_id": session_id,
            "interaction_count": len(session_memory.interactions),
            "timestamp": datetime.now().isoformat()
        }
        
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

@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """Synchronous chat endpoint (for simple requests)"""
    try:
        logger.info(f"Received chat message: {message.message}")
        
        # Get session ID from request if available, otherwise use default
        session_id = message.session_id or "default"
        
        # Handle /clear command
        normalized_msg = message.message.strip().lower() if message.message else ""
        if normalized_msg == "/clear" or normalized_msg == "clear":
            session_manager.clear_session(session_id)
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
    try:
        # Validate input
        if not q or not q.strip():
            raise HTTPException(status_code=400, detail="Query parameter 'q' is required and cannot be empty")

        # Sanitize and limit query length
        query = q.strip()[:200]  # Limit query length for security
        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty after trimming")

        # Parse types filter
        requested_types = set(t.strip().lower() for t in types.split(',') if t.strip())
        if not requested_types:
            requested_types = {"document", "image"}

        # Search results from different sources
        all_results = []

        # Document search
        if "document" in requested_types:
            try:
                grouped_results = orchestrator.search.search_and_group(query)
                doc_limit = limit if len(requested_types) == 1 else limit // 2

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
                logger.error(f"Error searching documents: {e}")

        # Image search
        if "image" in requested_types and orchestrator.indexer.image_indexer:
            try:
                image_results = orchestrator.indexer.image_indexer.search_images(query, top_k=limit // 2)

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
                logger.error(f"Error searching images: {e}")

        # Sort all results by similarity score (descending)
        all_results.sort(key=lambda x: x['similarity_score'], reverse=True)

        # Apply final limit
        final_results = all_results[:limit]

        return {
            "query": query,
            "count": len(final_results),
            "results": final_results,
            "types_searched": list(requested_types)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in universal search: {e}")
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
        config_manager.update_components(agent_registry, agent, orchestrator)
        
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
        config_manager.update_components(agent_registry, agent, orchestrator)
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
                                orchestrator.reindex_documents,
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
        indexed_docs = orchestrator.indexer.index_documents(folders)

        # Get stats
        doc_stats = orchestrator.indexer.get_stats()
        image_stats = {}
        if orchestrator.indexer.image_indexer:
            image_stats = orchestrator.indexer.image_indexer.get_stats()

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


@app.get("/api/files/preview")
async def preview_file(path: str):
    """
    Preview a file from whitelisted directories (data/reports, data/presentations, etc.).
    
    Returns file content with appropriate content-type headers for preview.
    Security: Only allows files from configured safe directories.
    """
    try:
        import os
        from pathlib import Path
        from fastapi.responses import FileResponse, StreamingResponse
        
        file_path = Path(path)
        
        # Resolve to absolute path
        if not file_path.is_absolute():
            # Try relative to project root
            project_root = Path(__file__).resolve().parent
            file_path = (project_root / file_path).resolve()
        
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
        
        # Check if file is within an allowed directory
        is_allowed = False
        for allowed_root in allowed_roots:
            try:
                file_path.resolve().relative_to(allowed_root.resolve())
                is_allowed = True
                break
            except ValueError:
                continue
        
        if not is_allowed:
            raise HTTPException(
                status_code=403,
                detail=f"File path not in allowed directories. Allowed: {[str(r) for r in allowed_roots]}"
            )
        
        # Check if file exists
        if not file_path.exists() or not file_path.is_file():
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
        
        # For PDFs and images, return file directly
        if ext in [".pdf", ".png", ".jpg", ".jpeg", ".gif"]:
            return FileResponse(
                str(file_path),
                media_type=content_type,
                filename=file_path.name
            )
        
        # For HTML/text files, read and return content
        if ext in [".html", ".txt", ".md"]:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return StreamingResponse(
                iter([content]),
                media_type=content_type
            )
        
        # For other files, return as download
        return FileResponse(
            str(file_path),
            media_type=content_type,
            filename=file_path.name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    logger.info("Starting recurring task scheduler...")
    await recurring_scheduler.start()

    logger.info("Starting Bluesky notification service...")
    await bluesky_notifications.start()


@app.on_event("shutdown")
async def shutdown_event():
    """Stop background services on app shutdown."""
    logger.info("Stopping recurring task scheduler...")
    await recurring_scheduler.stop()

    logger.info("Stopping Bluesky notification service...")
    await bluesky_notifications.stop()


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
        return {"success": True, "message": "Skipped to previous track"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error skipping to previous track: {e}")
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
