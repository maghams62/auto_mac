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
    /report <task>          - Generate PDF reports from local files
    /help [command]         - Show help for commands
    /agents                 - List all available agents
    /                      - Show slash command palette
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
import re

logger = logging.getLogger(__name__)


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
        "report": "report",
        "notify": "notifications",
        "notification": "notifications",
        "alert": "notifications",
    }

    # Special system commands (not agent-related)
    SYSTEM_COMMANDS = ["help", "agents", "clear"]

    # Quick palette entries (primary commands only)
    COMMAND_TOOLTIPS = [
        {"command": "/files", "label": "File Ops", "description": "Search, organize, zip local files"},
        {"command": "/folder", "label": "Folder Agent", "description": "List & reorganize folders"},
        {"command": "/browse", "label": "Browser", "description": "Search the web & extract content"},
        {"command": "/present", "label": "Presentations", "description": "Create Keynote/Pages docs"},
        {"command": "/email", "label": "Email", "description": "Draft messages in Mail.app"},
        {"command": "/write", "label": "Writing", "description": "Generate reports, notes, slides"},
        {"command": "/maps", "label": "Maps", "description": "Plan trips & routes"},
        {"command": "/stock", "label": "Stocks", "description": "Prices, charts, Google Finance"},
        {"command": "/report", "label": "Local Reports", "description": "PDF reports from local files"},
        {"command": "/message", "label": "iMessage", "description": "Send texts"},
        {"command": "/discord", "label": "Discord", "description": "Monitor channels"},
        {"command": "/reddit", "label": "Reddit", "description": "Scan subreddits"},
        {"command": "/twitter", "label": "Twitter", "description": "Summarize lists"},
        {"command": "/x", "label": "X/Twitter", "description": "Quick Twitter summaries"},
        {"command": "/notify", "label": "Notifications", "description": "Send system notifications"},
    ]

    # Agent descriptions for help
    AGENT_DESCRIPTIONS = {
        "file": "Handle file operations: search, organize, zip, screenshots",
        "folder": "Folder management: list, organize, rename files (LLM-driven, sandboxed)",
        "google": "Google search via official API (fast, structured results, no browser)",
        "browser": "Web browsing: search Google, navigate URLs, extract content",
        "presentation": "Create presentations: Keynote, Pages documents",
        "email": "Compose and send emails via Mail.app",
        "writing": "Generate content: reports, slide decks, meeting notes",
        "maps": "Plan trips with stops, get directions, open Maps",
        "google_finance": "Get stock data, prices, charts from Google Finance",
        "imessage": "Send iMessages to contacts",
        "notifications": "Send system notifications via Notification Center (with sound & alerts)",
        "discord": "Monitor Discord channels and mentions",
        "reddit": "Scan Reddit for mentions and posts",
        "twitter": "Track Twitter lists and activity",
        "report": "Create PDF reports strictly from local files (or stock data when requested)",
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
        "x": [
            '/x summarize last 1h',
            '/x what happened on Twitter in the past hour',
            '/x tweet Launch day! 🚀',
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
        help_match = re.match(r'^/help\s+(\w+)$', message.strip())
        if help_match:
            return {
                "is_command": True,
                "command": "help",
                "agent": help_match.group(1),
                "task": None
            }

        # Parse regular command
        match = self.pattern.match(message.strip())
        if not match:
            return {
                "is_command": True,
                "command": "invalid",
                "error": "Invalid command format. Use: /command <task>"
            }

        command = match.group(1).lower()
        task = match.group(2).strip()

        # Map command to agent
        agent = self.COMMAND_MAP.get(command)

        if not agent:
            return {
                "is_command": True,
                "command": "invalid",
                "error": f"Unknown command: /{command}. Type /help for available commands."
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

    def get_help(self, command: Optional[str] = None) -> str:
        """
        Get help text for commands.

        Args:
            command: Specific command to get help for, or None for general help

        Returns:
            Formatted help text
        """
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
            "Communication": ["email", "imessage", "discord", "reddit", "twitter"],
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
        agent_name = parsed["agent"]
        task = parsed["task"]

        # Special handling: /folder for explanation tasks should route to file agent
        if agent_name == "folder" and parsed["command"] in ["folder", "folders"]:
            # Check if task is about explaining/listing files (not folder management)
            explanation_keywords = ["explain", "list", "show", "what", "summarize", "describe", "overview"]
            management_keywords = ["organize", "rename", "plan", "apply", "normalize", "reorganize"]
            
            task_lower = task.lower().strip() if task else ""
            
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

            # Execute through agent
            # For now, we'll use the agent's primary tool
            # In future, could add agent-level "handle_task" method
            result = self._execute_agent_task(agent, agent_name, task)

            return True, {
                "type": "result",
                "agent": agent_name,
                "command": parsed["command"],
                "result": result
            }

        except Exception as e:
            logger.error(f"[SLASH COMMAND] Error: {e}", exc_info=True)
            return True, {
                "type": "error",
                "content": f"❌ Error executing command: {str(e)}"
            }

    def _get_llm_response_for_blocked_search(self, query: str, agent) -> str:
        """
        Get LLM response when Google search is blocked.
        
        Uses LLM knowledge to provide helpful information about the query.
        
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

Google search is currently blocked/not returning results. Based on your knowledge, please provide helpful information about this topic. 

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
            return f"I searched Google for '{query}', but Google appears to be blocking automated requests. Please try using /browse for browser-based search or visit Google Trends: https://trends.google.com"

    def _summarize_google_results(self, search_results: List[Dict], query: str, agent) -> Optional[str]:
        """
        Summarize Google search results using LLM.
        
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
            summary_prompt = f"""Based on the following Google search results for "{query}", provide a concise summary of what's trending or what the key information is.

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
                        "note": "Both Google search methods failed, but I've provided information based on your query."
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
                            "note": "Google search was blocked, but I've provided information based on your query."
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
