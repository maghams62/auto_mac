"""Agent module - Multi-agent system with hierarchical specialization."""

# Import individual agents
from .file_agent import FileAgent, FILE_AGENT_TOOLS
from .folder_agent import FolderAgent, FOLDER_AGENT_TOOLS
from .google_agent import GoogleAgent, GOOGLE_AGENT_TOOLS
from .browser_agent import BrowserAgent, BROWSER_AGENT_TOOLS, BROWSER_TOOLS  # BROWSER_TOOLS for compatibility
from .presentation_agent import PresentationAgent, PRESENTATION_AGENT_TOOLS
from .email_agent import EmailAgent, EMAIL_AGENT_TOOLS
from .writing_agent import WritingAgent, WRITING_AGENT_TOOLS
from .critic_agent import CriticAgent, CRITIC_AGENT_TOOLS
# Optional imports for agents with external dependencies
try:
    from .stock_agent import STOCK_AGENT_TOOLS
except ImportError:
    STOCK_AGENT_TOOLS = []
try:
    from .screen_agent import SCREEN_AGENT_TOOLS
except ImportError:
    SCREEN_AGENT_TOOLS = []
from .twitter_agent import TwitterAgent, TWITTER_AGENT_TOOLS
from .bluesky_agent import BlueskyAgent, BLUESKY_AGENT_TOOLS
from .notifications_agent import NotificationsAgent, NOTIFICATIONS_AGENT_TOOLS
from .vision_agent import VisionAgent, VISION_AGENT_TOOLS
from .reply_tool import ReplyAgent, REPLY_AGENT_TOOLS, REPLY_AGENT_HIERARCHY
from .spotify_agent import SpotifyAgent, SPOTIFY_AGENT_TOOLS, SPOTIFY_AGENT_HIERARCHY

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
    "FolderAgent",
    "GoogleAgent",
    "BrowserAgent",
    "PresentationAgent",
    "EmailAgent",
    "WritingAgent",
    "CriticAgent",
    "TwitterAgent",
    "BlueskyAgent",
    "NotificationsAgent",
    "VisionAgent",
    "ReplyAgent",
    "SpotifyAgent",

    # Agent registry
    "AgentRegistry",

    # Tool collections
    "FILE_AGENT_TOOLS",
    "FOLDER_AGENT_TOOLS",
    "GOOGLE_AGENT_TOOLS",
    "BROWSER_AGENT_TOOLS",
    "PRESENTATION_AGENT_TOOLS",
    "EMAIL_AGENT_TOOLS",
    "WRITING_AGENT_TOOLS",
    "CRITIC_AGENT_TOOLS",
    "TWITTER_AGENT_TOOLS",
    "BLUESKY_AGENT_TOOLS",
    "NOTIFICATIONS_AGENT_TOOLS",
    "VISION_AGENT_TOOLS",
    "REPLY_AGENT_TOOLS",
    "SPOTIFY_AGENT_TOOLS",
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
    "REPLY_AGENT_HIERARCHY",
]
