"""
Slash Command System for Direct Agent Interaction.

Allows users to bypass the orchestrator and talk directly to specific agents.

Available Commands:
    /files <task>           - Talk directly to File Agent
    /browse <task>          - Talk directly to Browser Agent
    /present <task>         - Talk directly to Presentation Agent
    /email <task>           - Talk directly to Email Agent
    /write <task>           - Talk directly to Writing Agent
    /maps <task>            - Talk directly to Maps Agent
    /stock <task>           - Talk directly to Stock/Finance Agent
    /message <task>         - Talk directly to iMessage Agent
    /discord <task>         - Talk directly to Discord Agent
    /reddit <task>          - Talk directly to Reddit Agent
    /twitter <task>         - Talk directly to Twitter Agent
    /bluesky <task>         - Talk directly to Bluesky Agent
    /spotify <task>         - Control Spotify playback (play/pause)
    /music <task>           - Control Spotify playback (alias)
    /whatsapp <task>        - Read and analyze WhatsApp messages
    /wa <task>              - WhatsApp (alias)
    /confetti               - Trigger celebratory confetti effects
    /notify <task>          - Send system notifications
    /report <task>          - Generate PDF reports from local files
    /help [command]         - Show help for commands
    /agents                 - List all available agents
    /                      - Show slash command palette
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import re

logger = logging.getLogger(__name__)


def _extract_quoted_text(text: str) -> Optional[str]:
    """Extract first quoted substring from text."""
    match = re.search(r'"([^"]+)"', text)
    if match:
        return match.group(1)
    match = re.search(r"'([^']+)'", text)
    if match:
        return match.group(1)
    return None


class SlashCommandParser:
    """Parse and route slash commands to appropriate agents."""

    # Command to agent mapping
    COMMAND_MAP = {
        "files": "file",
        "file": "file",
        "folder": "folder",  # Routes to file agent for explanation, folder agent for management
        "folders": "folder",  # Routes to file agent for explanation, folder agent for management
        "organize": "folder",
        "google": "google",
        "search": "google",
        "browse": "browser",
        "browser": "browser",
        "web": "browser",
        "present": "presentation",
        "presentation": "presentation",
        "keynote": "presentation",
        "pages": "presentation",
        "email": "email",
        "mail": "email",
        "write": "writing",
        "writing": "writing",
        "maps": "maps",
        "map": "maps",
        "directions": "maps",
        "stock": "google_finance",
        "stocks": "google_finance",
        "finance": "google_finance",
        "message": "imessage",
        "imessage": "imessage",
        "text": "imessage",
        "discord": "discord",
        "reddit": "reddit",
        "twitter": "twitter",
        "x": "twitter",  # Quick alias for Twitter summaries
        "bluesky": "bluesky",
        "sky": "bluesky",
        "report": "report",
        "notify": "notifications",
        "notification": "notifications",
        "alert": "notifications",
        "spotify": "spotify",
        "music": "spotify",
        "whatsapp": "whatsapp",
        "wa": "whatsapp",
        "confetti": "celebration",
        "celebrate": "celebration",
        "party": "celebration",
    }

    # Special system commands (not agent-related)
    SYSTEM_COMMANDS = ["help", "agents", "clear"]
    
    # Commands that can execute without a task (execute immediately)
    NO_TASK_COMMANDS = ["confetti", "celebrate", "party"]

    # Quick palette entries (primary commands only)
    COMMAND_TOOLTIPS = [
        {"command": "/files", "label": "File Ops", "description": "Search, organize, zip local files"},
        {"command": "/folder", "label": "Folder Agent", "description": "List & reorganize folders"},
        {"command": "/browse", "label": "Browser", "description": "Search the web & extract content"},
        {"command": "/present", "label": "Presentations", "description": "Create Keynote/Pages docs"},
        {"command": "/email", "label": "Email", "description": "Read, summarize & draft emails"},
        {"command": "/write", "label": "Writing", "description": "Generate reports, notes, slides"},
        {"command": "/maps", "label": "Maps", "description": "Plan trips & routes"},
        {"command": "/stock", "label": "Stocks", "description": "Prices, charts, Google Finance"},
        {"command": "/report", "label": "Local Reports", "description": "PDF reports from local files"},
        {"command": "/message", "label": "iMessage", "description": "Send texts"},
        {"command": "/discord", "label": "Discord", "description": "Monitor channels"},
        {"command": "/reddit", "label": "Reddit", "description": "Scan subreddits"},
        {"command": "/twitter", "label": "Twitter", "description": "Summarize lists"},
        {"command": "/x", "label": "X/Twitter", "description": "Quick Twitter summaries"},
        {"command": "/bluesky", "label": "Bluesky", "description": "Search, summarize, and post updates"},
        {"command": "/notify", "label": "Notifications", "description": "Send system notifications"},
        {"command": "/spotify", "label": "Spotify", "description": "Play and pause music"},
        {"command": "/whatsapp", "label": "WhatsApp", "description": "Read and analyze WhatsApp messages"},
        {"command": "/confetti", "label": "Confetti", "description": "Trigger celebratory confetti effects"},
    ]

    # Agent descriptions for help
    AGENT_DESCRIPTIONS = {
        "file": "Handle file operations: search, organize, zip, screenshots",
        "folder": "Folder management: list, organize, rename files (LLM-driven, sandboxed)",
        "google": "DuckDuckGo web search (legacy name), fast structured results without a browser",
        "browser": "Web browsing: search Google, navigate URLs, extract content",
        "presentation": "Create presentations: Keynote, Pages documents",
        "email": "Read, compose, send, and summarize emails via Mail.app",
        "writing": "Generate content: reports, slide decks, meeting notes",
        "maps": "Plan trips with stops, get directions, open Maps",
        "google_finance": "Get stock data, prices, charts from Google Finance",
        "imessage": "Send iMessages to contacts",
        "notifications": "Send system notifications via Notification Center (with sound & alerts)",
        "discord": "Monitor Discord channels and mentions",
        "reddit": "Scan Reddit for mentions and posts",
        "twitter": "Track Twitter lists and activity",
        "bluesky": "Search Bluesky posts, summarize activity, and publish updates",
        "report": "Create PDF reports strictly from local files (or stock data when requested)",
        "spotify": "Control Spotify playback: play music, pause music, get status",
        "whatsapp": "Read WhatsApp messages, summarize conversations, extract action items",
        "celebration": "Trigger celebratory confetti effects with emoji notifications",
    }

    # Example commands
    EXAMPLES = {
        "files": [
            '/files Organize my PDFs by topic',
            '/files Create a ZIP of all images',
            '/files Find documents about AI',
            '/files Explain all files',
            '/files List and explain files',
        ],
        "folder": [
            '/folder /Users/siddharthsuresh/Downloads/auto_mac',
            '/folder Explain files in test_docs',
            '/folder List files',
            '/folder organize alpha',
            '/organize test_data',
        ],
        "google": [
            '/google Python async programming tutorials',
            '/search latest AI news',
            '/google site:github.com machine learning',
        ],
        "browse": [
            '/browse Search for Python tutorials',
            '/browse Go to github.com and extract the trending repos',
        ],
        "present": [
            '/present Create a Keynote about AI trends',
            '/present Make a Pages document with this report',
        ],
        "email": [
            '/email Read the latest 10 emails',
            '/email Show emails from john@example.com',
            '/email Summarize emails from the past hour',
            '/email Draft an email about project status',
            '/email Send meeting notes to team@company.com',
        ],
        "write": [
            '/write Create a report on Q4 performance',
            '/write Generate meeting notes from this transcript',
        ],
        "maps": [
            '/maps Plan a trip from SF to LA with 2 gas stops',
            '/maps Get directions to Phoenix with lunch stop',
        ],
        "stock": [
            '/stock Get AAPL current price',
            '/stock Show TSLA chart for last month',
        ],
        "message": [
            '/message Send "Running late" to John',
        ],
        "report": [
            '/report Create a report on Tesla based on my local files',
            '/report Summarize the AI agent docs you can access',
        ],
        "notify": [
            '/notify Task complete: Stock report is ready',
            '/notify alert Email sent successfully with sound Glass',
            '/notify notification Background processing finished',
        ],
        "spotify": [
            '/spotify play',
            '/spotify pause',
            '/spotify play music',
            '/music pause',
        ],
        "whatsapp": [
            '/whatsapp Read messages from John',
            '/whatsapp List all chats',
            '/whatsapp Summarize messages from Family group',
            '/whatsapp Detect unread messages',
        ],
        "celebration": [
            '/confetti',
            '/celebrate',
            '/party',
        ],
        "x": [
            '/x summarize last 1h',
            '/x what happened on Twitter in the past hour',
            '/x tweet Launch day! 🚀',
        ],
        "bluesky": [
            '/bluesky search "agent ecosystems" limit:8',
            '/bluesky summarize "mac automation" 12h',
            '/bluesky post "Testing the Bluesky integration ✨"',
        ],
    }

    def __init__(self):
        """Initialize the parser."""
        self.pattern = re.compile(r'^/(\w+)\s+(.+)$', re.DOTALL)

    def parse(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Parse a message for slash commands.

        Args:
            message: User message that may contain slash command

        Returns:
            Dictionary with command info if valid slash command, None otherwise
            {
                "is_command": True,
                "command": "files",
                "agent": "file",
                "task": "Organize my PDFs by topic"
            }
        """
        # Check if message starts with /
        if not message.strip().startswith('/'):
            return None

        # Special commands
        stripped = message.strip()

        if stripped == '/':
            return {
                "is_command": True,
                "command": "palette",
                "agent": None,
                "task": None
            }

        if stripped == '/help':
            return {
                "is_command": True,
                "command": "help",
                "agent": None,
                "task": None
            }

        if stripped == '/agents':
            return {
                "is_command": True,
                "command": "agents",
                "agent": None,
                "task": None
            }

        if stripped == '/clear':
            return {
                "is_command": True,
                "command": "clear",
                "agent": None,
                "task": None
            }

        # Check for help on specific command
        help_match = re.match(r'^/help\s+(.+)$', message.strip())
        if help_match:
            help_arg = help_match.group(1).strip()
            # Check if it's a search query
            if help_arg.startswith('search '):
                return {
                    "is_command": True,
                    "command": "help",
                    "agent": None,
                    "task": None,
                    "help_mode": "search",
                    "search_query": help_arg[7:].strip()  # Remove "search " prefix
                }
            # Check for category filter
            elif help_arg.startswith('--category '):
                return {
                    "is_command": True,
                    "command": "help",
                    "agent": None,
                    "task": None,
                    "help_mode": "category",
                    "category": help_arg[11:].strip()  # Remove "--category " prefix
                }
            # Otherwise it's help for a specific command
            else:
                return {
                    "is_command": True,
                    "command": "help",
                    "agent": help_arg,
                    "task": None
                }

        # Parse regular command
        match = self.pattern.match(message.strip())
        if not match:
            # Check if it's a standalone command (e.g., /email with no task)
            standalone_match = re.match(r'^/(\w+)$', message.strip())
            if standalone_match:
                command = standalone_match.group(1).lower()
                # Check if it's a command that can execute without a task
                if command in self.NO_TASK_COMMANDS and command in self.COMMAND_MAP:
                    # Execute immediately without task
                    return {
                        "is_command": True,
                        "command": command,
                        "agent": self.COMMAND_MAP[command],
                        "task": None
                    }
                # Check if it's a valid command
                elif command in self.COMMAND_MAP:
                    # Return help for this command instead of error
                    return {
                        "is_command": True,
                        "command": "help",
                        "agent": command,
                        "task": None
                    }
                else:
                    # Unknown command - provide suggestions
                    from difflib import get_close_matches
                    suggestions = get_close_matches(command, self.COMMAND_MAP.keys(), n=3, cutoff=0.6)
                    error_msg = f"Unknown command: /{command}."
                    if suggestions:
                        error_msg += f"\n\nDid you mean:\n" + "\n".join([f"  • /{s}" for s in suggestions])
                    error_msg += "\n\nType /help for all available commands."
                    return {
                        "is_command": True,
                        "command": "invalid",
                        "error": error_msg
                    }

            return {
                "is_command": True,
                "command": "invalid",
                "error": "Invalid command format. Use: /command <task>\nType /help for available commands."
            }

        command = match.group(1).lower()
        task = match.group(2).strip()

        # Map command to agent
        agent = self.COMMAND_MAP.get(command)

        if not agent:
            # Provide suggestions for unknown commands
            from difflib import get_close_matches
            suggestions = get_close_matches(command, self.COMMAND_MAP.keys(), n=3, cutoff=0.6)
            error_msg = f"Unknown command: /{command}."
            if suggestions:
                error_msg += f"\n\nDid you mean:\n" + "\n".join([f"  • /{s}" for s in suggestions])
            error_msg += "\n\nType /help for all available commands."
            return {
                "is_command": True,
                "command": "invalid",
                "error": error_msg
            }

        return {
            "is_command": True,
            "command": command,
            "agent": agent,
            "task": task
        }

    def get_command_palette(self) -> str:
        """Return quick command palette text."""
        lines = [
            "⌨️ Slash Command Palette",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "Type a command below followed by your task (e.g., `/files Organize invoices`).",
            "",
        ]

        for tip in self.COMMAND_TOOLTIPS:
            lines.append(f"{tip['command']:<12} {tip['label']} — {tip['description']}")

        lines.append("")
        lines.append("💡 Tip: Use `/help <command>` for detailed usage and examples.")

        return "\n".join(lines)

    def get_help(self, command: Optional[str] = None, help_mode: Optional[str] = None,
                 search_query: Optional[str] = None, category: Optional[str] = None,
                 agent_registry=None) -> str:
        """
        Get help text for commands using HelpRegistry.

        Args:
            command: Specific command to get help for, or None for general help
            help_mode: 'search' or 'category' for filtered help
            search_query: Search query when help_mode is 'search'
            category: Category name when help_mode is 'category'
            agent_registry: Optional AgentRegistry for dynamic help

        Returns:
            Formatted help text
        """
        try:
            from .help_registry import HelpRegistry
            help_registry = HelpRegistry(agent_registry)
        except Exception as e:
            logger.warning(f"Could not load HelpRegistry: {e}, falling back to static help")
            return self._get_static_help(command)

        # Search mode
        if help_mode == "search" and search_query:
            results = help_registry.search(search_query, limit=10)
            if not results:
                return f"🔍 No results found for: {search_query}\n\nTry different keywords or type /help to see all commands."

            help_text = [
                f"🔍 Search Results for: {search_query}",
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                f"",
                f"Found {len(results)} result(s):",
                f"",
            ]

            for entry in results:
                help_text.append(f"{entry.icon} **{entry.name}**")
                help_text.append(f"   {entry.description}")
                if entry.examples:
                    help_text.append(f"   Example: {entry.examples[0]}")
                help_text.append("")

            help_text.append("💡 Tip: Use `/help <command>` for detailed help on a specific command.")
            return "\n".join(help_text)

        # Category mode
        if help_mode == "category" and category:
            entries = help_registry.get_by_category(category)
            if not entries:
                categories = help_registry.get_all_categories()
                cat_names = [c.name for c in categories]
                return f"❌ Unknown category: {category}\n\nAvailable categories:\n" + "\n".join([f"  • {c}" for c in cat_names])

            cat_info = help_registry.categories.get(category)
            help_text = [
                f"{cat_info.icon} **{cat_info.display_name}**",
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                f"",
                f"{cat_info.description}",
                f"",
                f"**Commands ({len(entries)}):**",
                f"",
            ]

            for entry in entries:
                if entry.type == "slash_command":
                    help_text.append(f"{entry.icon} {entry.name:<15} {entry.description}")

            return "\n".join(help_text)

        # Specific command help
        if command:
            entry = help_registry.get_entry(f"/{command}")
            if not entry:
                # Try without slash
                entry = help_registry.get_entry(command)

            if not entry:
                # Command not found - provide suggestions
                suggestions = help_registry.get_suggestions(f"/{command}")
                error_text = [f"❌ Unknown command: /{command}", ""]
                if suggestions:
                    error_text.append("Did you mean:")
                    for sug in suggestions:
                        error_text.append(f"  • {sug}")
                    error_text.append("")
                error_text.append("Type /help to see all available commands.")
                return "\n".join(error_text)

            # Format detailed help for command
            help_text = [
                f"{entry.icon} **{entry.name}**",
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                f"",
                f"{entry.description}",
                f"",
            ]

            if entry.long_description:
                help_text.append(f"{entry.long_description}")
                help_text.append("")

            help_text.append(f"**Usage:** {entry.name} <your task>")
            help_text.append("")

            if entry.examples:
                help_text.append("**Examples:**")
                for example in entry.examples[:5]:
                    help_text.append(f"  {example}")
                help_text.append("")

            if entry.agent:
                help_text.append(f"**Agent:** {entry.agent}")
                help_text.append("")

            if entry.related:
                help_text.append(f"**Related:** {', '.join(entry.related)}")
                help_text.append("")

            help_text.append("💡 **Tip:** Type the command without a task to see this help.")

            return "\n".join(help_text)

        # General help - show categories
        return self._get_general_help(help_registry)

    def _get_general_help(self, help_registry) -> str:
        """Generate general help text with categories."""
        categories = help_registry.get_all_categories()

        help_text = [
            "🎯 Slash Commands - Quick Access",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "Slash commands let you talk directly to agents for faster execution.",
            "",
            "**Quick Search:**",
            "  /help search <query>      - Search all commands",
            "  /help --category <name>   - Filter by category",
            "  /help <command>           - Detailed help for a command",
            "",
        ]

        # Show commands by category
        for cat in categories:
            if cat.command_count == 0:
                continue

            help_text.append(f"{cat.icon} **{cat.display_name}** ({cat.command_count} commands)")

            # Get commands in this category
            entries = help_registry.get_by_category(cat.name)
            slash_commands = [e for e in entries if e.type == "slash_command"]

            for entry in slash_commands[:3]:  # Show top 3
                help_text.append(f"   {entry.name:<15} {entry.description}")

            if len(slash_commands) > 3:
                help_text.append(f"   ... and {len(slash_commands) - 3} more")

            help_text.append("")

        help_text.extend([
            "**Examples:**",
            "  /files Organize my PDFs by topic",
            "  /email Read my latest 5 emails",
            "  /maps Plan trip from LA to SF",
            "  /help email           # Detailed email help",
            "  /help search stock    # Search for stock commands",
            "",
            "💡 **Tip:** Type any command alone (e.g., `/email`) to see its help!",
        ])

        return "\n".join(help_text)

    def _get_static_help(self, command: Optional[str] = None) -> str:
        """Fallback to static help if HelpRegistry fails."""
        if command:
            # Help for specific command
            agent = self.COMMAND_MAP.get(command)
            if not agent:
                return f"❌ Unknown command: /{command}\n\nType /help to see all available commands."

            description = self.AGENT_DESCRIPTIONS.get(agent, "No description available")
            examples = self.EXAMPLES.get(command, [])

            help_text = [
                f"📘 Help: /{command}",
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                f"",
                f"**Description:** {description}",
                f"",
                f"**Usage:** /{command} <your task>",
                f"",
            ]

            if examples:
                help_text.append("**Examples:**")
                for example in examples:
                    help_text.append(f"  {example}")
                help_text.append("")

            help_text.append(f"**Direct Agent:** {agent}")

            return "\n".join(help_text)

        # General help
        help_text = [
            "🎯 Slash Commands - Direct Agent Access",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "Slash commands let you talk directly to specific agents,",
            "bypassing the orchestrator for faster, focused interactions.",
            "",
            "📁 **File Operations:**",
            "  /files <task>         - Search, organize, zip files",
            "  /folder <task>        - Folder management (list, organize, rename)",
            "  /organize [path]      - Quick folder organization",
            "",
            "🌐 **Web Browsing:**",
            "  /browse <task>        - Search web, navigate, extract content",
            "",
            "📊 **Presentations:**",
            "  /present <task>       - Create Keynote/Pages documents",
            "",
            "📧 **Email:**",
            "  /email <task>         - Compose and send emails",
            "",
            "✍️ **Writing:**",
            "  /write <task>         - Generate reports, notes, content",
            "",
            "🗺️ **Maps & Travel:**",
            "  /maps <task>          - Plan trips, get directions",
            "",
            "📈 **Stocks & Finance:**",
            "  /stock <task>         - Get stock prices, charts, data",
            "  /report <task>        - Build PDF reports from local files (no hallucinations)",
            "",
            "💬 **Messaging:**",
            "  /message <task>       - Send iMessages",
            "  /discord <task>       - Monitor Discord",
            "  /reddit <task>        - Scan Reddit",
            "  /twitter <task>       - Track Twitter",
            "  /bluesky <task>       - Search & post on Bluesky",
            "",
            "ℹ️ **Help & Info:**",
            "  /help [command]       - Show help (optionally for specific command)",
            "  /agents               - List all available agents",
            "",
            "🧹 **Session Management:**",
            "  /clear                - Clear session memory and start fresh",
            "",
            "💡 **Examples:**",
            "  /files Organize my PDFs by topic",
            "  /browse Search for Python tutorials",
            "  /maps Plan trip from LA to SF with 2 gas stops",
            "  /stock Get AAPL current price",
            "",
            "📝 **Note:** Slash commands bypass orchestrator planning for",
            "     direct agent execution. For complex multi-agent tasks,",
            "     use natural language without slash commands.",
        ]

        return "\n".join(help_text)

    def get_agents_list(self) -> str:
        """Get formatted list of all agents."""
        lines = [
            "🤖 Available Agents",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        # Group by category
        categories = {
            "File & Document Operations": ["file"],
            "Web & Content": ["browser", "writing"],
            "Presentations & Documents": ["presentation"],
            "Communication": ["email", "imessage", "discord", "reddit", "twitter", "bluesky"],
            "Travel & Location": ["maps"],
            "Finance & Stocks": ["google_finance", "report"],
        }

        for category, agents in categories.items():
            lines.append(f"**{category}:**")
            for agent in agents:
                description = self.AGENT_DESCRIPTIONS.get(agent, "No description")
                # Find command(s) for this agent
                commands = [cmd for cmd, ag in self.COMMAND_MAP.items() if ag == agent]
                cmd_list = ", ".join(f"/{c}" for c in sorted(set(commands))[:2])
                lines.append(f"  • {agent}: {description}")
                lines.append(f"    Commands: {cmd_list}")
            lines.append("")

        lines.append("💡 Type /help <command> for details on any command")

        return "\n".join(lines)


class SlashCommandHandler:
    """Handle execution of slash commands."""

    def __init__(self, agent_registry, session_manager=None):
        """
        Initialize handler with agent registry.

        Args:
            agent_registry: AgentRegistry instance with all agents
            session_manager: Optional SessionManager for /clear command
        """
        self.registry = agent_registry
        self.session_manager = session_manager
        self.parser = SlashCommandParser()
        logger.info("[SLASH COMMANDS] Handler initialized")

    def handle(self, message: str, session_id: Optional[str] = None) -> Tuple[bool, Any]:
        """
        Handle a message, checking if it's a slash command.

        Args:
            message: User message
            session_id: Optional session ID for /clear command

        Returns:
            Tuple of (is_command, result)
            - is_command: True if this was a slash command
            - result: Either help text (str) or execution result (dict)
        """
        parsed = self.parser.parse(message)

        if not parsed:
            # Not a slash command
            return False, None

        # Handle special commands
        if parsed["command"] == "help":
            help_text = self.parser.get_help(parsed.get("agent"))
            return True, {"type": "help", "content": help_text}

        if parsed["command"] == "agents":
            agents_list = self.parser.get_agents_list()
            return True, {"type": "agents", "content": agents_list}

        if parsed["command"] == "palette":
            palette = self.parser.get_command_palette()
            return True, {"type": "palette", "content": palette}

        if parsed["command"] == "clear":
            if self.session_manager:
                memory = self.session_manager.clear_session(session_id)
                return True, {
                    "type": "clear",
                    "content": "✨ Context cleared. Starting a new session.",
                    "session_id": memory.session_id,
                    "new_session": True
                }
            else:
                return True, {
                    "type": "error",
                    "content": "❌ Session management not enabled"
                }

        if parsed["command"] == "invalid":
            return True, {"type": "error", "content": parsed.get("error")}

        # Execute agent command
        original_agent = parsed["agent"]
        agent_name = parsed["agent"]
        task = parsed["task"]
        task_lower = (task or "").lower().strip()

        if original_agent == "folder" and any(
            keyword in task_lower for keyword in ["summarize", "summarise", "summary"]
        ):
            folder_path = self._extract_folder_path(task or "")
            params: Dict[str, Any] = {}
            if folder_path:
                params["folder_path"] = folder_path

            listing = self.registry.execute_tool("folder_list", params, session_id=session_id)
            if listing.get("error"):
                return True, {
                    "type": "result",
                    "agent": "folder",
                    "original_agent": "folder",
                    "command": parsed["command"],
                    "result": listing,
                    "raw": listing,
                }

            reply_payload = self._format_folder_result(listing, task, session_id=session_id)
            if reply_payload:
                reply_payload.setdefault("_raw_result", listing)
                return True, {
                    "type": "result",
                    "agent": "folder",
                    "original_agent": "folder",
                    "command": parsed["command"],
                    "result": reply_payload,
                    "raw": listing,
                }

        # Direct handling for Bluesky to avoid LLM routing ambiguity
        if agent_name == "bluesky":
            try:
                mode, params = self._parse_bluesky_task(task)
            except ValueError as exc:
                return True, {
                    "type": "error",
                    "content": f"⚠ {exc}"
                }

            tool_map = {
                "search": "search_bluesky_posts",
                "summary": "summarize_bluesky_posts",
                "post": "post_bluesky_update",
            }

            tool_name = tool_map[mode]
            logger.info(f"[SLASH COMMAND] /{parsed['command']} -> bluesky ({mode})")
            logger.info(f"[SLASH COMMAND] Parameters: {params}")

            result = self.registry.execute_tool(tool_name, params, session_id=session_id)

            return True, {
                "type": "result",
                "agent": "bluesky",
                "command": parsed["command"],
                "mode": mode,
                "params": params,
                "result": result,
            }

        # Special handling: /folder for explanation tasks should route to file agent
        if agent_name == "folder" and parsed["command"] in ["folder", "folders"]:
            # Check if task is about explaining/listing files (not folder management)
            explanation_keywords = ["explain", "list", "show", "what", "summarize", "describe", "overview"]
            management_keywords = ["organize", "rename", "plan", "apply", "normalize", "reorganize"]

            # Route to file agent if:
            # 1. Task is empty (explain all files)
            # 2. Contains explanation keywords
            # 3. Is just a path (starts with / or ~ or contains /)
            # 4. Doesn't contain management keywords
            is_explanation = (
                not task_lower or
                any(keyword in task_lower for keyword in explanation_keywords) or
                (task_lower and (task_lower.startswith('/') or task_lower.startswith('~') or '/' in task_lower) and
                 not any(word in task_lower for word in management_keywords))
            )
            
            if is_explanation:
                agent_name = "file"
                logger.info(f"[SLASH COMMAND] Routing /folder explanation request to file agent")

        logger.info(f"[SLASH COMMAND] /{parsed['command']} -> {agent_name} agent")
        logger.info(f"[SLASH COMMAND] Task: {task}")

        try:
            agent = self.registry.get_agent(agent_name)
            if not agent:
                return True, {
                    "type": "error",
                    "content": f"❌ Agent '{agent_name}' not found"
                }

            # Special handling for celebration agent when no task (direct execution)
            if agent_name == "celebration" and (not task or not task.strip()):
                result = agent.execute("trigger_confetti", {})
            else:
                # Execute through agent
                # For now, we'll use the agent's primary tool
                # In future, could add agent-level "handle_task" method
                result = self._execute_agent_task(agent, agent_name, task)

            formatted_result = result

            if original_agent == "folder" and not result.get("error"):
                reply_payload = self._format_folder_result(result, task, session_id=session_id)
                if reply_payload:
                    formatted_result = reply_payload
                    formatted_result.setdefault("_raw_result", result)

            return True, {
                "type": "result",
                "agent": agent_name,
                "original_agent": original_agent,
                "command": parsed["command"],
                "result": formatted_result,
                "raw": result
            }

        except Exception as e:
            logger.error(f"[SLASH COMMAND] Error: {e}", exc_info=True)
            return True, {
                "type": "error",
                "content": f"❌ Error executing command: {str(e)}"
            }

    def _parse_bluesky_task(self, task: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parse a /bluesky command task to determine mode and parameters.
        Returns (mode, params) where mode is 'search', 'summary', or 'post'.
        """
        if not task or not task.strip():
            raise ValueError("Provide a task, e.g. /bluesky search \"AI agents\" limit:10")

        text = task.strip()
        lower = text.lower()

        config = getattr(self.registry, "config", {}).get("bluesky", {}) if hasattr(self.registry, "config") else {}
        default_limit = config.get("default_search_limit", 10)
        default_lookback = config.get("default_lookback_hours", 24)
        default_max_items = config.get("max_summary_items", 5)

        def _strip_patterns(source: str, patterns: List[re.Pattern]) -> Tuple[str, Dict[str, int]]:
            extracted: Dict[str, int] = {}
            remainder = source
            for pattern in patterns:
                match = pattern.search(remainder)
                if match:
                    key = pattern.pattern
                    value = int(match.group(1))
                    extracted[key] = value
                    remainder = remainder.replace(match.group(0), "")
            return remainder, extracted

        # Posting
        for prefix in ("post", "publish", "send", "tweet"):
            if lower.startswith(prefix + " "):
                message = text[len(prefix):].strip()
                if not message:
                    raise ValueError("Provide a message to post, e.g. /bluesky post \"Hello Bluesky\"")
                # Handle "-" separator (e.g., "tweet - message here")
                if message.startswith("-"):
                    message = message[1:].strip()
                quoted = _extract_quoted_text(message)
                if quoted:
                    message = quoted
                return "post", {"message": message.strip()}

        # Check for "last N tweets" pattern - should trigger summary mode
        last_tweets_match = re.search(r'\blast\s+(\d+)\s+(?:tweets?|posts?)', lower)
        if last_tweets_match:
            # Extract number of tweets/posts
            num_items = int(last_tweets_match.group(1))
            # Use summarize mode with the query
            return "summary", {
                "query": text,  # Pass full text so bluesky agent can parse it
                "max_items": min(num_items, 10),
                "lookback_hours": default_lookback
            }

        # Summaries
        if lower.startswith(("summarize", "summary", "analyze")):
            action_word = text.split(None, 1)[0]
            remainder = text[len(action_word):].strip()

            time_patterns = [
                re.compile(r'(\d+)\s*(?:hours?|hrs?|hr|h)\b', re.IGNORECASE),
                re.compile(r'(\d+)\s*(?:days?|d)\b', re.IGNORECASE),
            ]
            limit_patterns = [
                re.compile(r'(?:max|limit|items)\s*[:=]?\s*(\d+)', re.IGNORECASE),
            ]

            remainder, time_matches = _strip_patterns(remainder, time_patterns)
            remainder, limit_matches = _strip_patterns(remainder, limit_patterns)

            lookback_hours = None
            for pattern, value in time_matches.items():
                if "day" in pattern.lower():
                    lookback_hours = value * 24
                else:
                    lookback_hours = value
                break  # Use first match

            max_items = None
            for value in limit_matches.values():
                max_items = value
                break

            query = _extract_quoted_text(remainder) or remainder
            query = query.strip().strip('"').strip("'")
            if not query:
                raise ValueError("Provide a query to summarize, e.g. /bluesky summarize \"agent ecosystems\" 12h")

            params: Dict[str, Any] = {"query": query}
            if lookback_hours is not None:
                params["lookback_hours"] = lookback_hours
            else:
                params["lookback_hours"] = default_lookback
            if max_items is not None:
                params["max_items"] = max_items
            else:
                params["max_items"] = default_max_items

            return "summary", params

        # Searches (default)
        search_words = {"search", "find", "lookup", "scan"}
        first_word = text.split(None, 1)[0].lower()
        remainder = text[len(first_word):].strip() if first_word in search_words else text

        limit_match = re.search(r'(?:max|limit)\s*[:=]?\s*(\d+)', remainder, re.IGNORECASE)
        max_posts = default_limit
        if limit_match:
            max_posts = int(limit_match.group(1))
            remainder = remainder.replace(limit_match.group(0), "")

        query = _extract_quoted_text(remainder) or remainder
        query = query.strip().strip('"').strip("'")
        if not query:
            raise ValueError("Provide a query to search, e.g. /bluesky search \"AI agents\" limit:8")

        params = {"query": query, "max_posts": max_posts}
        return "search", params

    def _format_folder_result(
        self,
        result: Dict[str, Any],
        task: str,
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Convert folder agent outputs into a reply payload for user-facing display.
        """
        try:
            if result.get("error"):
                return None

            if "items" in result:
                items = result.get("items", [])
                total = result.get("total_count", len(items))
                files = [item for item in items if item.get("type") == "file"]
                dirs = [item for item in items if item.get("type") == "dir"]

                from collections import Counter

                ext_counter = Counter()
                for file_item in files:
                    ext = file_item.get("extension") or "(no extension)"
                    ext_counter[ext.lower()] += 1

                top_exts = ext_counter.most_common(5)

                folder_path = result.get("relative_path")
                if folder_path in (None, ".", ""):
                    folder_path = result.get("folder_path", "configured folder")

                message = f"Found {total} item{'s' if total != 1 else ''} in `{folder_path}`."
                if total == 0:
                    message = f"`{folder_path}` is empty."

                detail_lines = [
                    f"- Files: {len(files)}",
                    f"- Folders: {len(dirs)}",
                ]

                if top_exts:
                    detail_lines.append("\n**Top file types:**")
                    for ext, count in top_exts:
                        detail_lines.append(f"  - {ext.upper()}: {count}")

                sample_items = [item.get("name") for item in items][:5]
                if sample_items:
                    detail_lines.append("\n**Sample items:**")
                    for name in sample_items:
                        detail_lines.append(f"  - {name}")

                details = "\n".join(detail_lines)
                artifacts = [result.get("folder_path")] if result.get("folder_path") else []

                return self._format_with_reply(
                    message=message,
                    details=details,
                    artifacts=artifacts,
                    status="info",
                    session_id=session_id,
                )

            if "plan" in result and "changes_count" in result:
                changes = result.get("changes_count", 0)
                total_items = result.get("total_items", len(result.get("plan", [])))
                folder_path = result.get("folder_path", "")
                message = (
                    f"Alphabetical normalization plan prepared for `{Path(folder_path).name}`."
                    if folder_path else "Alphabetical normalization plan prepared."
                )
                if changes == 0:
                    message = "All items already follow the normalized naming pattern."

                detail_lines = [
                    f"- Total items checked: {total_items}",
                    f"- Items needing changes: {changes}",
                ]

                preview = [
                    f"{entry['current_name']} → {entry['proposed_name']}"
                    for entry in result.get("plan", []) if entry.get("needs_change")
                ][:5]
                if preview:
                    detail_lines.append("\n**Example changes:**")
                    for line in preview:
                        detail_lines.append(f"  - {line}")

                details = "\n".join(detail_lines)
                return self._format_with_reply(
                    message=message,
                    details=details,
                    artifacts=[folder_path] if folder_path else [],
                    status="info",
                    session_id=session_id,
                )

            if "summary" in result and "plan" in result and "success" in result:
                summary = result.get("summary", {})
                folder_path = result.get("folder_path", "")
                message = (
                    f"Organized files by type in `{Path(folder_path).name}`."
                    if folder_path else "Organized files by type."
                )
                if result.get("dry_run", True):
                    message = "Generated file-type organization plan (dry run)."

                detail_lines = [
                    f"- Files considered: {summary.get('total_files_considered', 0)}",
                    f"- Files moved: {summary.get('files_moved', 0)}",
                    f"- Files skipped: {summary.get('files_skipped', 0)}",
                    f"- Target folders: {', '.join(summary.get('target_folders', []))}"
                ]

                errors = result.get("errors") or []
                if errors:
                    detail_lines.append("\n**Errors:**")
                    for error in errors[:5]:
                        detail_lines.append(f"  - {error.get('file')}: {error.get('error')}")

                details = "\n".join(detail_lines)
                status = "partial_success" if errors else "success"

                return self._format_with_reply(
                    message=message,
                    details=details,
                    artifacts=[folder_path] if folder_path else [],
                    status=status,
                    session_id=session_id,
                )

            if "success" in result and "applied" in result and "skipped" in result:
                folder_path = result.get("folder_path", "")
                dry_run = result.get("dry_run", True)
                message = "Validated rename plan (dry run)." if dry_run else "Applied rename plan."

                detail_lines = [
                    f"- Applied: {len(result.get('applied', []))}",
                    f"- Skipped: {len(result.get('skipped', []))}",
                    f"- Errors: {len(result.get('errors', []))}",
                ]

                applied = result.get("applied", [])[:5]
                if applied:
                    detail_lines.append("\n**Sample changes:**")
                    for item in applied:
                        current = item.get("current_name") or item.get("file")
                        proposed = item.get("proposed_name") or item.get("target_path")
                        detail_lines.append(f"  - {current} → {proposed}")

                details = "\n".join(detail_lines)
                status = "partial_success" if result.get("errors") else "success"

                return self._format_with_reply(
                    message=message,
                    details=details,
                    artifacts=[folder_path] if folder_path else [],
                    status=status,
                    session_id=session_id,
                )

        except Exception as exc:
            logger.warning(f"[SLASH COMMAND] Failed to format folder result: {exc}", exc_info=True)

        return None

    def _format_with_reply(
        self,
        message: str,
        details: Optional[str],
        artifacts: Optional[List[str]],
        status: str = "success",
        session_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Invoke the reply_to_user tool to produce a consistent payload.
        """
        try:
            payload = {
                "message": message,
                "details": details or "",
                "artifacts": [artifact for artifact in (artifacts or []) if artifact],
                "status": status,
            }
            reply = self.registry.execute_tool("reply_to_user", payload, session_id=session_id)
            if reply.get("error"):
                logger.warning(f"[SLASH COMMAND] reply_to_user returned error: {reply}")
                return None
            return reply
        except Exception as exc:
            logger.warning(f"[SLASH COMMAND] Failed to call reply_to_user: {exc}")
            return None

    def _extract_folder_path(self, task: str) -> Optional[str]:
        """Attempt to extract a folder path from the user's task string."""
        if not task:
            return None

        quoted = re.search(r'["\']([^"\']+)["\']', task)
        if quoted:
            return quoted.group(1).strip()

        absolute = re.search(r'\s(/[^"\']+)', task)
        if absolute:
            candidate = absolute.group(1).strip()
            return candidate.rstrip('.,')

        return None

    def _get_llm_response_for_blocked_search(self, query: str, agent) -> str:
        """
        Get an LLM response when DuckDuckGo search is unavailable.

        Uses general knowledge to provide helpful information about the query.

        Args:
            query: The search query
            agent: Agent instance (to get config for API key)

        Returns:
            Response string from LLM
        """
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import SystemMessage, HumanMessage
            
            # Get API key
            api_key = None
            if hasattr(agent, 'config'):
                api_key = agent.config.get("openai", {}).get("api_key")
            if not api_key:
                import os
                api_key = os.getenv("OPENAI_API_KEY")
            
            if not api_key:
                return f"I searched Google for '{query}', but Google appears to be blocking automated requests. Please try using /browse for browser-based search or visit Google Trends: https://trends.google.com"
            
            llm = ChatOpenAI(model="gpt-4o", temperature=0.7, api_key=api_key)
            
            # Create prompt for LLM to provide information
            prompt = f"""The user asked: "{query}"

DuckDuckGo search is currently blocked/not returning results. Based on your knowledge, please provide helpful information about this topic. 

If the query is about trending topics or current events, provide general information about what's typically trending, or explain that real-time trending data requires access to Google Trends or other live sources.

Be helpful and informative, but note that this is based on general knowledge rather than real-time search results."""

            messages = [
                SystemMessage(content="You are a helpful assistant that provides information when search results are unavailable. Be informative and helpful."),
                HumanMessage(content=prompt)
            ]
            
            response = llm.invoke(messages)
            return response.content.strip()
            
        except Exception as e:
            logger.warning(f"[SLASH COMMAND] Failed to get LLM response for blocked search: {e}")
            return (
                f"I attempted a DuckDuckGo search for '{query}', but automated access appears to be blocked. "
                "Please try using /browse for browser-based search or visit https://duckduckgo.com directly."
            )

    def _summarize_google_results(self, search_results: List[Dict], query: str, agent) -> Optional[str]:
        """
        Summarize DuckDuckGo search results using LLM.
        
        Args:
            search_results: List of search result dictionaries
            query: The search query
            agent: Agent instance (to get config for API key)
            
        Returns:
            Summary string, or None if summarization fails
        """
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import SystemMessage, HumanMessage
            
            # Get API key
            api_key = None
            if hasattr(agent, 'config'):
                api_key = agent.config.get("openai", {}).get("api_key")
            if not api_key:
                import os
                api_key = os.getenv("OPENAI_API_KEY")
            
            if not api_key:
                logger.warning("[SLASH COMMAND] No OpenAI API key found for summarization")
                return None
            
            llm = ChatOpenAI(model="gpt-4o", temperature=0.0, api_key=api_key)
            
            # Format results for LLM
            results_text = "\n\n".join([
                f"**{i+1}. {r.get('title', 'No title')}**\n"
                f"URL: {r.get('link', 'N/A')}\n"
                f"{r.get('snippet', 'No description')}"
                for i, r in enumerate(search_results[:5])  # Limit to top 5 results
            ])
            
            # Create summarization prompt
            summary_prompt = f"""Based on the following DuckDuckGo search results for "{query}", provide a concise summary of what's trending or what the key information is.

Search Results:
{results_text}

Please provide a clear, concise summary that answers the user's query. Focus on the most important and relevant information from the search results."""

            summary_messages = [
                SystemMessage(content="You are a helpful assistant that summarizes search results. Provide clear, concise summaries based on the search results provided."),
                HumanMessage(content=summary_prompt)
            ]
            
            summary_response = llm.invoke(summary_messages)
            summary = summary_response.content.strip()
            
            return summary
            
        except Exception as e:
            logger.warning(f"[SLASH COMMAND] Failed to summarize Google results: {e}")
            return None

    def _execute_agent_task(self, agent, agent_name: str, task: str) -> Dict[str, Any]:
        """
        Execute a task through an agent.

        This uses LLM to determine which tool to call and what parameters to use.

        Args:
            agent: Agent instance
            agent_name: Name of the agent
            task: User's task description

        Returns:
            Execution result
        """
        # Import here to avoid circular dependency
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        import json
        import re

        # Get agent's available tools
        tools = agent.get_tools()
        tool_names = [tool.name for tool in tools]

        # Use LLM to determine which tool and parameters
        # Get API key from agent's config if available
        api_key = None
        if hasattr(agent, 'config'):
            api_key = agent.config.get("openai", {}).get("api_key")
        if not api_key:
            import os
            api_key = os.getenv("OPENAI_API_KEY")
        llm = ChatOpenAI(model="gpt-4o", temperature=0.0, api_key=api_key)

        tool_descriptions = []
        for tool in tools:
            tool_descriptions.append(f"- {tool.name}: {tool.description}")

        prompt = f"""You are helping route a user task to the appropriate tool in the {agent_name} agent.

Available Tools:
{chr(10).join(tool_descriptions)}

User Task: "{task}"

Determine:
1. Which tool to use
2. What parameters to pass

Respond with JSON:
{{
  "tool": "tool_name",
  "parameters": {{"param1": "value1", "param2": "value2"}},
  "reasoning": "Why this tool and these parameters"
}}

IMPORTANT: Extract ALL parameters from the user's natural language task.
Use LLM reasoning to parse values from the task description."""

        try:
            messages = [
                SystemMessage(content="You route tasks to tools. Respond only with JSON."),
                HumanMessage(content=prompt)
            ]

            response = llm.invoke(messages)
            content = response.content.strip()

            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group()

            routing = json.loads(content)

            tool_name = routing["tool"]
            parameters = routing["parameters"]

            logger.info(f"[SLASH COMMAND] LLM selected: {tool_name}")
            logger.info(f"[SLASH COMMAND] Parameters: {parameters}")

            # Execute the tool
            result = agent.execute(tool_name, parameters)

            # Special handling for Google agent: summarize search results
            if agent_name == "google" and not result.get("error") and "results" in result:
                search_results = result.get("results", [])
                query = result.get("query", task)
                
                if search_results:
                    # We have results - summarize them
                    summary = self._summarize_google_results(search_results, query, agent)
                    if summary:
                        # Return summarized result
                        return {
                            "query": query,
                            "summary": summary,
                            "results": search_results,  # Keep original results for reference
                            "num_results": len(search_results),
                            "total_results": result.get("total_results", 0),
                            "search_time": result.get("search_time", 0)
                        }
                    # Return original result if summarization fails
                    return result
                else:
                    # No results even after browser fallback - use LLM to provide helpful information
                    # The Google agent already tried browser fallback, so if we're here, both methods failed
                    llm_response = self._get_llm_response_for_blocked_search(query, agent)
                    return {
                        "query": query,
                        "summary": llm_response,
                        "results": [],
                        "num_results": 0,
                        "total_results": 0,
                        "search_type": result.get("search_type", "web"),
                        "note": "Both DuckDuckGo search attempts failed, but I've provided information based on your query."
                    }

            return result

        except Exception as e:
            logger.error(f"[SLASH COMMAND] Routing error: {e}")
            # Fallback: try first tool with task as content
            if tools:
                fallback_tool = tools[0].name
                logger.info(f"[SLASH COMMAND] Falling back to: {fallback_tool}")
                result = agent.execute(fallback_tool, {"query": task})
                
                # Apply Google summarization to fallback result too
                if agent_name == "google" and not result.get("error") and "results" in result:
                    search_results = result.get("results", [])
                    if search_results:
                        summary = self._summarize_google_results(search_results, task, agent)
                        if summary:
                            return {
                                "query": task,
                                "summary": summary,
                                "results": search_results,
                                "num_results": len(search_results),
                                "total_results": result.get("total_results", 0),
                                "search_time": result.get("search_time", 0)
                            }
                    else:
                        # No results - use LLM to provide helpful information
                        llm_response = self._get_llm_response_for_blocked_search(task, agent)
                        return {
                            "query": task,
                            "summary": llm_response,
                            "results": [],
                            "num_results": 0,
                            "total_results": 0,
                            "search_type": result.get("search_type", "web"),
                            "note": "DuckDuckGo search was blocked, but I've provided information based on your query."
                        }
                
                return result
            else:
                return {
                    "error": True,
                    "error_message": f"No tools available in {agent_name} agent"
                }


# Convenience function
def create_slash_command_handler(agent_registry, session_manager=None):
    """
    Create a slash command handler.

    Args:
        agent_registry: AgentRegistry instance
        session_manager: Optional SessionManager for /clear command

    Returns:
        SlashCommandHandler instance
    """
    return SlashCommandHandler(agent_registry, session_manager)
