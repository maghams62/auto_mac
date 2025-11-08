"""Agent module - Multi-agent system with hierarchical specialization."""

# Import individual agents
from .file_agent import FileAgent, FILE_AGENT_TOOLS
from .browser_agent import BrowserAgent, BROWSER_AGENT_TOOLS, BROWSER_TOOLS  # BROWSER_TOOLS for compatibility
from .presentation_agent import PresentationAgent, PRESENTATION_AGENT_TOOLS
from .email_agent import EmailAgent, EMAIL_AGENT_TOOLS
from .writing_agent import WritingAgent, WRITING_AGENT_TOOLS
from .critic_agent import CriticAgent, CRITIC_AGENT_TOOLS
from .stock_agent import STOCK_AGENT_TOOLS
from .screen_agent import SCREEN_AGENT_TOOLS

# Import registry
from .agent_registry import (
    AgentRegistry,
    ALL_AGENT_TOOLS,
    ALL_TOOLS,  # Legacy compatibility
    AGENT_HIERARCHY_DOCS,
    get_agent_tool_mapping,
    print_agent_hierarchy
)

# Import main agent (legacy)
from .agent import AutomationAgent

__all__ = [
    # Individual agents
    "FileAgent",
    "BrowserAgent",
    "PresentationAgent",
    "EmailAgent",
    "WritingAgent",
    "CriticAgent",

    # Agent registry
    "AgentRegistry",

    # Tool collections
    "FILE_AGENT_TOOLS",
    "BROWSER_AGENT_TOOLS",
    "PRESENTATION_AGENT_TOOLS",
    "EMAIL_AGENT_TOOLS",
    "WRITING_AGENT_TOOLS",
    "CRITIC_AGENT_TOOLS",
    "STOCK_AGENT_TOOLS",
    "SCREEN_AGENT_TOOLS",
    "ALL_AGENT_TOOLS",

    # Legacy compatibility
    "ALL_TOOLS",
    "BROWSER_TOOLS",
    "AutomationAgent",

    # Utilities
    "AGENT_HIERARCHY_DOCS",
    "get_agent_tool_mapping",
    "print_agent_hierarchy",
]
