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
    /recurring <schedule>   - Schedule recurring tasks (e.g., weekly reports)
    /help [command]         - Show help for commands
    /agents                 - List all available agents
    /                      - Show slash command palette
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import re

logger = logging.getLogger(__name__)


def get_demo_documents_root(config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Get the demo documents root directory from config.

    This returns the first configured document folder, which should be
    the test_docs directory for demo purposes.

    Args:
        config: Configuration dictionary (optional)

    Returns:
        Path to test documents directory, or None if not configured
    """
    if not config:
        return None

    # Try documents.folders[0] first
    folders = config.get("documents", {}).get("folders", [])
    if folders:
        return folders[0]

    # Fallback to document_directory (legacy)
    return config.get("document_directory")


def _extract_quoted_text(text: str) -> Optional[str]:
    """Extract first quoted substring from text."""
    match = re.search(r'"([^"]+)"', text)
    if match:
        return match.group(1)
    match = re.search(r"'([^']+)'", text)
    if match:
        return match.group(1)
    return None


def _extract_ticker(text: str) -> Optional[str]:
    """Extract stock ticker symbol from text (uppercase letters, typically 1-5 chars)."""
    # Look for uppercase letter sequences that look like tickers
    ticker_match = re.search(r'\b([A-Z]{1,5})\b', text)
    if ticker_match:
        candidate = ticker_match.group(1)
        # Common tickers are 1-5 uppercase letters
        if 1 <= len(candidate) <= 5 and candidate.isalpha():
            return candidate
    return None


def _extract_time_window(text: str) -> Optional[Dict[str, int]]:
    """Extract time window from text (hours or minutes)."""
    text_lower = text.lower()
    
    # Hours pattern: "last 2 hours", "past 1 hour", "24h", "12 hours"
    hours_match = re.search(r'(?:last|past|in|for)\s+(\d+)\s*(?:hours?|hrs?|hr|h)\b', text_lower)
    if hours_match:
        return {"hours": int(hours_match.group(1))}
    
    # Minutes pattern: "last 30 minutes", "past 15 mins"
    minutes_match = re.search(r'(?:last|past|in|for)\s+(\d+)\s*(?:minutes?|mins?|min|m)\b', text_lower)
    if minutes_match:
        return {"minutes": int(minutes_match.group(1))}
    
    # Short form: "1h", "2h", "30m"
    short_hours = re.search(r'\b(\d+)\s*h\b', text_lower)
    if short_hours:
        return {"hours": int(short_hours.group(1))}
    
    short_minutes = re.search(r'\b(\d+)\s*m\b', text_lower)
    if short_minutes:
        return {"minutes": int(short_minutes.group(1))}
    
    return None


def _extract_count(text: str, default: int = 10) -> int:
    """Extract count/number from text (e.g., "latest 5", "10 emails")."""
    # Pattern: "latest 5", "recent 10", "first 3"
    count_match = re.search(r'\b(latest|recent|first|last|top|next)\s+(\d+)\b', text.lower())
    if count_match:
        return int(count_match.group(2))
    
    # Pattern: "5 emails", "10 messages"
    direct_count = re.search(r'\b(\d+)\s+(?:emails?|messages?|items?|results?|posts?|tweets?)\b', text.lower())
    if direct_count:
        return int(direct_count.group(1))
    
    # Pattern: just a number at the start
    number_start = re.match(r'^(\d+)', text.strip())
    if number_start:
        return int(number_start.group(1))
    
    return default


def _strip_command_verbs(text: str, verbs: List[str]) -> str:
    """Strip command verbs from text (e.g., 'say', 'post', 'tweet' -> message text)."""
    text_lower = text.lower()
    for verb in verbs:
        # Match verb at start followed by space/colon/dash
        pattern = rf'^{re.escape(verb)}\s*[:-\s]+(.+)$'
        match = re.match(pattern, text_lower)
        if match:
            return match.group(1).strip()
        # Also match verb at start with just space
        if text_lower.startswith(verb + ' '):
            return text[len(verb):].strip()
    return text.strip()


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
        "weather": "weather",
        "forecast": "weather",
        "notes": "notes",
        "note": "notes",
        "reminders": "reminders",
        "reminder": "reminders",
        "remind": "reminders",
        "calendar": "calendar",
        "cal": "calendar",
        "recurring": "recurring",
        "schedule": "recurring",
    }

    # Special system commands (not agent-related)
    SYSTEM_COMMANDS = ["help", "agents", "clear", "recurring"]
    
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
        {"command": "/weather", "label": "Weather", "description": "Get weather forecasts"},
        {"command": "/notes", "label": "Notes", "description": "Create and manage Apple Notes"},
        {"command": "/remind", "label": "Reminders", "description": "Create time-based reminders"},
        {"command": "/calendar", "label": "Calendar", "description": "List events & prepare meeting briefs"},
        {"command": "/recurring", "label": "Recurring Tasks", "description": "Schedule weekly/daily automated tasks"},
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
        "weather": "Get weather forecasts for locations and timeframes (today, tomorrow, week)",
        "notes": "Create, append, and read notes in Apple Notes (persistent storage)",
        "reminders": "Create and manage time-based reminders in Apple Reminders",
        "calendar": "Read calendar events and generate meeting briefs from indexed documents",
        "recurring": "Schedule recurring automated tasks (weekly reports, daily summaries, etc.)",
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
            '/folder List files',
            '/folder Explain files',
            '/folder organize alpha',
            '/organize music files',
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
            '/spotify play Viva la Vida',
            '/spotify play Viva la something',
            '/spotify play that song called Viva la something',
            '/spotify status',
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
        "weather": [
            '/weather today',
            '/weather NYC tomorrow',
            '/weather "San Francisco" week',
            '/forecast LA 3day',
        ],
        "notes": [
            '/notes create "Meeting Notes" with body "Discussed Q4 plans"',
            '/notes append "Daily Journal" with "Today was productive"',
            '/notes read "Project Ideas"',
        ],
        "reminders": [
            '/remind "Bring umbrella" at 7am',
            '/remind "Call mom" tomorrow at 5pm',
            '/reminders complete "Bring umbrella"',
        ],
        "calendar": [
            '/calendar List my upcoming events',
            '/calendar prep for Q4 Review meeting',
            '/calendar brief docs for Team Standup',
            '/calendar details for "Project Kickoff"',
        ],
        "recurring": [
            '/recurring Create a weekly screen time report and email it every Friday',
            '/recurring Generate a daily summary of my files every day at 9am',
            '/schedule Send me a weekly summary of my documents every Monday',
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

        # Allow escaping paths: // at the start means "not a command"
        if message.strip().startswith('//'):
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
                # Only treat as a command if it's in our known command map
                if command not in self.COMMAND_MAP:
                    # Unknown token - let it fall through to orchestrator
                    return None

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

            # Invalid format, but not necessarily a slash command - could be a path
            return None

        command = match.group(1).lower()
        task = match.group(2).strip()

        # Only treat as a command if it's in our known command map
        if command not in self.COMMAND_MAP:
            # Unknown token - let it fall through to orchestrator
            return None

        # Map command to agent
        agent = self.COMMAND_MAP.get(command)

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

    def __init__(self, agent_registry, session_manager=None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize handler with agent registry.

        Args:
            agent_registry: AgentRegistry instance with all agents
            session_manager: Optional SessionManager for /clear command
            config: Configuration dictionary for demo constraints
        """
        self.registry = agent_registry
        self.session_manager = session_manager
        self.config = config or {}
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

        if parsed["command"] == "recurring" or parsed["agent"] == "recurring":
            return True, {
                "type": "recurring",
                "content": "Scheduling recurring task...",
                "task": parsed.get("task", ""),
                "raw_command": message
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

            # Format post results with friendly message
            if mode == "post" and isinstance(result, dict):
                if result.get("success") and not result.get("error"):
                    # Successful post
                    message_text = params.get("message", "")
                    # Truncate long messages for display
                    display_text = message_text if len(message_text) <= 100 else message_text[:97] + "..."
                    result["message"] = f'Posted to Bluesky: "{display_text}"'
                elif result.get("error"):
                    # Post failed
                    error_msg = result.get("error_message") or result.get("error") or "Unknown error"
                    result["message"] = f"Failed to post to Bluesky: {error_msg}"

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
            # Use deterministic routing for all commands
            demo_root_message = None
            tool_name = None
            params = {}
            status_msg = None
            routing_attempted = False
            
            # Route based on agent name
            if agent_name == "file" and task:
                routing_attempted = True
                tool_name, params, demo_root_message = self._route_files_command(task)
            elif agent_name == "folder" and task:
                routing_attempted = True
                tool_name, params, demo_root_message = self._route_folder_command(task)
            elif agent_name == "google" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_google_command(task)
            elif agent_name == "browser" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_browser_command(task)
            elif agent_name == "presentation" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_present_command(task)
            elif agent_name == "email" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_email_command(task)
            elif agent_name == "writing" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_write_command(task)
            elif agent_name == "maps" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_maps_command(task)
            elif agent_name == "google_finance" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_stock_command(task)
            elif agent_name == "imessage" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_messaging_command(task, "imessage")
            elif agent_name == "whatsapp" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_messaging_command(task, "whatsapp")
            elif agent_name == "discord" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_messaging_command(task, "discord")
            elif agent_name == "reddit" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_messaging_command(task, "reddit")
            elif agent_name == "twitter" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_messaging_command(task, "twitter")
            # Note: Bluesky is handled above with _parse_bluesky_task, so skip here
            elif agent_name == "report" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_report_command(task)
            elif agent_name == "notifications" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_notify_command(task)
            elif agent_name == "spotify" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_spotify_command(task)
            elif agent_name == "weather" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_weather_command(task)
            elif agent_name == "notes" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_notes_command(task)
            elif agent_name == "reminders" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_reminders_command(task)
            elif agent_name == "calendar" and task:
                routing_attempted = True
                tool_name, params, status_msg = self._route_calendar_command(task)

            # Execute deterministic routing if we have a tool_name
            if tool_name:
                logger.info(f"[SLASH COMMAND] Deterministic routing: {tool_name} with params {params}")
                try:
                    result = self.registry.execute_tool(tool_name, params, session_id=session_id)
                    
                    # Add status message if present
                    if status_msg and isinstance(result, dict):
                        if result.get("message"):
                            result["message"] = f"{status_msg}\n\n{result['message']}"
                        else:
                            result["message"] = status_msg
                except Exception as e:
                    logger.error(f"[SLASH COMMAND] Tool execution error: {e}", exc_info=True)
                    # Fall back to orchestrator on tool execution error
                    return True, {
                        "type": "retry_with_orchestrator",
                        "content": f"⚠ Direct /{parsed['command']} execution encountered an issue. Let me try routing through the main assistant...",
                        "original_message": message,
                        "error": str(e)
                    }
            elif routing_attempted and tool_name is None:
                # Routing function was called but returned None - use orchestrator
                logger.info(f"[SLASH COMMAND] Routing returned None, using orchestrator")
                return True, {
                    "type": "retry_with_orchestrator",
                    "content": None,  # Silent fallback
                    "original_message": message
                }
            else:
                # For commands without deterministic routing or special cases, use agent-based execution
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
                    # Execute through agent using LLM routing
                    result = self._execute_agent_task(agent, agent_name, task)

            formatted_result = result

            if isinstance(result, dict) and not result.get("error"):
                # Add demo root message if present
                if demo_root_message:
                    # Prepend demo root message to the result message
                    if formatted_result.get("message"):
                        formatted_result["message"] = f"{demo_root_message}\n\n{formatted_result['message']}"
                    elif isinstance(formatted_result, dict) and not formatted_result.get("type") == "reply":
                        # If no message yet, create one with demo root info
                        formatted_result["message"] = demo_root_message
                
                # Format RAG pipeline results
                if result.get("rag_pipeline"):
                    reply_payload = self._format_rag_result(result, task, session_id=session_id)
                    if reply_payload:
                        formatted_result = reply_payload
                        formatted_result.setdefault("_raw_result", result)
                        # Add demo root message to formatted reply
                        if demo_root_message and formatted_result.get("message"):
                            formatted_result["message"] = f"{demo_root_message}\n\n{formatted_result['message']}"
                elif original_agent == "folder":
                    reply_payload = self._format_folder_result(result, task, session_id=session_id)
                    if reply_payload:
                        formatted_result = reply_payload
                        formatted_result.setdefault("_raw_result", result)
                        # Add demo root message to formatted reply
                        if demo_root_message and formatted_result.get("message"):
                            formatted_result["message"] = f"{demo_root_message}\n\n{formatted_result['message']}"
                if formatted_result is result:
                    generic_reply = self._format_generic_reply(
                        agent_name=agent_name,
                        command=parsed["command"],
                        task=task,
                        result=result,
                        session_id=session_id,
                    )
                    if generic_reply:
                        formatted_result = generic_reply
                        formatted_result.setdefault("_raw_result", result)
                        # Add demo root message to generic reply
                        if demo_root_message and formatted_result.get("message"):
                            formatted_result["message"] = f"{demo_root_message}\n\n{formatted_result['message']}"
            elif not isinstance(result, dict):
                generic_reply = self._format_generic_reply(
                    agent_name=agent_name,
                    command=parsed["command"],
                    task=task,
                    result=result,
                    session_id=session_id,
                )
                if generic_reply:
                    generic_reply.setdefault("_raw_result", result)
                    formatted_result = generic_reply

            return True, {
                "type": "result",
                "agent": agent_name,
                "original_agent": original_agent,
                "command": parsed["command"],
                "result": formatted_result,
                "raw": result
            }

        except Exception as e:
            logger.error(f"[SLASH COMMAND] Error executing /{parsed['command']}: {e}", exc_info=True)

            # Check if this is a "tool not found" or "missing params" error that should retry
            error_str = str(e).lower()
            should_retry = any(phrase in error_str for phrase in [
                "tool not found",
                "missing parameter",
                "permission denied",
                "not found",
                "does not exist"
            ])

            if should_retry:
                # Return a friendly error suggesting the orchestrator will retry
                return True, {
                    "type": "retry_with_orchestrator",
                    "content": f"⚠ Direct /{parsed['command']} execution encountered an issue. Let me try routing through the main assistant...",
                    "original_message": message,
                    "error": str(e)
                }
            else:
                # Return regular error
                return True, {
                    "type": "error",
                    "content": f"❌ Error executing /{parsed['command']}: {str(e)}"
                }

    def _parse_bluesky_task(self, task: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parse a /bluesky command task to determine mode and parameters.
        Returns (mode, params) where mode is 'search', 'summary', or 'post'.

        Intent detection:
        1. Explicit verbs (post, say, tweet, announce) → post mode
        2. Short free-form text (≤128 chars, no search/summary keywords) → post mode
        3. Time/window hints (last, hour, day) → summary mode
        4. Search keywords or longer text → search mode
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

        # 1. Explicit posting verbs
        posting_verbs = ["post", "publish", "send", "tweet", "say", "announce"]
        for verb in posting_verbs:
            if lower.startswith(verb + " ") or lower.startswith(verb + ":"):
                # Strip the verb and any separator (space, colon, dash)
                message = text[len(verb):].strip()
                if message.startswith(":"):
                    message = message[1:].strip()
                if message.startswith("-"):
                    message = message[1:].strip()

                if not message:
                    raise ValueError(f"Provide a message to post, e.g. /bluesky {verb} \"Hello Bluesky\"")

                # Extract from quotes if present
                quoted = _extract_quoted_text(message)
                if quoted:
                    message = quoted

                return "post", {"message": message.strip()}

        # 2. Short free-form text heuristic (post mode)
        # If text is short (≤128 chars) and doesn't contain explicit keywords, treat as post
        search_keywords = ["search", "find", "lookup", "scan", "query"]
        summary_keywords = ["summarize", "summary", "analyze", "last", "recent"]
        has_search_keyword = any(kw in lower for kw in search_keywords)
        has_summary_keyword = any(kw in lower for kw in summary_keywords)

        if len(text) <= 128 and not has_search_keyword and not has_summary_keyword:
            # Likely a post - short, natural language without explicit mode keywords
            return "post", {"message": text}

        # 3. Time/window hints - summary mode
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

        # Explicit summaries
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

    def _format_rag_result(
        self,
        result: Dict[str, Any],
        task: str,
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Format RAG pipeline results for user-facing display.
        """
        try:
            summary = result.get("summary") or result.get("message", "")
            doc_title = result.get("doc_title", "Unknown Document")
            word_count = result.get("word_count", 0)
            
            if not summary:
                return None
            
            # Format as a readable summary
            message = f"## Summary: {doc_title}\n\n{summary}"
            if word_count > 0:
                message += f"\n\n*Summary length: {word_count} words*"
            
            return {
                "type": "rag_summary",
                "message": message,
                "summary": summary,
                "doc_title": doc_title,
                "doc_path": result.get("doc_path"),
                "word_count": word_count,
                "rag_pipeline": True  # Preserve RAG pipeline flag
            }
        except Exception as e:
            logger.error(f"[SLASH COMMAND] Error formatting RAG result: {e}")
            return None

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

    def _format_generic_reply(
        self,
        agent_name: str,
        command: str,
        task: str,
        result: Any,
        *,
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a reply_to_user payload for generic agent results.
        """
        if not isinstance(result, dict):
            message = str(result)
            return self._format_with_reply(
                message=message or f"Completed {command} command.",
                details="",
                artifacts=[],
                session_id=session_id
            )

        if result.get("type") == "reply":
            return result

        message = (
            result.get("message")
            or result.get("summary")
            or result.get("content")
            or result.get("response")
            or ""
        )

        if not message:
            fallback_task = task or command or agent_name
            message = f"Completed {fallback_task}."

        details = ""
        if isinstance(result.get("details"), str):
            details = result["details"]

        artifacts: List[str] = []
        artifact_keys = [
            "document_path",
            "file_path",
            "zip_path",
            "output_path",
            "maps_url",
            "presentation_path",
            "report_path",
        ]
        for key in artifact_keys:
            value = result.get(key)
            if isinstance(value, str):
                artifacts.append(value)

        status = "error" if result.get("error") else result.get("status", "success")

        return self._format_with_reply(
            message=message,
            details=details,
            artifacts=artifacts,
            status=status,
            session_id=session_id,
        )

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

    def _route_files_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Deterministically route /files commands to appropriate tools.

        Args:
            task: User task string

        Returns:
            Tuple of (tool_name, parameters, demo_root_message)
            demo_root_message is None if user specified a path, otherwise contains the demo root path message
        """
        task_lower = task.lower().strip()
        demo_root = get_demo_documents_root(self.config)
        user_specified_path = self._extract_folder_path(task)
        demo_root_message = None
        
        # If no path specified and demo root exists, use it and prepare message
        if not user_specified_path and demo_root:
            demo_root_message = f"Working in {demo_root}..."

        # RAG/summarize keywords
        if any(kw in task_lower for kw in ["summarize", "summarise", "summary", "explain", "describe", "what is", "tell me about"]):
            # Extract topic from task
            import re
            rag_keywords_pattern = r'\b(summarize|summarise|summary|explain|describe|what is|tell me about)\b'
            topic = re.sub(rag_keywords_pattern, '', task, flags=re.IGNORECASE).strip()
            topic = re.sub(r'\b(the|my|files|docs|documents|file|doc)\b', '', topic, flags=re.IGNORECASE).strip()

            return "search_documents", {
                "query": topic or task,
                "user_request": task,
                "source_path": demo_root
            }, demo_root_message

        # Organize files
        if any(kw in task_lower for kw in ["organize", "sort", "arrange"]):
            return "organize_files", {
                "folder_path": demo_root or user_specified_path,
                "organization_type": "type"
            }, demo_root_message

        # Create ZIP
        if any(kw in task_lower for kw in ["zip", "compress", "archive"]):
            return "create_zip_archive", {
                "source_path": demo_root or user_specified_path,
                "archive_name": "archive.zip"
            }, demo_root_message

        # Screenshot
        if any(kw in task_lower for kw in ["screenshot", "capture", "snap"]):
            return "take_screenshot", {
                "save_path": "data/screenshots"
            }, None

        # List/show all files matching query
        listing_keywords = ["show all", "list all", "pull up all", "find all"]
        if any(kw in task_lower for kw in listing_keywords) or \
           (task_lower.startswith("all ") and "files" in task_lower):
            # Extract query by removing listing keywords
            import re
            listing_pattern = r'\b(show all|list all|pull up all|find all|all)\b'
            query = re.sub(listing_pattern, '', task, flags=re.IGNORECASE).strip()
            query = re.sub(r'\b(files|file|docs|documents|doc)\b', '', query, flags=re.IGNORECASE).strip()
            
            return "list_related_documents", {
                "query": query or task,
                "max_results": 10
            }, demo_root_message

        # Default: search documents
        return "search_documents", {
            "query": task,
            "user_request": task,
            "source_path": demo_root
        }, demo_root_message

    def _route_folder_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Deterministically route /folder commands to appropriate tools.

        Args:
            task: User task string

        Returns:
            Tuple of (tool_name, parameters, demo_root_message)
            demo_root_message is None if user specified a path, otherwise contains the demo root path message
        """
        task_lower = task.lower().strip()
        demo_root = get_demo_documents_root(self.config)
        user_specified_path = self._extract_folder_path(task)
        folder_path = user_specified_path or demo_root
        demo_root_message = None
        
        # If no path specified and demo root exists, use it and prepare message
        if not user_specified_path and demo_root:
            demo_root_message = f"Working in {demo_root}..."

        # List files
        if any(kw in task_lower for kw in ["list", "show", "display"]) or not task_lower:
            return "folder_list", {"folder_path": folder_path}, demo_root_message

        # Organize files
        if any(kw in task_lower for kw in ["organize", "sort", "arrange"]):
            return "folder_organize_by_type", {"folder_path": folder_path, "dry_run": True}, demo_root_message

        # Rename/normalize
        if any(kw in task_lower for kw in ["rename", "normalize", "alpha"]):
            return "folder_normalize_names", {"folder_path": folder_path, "dry_run": True}, demo_root_message

        # Default: list
        return "folder_list", {"folder_path": folder_path}, demo_root_message

    def _route_google_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Deterministically route /google or /search commands to google_search tool.
        
        Args:
            task: User task string
            
        Returns:
            Tuple of (tool_name, parameters, status_msg)
        """
        task_lower = task.lower().strip()
        
        # Extract query - remove command-like prefixes
        query = task.strip()
        query = re.sub(r'^(search|find|lookup|query)\s+', '', query, flags=re.IGNORECASE)
        
        # Extract number of results if specified
        num_results = _extract_count(task, default=5)
        
        return "google_search", {
            "query": query,
            "num_results": num_results
        }, None

    def _route_browser_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Deterministically route /browse commands to browser tools.
        
        Args:
            task: User task string
            
        Returns:
            Tuple of (tool_name, parameters, status_msg)
        """
        task_lower = task.lower().strip()
        
        # Check for URL patterns
        url_pattern = re.compile(r'https?://[^\s]+|www\.[^\s]+|[a-z0-9-]+\.[a-z]{2,}/[^\s]*')
        url_match = url_pattern.search(task)
        
        if url_match:
            url = url_match.group(0)
            # Normalize URL
            if not url.startswith('http'):
                url = 'https://' + url
            
            # Check for screenshot request
            if any(kw in task_lower for kw in ["screenshot", "capture", "snap"]):
                return "take_web_screenshot", {
                    "url": url,
                    "full_page": "full" in task_lower or "entire" in task_lower
                }, None
            
            # Check for extract content
            if any(kw in task_lower for kw in ["extract", "get content", "read", "content"]):
                return "extract_page_content", {
                    "url": url
                }, None
            
            # Default: navigate to URL
            return "navigate_to_url", {
                "url": url
            }, None
        
        # Check for search request
        if any(kw in task_lower for kw in ["search", "find", "lookup"]):
            query = re.sub(r'^(search|find|lookup)\s+', '', task, flags=re.IGNORECASE).strip()
            return "google_search", {
                "query": query,
                "num_results": _extract_count(task, default=5)
            }, None
        
        # Check for close browser
        if any(kw in task_lower for kw in ["close", "quit", "exit"]):
            return "close_browser", {}, None
        
        # Default: treat as search query
        return "google_search", {
            "query": task,
            "num_results": 5
        }, None

    def _route_present_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Deterministically route /present commands to presentation tools.
        
        Args:
            task: User task string
            
        Returns:
            Tuple of (tool_name, parameters, status_msg)
        """
        task_lower = task.lower().strip()
        
        # Extract title and content from task
        # Pattern: "Create a Keynote about X" or "Make a Pages document with Y"
        title_match = re.search(r'(?:about|on|for|titled?)\s+([^,]+?)(?:\s+with|\s+containing|$)', task_lower)
        title = title_match.group(1).strip() if title_match else "Presentation"
        
        # Check for Pages document
        if any(kw in task_lower for kw in ["pages", "document", "doc"]):
            # Extract content description
            content_desc = re.sub(r'^(create|make|generate)\s+(?:a\s+)?pages?\s+(?:document|doc)?\s*', '', task_lower, flags=re.IGNORECASE)
            content_desc = re.sub(r'\s+with\s+.+$', '', content_desc).strip()
            
            return "create_pages_doc", {
                "title": title,
                "content": content_desc or task
            }, None
        
        # Check for Keynote/slides
        if any(kw in task_lower for kw in ["keynote", "slides", "presentation", "deck"]):
            # Extract content description
            content_desc = re.sub(r'^(create|make|generate)\s+(?:a\s+)?(?:keynote|slides?|presentation|deck)?\s*', '', task_lower, flags=re.IGNORECASE)
            content_desc = re.sub(r'\s+about\s+.+$', '', content_desc).strip()
            
            # Check if we need slide deck content first
            if len(content_desc) > 200 or any(kw in task_lower for kw in ["detailed", "comprehensive", "multiple"]):
                # Use create_slide_deck_content first, then create_keynote
                # For now, route to create_keynote with content
                return "create_keynote", {
                    "title": title,
                    "content": content_desc or task
                }, None
            
            return "create_keynote", {
                "title": title,
                "content": content_desc or task
            }, None
        
        # Default: Keynote
        return "create_keynote", {
            "title": title,
            "content": task
        }, None

    def _route_email_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Route /email commands to email tools.

        Simple queries (single tool, clear parameters) use deterministic routing for performance.
        Complex queries (summarization, multi-step workflows) delegate to orchestrator for LLM planning.

        Args:
            task: User task string

        Returns:
            Tuple of (tool_name, parameters, status_msg)
            Returns (None, {}, None) for complex queries that need LLM planning via orchestrator
        """
        task_lower = task.lower().strip()

        # COMPLEX QUERIES: Delegate to orchestrator for LLM-driven planning
        # These require multi-step workflows (read + summarize) that benefit from LLM planning

        # Summarization queries - require reading emails first, then summarizing
        if any(kw in task_lower for kw in ["summarize", "summary", "summarise"]):
            logger.info(f"[SLASH COMMAND] Email summarization query detected, delegating to orchestrator: {task}")

            # Extract intent hints for the planner
            intent_hints = {
                "action": "summarize",
                "workflow": "email_summarization"
            }

            # Extract count (e.g., "last 3 emails", "5 emails")
            count = _extract_count(task, default=None)
            if count:
                intent_hints["count"] = count
                logger.info(f"[SLASH COMMAND] Extracted count hint: {count}")

            # Extract sender (e.g., "from john@example.com", "by John Doe")
            sender_match = re.search(r'(?:from|by|sent by)\s+([^\s]+@[^\s]+|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', task)
            if sender_match:
                sender = sender_match.group(1).strip()
                intent_hints["sender"] = sender
                logger.info(f"[SLASH COMMAND] Extracted sender hint: {sender}")

            # Extract time window (e.g., "last hour", "past 2 hours")
            time_window = _extract_time_window(task)
            if time_window:
                intent_hints["time_window"] = time_window
                logger.info(f"[SLASH COMMAND] Extracted time window hint: {time_window}")

            # Extract focus keywords (e.g., "action items", "deadlines")
            focus_keywords = ["action items", "deadlines", "important", "urgent", "key decisions", "updates"]
            for keyword in focus_keywords:
                if keyword in task_lower:
                    intent_hints["focus"] = keyword
                    logger.info(f"[SLASH COMMAND] Extracted focus hint: {keyword}")
                    break

            logger.info(f"[SLASH COMMAND] [EMAIL WORKFLOW] Intent hints extracted: {intent_hints}")

            # Return None to trigger orchestrator routing, which will use LLM to plan:
            # 1. Read emails (read_latest_emails, read_emails_by_sender, or read_emails_by_time)
            # 2. Summarize emails (summarize_emails)
            # The hints dictionary will be accessible to the planner as parsed["intent_hints"]
            return None, {"intent_hints": intent_hints}, None
        
        # Reply queries - complex, need to find original email first
        if any(kw in task_lower for kw in ["reply", "respond"]):
            logger.info(f"[SLASH COMMAND] Email reply query detected, delegating to orchestrator: {task}")
            # Return None to let LLM handle finding the original email and composing reply
            return None, {}, None
        
        # SIMPLE QUERIES: Deterministic routing for performance
        
        # Read latest emails (simple, single tool)
        if any(kw in task_lower for kw in ["read", "show", "get", "latest", "recent"]) and "summarize" not in task_lower:
            count = _extract_count(task, default=10)
            return "read_latest_emails", {
                "count": min(count, 50),  # Cap at 50
                "mailbox": "INBOX"
            }, None
        
        # Read by sender (simple, single tool, but only if not summarizing)
        sender_match = re.search(r'(?:from|by)\s+([^\s]+@[^\s]+|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', task_lower)
        if sender_match and "summarize" not in task_lower:
            sender = sender_match.group(1).strip()
            count = _extract_count(task, default=10)
            return "read_emails_by_sender", {
                "sender": sender,
                "count": min(count, 50)
            }, None
        
        # Read by time (simple, single tool, but only if not summarizing)
        time_window = _extract_time_window(task)
        if (time_window or any(kw in task_lower for kw in ["hour", "minute", "past", "last"])) and "summarize" not in task_lower:
            if time_window:
                return "read_emails_by_time", {
                    **time_window,
                    "mailbox": "INBOX"
                }, None
            else:
                # If time keywords present but no number extracted, delegate to orchestrator for LLM reasoning
                # This avoids hardcoding a default value
                logger.info(f"[SLASH COMMAND] Time keywords detected but no number found, delegating to orchestrator: {task}")
                return None, {}, None
        
        # Compose/draft email (simple, single tool if parameters are clear)
        if any(kw in task_lower for kw in ["compose", "draft", "write", "create", "send"]):
            # Extract recipient, subject, body
            recipient_match = re.search(r'(?:to|for)\s+([^\s]+@[^\s]+)', task_lower)
            recipient = recipient_match.group(1) if recipient_match else None
            
            subject_match = re.search(r'(?:subject|about|regarding)\s+["\']?([^"\']+)["\']?', task_lower)
            subject = subject_match.group(1) if subject_match else "Email"
            
            body_match = re.search(r'(?:body|message|content|saying)\s+["\'](.+)["\']', task_lower)
            body = body_match.group(1) if body_match else task
            
            send = "send" in task_lower and "draft" not in task_lower
            
            return "compose_email", {
                "subject": subject,
                "body": body,
                "recipient": recipient,
                "send": send
            }, None
        
        # Default: read latest (simple fallback)
        return "read_latest_emails", {
            "count": 10,
            "mailbox": "INBOX"
        }, None

    def _route_write_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Deterministically route /write commands to writing tools.
        
        Args:
            task: User task string
            
        Returns:
            Tuple of (tool_name, parameters, status_msg)
        """
        task_lower = task.lower().strip()
        
        # Meeting notes
        if any(kw in task_lower for kw in ["meeting", "notes", "minutes", "transcript"]):
            title_match = re.search(r'(?:for|about|titled?)\s+([^,]+?)(?:\s+with|\s+containing|$)', task_lower)
            title = title_match.group(1).strip() if title_match else "Meeting Notes"
            
            return "create_meeting_notes", {
                "content": task,
                "meeting_title": title,
                "include_action_items": True
            }, None
        
        # Report
        if any(kw in task_lower for kw in ["report", "detailed", "comprehensive", "analysis"]):
            title_match = re.search(r'(?:report|analysis|on|about)\s+([^,]+?)(?:\s+with|\s+containing|$)', task_lower)
            title = title_match.group(1).strip() if title_match else "Report"
            
            # Determine report style
            style = "business"
            if "academic" in task_lower or "research" in task_lower:
                style = "academic"
            elif "technical" in task_lower or "spec" in task_lower:
                style = "technical"
            elif "executive" in task_lower or "summary" in task_lower:
                style = "executive"
            
            return "create_detailed_report", {
                "content": task,
                "title": title,
                "report_style": style
            }, None
        
        # Slide deck content
        if any(kw in task_lower for kw in ["slides", "presentation", "deck", "keynote"]):
            title_match = re.search(r'(?:slides?|presentation|deck|keynote)\s+(?:about|on|for)?\s*([^,]+?)(?:\s+with|\s+containing|$)', task_lower)
            title = title_match.group(1).strip() if title_match else "Presentation"
            
            num_slides_match = re.search(r'(\d+)\s+slides?', task_lower)
            num_slides = int(num_slides_match.group(1)) if num_slides_match else None
            
            return "create_slide_deck_content", {
                "content": task,
                "title": title,
                "num_slides": num_slides
            }, None
        
        # Synthesize content (default)
        title_match = re.search(r'(?:about|on|for|titled?)\s+([^,]+?)(?:\s+with|\s+containing|$)', task_lower)
        title = title_match.group(1).strip() if title_match else "Content"
        
        return "synthesize_content", {
            "source_contents": [task],
            "topic": title,
            "synthesis_style": "comprehensive"
        }, None

    def _route_maps_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Deterministically route /maps commands to maps tools.
        
        Args:
            task: User task string
            
        Returns:
            Tuple of (tool_name, parameters, status_msg)
        """
        task_lower = task.lower().strip()
        
        # Extract origin and destination
        # Pattern: "from X to Y" or "X to Y"
        origin_dest_match = re.search(r'(?:from|between)\s+([^,]+?)\s+to\s+([^,]+)', task_lower)
        if not origin_dest_match:
            origin_dest_match = re.search(r'^([^,]+?)\s+to\s+([^,]+)', task_lower)
        
        if origin_dest_match:
            origin = origin_dest_match.group(1).strip()
            destination = origin_dest_match.group(2).strip()
            
            # Extract stops
            fuel_stops_match = re.search(r'(\d+)\s*(?:fuel|gas|gasoline)\s*stops?', task_lower)
            num_fuel_stops = int(fuel_stops_match.group(1)) if fuel_stops_match else 0
            
            food_stops_match = re.search(r'(\d+)\s*(?:food|meal|lunch|dinner|breakfast|restaurant)\s*stops?', task_lower)
            num_food_stops = int(food_stops_match.group(1)) if food_stops_match else 0
            
            # Extract departure time
            time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))|(\d{1,2}\s*(?:am|pm|AM|PM))', task_lower)
            departure_time = time_match.group(0) if time_match else None
            
            # Check for Google Maps preference
            use_google_maps = "google" in task_lower and "maps" in task_lower
            
            return "plan_trip_with_stops", {
                "origin": origin,
                "destination": destination,
                "num_fuel_stops": num_fuel_stops,
                "num_food_stops": num_food_stops,
                "departure_time": departure_time,
                "use_google_maps": use_google_maps,
                "open_maps": True
            }, None
        
        # Simple route opening
        if "open" in task_lower or "show" in task_lower:
            # Try to extract origin/destination from simpler patterns
            simple_match = re.search(r'([^,]+?)\s+to\s+([^,]+)', task_lower)
            if simple_match:
                return "open_maps_with_route", {
                    "origin": simple_match.group(1).strip(),
                    "destination": simple_match.group(2).strip(),
                    "start_navigation": "start" in task_lower or "navigate" in task_lower
                }, None
        
        # If we can't parse, return None to use orchestrator
        return None, {}, None

    def _route_stock_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Deterministically route /stock commands to stock tools.
        
        Args:
            task: User task string
            
        Returns:
            Tuple of (tool_name, parameters, status_msg)
        """
        task_lower = task.lower().strip()
        
        # Extract ticker
        ticker = _extract_ticker(task)
        if not ticker:
            # Try to find company name and convert to ticker
            # This is complex, so for now return None to use orchestrator
            return None, {}, None
        
        # Check for chart request
        if any(kw in task_lower for kw in ["chart", "graph", "history", "performance", "trend"]):
            # Extract period
            period = "1mo"  # default
            if "day" in task_lower or "today" in task_lower:
                period = "1d"
            elif "week" in task_lower:
                period = "5d"
            elif "month" in task_lower:
                period = "1mo"
            elif "year" in task_lower:
                period = "1y"
            
            # For charts, we'd need get_stock_chart - if not available, use get_stock_price
            # Check if tool exists by trying to route to it
            return "get_stock_price", {
                "symbol": ticker
            }, None
        
        # Default: get stock price
        return "get_stock_price", {
            "symbol": ticker
        }, None

    def _route_messaging_command(self, task: str, platform: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Deterministically route messaging commands (imessage/whatsapp/discord/reddit/twitter/bluesky).
        
        Args:
            task: User task string
            platform: Platform name (imessage, whatsapp, discord, reddit, twitter, bluesky)
            
        Returns:
            Tuple of (tool_name, parameters, status_msg)
        """
        task_lower = task.lower().strip()
        
        # Bluesky already has its own routing, but handle post case here too
        if platform == "bluesky":
            # Check for post/say verbs
            if any(kw in task_lower for kw in ["post", "say", "tweet", "publish", "send"]):
                message = _strip_command_verbs(task, ["post", "say", "tweet", "publish", "send"])
                quoted = _extract_quoted_text(message)
                if quoted:
                    message = quoted
                return "post_bluesky_update", {
                    "message": message or task
                }, None
        
        # For other platforms, detect read vs send
        # Read operations
        if any(kw in task_lower for kw in ["read", "show", "get", "list", "summarize"]):
            # Platform-specific read tools would go here
            # For now, return None to use orchestrator
            return None, {}, None
        
        # Send operations
        if any(kw in task_lower for kw in ["send", "post", "message", "text"]):
            # Extract recipient and message
            recipient_match = re.search(r'(?:to|for)\s+([^\s]+)', task_lower)
            recipient = recipient_match.group(1) if recipient_match else None
            
            message = _strip_command_verbs(task, ["send", "post", "message", "text"])
            message = re.sub(r'^(?:to|for)\s+[^\s]+\s+', '', message, flags=re.IGNORECASE).strip()
            quoted = _extract_quoted_text(message)
            if quoted:
                message = quoted
            
            # Platform-specific send tools
            if platform == "imessage":
                return "send_imessage", {
                    "message": message or task,
                    "recipient": recipient
                }, None
        
        # Default: return None to use orchestrator
        return None, {}, None

    def _route_report_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Deterministically route /report commands to report tools.
        
        Args:
            task: User task string
            
        Returns:
            Tuple of (tool_name, parameters, status_msg)
        """
        # Report command typically uses create_detailed_report
        # Extract topic/title
        title_match = re.search(r'(?:report|on|about)\s+([^,]+?)(?:\s+with|\s+containing|$)', task.lower())
        title = title_match.group(1).strip() if title_match else "Report"
        
        return "create_detailed_report", {
            "content": task,
            "title": title,
            "report_style": "business"
        }, None

    def _route_notify_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Deterministically route /notify commands to notification tools.
        
        Args:
            task: User task string
            
        Returns:
            Tuple of (tool_name, parameters, status_msg)
        """
        # Extract title and message
        # Pattern: "Task complete: Stock report is ready"
        colon_match = re.search(r'^([^:]+):\s*(.+)$', task)
        if colon_match:
            title = colon_match.group(1).strip()
            message = colon_match.group(2).strip()
        else:
            # Try "alert X" or "notification X"
            alert_match = re.search(r'^(?:alert|notification)\s+(.+)$', task, flags=re.IGNORECASE)
            if alert_match:
                title = "Notification"
                message = alert_match.group(1).strip()
            else:
                title = "Notification"
                message = task
        
        # Extract sound
        sound_match = re.search(r'sound\s+(\w+)', task.lower())
        sound = sound_match.group(1).capitalize() if sound_match else None
        
        # Extract subtitle
        subtitle_match = re.search(r'subtitle[:\s]+([^,]+)', task.lower())
        subtitle = subtitle_match.group(1).strip() if subtitle_match else None
        
        return "send_notification", {
            "title": title,
            "message": message,
            "sound": sound,
            "subtitle": subtitle
        }, None

    def _route_spotify_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Route /spotify or /music commands to Spotify tools.
        
        Routing Logic (Priority Order):
        1. Pause/Stop → pause_music (exact match: "pause", "stop")
        2. Status → get_spotify_status (contains: "status", "what", "current", "playing")
        3. Song Play → play_song (contains "play"/"start"/"resume" + song name)
        4. Simple Play → play_music (just "play"/"start"/"resume" without song name)
        5. Default → play_music
        
        Song Name Extraction:
        - Removes play keywords: "play", "start", "resume"
        - Removes natural language prefixes: "that song called", "the song", "song"
        - Preserves rest as song name (may be fuzzy/imprecise)
        
        Examples:
        - "/spotify pause" → ("pause_music", {}, None)
        - "/spotify play" → ("play_music", {}, None)
        - "/spotify play Viva la Vida" → ("play_song", {"song_name": "Viva la Vida"}, None)
        - "/spotify play Viva la something" → ("play_song", {"song_name": "Viva la something"}, None)
        - "/spotify play that song called Viva la something" → ("play_song", {"song_name": "Viva la something"}, None)
        - "/spotify status" → ("get_spotify_status", {}, None)
        - "/spotify what's playing" → ("get_spotify_status", {}, None)
        
        Args:
            task: User task string (e.g., "play Viva la Vida", "pause", "status")
            
        Returns:
            Tuple of (tool_name, parameters, status_msg)
            - tool_name: "play_music" | "pause_music" | "get_spotify_status" | "play_song"
            - parameters: Dict with tool-specific params (e.g., {"song_name": "..."} for play_song)
            - status_msg: Optional status message (None for Spotify commands)
        """
        task_lower = task.lower().strip()
        task_original = task.strip()
        
        # Priority 1: Check for pause/stop (exact match, highest priority)
        pause_pattern = re.match(r'^(pause|stop)$', task_lower)
        if pause_pattern:
            return "pause_music", {}, None
        
        # Priority 2: Check for status requests
        # Only match question-style phrases to avoid catching "start playing [song]"
        # Patterns: "what's playing", "what is playing", "currently playing", "status", etc.
        status_patterns = [
            r"^(what|which|who)\s+(is|'s|are)\s+(playing|current)",
            r"^(what|which|who)\s+(playing|current)",
            r"^status$",
            r"^current\s+(track|song|playing)",
            r"^now\s+playing",
        ]
        for pattern in status_patterns:
            if re.match(pattern, task_lower):
                return "get_spotify_status", {}, None
        
        # Also check if "playing" appears with question words (but not "play [song]")
        if "playing" in task_lower:
            # Check if it's a question-style phrase, not a play command
            question_words = ["what", "which", "who", "current", "now"]
            words_before_playing = task_lower.split("playing")[0].strip().split()
            # Check if any question word appears in the last 2 words before "playing"
            if words_before_playing:
                last_words = words_before_playing[-2:] if len(words_before_playing) >= 2 else words_before_playing
                if any(qw in last_words for qw in question_words):
                    return "get_spotify_status", {}, None
            # Also check for "what's" or "what is" before "playing"
            if "what" in task_lower and "playing" in task_lower:
                what_pos = task_lower.find("what")
                playing_pos = task_lower.find("playing")
                if what_pos < playing_pos:
                    return "get_spotify_status", {}, None
        
        # Priority 3: Check for song play requests
        # Pattern: play/start/resume + song name (more than just the keyword)
        play_keywords = ["play", "start", "resume"]
        play_match = re.search(r'\b(' + '|'.join(play_keywords) + r')\b', task_lower)
        
        if play_match:
            # Extract everything after the play keyword
            play_pos = play_match.end()
            after_play = task_original[play_pos:].strip()
            
            # Remove natural language prefixes
            natural_lang_patterns = [
                r"^that\s+song\s+called\s+",
                r"^the\s+song\s+",
                r"^song\s+",
                r"^track\s+",
            ]
            for pattern in natural_lang_patterns:
                after_play = re.sub(pattern, '', after_play, flags=re.IGNORECASE).strip()
            
            # If there's substantial content after "play", it's a song name
            if after_play and len(after_play) > 2:
                return "play_song", {"song_name": after_play}, None
        
        # Priority 4: Simple play without song name
        if play_match:
            return "play_music", {}, None
        
        # Priority 5: Default to play
        return "play_music", {}, None

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
            from ...utils import get_temperature_for_model

            # Get API key and config
            api_key = None
            config = {}
            if hasattr(agent, 'config'):
                config = agent.config
                api_key = config.get("openai", {}).get("api_key")
            if not api_key:
                import os
                api_key = os.getenv("OPENAI_API_KEY")

            if not api_key:
                return f"I searched Google for '{query}', but Google appears to be blocking automated requests. Please try using /browse for browser-based search or visit Google Trends: https://trends.google.com"

            model = config.get("openai", {}).get("model", "gpt-4o")
            temperature = get_temperature_for_model(config, default_temperature=0.7) if config else 0.7
            # Override for o-series models
            if model.startswith(("o1", "o3", "o4")):
                temperature = 1.0

            llm = ChatOpenAI(model=model, temperature=temperature, api_key=api_key)
            
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
            from ...utils import get_temperature_for_model

            # Get API key and config
            api_key = None
            config = {}
            if hasattr(agent, 'config'):
                config = agent.config
                api_key = config.get("openai", {}).get("api_key")
            if not api_key:
                import os
                api_key = os.getenv("OPENAI_API_KEY")

            if not api_key:
                logger.warning("[SLASH COMMAND] No OpenAI API key found for summarization")
                return None

            model = config.get("openai", {}).get("model", "gpt-4o")
            temperature = get_temperature_for_model(config, default_temperature=0.0) if config else 0.0
            # Override for o-series models
            if model.startswith(("o1", "o3", "o4")):
                temperature = 1.0

            llm = ChatOpenAI(model=model, temperature=temperature, api_key=api_key)
            
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
        # Get API key and config from agent if available
        from src.utils import get_temperature_for_model

        api_key = None
        config = {}
        if hasattr(agent, 'config'):
            config = agent.config
            api_key = config.get("openai", {}).get("api_key")
        if not api_key:
            import os
            api_key = os.getenv("OPENAI_API_KEY")

        model = config.get("openai", {}).get("model", "gpt-4o") if config else "gpt-4o"
        temperature = get_temperature_for_model(config, default_temperature=0.0) if config else 0.0
        # Override for o-series models
        if model.startswith(("o1", "o3", "o4")):
            temperature = 1.0

        llm = ChatOpenAI(model=model, temperature=temperature, api_key=api_key)

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

    def _execute_rag_pipeline(self, task: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute RAG pipeline for summarize/explain requests.
        
        Pipeline: search_documents → extract_section → synthesize_content → reply_to_user
        
        Args:
            task: User task (e.g., "Summarize the Ed Sheeran files")
            session_id: Optional session ID
            
        Returns:
            Result dictionary with synthesized summary
        """
        logger.info(f"[SLASH COMMAND] Executing RAG pipeline for: {task}")
        
        # Extract topic from task (remove summarize/explain keywords)
        import re
        rag_keywords_pattern = r'\b(summarize|summarise|summary|explain|describe|what is|tell me about)\b'
        topic = re.sub(rag_keywords_pattern, '', task, flags=re.IGNORECASE).strip()
        topic = re.sub(r'\b(the|my|files|docs|documents|file|doc)\b', '', topic, flags=re.IGNORECASE).strip()
        
        if not topic:
            topic = task  # Fallback to full task if extraction fails
        
        # Step 1: Search for documents
        search_result = self.registry.execute_tool(
            "search_documents",
            {"query": topic, "user_request": task},
            session_id=session_id
        )
        
        if search_result.get("error"):
            # No documents found - return structured error
            return {
                "error": True,
                "error_type": "NotFoundError",
                "error_message": f"No documents found matching '{topic}'. Please check your document index or try a different search term.",
                "rag_pipeline": True,
                "step": "search"
            }
        
        doc_path = search_result.get("doc_path")
        if not doc_path:
            return {
                "error": True,
                "error_type": "SearchError",
                "error_message": "Document search completed but no document path returned.",
                "rag_pipeline": True,
                "step": "search"
            }
        
        # Step 2: Extract section
        extract_result = self.registry.execute_tool(
            "extract_section",
            {"doc_path": doc_path, "section": "all"},
            session_id=session_id
        )
        
        if extract_result.get("error"):
            # Extraction failed - try to use content preview from search if available
            content_preview = search_result.get("content_preview", "")
            if content_preview:
                extracted_text = content_preview
            else:
                return {
                    "error": True,
                    "error_type": "ExtractionError",
                    "error_message": extract_result.get("error_message", "Failed to extract document content."),
                    "rag_pipeline": True,
                    "step": "extract",
                    "doc_path": doc_path
                }
        else:
            extracted_text = extract_result.get("extracted_text", "")
            if not extracted_text:
                return {
                    "error": True,
                    "error_type": "ExtractionError",
                    "error_message": "Document extraction completed but no content returned.",
                    "rag_pipeline": True,
                    "step": "extract"
                }
        
        # Step 3: Synthesize content
        # Determine synthesis style based on keywords
        synthesis_style = "concise"
        if "explain" in task.lower() or "detailed" in task.lower() or "comprehensive" in task.lower():
            synthesis_style = "comprehensive"
        
        synth_result = self.registry.execute_tool(
            "synthesize_content",
            {
                "source_contents": [extracted_text],
                "topic": f"{topic} Summary" if "summar" in task.lower() else f"{topic} Explanation",
                "synthesis_style": synthesis_style
            },
            session_id=session_id
        )
        
        if synth_result.get("error"):
            return {
                "error": True,
                "error_type": "SynthesisError",
                "error_message": synth_result.get("error_message", "Failed to synthesize content."),
                "rag_pipeline": True,
                "step": "synthesize"
            }
        
        synthesized_content = synth_result.get("synthesized_content", "")
        if not synthesized_content:
            return {
                "error": True,
                "error_type": "SynthesisError",
                "error_message": "Content synthesis completed but no summary returned.",
                "rag_pipeline": True,
                "step": "synthesize"
            }
        
        # Step 4: Format as reply (mimicking reply_to_user)
        return {
            "summary": synthesized_content,
            "doc_title": search_result.get("doc_title", "Unknown"),
            "doc_path": doc_path,
            "word_count": synth_result.get("word_count", 0),
            "rag_pipeline": True,
            "message": synthesized_content  # For compatibility with reply_to_user format
        }

    def _route_weather_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """Route /weather commands to appropriate weather agent tools."""
        task_lower = task.lower().strip()

        # Extract location (quoted or first capitalized words)
        location = _extract_quoted_text(task)
        if not location:
            words = task.split()
            cap_words = []
            for word in words:
                if word and word[0].isupper() and word.lower() not in ["today", "tomorrow", "week", "now", "current"]:
                    cap_words.append(word)
                elif cap_words:
                    break
            if cap_words:
                location = " ".join(cap_words)

        # Extract timeframe
        timeframe = "today"
        if "tomorrow" in task_lower:
            timeframe = "tomorrow"
        elif "week" in task_lower or "7 day" in task_lower or "7day" in task_lower:
            timeframe = "week"
        elif "3 day" in task_lower or "3day" in task_lower:
            timeframe = "3day"
        elif "now" in task_lower or "current" in task_lower:
            timeframe = "now"

        params = {"timeframe": timeframe}
        if location:
            params["location"] = location

        return "get_weather_forecast", params, None

    def _route_notes_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """Route /notes commands to appropriate notes agent tools."""
        task_lower = task.lower().strip()

        if any(keyword in task_lower for keyword in ["create", "new", "make"]):
            title = _extract_quoted_text(task)
            body_match = re.search(r'(?:with body|with|body)\s+["\']?(.+?)["\']?\s*$', task, re.IGNORECASE | re.DOTALL)
            body = body_match.group(1).strip().strip('"\'') if body_match else ""
            folder = "Notes"
            folder_match = re.search(r'(?:in folder|folder|in)\s+["\']?([^"\']+)["\']?', task, re.IGNORECASE)
            if folder_match:
                folder = folder_match.group(1).strip()
            if title and body:
                return "create_note", {"title": title, "body": body, "folder": folder}, None

        elif any(keyword in task_lower for keyword in ["append", "add to", "update"]):
            note_title = _extract_quoted_text(task)
            content_match = re.search(r'with\s+["\']?(.+?)["\']?\s*$', task, re.IGNORECASE | re.DOTALL)
            content = content_match.group(1).strip().strip('"\'') if content_match else ""
            if note_title and content:
                return "append_note", {"note_title": note_title, "content": content}, None

        elif any(keyword in task_lower for keyword in ["read", "get", "show", "retrieve"]):
            note_title = _extract_quoted_text(task)
            if note_title:
                return "get_note", {"note_title": note_title}, None

        return None, {}, None

    def _route_reminders_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """Route /reminders commands to appropriate reminders agent tools."""
        task_lower = task.lower().strip()

        if "complete" in task_lower or "done" in task_lower:
            reminder_title = _extract_quoted_text(task)
            if reminder_title:
                return "complete_reminder", {"reminder_title": reminder_title}, None

        # create_reminder
        title = _extract_quoted_text(task)
        due_time = None
        time_match = re.search(r'(?:at|tomorrow at|today at|in)\s+(.+?)(?:\s+in list|\s*$)', task, re.IGNORECASE)
        if time_match:
            due_time = time_match.group(1).strip()
        elif "tomorrow" in task_lower:
            due_time = "tomorrow"
        elif "today" in task_lower:
            due_time = "today"

        if title:
            params = {"title": title}
            if due_time:
                params["due_time"] = due_time
            return "create_reminder", params, None

        return None, {}, None

    def _route_calendar_command(self, task: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """Route /calendar commands to appropriate calendar agent tools."""
        task_lower = task.lower().strip()

        # prepare_meeting_brief - keywords: "prep", "brief", "docs for"
        if any(keyword in task_lower for keyword in ["prep", "brief", "docs for", "prepare"]):
            # Extract event title
            event_title = None
            
            # Try to extract from "prep for X" or "brief for X" or "docs for X"
            for pattern in [
                r'(?:prep|brief|prepare|docs for)\s+(?:for\s+)?["\']?([^"\']+)["\']?',
                r'(?:prep|brief|prepare|docs for)\s+(?:the\s+)?(.+?)(?:\s+meeting|\s*$)',
            ]:
                match = re.search(pattern, task, re.IGNORECASE)
                if match:
                    event_title = match.group(1).strip().strip('"\'')
                    break
            
            # Fallback: extract quoted text or use remaining text
            if not event_title:
                event_title = _extract_quoted_text(task)
                if not event_title:
                    # Use text after keywords
                    for keyword in ["prep", "brief", "prepare", "docs for"]:
                        if keyword in task_lower:
                            parts = task_lower.split(keyword, 1)
                            if len(parts) > 1:
                                event_title = parts[1].strip().strip('"\'')
                                # Remove common trailing words
                                event_title = re.sub(r'\s+(meeting|event|call)$', '', event_title, flags=re.IGNORECASE)
                                break

            if event_title:
                # Check for save_to_note flag
                save_to_note = any(keyword in task_lower for keyword in ["save", "note", "store"])
                return "prepare_meeting_brief", {
                    "event_title": event_title,
                    "save_to_note": save_to_note
                }, None

        # list_calendar_events - keywords: "list", "upcoming", "events", "show"
        elif any(keyword in task_lower for keyword in ["list", "upcoming", "events", "show", "what"]):
            days_ahead = 7
            # Try to extract number of days
            days_match = re.search(r'(\d+)\s*(?:days?|weeks?)', task_lower)
            if days_match:
                days = int(days_match.group(1))
                if "week" in days_match.group(0):
                    days = days * 7
                days_ahead = min(max(1, days), 30)
            return "list_calendar_events", {"days_ahead": days_ahead}, None

        # get_calendar_event_details - keywords: "details", "info", "about"
        elif any(keyword in task_lower for keyword in ["details", "info", "about", "get"]):
            event_title = _extract_quoted_text(task)
            if not event_title:
                # Extract from "details for X" or "info about X"
                for pattern in [
                    r'(?:details|info|about|get)\s+(?:for|about)\s+["\']?([^"\']+)["\']?',
                    r'(?:details|info|about|get)\s+["\']?([^"\']+)["\']?',
                ]:
                    match = re.search(pattern, task, re.IGNORECASE)
                    if match:
                        event_title = match.group(1).strip().strip('"\'')
                        break
                if not event_title:
                    # Use remaining text after keywords
                    for keyword in ["details", "info", "about"]:
                        if keyword in task_lower:
                            parts = task_lower.split(keyword, 1)
                            if len(parts) > 1:
                                event_title = parts[1].strip().strip('"\'')
                                break

            if event_title:
                return "get_calendar_event_details", {"event_title": event_title}, None

        # Default: if no clear intent, return None to let agent handle it
        return None, {}, None


def parse_recurring_task_spec(task_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse a recurring task specification from natural language.

    Args:
        task_text: Task specification text

    Returns:
        Dictionary with parsed schedule and action info, or None if invalid

    Examples:
        "Create a weekly screen time report and email it every Friday"
        "Generate a daily summary every day at 9am"
        "Send me a weekly summary every Monday at 10am"
    """
    import re
    from datetime import datetime

    task_lower = task_text.lower()

    # Extract action type
    action_kind = None
    if "screen time" in task_lower:
        action_kind = "screen_time_report"
    elif "summary" in task_lower or "report" in task_lower:
        action_kind = "file_summary_report"
    else:
        # Default to general report
        action_kind = "general_report"

    # Extract schedule type and timing
    schedule_type = None
    weekday = None
    time_str = "09:00"  # Default to 9am

    # Weekly schedule
    if "weekly" in task_lower or "every week" in task_lower:
        schedule_type = "weekly"

        # Extract day of week
        weekday_map = {
            "monday": 0, "mon": 0,
            "tuesday": 1, "tue": 1, "tues": 1,
            "wednesday": 2, "wed": 2,
            "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
            "friday": 4, "fri": 4,
            "saturday": 5, "sat": 5,
            "sunday": 6, "sun": 6
        }

        for day_name, day_num in weekday_map.items():
            if day_name in task_lower:
                weekday = day_num
                break

        # Default to Friday if weekly but no day specified
        if weekday is None:
            weekday = 4  # Friday

    # Daily schedule
    elif "daily" in task_lower or "every day" in task_lower:
        schedule_type = "daily"

    else:
        # Try to extract day of week for implicit weekly
        weekday_map = {
            "monday": 0, "mon": 0,
            "tuesday": 1, "tue": 1, "tues": 1,
            "wednesday": 2, "wed": 2,
            "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
            "friday": 4, "fri": 4,
            "saturday": 5, "sat": 5,
            "sunday": 6, "sun": 6
        }

        for day_name, day_num in weekday_map.items():
            if day_name in task_lower:
                schedule_type = "weekly"
                weekday = day_num
                break

    if not schedule_type:
        return None

    # Extract time
    time_patterns = [
        r'at (\d{1,2})\s*(?::(\d{2}))?\s*(am|pm)',  # "at 9am", "at 2:30pm"
        r'(\d{1,2})\s*(?::(\d{2}))?\s*(am|pm)',     # "9am", "2:30pm"
        r'at (\d{1,2}):(\d{2})',                     # "at 09:00", "at 14:30"
    ]

    for pattern in time_patterns:
        match = re.search(pattern, task_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.lastindex >= 2 and match.group(2) else 0
            meridiem = match.group(3) if match.lastindex >= 3 else None

            if meridiem:
                if meridiem == "pm" and hour != 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0

            time_str = f"{hour:02d}:{minute:02d}"
            break

    # Extract delivery mode
    delivery_mode = None
    send = False

    if "email" in task_lower or "send" in task_lower:
        delivery_mode = "email"
        send = True

    # Create friendly name
    if action_kind == "screen_time_report":
        name = f"Weekly Screen Time Report"
    else:
        name = f"Scheduled {schedule_type.capitalize()} Report"

    return {
        "name": name,
        "schedule": {
            "type": schedule_type,
            "weekday": weekday,
            "time": time_str,
            "tz": "America/Los_Angeles"  # TODO: Use user's timezone from config
        },
        "action": {
            "kind": action_kind,
            "delivery": {
                "mode": delivery_mode,
                "send": send,
                "recipient": "default"
            }
        }
    }


# Convenience function
def create_slash_command_handler(agent_registry, session_manager=None, config: Optional[Dict[str, Any]] = None):
    """
    Create a slash command handler.

    Args:
        agent_registry: AgentRegistry instance
        session_manager: Optional SessionManager for /clear command
        config: Configuration dictionary for demo constraints

    Returns:
        SlashCommandHandler instance
    """
    return SlashCommandHandler(agent_registry, session_manager, config)
