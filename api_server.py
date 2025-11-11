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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Mac Automation Assistant API")

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import global ConfigManager
from src.config_manager import get_global_config_manager, set_global_config_manager, ConfigManager

# Initialize global config manager
config_manager = get_global_config_manager()

# Get config from manager
config = config_manager.get_config()

# Initialize session manager
session_manager = SessionManager(storage_dir="data/sessions")

# Initialize agent registry with session support
agent_registry = AgentRegistry(config, session_manager=session_manager)

# Initialize automation agent with session support
agent = AutomationAgent(config, session_manager=session_manager)

# Initialize workflow orchestrator for indexing
orchestrator = WorkflowOrchestrator(config)

# Store references for hot-reload
config_manager.update_components(agent_registry, agent, orchestrator)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # session_id -> websocket
        self.websocket_to_session: Dict[WebSocket, str] = {}
        # Async lock for thread-safe access to connection dictionaries
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        async with self._lock:
            self.active_connections[session_id] = websocket
            self.websocket_to_session[websocket] = session_id
            logger.info(f"Client connected with session {session_id}. Total connections: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            session_id = self.websocket_to_session.get(websocket)
            if session_id:
                self.active_connections.pop(session_id, None)
                self.websocket_to_session.pop(websocket, None)
                logger.info(f"Client disconnected (session: {session_id}). Total connections: {len(self.active_connections)}")

    async def send_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def broadcast(self, message: dict):
        async with self._lock:
            # Create a copy of connections to avoid modification during iteration
            connections = list(self.active_connections.values())
        
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")

manager = ConnectionManager()

# Track active agent tasks so we can support safe cancellation per session
# Use async lock for thread-safe access
_session_tasks_lock = asyncio.Lock()
session_tasks: Dict[str, asyncio.Task] = {}
session_cancel_events: Dict[str, Event] = {}

# Pydantic models for API
class ChatMessage(BaseModel):
    message: str
    timestamp: Optional[str] = None

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
        return f"❌ **Error:** {result.get('error_message', 'Unknown error')}"
    
    # Default formatting
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
    
    try:
        result = await asyncio.to_thread(agent.run, user_message, session_id, cancel_event)
        result_dict = result if isinstance(result, dict) else {"message": str(result)}
        result_status = result_dict.get("status", "completed")

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
        
        # If no Maps URL found, use default formatting
        if not formatted_message or formatted_message == json.dumps(result_dict, indent=2):
            # Try to extract meaningful message from result structure
            if "step_results" in result_dict and result_dict["step_results"]:
                # Get the first result's message if available
                first_result = list(result_dict["step_results"].values())[0]
                if isinstance(first_result, dict) and "message" in first_result:
                    formatted_message = first_result["message"]
                elif isinstance(first_result, dict) and "maps_url" in first_result:
                    formatted_message = format_result_message(first_result)
            elif "results" in result_dict and result_dict["results"]:
                # Get the first result's message if available
                first_result = list(result_dict["results"].values())[0]
                if isinstance(first_result, dict) and "message" in first_result:
                    formatted_message = first_result["message"]
                elif isinstance(first_result, dict) and "maps_url" in first_result:
                    formatted_message = format_result_message(first_result)

        await manager.send_message({
            "type": "response",
            "message": formatted_message,
            "status": result_status,
            "session_id": session_id,
            "interaction_count": len(session_memory.interactions),
            "timestamp": datetime.now().isoformat()
        }, websocket)

        if result_status == "cancelled":
            await manager.send_message({
                "type": "status",
                "status": "cancelled",
                "message": result_dict.get("message", "Execution cancelled."),
                "timestamp": datetime.now().isoformat()
            }, websocket)

    except asyncio.CancelledError:
        logger.info(f"Agent task cancelled for session {session_id}")
        await manager.send_message({
            "type": "status",
            "status": "cancelled",
            "message": "Execution cancelled.",
            "timestamp": datetime.now().isoformat()
        }, websocket)
    except Exception as e:
        logger.error(f"Error executing task: {e}")
        await manager.send_message({
            "type": "error",
            "message": f"Error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }, websocket)
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
        "service": "Mac Automation Assistant API",
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
        registry = AgentRegistry(config)
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
        
        # Handle /clear command
        normalized_msg = message.message.strip().lower() if message.message else ""
        if normalized_msg == "/clear" or normalized_msg == "clear":
            # Get session ID from request if available, otherwise use default
            session_id = getattr(message, 'session_id', None) or "default"
            session_manager.clear_session(session_id)
            return ChatResponse(
                response="✨ Context cleared. Starting a new session.",
                status="completed",
                timestamp=datetime.now().isoformat()
            )

        # Execute the task using the automation agent
        result = agent.run(message.message)

        return ChatResponse(
            response=str(result),
            status="completed",
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
        registry = AgentRegistry(config)

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

    await manager.connect(websocket, session_id)

    # Get session memory
    memory = session_manager.get_or_create_session(session_id)
    is_new_session = memory.is_new_session()

    try:
        # Send welcome message with session info
        await manager.send_message({
            "type": "system",
            "message": "Connected to Mac Automation Assistant",
            "session_id": session_id,
            "session_status": "new" if is_new_session else "resumed",
            "interactions": len(memory.interactions),
            "timestamp": datetime.now().isoformat()
        }, websocket)

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
                                
                                folders = config.get('documents', {}).get('folders', [])
                                folders_str = ', '.join([Path(f).name for f in folders])
                                
                                await manager.send_message({
                                    "type": "response",
                                    "message": f"✅ Indexing complete!\n\n📊 **Results:**\n- Documents indexed: {indexed_count}\n- Total chunks: {total_chunks}\n- Folders: {folders_str}\n\nYour documents are now searchable and the agent can use them as context.",
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

            # Atomic check-and-create task pattern
            async with _session_tasks_lock:
                if session_id in session_tasks:
                    existing_task = session_tasks[session_id]
                    if existing_task and not existing_task.done():
                        # Release lock before sending message
                        has_active = True
                    else:
                        # Clean up done task
                        session_tasks.pop(session_id, None)
                        session_cancel_events.pop(session_id, None)
                        has_active = False
                else:
                    has_active = False
            
            if has_active:
                await manager.send_message({
                    "type": "status",
                    "status": "processing",
                    "message": "Still working on your previous request. Please wait or press Stop.",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                continue

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

@app.post("/api/reindex")
async def reindex_documents():
    """Trigger document reindexing"""
    try:
        logger.info("Document reindexing not yet implemented in this API version")
        return {"status": "info", "message": "Document reindexing feature coming soon"}
    except Exception as e:
        logger.error(f"Error reindexing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribe audio using OpenAI Whisper API.
    
    Accepts audio files and returns transcribed text.
    """
    try:
        logger.info(f"Received audio file for transcription: {audio.filename}")
        
        # Get OpenAI API key from config (already loaded at startup)
        api_key = config.get("openai", {}).get("api_key")
        if not api_key or api_key.startswith("${"):
            # Fallback to environment variable
            api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_file:
            content = await audio.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Transcribe using OpenAI Whisper
            with open(tmp_file_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"  # Optional: specify language for better accuracy
                )
            
            logger.info(f"Transcription successful: {transcript.text[:100]}...")
            
            return {
                "text": transcript.text,
                "status": "success"
            }
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
                
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
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
        
        # Get OpenAI API key
        api_key = config.get("openai", {}).get("api_key")
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


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Mac Automation Assistant API Server...")
    logger.info("API will be available at http://localhost:8000")
    logger.info("WebSocket endpoint: ws://localhost:8000/ws/chat")
    logger.info("API docs: http://localhost:8000/docs")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
