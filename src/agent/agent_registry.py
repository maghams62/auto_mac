"""
Agent Registry - Central registry for all hierarchical agents.

This module provides a unified interface to all specialized agents:
- File Agent (document search, extraction, organization)
- Browser Agent (web search, navigation, content extraction)
- Presentation Agent (Keynote, Pages creation)
- Email Agent (email composition and sending)
- Critic Agent (verification, reflection, quality assurance)

Each agent acts as a mini-orchestrator for its domain.
"""

from typing import Dict, Any, List, Optional
import logging

from ..memory import SessionManager

from .file_agent import FileAgent, FILE_AGENT_TOOLS, FILE_AGENT_HIERARCHY
from .folder_agent import FolderAgent, FOLDER_AGENT_TOOLS, FOLDER_AGENT_HIERARCHY
from .google_agent import GoogleAgent, GOOGLE_AGENT_TOOLS, GOOGLE_AGENT_HIERARCHY
from .browser_agent import BrowserAgent, BROWSER_AGENT_TOOLS, BROWSER_AGENT_HIERARCHY
from .presentation_agent import PresentationAgent, PRESENTATION_AGENT_TOOLS, PRESENTATION_AGENT_HIERARCHY
from .email_agent import EmailAgent, EMAIL_AGENT_TOOLS, EMAIL_AGENT_HIERARCHY
from .critic_agent import CriticAgent, CRITIC_AGENT_TOOLS, CRITIC_AGENT_HIERARCHY
from .writing_agent import WritingAgent, WRITING_AGENT_TOOLS, WRITING_AGENT_HIERARCHY
# Optional imports for agents with external dependencies
try:
    from .stock_agent import STOCK_AGENT_TOOLS, STOCK_AGENT_HIERARCHY
except ImportError:
    STOCK_AGENT_TOOLS = []
    STOCK_AGENT_HIERARCHY = ""
try:
    from .screen_agent import SCREEN_AGENT_TOOLS, SCREEN_AGENT_HIERARCHY
except ImportError:
    SCREEN_AGENT_TOOLS = []
    SCREEN_AGENT_HIERARCHY = ""
from .report_agent import ReportAgent, REPORT_AGENT_TOOLS, REPORT_AGENT_HIERARCHY
from .google_finance_agent import GoogleFinanceAgent, GOOGLE_FINANCE_AGENT_TOOLS, GOOGLE_FINANCE_AGENT_HIERARCHY
from .enriched_stock_agent import EnrichedStockAgent, ENRICHED_STOCK_AGENT_TOOLS
from .maps_agent import MapsAgent, MAPS_AGENT_TOOLS, MAPS_AGENT_HIERARCHY
from .imessage_agent import iMessageAgent, IMESSAGE_AGENT_TOOLS, IMESSAGE_AGENT_HIERARCHY
from .discord_agent import DiscordAgent, DISCORD_AGENT_TOOLS, DISCORD_AGENT_HIERARCHY
from .reddit_agent import RedditAgent, REDDIT_AGENT_TOOLS, REDDIT_AGENT_HIERARCHY
from .twitter_agent import TwitterAgent, TWITTER_AGENT_TOOLS, TWITTER_AGENT_HIERARCHY
from .notifications_agent import NotificationsAgent, NOTIFICATIONS_AGENT_TOOLS, NOTIFICATIONS_AGENT_HIERARCHY
from .vision_agent import VisionAgent, VISION_AGENT_TOOLS, VISION_AGENT_HIERARCHY
from .micro_actions_agent import MicroActionsAgent, MICRO_ACTIONS_AGENT_TOOLS, MICRO_ACTIONS_AGENT_HIERARCHY
from .voice_agent import VoiceAgent, VOICE_AGENT_TOOLS, VOICE_AGENT_HIERARCHY
from .bluesky_agent import BlueskyAgent, BLUESKY_AGENT_TOOLS, BLUESKY_AGENT_HIERARCHY
from .whatsapp_agent import WhatsAppAgent, WHATSAPP_AGENT_TOOLS, WHATSAPP_AGENT_HIERARCHY
from .reply_tool import ReplyAgent, REPLY_AGENT_TOOLS, REPLY_AGENT_HIERARCHY
from .spotify_agent import SpotifyAgent, SPOTIFY_AGENT_TOOLS, SPOTIFY_AGENT_HIERARCHY
from .celebration_agent import CelebrationAgent, CELEBRATION_AGENT_TOOLS, CELEBRATION_AGENT_HIERARCHY
from .weather_agent import WEATHER_AGENT_TOOLS, WEATHER_AGENT_HIERARCHY
from .notes_agent import NOTES_AGENT_TOOLS, NOTES_AGENT_HIERARCHY
from .reminders_agent import REMINDERS_AGENT_TOOLS, REMINDERS_AGENT_HIERARCHY
from .calendar_agent import CalendarAgent, CALENDAR_AGENT_TOOLS, CALENDAR_AGENT_HIERARCHY

logger = logging.getLogger(__name__)


# Combined tool registry (for backwards compatibility)
ALL_AGENT_TOOLS = (
    FILE_AGENT_TOOLS +
    FOLDER_AGENT_TOOLS +
    GOOGLE_AGENT_TOOLS +
    BROWSER_AGENT_TOOLS +
    PRESENTATION_AGENT_TOOLS +
    EMAIL_AGENT_TOOLS +
    WRITING_AGENT_TOOLS +
    CRITIC_AGENT_TOOLS +
    STOCK_AGENT_TOOLS +
    SCREEN_AGENT_TOOLS +
    REPORT_AGENT_TOOLS +
    GOOGLE_FINANCE_AGENT_TOOLS +
    MAPS_AGENT_TOOLS +
    IMESSAGE_AGENT_TOOLS +
    DISCORD_AGENT_TOOLS +
    REDDIT_AGENT_TOOLS +
    TWITTER_AGENT_TOOLS +
    BLUESKY_AGENT_TOOLS +
    NOTIFICATIONS_AGENT_TOOLS +
    VISION_AGENT_TOOLS +
    MICRO_ACTIONS_AGENT_TOOLS +
    VOICE_AGENT_TOOLS +
    WHATSAPP_AGENT_TOOLS +
    REPLY_AGENT_TOOLS +
    SPOTIFY_AGENT_TOOLS +
    CELEBRATION_AGENT_TOOLS +
    WEATHER_AGENT_TOOLS +
    NOTES_AGENT_TOOLS +
    REMINDERS_AGENT_TOOLS +
    CALENDAR_AGENT_TOOLS
)
# Legacy compatibility
ALL_TOOLS = FILE_AGENT_TOOLS + PRESENTATION_AGENT_TOOLS + EMAIL_AGENT_TOOLS
BROWSER_TOOLS = BROWSER_AGENT_TOOLS


# Agent hierarchy documentation
AGENT_HIERARCHY_DOCS = """
Multi-Agent System Hierarchy:
=============================

The system is organized into specialized agents, each acting as a mini-orchestrator
for its domain:

1. FILE AGENT (5 tools)
   └─ Domain: Document and file operations
   └─ Tools: search_documents, extract_section, take_screenshot, organize_files, create_zip_archive

2. BROWSER AGENT (5 tools)
   └─ Domain: Web browsing and content extraction
   └─ Tools: google_search, navigate_to_url, extract_page_content, take_web_screenshot, close_browser

3. PRESENTATION AGENT (3 tools)
   └─ Domain: Presentation and document creation
   └─ Tools: create_keynote, create_keynote_with_images, create_pages_doc

4. EMAIL AGENT (6 tools)
   └─ Domain: Email operations
   └─ Tools: compose_email, reply_to_email, read_latest_emails, read_emails_by_sender, read_emails_by_time, summarize_emails

5. WRITING AGENT (4 tools)
   └─ Domain: Content synthesis and writing
   └─ Tools: synthesize_content, create_slide_deck_content, create_detailed_report, create_meeting_notes

6. CRITIC AGENT (4 tools)
   └─ Domain: Verification, reflection, and quality assurance
   └─ Tools: verify_output, reflect_on_failure, validate_plan, check_quality

7. TWITTER AGENT (1 tool)
   └─ Domain: Twitter list ingestion/summarization
   └─ Tools: summarize_list_activity

8. BLUESKY AGENT (3 tools)
   └─ Domain: Bluesky social discovery, summaries, and posting
   └─ Tools: search_bluesky_posts, summarize_bluesky_posts, post_bluesky_update

9. MAPS AGENT (2 tools)
   └─ Domain: Apple Maps trip planning and navigation
   └─ Tools: plan_trip_with_stops, open_maps_with_route
   └─ Integration: Uses AppleScript automation (MapsAutomation) for native macOS Maps.app control

10. MICRO ACTIONS AGENT (3 tools)
   └─ Domain: Lightweight everyday utilities
   └─ Tools: launch_app, copy_snippet, set_timer
   └─ Integration: Built on simple AppleScript/open calls for fast micro-actions

11. VISION AGENT (1 tool)
   └─ Domain: Vision-assisted UI disambiguation
   └─ Tools: analyze_ui_screenshot
   └─ Purpose: Inspect screenshots when scripted flows fail or become ambiguous

12. VOICE AGENT (2 tools)
   └─ Domain: Speech-to-text and text-to-speech
   └─ Tools: transcribe_audio_file, text_to_speech
   └─ Integration: Uses OpenAI Whisper API for STT and OpenAI TTS API for speech generation

13. WHATSAPP AGENT (9 tools)
   └─ Domain: WhatsApp message reading and analysis
   └─ Tools: whatsapp_ensure_session, whatsapp_navigate_to_chat, whatsapp_read_messages, whatsapp_read_messages_from_sender, whatsapp_read_group_messages, whatsapp_detect_unread, whatsapp_list_chats, whatsapp_summarize_messages, whatsapp_extract_action_items
   └─ Integration: Uses macOS UI automation (AppleScript/System Events) for WhatsApp Desktop, similar to Discord agent pattern

14. REPLY AGENT (1 tool)
   └─ Domain: User communication
   └─ Tools: reply_to_user
   └─ Purpose: Centralizes UI-facing messaging so agents deliver polished summaries instead of raw JSON payloads

15. SPOTIFY AGENT (4 tools)
   └─ Domain: Music playback control
   └─ Tools: play_music, pause_music, get_spotify_status, play_song
   └─ Integration: Uses AppleScript to control Spotify desktop app on macOS
   └─ Features: LLM-powered semantic song name disambiguation for fuzzy/imprecise song names

16. CELEBRATION AGENT (1 tool)
   └─ Domain: Celebratory effects and fun interactions
   └─ Tools: trigger_confetti
   └─ Integration: Uses AppleScript to trigger macOS celebration effects

17. WEATHER AGENT (1 tool)
   └─ Domain: Weather forecast retrieval and conditional logic
   └─ Tools: get_weather_forecast
   └─ Integration: Uses macOS Weather.app via AppleScript/System Events
   └─ Pattern: Returns structured data → LLM interprets → Conditional actions (reminders/notes)

18. NOTES AGENT (3 tools)
   └─ Domain: Apple Notes creation and management
   └─ Tools: create_note, append_note, get_note
   └─ Integration: Uses macOS Notes.app via AppleScript
   └─ Pattern: Persistent storage for LLM-generated content, reports, and summaries

19. REMINDERS AGENT (2 tools)
   └─ Domain: Time-based reminders and task management
   └─ Tools: create_reminder, complete_reminder
   └─ Integration: Uses macOS Reminders.app via AppleScript
   └─ Pattern: LLM-inferred timing from natural language, conditional reminder creation

20. CALENDAR AGENT (3 tools)
   └─ Domain: Calendar event reading and meeting preparation
   └─ Tools: list_calendar_events, get_calendar_event_details, prepare_meeting_brief
   └─ Integration: Uses Calendar.app via AppleScript, DocumentIndexer for semantic search
   └─ Pattern: Reads events → LLM generates search queries → Searches documents → Synthesizes briefs

Additional agents are wired for iMessage, Discord, Reddit, Stock, Screen, Report, etc., bringing the total to 65+ tools (and growing).

Each agent:
- Has a clear domain of responsibility
- Acts as a mini-orchestrator for its tools
- Provides hierarchical tool organization
- Implements atomic operations within its domain
- Can be used independently or coordinated by main orchestrator
"""


class AgentRegistry:
    """
    Central registry for all specialized agents.

    Provides unified access to:
    - File operations (FileAgent)
    - Web browsing (BrowserAgent)
    - Presentations (PresentationAgent)
    - Email (EmailAgent)
    - Content writing (WritingAgent)
    - Verification (CriticAgent)
    """

    def __init__(
        self,
        config: Dict[str, Any],
        session_manager: Optional[SessionManager] = None
    ):
        self.config = config

        # Session management
        self.session_manager = session_manager
        if self.session_manager:
            logger.info("[AGENT REGISTRY] Session management enabled")

        # Agent class registry
        # These will be eagerly instantiated at the end of __init__
        self._agent_classes = {
            "file": FileAgent,
            "folder": FolderAgent,
            "google": GoogleAgent,
            "browser": BrowserAgent,
            "presentation": PresentationAgent,
            "email": EmailAgent,
            "writing": WritingAgent,
            "critic": CriticAgent,
            "report": ReportAgent,
            "google_finance": GoogleFinanceAgent,
            "enriched_stock": EnrichedStockAgent,
            "maps": MapsAgent,
            "imessage": iMessageAgent,
            "discord": DiscordAgent,
            "reddit": RedditAgent,
            "twitter": TwitterAgent,
            "notifications": NotificationsAgent,
            "micro_actions": MicroActionsAgent,
            "voice": VoiceAgent,
            "vision": VisionAgent,
            "bluesky": BlueskyAgent,
            "whatsapp": WhatsAppAgent,
            "reply": ReplyAgent,
            "spotify": SpotifyAgent,
            "celebration": CelebrationAgent,
            "calendar": CalendarAgent,
        }

        # Registry of instantiated agents (populated during eager initialization)
        self.agents = {}

        # Create tool-to-agent mapping (using tool lists, not instances)
        self.tool_to_agent = {}
        tool_lists = {
            "file": FILE_AGENT_TOOLS,
            "folder": FOLDER_AGENT_TOOLS,
            "google": GOOGLE_AGENT_TOOLS,
            "browser": BROWSER_AGENT_TOOLS,
            "presentation": PRESENTATION_AGENT_TOOLS,
            "email": EMAIL_AGENT_TOOLS,
            "writing": WRITING_AGENT_TOOLS,
            "critic": CRITIC_AGENT_TOOLS,
            "report": REPORT_AGENT_TOOLS,
            "google_finance": GOOGLE_FINANCE_AGENT_TOOLS,
            "maps": MAPS_AGENT_TOOLS,
            "imessage": IMESSAGE_AGENT_TOOLS,
            "discord": DISCORD_AGENT_TOOLS,
            "reddit": REDDIT_AGENT_TOOLS,
            "twitter": TWITTER_AGENT_TOOLS,
            "notifications": NOTIFICATIONS_AGENT_TOOLS,
            "micro_actions": MICRO_ACTIONS_AGENT_TOOLS,
            "voice": VOICE_AGENT_TOOLS,
            "vision": VISION_AGENT_TOOLS,
            "bluesky": BLUESKY_AGENT_TOOLS,
            "whatsapp": WHATSAPP_AGENT_TOOLS,
            "reply": REPLY_AGENT_TOOLS,
            "spotify": SPOTIFY_AGENT_TOOLS,
            "celebration": CELEBRATION_AGENT_TOOLS,
            "calendar": CALENDAR_AGENT_TOOLS,
        }

        for agent_name, tools in tool_lists.items():
            for tool in tools:
                self.tool_to_agent[tool.name] = agent_name

        # EAGER INITIALIZATION: Instantiate all agents at startup
        # This ensures atomic, predictable behavior and prevents lazy loading issues
        logger.info(f"[AGENT REGISTRY] Eagerly initializing {len(self._agent_classes)} agents...")
        for agent_name, agent_class in self._agent_classes.items():
            try:
                self.agents[agent_name] = agent_class(self.config)
                logger.debug(f"[AGENT REGISTRY] ✓ Initialized {agent_name} agent")
            except Exception as e:
                logger.error(f"[AGENT REGISTRY] ✗ Failed to initialize {agent_name} agent: {e}")
                # Continue with other agents even if one fails

        logger.info(f"[AGENT REGISTRY] Initialized {len(self.agents)}/{len(self._agent_classes)} agents with {len(self.tool_to_agent)} tools (eager loading enabled)")

    def get_agent(self, agent_name: str):
        """
        Get a specific agent by name.

        All agents are eagerly initialized at startup, so this is a simple lookup.
        """
        if agent_name in self.agents:
            return self.agents[agent_name]

        logger.warning(f"[AGENT REGISTRY] Unknown agent: {agent_name}")
        return None

    def get_agent_for_tool(self, tool_name: str):
        """Get the agent responsible for a specific tool."""
        agent_name = self.tool_to_agent.get(tool_name)
        if agent_name:
            return self.get_agent(agent_name)
        return None

    def initialize_agents(self, agent_names: List[str]) -> None:
        """
        Pre-initialize specific agents (called by intent planner).

        Note: With eager initialization enabled, all agents are already initialized
        at startup, so this method is now a no-op kept for backwards compatibility.

        Args:
            agent_names: List of agent names to initialize
        """
        # No-op: All agents are already eagerly initialized in __init__
        logger.debug(f"[AGENT REGISTRY] initialize_agents() called but agents already initialized (eager mode)")

    def get_all_tools(self) -> List:
        """Get all tools from all agents."""
        return ALL_AGENT_TOOLS

    def get_tools_by_agent(self, agent_name: str) -> List:
        """Get tools for a specific agent."""
        agent = self.get_agent(agent_name)
        if agent:
            return agent.get_tools()
        return []

    def get_hierarchy_docs(self) -> str:
        """Get complete hierarchy documentation."""
        docs = [AGENT_HIERARCHY_DOCS]

        docs.append("\n" + "=" * 80)
        docs.append("\nDETAILED AGENT HIERARCHIES:\n")
        docs.append("=" * 80)

        for agent_name, agent in self.agents.items():
            docs.append(f"\n{agent_name.upper()} AGENT:")
            docs.append(agent.get_hierarchy())

        return "\n".join(docs)

    def execute_tool(
        self,
        tool_name: str,
        inputs: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Route and execute a tool through its responsible agent.

        This is the main execution interface - tools are automatically routed
        to their owning agent.

        Args:
            tool_name: Name of tool to execute
            inputs: Tool input parameters
            session_id: Optional session ID for context tracking
        """
        agent = self.get_agent_for_tool(tool_name)

        if not agent:
            logger.error(f"[AGENT REGISTRY] No agent found for tool: {tool_name}")
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Tool '{tool_name}' not found in any agent",
                "available_tools": list(self.tool_to_agent.keys())
            }

        # Route to agent
        agent_name = self.tool_to_agent[tool_name]
        logger.info(f"[AGENT REGISTRY] Routing {tool_name} to {agent_name} agent")

        # Track tool usage in session memory
        if self.session_manager and session_id:
            memory = self.session_manager.get_or_create_session(session_id)
            memory.metadata["tools_used"].add(tool_name)
            memory.metadata["agents_used"].add(agent_name)

        result = agent.execute(tool_name, inputs)

        # Ensure result is a dictionary (defensive programming)
        if not isinstance(result, dict):
            logger.warning(f"[AGENT REGISTRY] Tool {tool_name} returned non-dict result: {type(result)}")
            result = {"output": result, "error": False}

        # Store result in session context if needed
        if self.session_manager and session_id and not result.get("error"):
            memory = self.session_manager.get_or_create_session(session_id)
            # Store commonly referenced results (with defensive .get() calls)
            if tool_name == "take_screenshot":
                screenshot_path = result.get("screenshot_path")
                if not screenshot_path:
                    # Try alternative field name
                    screenshot_paths = result.get("screenshot_paths", [])
                    if isinstance(screenshot_paths, list) and len(screenshot_paths) > 0:
                        screenshot_path = screenshot_paths[0]
                if screenshot_path:
                    memory.set_context("last_screenshot_path", screenshot_path)
            elif tool_name == "create_keynote" or tool_name == "create_keynote_with_images":
                file_path = result.get("file_path") or result.get("keynote_path")
                if file_path:
                    memory.set_context("last_presentation_path", file_path)
            elif tool_name == "search_documents":
                documents = result.get("documents", [])
                if documents:
                    memory.set_context("last_search_results", documents)

        return result

    def get_agent_stats(self) -> Dict[str, Any]:
        """Get statistics about registered agents and tools."""
        return {
            "total_agents": len(self.agents),
            "total_tools": len(self.tool_to_agent),
            "agents": {
                agent_name: len(agent.get_tools())
                for agent_name, agent in self.agents.items()
            },
            "tool_distribution": {
                agent_name: [tool.name for tool in agent.get_tools()]
                for agent_name, agent in self.agents.items()
            }
        }


def get_agent_tool_mapping() -> Dict[str, str]:
    """
    Get a mapping of tool names to their owning agent.

    Returns:
        Dictionary mapping tool_name -> agent_name
    """
    mapping = {}

    for tool in FILE_AGENT_TOOLS:
        mapping[tool.name] = "file"

    for tool in FOLDER_AGENT_TOOLS:
        mapping[tool.name] = "folder"

    for tool in GOOGLE_AGENT_TOOLS:
        mapping[tool.name] = "google"

    for tool in BROWSER_AGENT_TOOLS:
        mapping[tool.name] = "browser"

    for tool in PRESENTATION_AGENT_TOOLS:
        mapping[tool.name] = "presentation"

    for tool in EMAIL_AGENT_TOOLS:
        mapping[tool.name] = "email"

    for tool in WRITING_AGENT_TOOLS:
        mapping[tool.name] = "writing"

    for tool in CRITIC_AGENT_TOOLS:
        mapping[tool.name] = "critic"

    for tool in REPORT_AGENT_TOOLS:
        mapping[tool.name] = "report"

    for tool in STOCK_AGENT_TOOLS:
        mapping[tool.name] = "stock"

    for tool in SCREEN_AGENT_TOOLS:
        mapping[tool.name] = "screen"

    for tool in GOOGLE_FINANCE_AGENT_TOOLS:
        mapping[tool.name] = "google_finance"

    for tool in MAPS_AGENT_TOOLS:
        mapping[tool.name] = "maps"

    for tool in IMESSAGE_AGENT_TOOLS:
        mapping[tool.name] = "imessage"

    for tool in DISCORD_AGENT_TOOLS:
        mapping[tool.name] = "discord"

    for tool in REDDIT_AGENT_TOOLS:
        mapping[tool.name] = "reddit"

    for tool in TWITTER_AGENT_TOOLS:
        mapping[tool.name] = "twitter"

    for tool in NOTIFICATIONS_AGENT_TOOLS:
        mapping[tool.name] = "notifications"

    for tool in MICRO_ACTIONS_AGENT_TOOLS:
        mapping[tool.name] = "micro_actions"

    for tool in VOICE_AGENT_TOOLS:
        mapping[tool.name] = "voice"

    return mapping


def print_agent_hierarchy():
    """Print the complete agent hierarchy for debugging."""
    print(AGENT_HIERARCHY_DOCS)
    print("\n" + "=" * 80)
    print("TOOL TO AGENT MAPPING:")
    print("=" * 80)

    mapping = get_agent_tool_mapping()
    for agent_name in ["file", "browser", "presentation", "email", "writing", "critic", "twitter"]:
        tools = [tool for tool, agent in mapping.items() if agent == agent_name]
        print(f"\n{agent_name.upper()} AGENT ({len(tools)} tools):")
        for tool in tools:
            print(f"  - {tool}")
