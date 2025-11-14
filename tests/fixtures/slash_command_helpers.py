"""
Reusable helpers for slash command testing.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from typing import Dict, Any, Optional, Tuple
from src.ui.slash_commands import SlashCommandParser, SlashCommandHandler
from src.agent.agent_registry import AgentRegistry
from src.utils import load_config
from src.memory import SessionManager


def create_slash_handler(session_manager=None, config=None):
    """Create a SlashCommandHandler instance for testing."""
    if config is None:
        config = load_config()
    
    registry = AgentRegistry(config, session_manager=session_manager)
    handler = SlashCommandHandler(registry, session_manager=session_manager, config=config)
    return handler


def invoke_slash_command(handler: SlashCommandHandler, command: str, session_id: Optional[str] = None) -> Tuple[bool, Any]:
    """
    Invoke a slash command and return (is_command, result).
    
    Args:
        handler: SlashCommandHandler instance
        command: Command string (e.g., "/email read my emails")
        session_id: Optional session ID
        
    Returns:
        Tuple of (is_command, result)
    """
    return handler.handle(command, session_id=session_id)


def parse_slash_command(command: str) -> Optional[Dict[str, Any]]:
    """
    Parse a slash command string.
    
    Args:
        command: Command string (e.g., "/email read my emails")
        
    Returns:
        Parsed command dict or None if not a command
    """
    parser = SlashCommandParser()
    return parser.parse(command)


def get_supported_commands() -> list[str]:
    """Get list of supported slash commands."""
    parser = SlashCommandParser()
    return list(parser.COMMAND_MAP.keys())


def is_supported_command(command: str) -> bool:
    """
    Check if a command is supported.
    
    Args:
        command: Command name without slash (e.g., "email", "maps")
        
    Returns:
        True if command is supported, False otherwise
    """
    parser = SlashCommandParser()
    return command.lower() in parser.COMMAND_MAP


def get_usage_metrics(handler: SlashCommandHandler) -> Dict[str, int]:
    """Get usage metrics from handler."""
    return dict(handler._usage_metrics)

