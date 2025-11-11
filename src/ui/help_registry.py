"""
Dynamic Help Registry System.

Auto-discovers agents, tools, and commands to provide comprehensive help.
Inspired by Raycast's command palette for discoverability.
"""

import logging
from typing import List, Dict, Optional, Any
from difflib import get_close_matches

from .help_models import HelpEntry, AgentHelp, CategoryInfo, ParameterInfo

logger = logging.getLogger(__name__)


# Category definitions with icons
CATEGORIES = {
    "files": CategoryInfo(
        name="files",
        display_name="File Operations",
        description="Search, organize, and manage local files",
        icon="📁"
    ),
    "web": CategoryInfo(
        name="web",
        display_name="Web & Search",
        description="Browse web, search Google, extract content",
        icon="🌐"
    ),
    "email": CategoryInfo(
        name="email",
        display_name="Email",
        description="Read, compose, and send emails",
        icon="📧"
    ),
    "communication": CategoryInfo(
        name="communication",
        display_name="Messaging",
        description="iMessage, Discord, Reddit, Twitter, Bluesky, WhatsApp",
        icon="💬"
    ),
    "productivity": CategoryInfo(
        name="productivity",
        display_name="Productivity",
        description="Presentations, documents, notes, writing",
        icon="📊"
    ),
    "finance": CategoryInfo(
        name="finance",
        display_name="Finance",
        description="Stock prices, charts, financial reports",
        icon="💰"
    ),
    "maps": CategoryInfo(
        name="maps",
        display_name="Maps & Navigation",
        description="Plan trips, get directions, navigate",
        icon="🗺️"
    ),
    "system": CategoryInfo(
        name="system",
        display_name="System & Utilities",
        description="Notifications, app launching, timers, voice",
        icon="⚙️"
    )
}


class HelpRegistry:
    """
    Central registry for all help information.

    Auto-discovers agents, tools, and commands from the agent registry
    and provides search, filter, and suggestion capabilities.
    """

    def __init__(self, agent_registry=None):
        """
        Initialize help registry.

        Args:
            agent_registry: Optional AgentRegistry instance for dynamic discovery
        """
        self.agent_registry = agent_registry
        self.entries: Dict[str, HelpEntry] = {}
        self.agents: Dict[str, AgentHelp] = {}
        self.categories: Dict[str, CategoryInfo] = CATEGORIES.copy()

        # Build help database
        self._build_slash_commands()
        if agent_registry:
            self._discover_agents()

        logger.info(f"[HELP REGISTRY] Initialized with {len(self.entries)} entries and {len(self.agents)} agents")

    def _build_slash_commands(self):
        """Build help entries for all slash commands."""

        # File Operations
        self.entries["/files"] = HelpEntry(
            name="/files",
            type="slash_command",
            category="files",
            description="File operations - search, organize, manage files",
            long_description="Talk directly to the File Agent for document search, file organization, screenshots, and archiving.",
            examples=[
                "/files Find documents about AI",
                "/files Organize my PDFs by topic",
                "/files Create a ZIP archive of all images",
                "/files Take a screenshot"
            ],
            tags=["file", "document", "search", "organize", "zip", "screenshot"],
            related=["/folder", "/organize"],
            agent="file",
            icon="📁",
            level="basic"
        )

        self.entries["/folder"] = HelpEntry(
            name="/folder",
            type="slash_command",
            category="files",
            description="Folder operations - create, list, manage folders",
            long_description="Manage folders with the Folder Agent - create directories, list contents, and organize folder structures.",
            examples=[
                "/folder Create a new folder called Projects",
                "/folder List all folders in Documents",
                "/folder Show me the contents of ~/Downloads"
            ],
            tags=["folder", "directory", "create", "list"],
            related=["/files", "/organize"],
            agent="folder",
            icon="📂",
            level="basic"
        )

        self.entries["/organize"] = HelpEntry(
            name="/organize",
            type="slash_command",
            category="files",
            description="Organize files using LLM categorization",
            long_description="Automatically organize files into folders using AI-powered categorization. Great for cleaning up messy directories.",
            examples=[
                "/organize Organize my Downloads folder",
                "/organize Sort PDFs by topic",
                "/organize Clean up my Desktop"
            ],
            tags=["organize", "categorize", "clean", "sort"],
            related=["/files", "/folder"],
            agent="file",
            icon="🗂️",
            level="basic"
        )

        # Web Operations
        self.entries["/browse"] = HelpEntry(
            name="/browse",
            type="slash_command",
            category="web",
            description="Web browsing - navigate, extract content, screenshots",
            long_description="Use the Browser Agent to navigate websites, extract content, take web screenshots, and automate web tasks.",
            examples=[
                "/browse Go to github.com",
                "/browse Extract the main content from techcrunch.com",
                "/browse Take a screenshot of nytimes.com",
                "/browse Search for Python tutorials"
            ],
            tags=["browse", "web", "navigate", "extract", "screenshot"],
            related=["/google", "/search"],
            agent="browser",
            icon="🌐",
            level="basic"
        )

        self.entries["/google"] = HelpEntry(
            name="/google",
            type="slash_command",
            category="web",
            description="DuckDuckGo search (legacy /google alias) - find information on the web",
            long_description="Perform a DuckDuckGo web search and receive structured results with titles, URLs, and snippets. The command retains the historical /google alias for backwards compatibility.",
            examples=[
                "/google Search for Claude AI assistant",
                "/google Find Python documentation",
                "/google Look up Mac automation tools"
            ],
            tags=["duckduckgo", "search", "web", "find"],
            related=["/browse", "/search"],
            agent="google",
            icon="🔍",
            level="basic"
        )

        self.entries["/search"] = HelpEntry(
            name="/search",
            type="slash_command",
            category="files",
            description="Semantic document search using embeddings",
            long_description="Search your local documents using AI-powered semantic search. Understands meaning, not just keywords.",
            examples=[
                "/search Find documents about machine learning",
                "/search Look for financial reports",
                "/search Search for meeting notes from last week"
            ],
            tags=["search", "semantic", "documents", "find", "embeddings"],
            related=["/files"],
            agent="file",
            icon="🔎",
            level="intermediate"
        )

        # Presentations & Documents
        self.entries["/present"] = HelpEntry(
            name="/present",
            type="slash_command",
            category="productivity",
            description="Create presentations and documents (Keynote/Pages)",
            long_description="Create beautiful Keynote presentations or Pages documents with AI-generated content.",
            examples=[
                "/present Create a presentation about AI",
                "/present Make a Keynote deck on climate change",
                "/present Create a Pages document with quarterly report"
            ],
            tags=["presentation", "keynote", "pages", "document", "create"],
            related=["/write"],
            agent="presentation",
            icon="📊",
            level="basic"
        )

        # Email
        self.entries["/email"] = HelpEntry(
            name="/email",
            type="slash_command",
            category="email",
            description="Email operations - read, compose, reply, summarize",
            long_description="Manage your emails with Mail.app integration. Read, compose, reply, and get AI summaries of your inbox.",
            examples=[
                "/email Read my latest 5 emails",
                "/email Show emails from john@example.com",
                "/email Summarize emails from the past hour",
                "/email Reply to John's email saying thanks",
                "/email Compose an email to Sarah about the meeting"
            ],
            tags=["email", "mail", "read", "compose", "reply", "summarize"],
            related=[],
            agent="email",
            icon="📧",
            level="basic"
        )

        # Writing
        self.entries["/write"] = HelpEntry(
            name="/write",
            type="slash_command",
            category="productivity",
            description="AI writing assistant - content synthesis, reports, notes",
            long_description="Generate written content using AI. Create reports, meeting notes, summaries, and more.",
            examples=[
                "/write Create a report on AI trends",
                "/write Synthesize content from my research",
                "/write Generate meeting notes",
                "/write Create detailed documentation"
            ],
            tags=["write", "writing", "content", "generate", "ai"],
            related=["/present"],
            agent="writing",
            icon="✍️",
            level="basic"
        )

        # Maps
        self.entries["/maps"] = HelpEntry(
            name="/maps",
            type="slash_command",
            category="maps",
            description="Apple Maps integration - plan trips, navigate, directions",
            long_description="Use Apple Maps to plan trips with multiple stops, get directions, and navigate.",
            examples=[
                "/maps Plan a trip from SF to LA with stops",
                "/maps Navigate to the nearest coffee shop",
                "/maps Get directions to 123 Main St"
            ],
            tags=["maps", "navigation", "trip", "directions", "route"],
            related=[],
            agent="maps",
            icon="🗺️",
            level="basic"
        )

        # Finance
        self.entries["/stock"] = HelpEntry(
            name="/stock",
            type="slash_command",
            category="finance",
            description="Stock prices, charts, and financial data",
            long_description="Get real-time stock prices, historical charts, and compare multiple stocks.",
            examples=[
                "/stock Get the price of AAPL",
                "/stock Show me Tesla's stock chart",
                "/stock Compare AAPL and MSFT"
            ],
            tags=["stock", "finance", "price", "chart", "market"],
            related=["/report"],
            agent="stock",
            icon="📈",
            level="basic"
        )

        self.entries["/report"] = HelpEntry(
            name="/report",
            type="slash_command",
            category="finance",
            description="Generate financial reports and analysis",
            long_description="Create comprehensive financial reports with stock analysis, charts, and insights.",
            examples=[
                "/report Create a stock report for AAPL",
                "/report Generate quarterly analysis",
                "/report Make a portfolio performance report"
            ],
            tags=["report", "finance", "analysis", "stock"],
            related=["/stock"],
            agent="report",
            icon="📊",
            level="intermediate"
        )

        # Messaging
        self.entries["/message"] = HelpEntry(
            name="/message",
            type="slash_command",
            category="communication",
            description="iMessage integration - send messages",
            long_description="Send iMessages to contacts using Messages.app.",
            examples=[
                "/message Send 'Hello' to John",
                "/message Text Sarah about the meeting"
            ],
            tags=["message", "imessage", "text", "send"],
            related=["/discord", "/twitter"],
            agent="imessage",
            icon="💬",
            level="basic"
        )

        self.entries["/discord"] = HelpEntry(
            name="/discord",
            type="slash_command",
            category="communication",
            description="Discord integration - read and send messages",
            long_description="Read Discord channels and send messages using Discord desktop app.",
            examples=[
                "/discord Read latest messages from #general",
                "/discord Send a message to #announcements"
            ],
            tags=["discord", "chat", "message", "send", "read"],
            related=["/message", "/reddit"],
            agent="discord",
            icon="💬",
            level="intermediate"
        )

        self.entries["/reddit"] = HelpEntry(
            name="/reddit",
            type="slash_command",
            category="communication",
            description="Reddit integration - browse posts and subreddits",
            long_description="Search Reddit, read posts, and browse subreddits.",
            examples=[
                "/reddit Show top posts from r/python",
                "/reddit Search for AI discussions"
            ],
            tags=["reddit", "social", "posts", "subreddit"],
            related=["/twitter", "/bluesky"],
            agent="reddit",
            icon="🤖",
            level="basic"
        )

        self.entries["/twitter"] = HelpEntry(
            name="/twitter",
            type="slash_command",
            category="communication",
            description="Twitter/X integration - read Twitter lists",
            long_description="Summarize activity from your Twitter lists.",
            examples=[
                "/twitter Summarize my Tech list",
                "/twitter Show recent activity from AI researchers"
            ],
            tags=["twitter", "x", "social", "list", "summarize"],
            related=["/bluesky", "/reddit"],
            agent="twitter",
            icon="🐦",
            level="intermediate"
        )

        self.entries["/bluesky"] = HelpEntry(
            name="/bluesky",
            type="slash_command",
            category="communication",
            description="Bluesky integration - search, summarize, post",
            long_description="Search Bluesky posts, get summaries, and publish updates.",
            examples=[
                "/bluesky Search for posts about AI",
                "/bluesky Summarize recent posts about Python",
                "/bluesky Post an update about my project"
            ],
            tags=["bluesky", "social", "search", "post", "summarize"],
            related=["/twitter", "/reddit"],
            agent="bluesky",
            icon="🦋",
            level="basic"
        )

        # System & Utilities
        self.entries["/notify"] = HelpEntry(
            name="/notify",
            type="slash_command",
            category="system",
            description="Send macOS notifications",
            long_description="Create system notifications with custom titles and messages.",
            examples=[
                "/notify Remind me to take a break",
                "/notify Meeting in 10 minutes"
            ],
            tags=["notify", "notification", "alert", "reminder"],
            related=[],
            agent="notifications",
            icon="🔔",
            level="basic"
        )

        # Spotify
        self.entries["/spotify"] = HelpEntry(
            name="/spotify",
            type="slash_command",
            category="media",
            description="Control Spotify playback",
            long_description="Play and pause music in Spotify. Works with natural language commands like 'play music' or 'pause'.",
            examples=[
                "/spotify play",
                "/spotify pause",
                "/spotify play music",
                "/music pause"
            ],
            tags=["spotify", "music", "play", "pause", "playback"],
            related=[],
            agent="spotify",
            icon="🎵",
            level="basic"
        )

        # Celebration/Confetti
        self.entries["/confetti"] = HelpEntry(
            name="/confetti",
            type="slash_command",
            category="fun",
            description="Trigger celebratory confetti effects",
            long_description="Trigger celebratory confetti effects with emoji notification spam and voice announcement. Perfect for celebrating task completions!",
            examples=[
                "/confetti",
                "/celebrate",
                "/party"
            ],
            tags=["confetti", "celebrate", "party", "celebration", "fun"],
            related=[],
            agent="celebration",
            icon="🎉",
            level="basic"
        )

        # Meta commands
        self.entries["/help"] = HelpEntry(
            name="/help",
            type="slash_command",
            category="system",
            description="Show this help information",
            long_description="Display comprehensive help about all commands, agents, and tools. Supports search and filtering.",
            examples=[
                "/help",
                "/help files",
                "/help --category email",
                "/help search organize"
            ],
            tags=["help", "documentation", "commands", "guide"],
            related=["/agents"],
            icon="❓",
            level="basic"
        )

        self.entries["/agents"] = HelpEntry(
            name="/agents",
            type="slash_command",
            category="system",
            description="List all available agents and their capabilities",
            long_description="Show detailed information about all agents, their tools, and example usage.",
            examples=[
                "/agents",
                "/agents file",
                "/agents --verbose"
            ],
            tags=["agents", "tools", "capabilities", "list"],
            related=["/help"],
            icon="🤖",
            level="intermediate"
        )

        self.entries["/clear"] = HelpEntry(
            name="/clear",
            type="slash_command",
            category="system",
            description="Clear the conversation history",
            long_description="Reset the chat and start a new conversation.",
            examples=[
                "/clear"
            ],
            tags=["clear", "reset", "new", "clean"],
            related=[],
            icon="🧹",
            level="basic"
        )

        # Update category counts
        for entry in self.entries.values():
            if entry.category in self.categories:
                self.categories[entry.category].command_count += 1

    def _discover_agents(self):
        """Discover agents and their tools from agent registry."""
        if not self.agent_registry:
            return

        # Get agent-tool mapping
        for agent_name, agent_class in self.agent_registry._agent_classes.items():
            # Get agent instance (lazy load)
            agent = self.agent_registry.get_agent(agent_name)
            if not agent:
                continue

            # Get tools
            tools = agent.get_tools()

            # Map agent to category
            category = self._get_agent_category(agent_name)

            # Get agent hierarchy/description
            hierarchy = agent.get_hierarchy() if hasattr(agent, 'get_hierarchy') else ""

            # Create AgentHelp entry
            agent_help = AgentHelp(
                name=agent_name,
                display_name=self._format_agent_name(agent_name),
                description=self._extract_agent_description(hierarchy),
                category=category,
                icon=self._get_agent_icon(agent_name),
                tool_count=len(tools),
                tools=[],
                slash_commands=self._get_slash_commands_for_agent(agent_name),
                examples=[]
            )

            # Add tool help entries
            for tool in tools:
                tool_entry = self._create_tool_help_entry(tool, agent_name, category)
                agent_help.tools.append(tool_entry)
                # Also add to main entries
                self.entries[f"{agent_name}.{tool.name}"] = tool_entry

            self.agents[agent_name] = agent_help

            # Update category counts
            if category in self.categories:
                self.categories[category].agent_count += 1

    def _create_tool_help_entry(self, tool, agent_name: str, category: str) -> HelpEntry:
        """Create a HelpEntry from a LangChain tool."""
        # Extract parameters from tool schema
        parameters = []
        if hasattr(tool, 'args_schema') and tool.args_schema:
            schema = tool.args_schema
            if hasattr(schema, 'model_fields'):
                # Pydantic v2
                for field_name, field_info in schema.model_fields.items():
                    parameters.append(ParameterInfo(
                        name=field_name,
                        type=str(field_info.annotation),
                        description=field_info.description or "",
                        required=field_info.is_required()
                    ))
            elif hasattr(schema, '__fields__'):
                # Pydantic v1
                for field_name, field_info in schema.__fields__.items():
                    parameters.append(ParameterInfo(
                        name=field_name,
                        type=str(field_info.type_),
                        description=field_info.field_info.description or "",
                        required=field_info.required
                    ))

        return HelpEntry(
            name=tool.name,
            type="tool",
            category=category,
            description=tool.description or "",
            parameters=parameters,
            agent=agent_name,
            tags=[agent_name, tool.name, category],
            icon="🔧"
        )

    def _get_agent_category(self, agent_name: str) -> str:
        """Map agent name to category."""
        category_map = {
            "file": "files",
            "folder": "files",
            "google": "web",
            "browser": "web",
            "presentation": "productivity",
            "email": "email",
            "writing": "productivity",
            "maps": "maps",
            "stock": "finance",
            "report": "finance",
            "google_finance": "finance",
            "imessage": "communication",
            "discord": "communication",
            "reddit": "communication",
            "twitter": "communication",
            "bluesky": "communication",
            "whatsapp": "communication",
            "notifications": "system",
            "micro_actions": "system",
            "voice": "system",
            "celebration": "system",
        }
        return category_map.get(agent_name, "system")

    def _format_agent_name(self, agent_name: str) -> str:
        """Format agent name for display."""
        name_map = {
            "file": "File Agent",
            "folder": "Folder Agent",
            "google": "Google Search Agent",
            "browser": "Browser Agent",
            "presentation": "Presentation Agent",
            "email": "Email Agent",
            "writing": "Writing Agent",
            "maps": "Maps Agent",
            "stock": "Stock Agent",
            "report": "Report Agent",
            "google_finance": "Google Finance Agent",
            "imessage": "iMessage Agent",
            "discord": "Discord Agent",
            "reddit": "Reddit Agent",
            "twitter": "Twitter Agent",
            "bluesky": "Bluesky Agent",
            "whatsapp": "WhatsApp Agent",
            "notifications": "Notifications Agent",
            "micro_actions": "Micro Actions Agent",
            "voice": "Voice Agent",
            "spotify": "Spotify Agent",
            "celebration": "Celebration Agent",
        }
        return name_map.get(agent_name, agent_name.title() + " Agent")

    def _get_agent_icon(self, agent_name: str) -> str:
        """Get icon for agent."""
        icon_map = {
            "file": "📁",
            "folder": "📂",
            "google": "🔍",
            "browser": "🌐",
            "presentation": "📊",
            "email": "📧",
            "writing": "✍️",
            "maps": "🗺️",
            "stock": "📈",
            "report": "📊",
            "google_finance": "💰",
            "imessage": "💬",
            "discord": "💬",
            "reddit": "🤖",
            "twitter": "🐦",
            "bluesky": "🦋",
            "whatsapp": "💬",
            "notifications": "🔔",
            "micro_actions": "⚡",
            "voice": "🎤",
            "spotify": "🎵",
            "celebration": "🎉",
        }
        return icon_map.get(agent_name, "🤖")

    def _extract_agent_description(self, hierarchy: str) -> str:
        """Extract description from agent hierarchy documentation."""
        lines = hierarchy.split('\n')
        for line in lines:
            if "Domain:" in line:
                return line.split("Domain:")[-1].strip()
        return "Agent for automation tasks"

    def _get_slash_commands_for_agent(self, agent_name: str) -> List[str]:
        """Get slash commands that use this agent."""
        commands = []
        for entry in self.entries.values():
            if entry.type == "slash_command" and entry.agent == agent_name:
                commands.append(entry.name)
        return commands

    # Search and Filter Methods

    def search(self, query: str, limit: int = 10) -> List[HelpEntry]:
        """
        Search help entries by query string.

        Uses fuzzy matching on names, descriptions, tags, and examples.
        """
        query = query.lower()
        results = []

        for entry in self.entries.values():
            score = 0

            # Exact name match (highest priority)
            if query in entry.name.lower():
                score += 100

            # Description match
            if query in entry.description.lower():
                score += 50

            # Tag match
            for tag in entry.tags:
                if query in tag.lower():
                    score += 30

            # Example match
            for example in entry.examples:
                if query in example.lower():
                    score += 20

            # Long description match
            if entry.long_description and query in entry.long_description.lower():
                score += 10

            if score > 0:
                results.append((score, entry))

        # Sort by score (descending)
        results.sort(key=lambda x: x[0], reverse=True)

        return [entry for score, entry in results[:limit]]

    def get_by_category(self, category: str) -> List[HelpEntry]:
        """Get all entries in a category."""
        return [
            entry for entry in self.entries.values()
            if entry.category == category
        ]

    def get_by_type(self, entry_type: str) -> List[HelpEntry]:
        """Get all entries of a specific type."""
        return [
            entry for entry in self.entries.values()
            if entry.type == entry_type
        ]

    def get_suggestions(self, failed_command: str) -> List[str]:
        """Get command suggestions for a failed/unknown command."""
        # Get all command names
        command_names = [
            entry.name for entry in self.entries.values()
            if entry.type == "slash_command"
        ]

        # Use difflib to find close matches
        matches = get_close_matches(failed_command, command_names, n=3, cutoff=0.6)

        return matches

    def get_all_categories(self) -> List[CategoryInfo]:
        """Get all categories with their metadata."""
        return list(self.categories.values())

    def get_all_slash_commands(self) -> List[HelpEntry]:
        """Get all slash command entries."""
        return self.get_by_type("slash_command")

    def get_all_agents(self) -> List[AgentHelp]:
        """Get all agent help entries."""
        return list(self.agents.values())

    def get_agent(self, agent_name: str) -> Optional[AgentHelp]:
        """Get help for a specific agent."""
        return self.agents.get(agent_name)

    def get_entry(self, name: str) -> Optional[HelpEntry]:
        """Get a specific help entry by name."""
        return self.entries.get(name)

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire help registry to dictionary for JSON export."""
        return {
            "categories": {
                name: cat.to_dict()
                for name, cat in self.categories.items()
            },
            "commands": {
                name: entry.to_dict()
                for name, entry in self.entries.items()
                if entry.type == "slash_command"
            },
            "agents": {
                name: agent.to_dict()
                for name, agent in self.agents.items()
            },
            "total_entries": len(self.entries),
            "total_agents": len(self.agents),
            "total_categories": len(self.categories)
        }
