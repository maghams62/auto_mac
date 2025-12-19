"""
WhatsApp Agent - Bridges Mac automation with the WhatsApp Desktop client.

Responsibilities:
- Verify WhatsApp Desktop session is active and logged in
- Navigate to specific chats/groups
- Read messages from chats/groups
- Filter messages by sender (for groups)
- Summarize messages using LLM
- Extract action items from conversations
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import logging

from src.config import get_config_context
from src.config_validator import ConfigValidationError
from ..automation.whatsapp_controller import WhatsAppController
from ..utils import get_temperature_for_model

logger = logging.getLogger(__name__)


def _load_whatsapp_runtime():
    """Load config and validated WhatsApp settings."""
    context = get_config_context()
    accessor = context.accessor
    whatsapp_settings = accessor.get_whatsapp_config()
    return context.data, accessor, whatsapp_settings


def _get_controller() -> WhatsAppController:
    """Get WhatsApp controller instance."""
    config, _, _ = _load_whatsapp_runtime()
    return WhatsAppController(config)


def _summarize_messages_with_llm(
    config: Dict[str, Any],
    messages: List[str],
    contact_name: str,
    is_group: bool = False
) -> str:
    """Summarize messages using LLM."""
    if not messages:
        return "No messages available to summarize."
    
    # Format messages for LLM
    formatted_messages = "\n".join([f"- {msg}" for msg in messages])
    
    openai_config = config.get("openai", {})
    llm = ChatOpenAI(
        model=openai_config.get("model", "gpt-4o"),
        temperature=get_temperature_for_model(config, default_temperature=0.3),
        max_tokens=500,
        api_key=openai_config.get("api_key")
    )
    
    chat_type = "group" if is_group else "chat"
    system_text = (
        f"You are a helpful assistant that summarizes WhatsApp {chat_type} conversations. "
        "Provide a concise summary highlighting key points, decisions, and important information."
    )
    human_text = (
        f"Summarize the following messages from the WhatsApp {chat_type} '{contact_name}':\n\n"
        f"{formatted_messages}\n\n"
        "Provide:\n"
        "1. A brief overview of the conversation\n"
        "2. Key points discussed\n"
        "3. Any action items or decisions made"
    )
    
    try:
        response = llm.invoke([
            SystemMessage(content=system_text),
            HumanMessage(content=human_text),
        ])
        return response.content
    except Exception as e:
        logger.error(f"Error summarizing messages: {e}")
        return f"Error generating summary: {str(e)}"


def _extract_action_items_with_llm(
    config: Dict[str, Any],
    messages: List[str],
    contact_name: str
) -> List[str]:
    """Extract action items from messages using LLM."""
    if not messages:
        return []
    
    formatted_messages = "\n".join([f"- {msg}" for msg in messages])
    
    openai_config = config.get("openai", {})
    llm = ChatOpenAI(
        model=openai_config.get("model", "gpt-4o"),
        temperature=get_temperature_for_model(config, default_temperature=0.2),
        max_tokens=300,
        api_key=openai_config.get("api_key")
    )
    
    system_text = (
        "You are a helpful assistant that extracts action items and tasks from conversations. "
        "Return only a bulleted list of action items, one per line, without numbering or extra formatting."
    )
    human_text = (
        f"Extract action items and tasks from these WhatsApp messages:\n\n"
        f"{formatted_messages}\n\n"
        "Return only actionable items (tasks, deadlines, things to do). "
        "One item per line, prefixed with '- '."
    )
    
    try:
        response = llm.invoke([
            SystemMessage(content=system_text),
            HumanMessage(content=human_text),
        ])
        # Parse response into list
        items = [line.strip().lstrip("- ").strip() for line in response.content.split("\n") if line.strip()]
        return [item for item in items if item]
    except Exception as e:
        logger.error(f"Error extracting action items: {e}")
        return []


@tool
def whatsapp_ensure_session() -> Dict[str, Any]:
    """
    Bring WhatsApp Desktop to the foreground and verify it's running and logged in.
    
    Use this before any other WhatsApp actions if you're unsure whether WhatsApp
    is running or authenticated. Returns details about session status.
    """
    logger.info("[WHATSAPP AGENT] Tool: whatsapp_ensure_session()")
    try:
        controller = _get_controller()
    except ConfigValidationError as exc:
        return {
            "error": True,
            "error_type": "ConfigurationError",
            "error_message": str(exc),
            "retry_possible": False,
        }
    return controller.ensure_session()


@tool
def whatsapp_navigate_to_chat(
    contact_name: str,
    is_group: bool = False
) -> Dict[str, Any]:
    """
    Navigate to a specific WhatsApp chat or group.
    
    Args:
        contact_name: Name of contact or group to navigate to
        is_group: Whether this is a group chat (default: False)
    """
    logger.info(f"[WHATSAPP AGENT] Tool: whatsapp_navigate_to_chat(contact='{contact_name}', is_group={is_group})")
    try:
        controller = _get_controller()
    except ConfigValidationError as exc:
        return {
            "error": True,
            "error_type": "ConfigurationError",
            "error_message": str(exc),
            "retry_possible": False,
        }
    return controller.navigate_to_chat(contact_name, is_group)


@tool
def whatsapp_read_messages(
    contact_name: str,
    limit: int = 20,
    is_group: bool = False
) -> Dict[str, Any]:
    """
    Read recent messages from a WhatsApp chat or group.
    
    Args:
        contact_name: Name of contact or group
        limit: Maximum number of messages to return (most recent, default: 20)
        is_group: Whether this is a group chat (default: False)
    """
    logger.info(f"[WHATSAPP AGENT] Tool: whatsapp_read_messages(contact='{contact_name}', limit={limit}, is_group={is_group})")
    try:
        controller = _get_controller()
    except ConfigValidationError as exc:
        return {
            "error": True,
            "error_type": "ConfigurationError",
            "error_message": str(exc),
            "retry_possible": False,
        }
    return controller.read_messages(contact_name, limit=limit, is_group=is_group)


@tool
def whatsapp_read_messages_from_sender(
    contact_name: str,
    sender_name: str,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Read messages from a specific sender within a group chat.
    
    Args:
        contact_name: Name of the group
        sender_name: Name of the sender to filter by
        limit: Maximum number of messages to return (default: 20)
    """
    logger.info(f"[WHATSAPP AGENT] Tool: whatsapp_read_messages_from_sender(contact='{contact_name}', sender='{sender_name}', limit={limit})")
    try:
        controller = _get_controller()
    except ConfigValidationError as exc:
        return {
            "error": True,
            "error_type": "ConfigurationError",
            "error_message": str(exc),
            "retry_possible": False,
        }
    return controller.read_messages_from_sender(contact_name, sender_name, limit=limit, is_group=True)


@tool
def whatsapp_read_group_messages(
    group_name: str,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Read recent messages from a WhatsApp group.
    
    Args:
        group_name: Name of the group
        limit: Maximum number of messages to return (most recent, default: 20)
    """
    logger.info(f"[WHATSAPP AGENT] Tool: whatsapp_read_group_messages(group='{group_name}', limit={limit})")
    try:
        controller = _get_controller()
    except ConfigValidationError as exc:
        return {
            "error": True,
            "error_type": "ConfigurationError",
            "error_message": str(exc),
            "retry_possible": False,
        }
    return controller.read_messages(group_name, limit=limit, is_group=True)


@tool
def whatsapp_detect_unread() -> Dict[str, Any]:
    """
    Detect chats/groups with unread messages.
    
    Returns a list of chats that have unread indicators.
    """
    logger.info("[WHATSAPP AGENT] Tool: whatsapp_detect_unread()")
    try:
        controller = _get_controller()
    except ConfigValidationError as exc:
        return {
            "error": True,
            "error_type": "ConfigurationError",
            "error_message": str(exc),
            "retry_possible": False,
        }
    return controller.detect_unread_chats()


@tool
def whatsapp_list_chats() -> Dict[str, Any]:
    """
    List all available chats and groups in WhatsApp.
    
    Returns a list of all chats/groups visible in the chat list.
    """
    logger.info("[WHATSAPP AGENT] Tool: whatsapp_list_chats()")
    try:
        controller = _get_controller()
    except ConfigValidationError as exc:
        return {
            "error": True,
            "error_type": "ConfigurationError",
            "error_message": str(exc),
            "retry_possible": False,
        }
    return controller.get_chat_list()


@tool
def whatsapp_summarize_messages(
    contact_name: str,
    is_group: bool = False,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Read and summarize messages from a WhatsApp chat or group using AI.
    
    Args:
        contact_name: Name of contact or group
        is_group: Whether this is a group chat (default: False)
        limit: Maximum number of messages to read before summarizing (default: 50)
    """
    logger.info(f"[WHATSAPP AGENT] Tool: whatsapp_summarize_messages(contact='{contact_name}', is_group={is_group}, limit={limit})")
    
    try:
        config, _, _ = _load_whatsapp_runtime()
    except ConfigValidationError as exc:
        return {
            "error": True,
            "error_type": "ConfigurationError",
            "error_message": str(exc),
            "retry_possible": False,
        }
    
    try:
        controller = _get_controller()
    except ConfigValidationError as exc:
        return {
            "error": True,
            "error_type": "ConfigurationError",
            "error_message": str(exc),
            "retry_possible": False,
        }
    read_result = controller.read_messages(contact_name, limit=limit, is_group=is_group)
    
    if read_result.get("error"):
        return read_result
    
    messages = read_result.get("messages", [])
    if not messages:
        return {
            "success": True,
            "contact": contact_name,
            "is_group": is_group,
            "summary": "No messages found to summarize.",
            "messages_count": 0,
        }
    
    summary = _summarize_messages_with_llm(config, messages, contact_name, is_group)
    
    return {
        "success": True,
        "contact": contact_name,
        "is_group": is_group,
        "summary": summary,
        "messages_count": len(messages),
        "messages_preview": messages[:5],  # Show first 5 as preview
    }


@tool
def whatsapp_extract_action_items(
    contact_name: str,
    is_group: bool = False,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Read messages and extract action items/tasks using AI.
    
    Args:
        contact_name: Name of contact or group
        is_group: Whether this is a group chat (default: False)
        limit: Maximum number of messages to read before extracting (default: 50)
    """
    logger.info(f"[WHATSAPP AGENT] Tool: whatsapp_extract_action_items(contact='{contact_name}', is_group={is_group}, limit={limit})")
    
    try:
        config, _, _ = _load_whatsapp_runtime()
    except ConfigValidationError as exc:
        return {
            "error": True,
            "error_type": "ConfigurationError",
            "error_message": str(exc),
            "retry_possible": False,
        }
    
    try:
        controller = _get_controller()
    except ConfigValidationError as exc:
        return {
            "error": True,
            "error_type": "ConfigurationError",
            "error_message": str(exc),
            "retry_possible": False,
        }
    read_result = controller.read_messages(contact_name, limit=limit, is_group=is_group)
    
    if read_result.get("error"):
        return read_result
    
    messages = read_result.get("messages", [])
    if not messages:
        return {
            "success": True,
            "contact": contact_name,
            "is_group": is_group,
            "action_items": [],
            "messages_count": 0,
        }
    
    action_items = _extract_action_items_with_llm(config, messages, contact_name)
    
    return {
        "success": True,
        "contact": contact_name,
        "is_group": is_group,
        "action_items": action_items,
        "messages_count": len(messages),
        "messages_preview": messages[:5],  # Show first 5 as preview
    }


WHATSAPP_AGENT_TOOLS = [
    whatsapp_ensure_session,
    whatsapp_navigate_to_chat,
    whatsapp_read_messages,
    whatsapp_read_messages_from_sender,
    whatsapp_read_group_messages,
    whatsapp_detect_unread,
    whatsapp_list_chats,
    whatsapp_summarize_messages,
    whatsapp_extract_action_items,
]


WHATSAPP_AGENT_HIERARCHY = """
WhatsApp Agent Hierarchy:
========================
Domain: WhatsApp message reading and analysis

LEVEL 1: Session + Navigation
└─ whatsapp_ensure_session() → Verify WhatsApp is running and logged in
└─ whatsapp_navigate_to_chat(contact_name, is_group?) → Navigate to specific chat/group
└─ whatsapp_list_chats() → List all available chats/groups

LEVEL 2: Message Reading
└─ whatsapp_read_messages(contact_name, limit?, is_group?) → Read recent messages
└─ whatsapp_read_group_messages(group_name, limit?) → Read messages from a group
└─ whatsapp_read_messages_from_sender(contact_name, sender_name, limit?) → Filter by sender in groups
└─ whatsapp_detect_unread() → Find chats with unread messages

LEVEL 3: AI-Powered Analysis
└─ whatsapp_summarize_messages(contact_name, is_group?, limit?) → AI summary of conversation
└─ whatsapp_extract_action_items(contact_name, is_group?, limit?) → Extract tasks/action items

Integration: Uses macOS UI automation (AppleScript/System Events) to interact with WhatsApp Desktop.
Similar to Discord agent pattern but focused on reading (no sending).
"""


class WhatsAppAgent:
    """
    WhatsApp Agent - Mini-orchestrator that exposes WhatsApp UI automation as LangChain tools.
    
    Focuses on reading messages and providing AI-powered analysis (summarization, action items).
    Does not support sending messages (as per requirements).
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in WHATSAPP_AGENT_TOOLS}
        logger.info(f"[WHATSAPP AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all WhatsApp agent tools."""
        return WHATSAPP_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get WhatsApp agent hierarchy documentation."""
        return WHATSAPP_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a WhatsApp agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"WhatsApp agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[WHATSAPP AGENT] Executing tool: {tool_name}")

        try:
            return tool.invoke(inputs)
        except Exception as exc:
            logger.exception("WhatsApp agent execution error")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(exc),
                "retry_possible": False
            }
