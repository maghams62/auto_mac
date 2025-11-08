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

from typing import Dict, Any, List
import logging

from .file_agent import FileAgent, FILE_AGENT_TOOLS, FILE_AGENT_HIERARCHY
from .browser_agent import BrowserAgent, BROWSER_AGENT_TOOLS, BROWSER_AGENT_HIERARCHY
from .presentation_agent import PresentationAgent, PRESENTATION_AGENT_TOOLS, PRESENTATION_AGENT_HIERARCHY
from .email_agent import EmailAgent, EMAIL_AGENT_TOOLS, EMAIL_AGENT_HIERARCHY
from .critic_agent import CriticAgent, CRITIC_AGENT_TOOLS, CRITIC_AGENT_HIERARCHY
from .writing_agent import WritingAgent, WRITING_AGENT_TOOLS, WRITING_AGENT_HIERARCHY
from .stock_agent import STOCK_AGENT_TOOLS, STOCK_AGENT_HIERARCHY
from .screen_agent import SCREEN_AGENT_TOOLS, SCREEN_AGENT_HIERARCHY
from .report_agent import ReportAgent, REPORT_AGENT_TOOLS, REPORT_AGENT_HIERARCHY
from .google_finance_agent import GoogleFinanceAgent, GOOGLE_FINANCE_AGENT_TOOLS, GOOGLE_FINANCE_AGENT_HIERARCHY
from .maps_agent import MapsAgent, MAPS_AGENT_TOOLS, MAPS_AGENT_HIERARCHY
from .imessage_agent import iMessageAgent, IMESSAGE_AGENT_TOOLS, IMESSAGE_AGENT_HIERARCHY

logger = logging.getLogger(__name__)


# Combined tool registry (for backwards compatibility)
ALL_AGENT_TOOLS = (
    FILE_AGENT_TOOLS +
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
    IMESSAGE_AGENT_TOOLS
)

# Legacy compatibility
ALL_TOOLS = FILE_AGENT_TOOLS + PRESENTATION_AGENT_TOOLS + EMAIL_AGENT_TOOLS
BROWSER_TOOLS = BROWSER_AGENT_TOOLS


# Agent hierarchy documentation
AGENT_HIERARCHY_DOCS = """
Multi-Agent System Hierarchy:
=============================

The system is organized into 6 specialized agents, each acting as a mini-orchestrator
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

4. EMAIL AGENT (1 tool)
   └─ Domain: Email operations
   └─ Tools: compose_email

5. WRITING AGENT (4 tools)
   └─ Domain: Content synthesis and writing
   └─ Tools: synthesize_content, create_slide_deck_content, create_detailed_report, create_meeting_notes

6. CRITIC AGENT (4 tools)
   └─ Domain: Verification, reflection, and quality assurance
   └─ Tools: verify_output, reflect_on_failure, validate_plan, check_quality

Total: 22 tools across 6 specialized agents

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

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # Initialize all agents
        self.file_agent = FileAgent(config)
        self.browser_agent = BrowserAgent(config)
        self.presentation_agent = PresentationAgent(config)
        self.email_agent = EmailAgent(config)
        self.writing_agent = WritingAgent(config)
        self.critic_agent = CriticAgent(config)
        self.report_agent = ReportAgent(config)
        self.google_finance_agent = GoogleFinanceAgent(config)
        self.maps_agent = MapsAgent(config)
        self.imessage_agent = iMessageAgent(config)

        # Create agent mapping
        self.agents = {
            "file": self.file_agent,
            "browser": self.browser_agent,
            "presentation": self.presentation_agent,
            "email": self.email_agent,
            "writing": self.writing_agent,
            "critic": self.critic_agent,
            "report": self.report_agent,
            "google_finance": self.google_finance_agent,
            "maps": self.maps_agent,
            "imessage": self.imessage_agent,
        }

        # Create tool-to-agent mapping for routing
        self.tool_to_agent = {}
        for agent_name, agent in self.agents.items():
            for tool in agent.get_tools():
                self.tool_to_agent[tool.name] = agent_name

        logger.info(f"[AGENT REGISTRY] Initialized with {len(self.agents)} agents and {len(self.tool_to_agent)} tools")

    def get_agent(self, agent_name: str):
        """Get a specific agent by name."""
        return self.agents.get(agent_name)

    def get_agent_for_tool(self, tool_name: str):
        """Get the agent responsible for a specific tool."""
        agent_name = self.tool_to_agent.get(tool_name)
        if agent_name:
            return self.agents[agent_name]
        return None

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

    def execute_tool(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route and execute a tool through its responsible agent.

        This is the main execution interface - tools are automatically routed
        to their owning agent.
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

        return agent.execute(tool_name, inputs)

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

    return mapping


def print_agent_hierarchy():
    """Print the complete agent hierarchy for debugging."""
    print(AGENT_HIERARCHY_DOCS)
    print("\n" + "=" * 80)
    print("TOOL TO AGENT MAPPING:")
    print("=" * 80)

    mapping = get_agent_tool_mapping()
    for agent_name in ["file", "browser", "presentation", "email", "writing", "critic"]:
        tools = [tool for tool, agent in mapping.items() if agent == agent_name]
        print(f"\n{agent_name.upper()} AGENT ({len(tools)} tools):")
        for tool in tools:
            print(f"  - {tool}")
