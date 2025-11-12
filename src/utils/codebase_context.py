"""
Codebase Context Generator for Cerebro OS

This module generates comprehensive documentation and context about the Cerebro OS
codebase for LLM consumption. It helps fresh LLMs understand the architecture,
configuration, and key components.
"""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class CodebaseOverview:
    """Overview of the codebase structure."""
    name: str = "Cerebro OS"
    version: str = "2.0"
    description: str = "AI-powered macOS automation system"
    architecture: str = "LangGraph multi-agent system"
    entry_points: List[str] = field(default_factory=lambda: ["main.py", "src/agent/agent.py"])
    key_directories: Dict[str, str] = field(default_factory=lambda: {
        "src/": "Main source code",
        "src/agent/": "Agent implementations",
        "src/automation/": "OS automation helpers",
        "src/integrations/": "External service integrations",
        "src/memory/": "Session and reasoning trace management",
        "src/utils/": "Utility functions",
        "prompts/": "LLM prompts and templates",
        "docs/": "Documentation",
        "tests/": "Test suite"
    })


@dataclass
class AgentDocumentation:
    """Documentation for agents."""
    name: str
    domain: str
    tools: List[str]
    description: str
    file_path: str


@dataclass
class ConfigurationContext:
    """Configuration context and requirements."""
    config_file: str = "config.yaml"
    required_env_vars: List[str] = field(default_factory=list)
    optional_env_vars: List[str] = field(default_factory=list)
    feature_flags: Dict[str, bool] = field(default_factory=dict)
    key_settings: Dict[str, Any] = field(default_factory=dict)


class CodebaseContextGenerator:
    """
    Generates comprehensive context about the Cerebro OS codebase for LLMs.

    This helps fresh LLMs understand:
    - Overall architecture and design
    - Key components and their purposes
    - Configuration requirements
    - Agent capabilities and tools
    - Important patterns and conventions
    """

    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize the context generator.

        Args:
            project_root: Root directory of the project (auto-detected if None)
        """
        self.project_root = Path(project_root) if project_root else self._find_project_root()
        self._cache: Dict[str, Any] = {}

    def _find_project_root(self) -> Path:
        """Find the project root directory."""
        current = Path.cwd()
        while current.parent != current:
            if (current / "config.yaml").exists() and (current / "main.py").exists():
                return current
            current = current.parent
        return Path.cwd()  # Fallback

    def generate_full_context(self) -> str:
        """
        Generate comprehensive context about the entire codebase.

        Returns:
            Formatted context string for LLM consumption
        """
        sections = []

        # Overview
        sections.append(self._generate_overview_section())

        # Architecture
        sections.append(self._generate_architecture_section())

        # Configuration
        sections.append(self._generate_configuration_section())

        # Agents and Tools
        sections.append(self._generate_agents_section())

        # Key Patterns
        sections.append(self._generate_patterns_section())

        # File Structure
        sections.append(self._generate_file_structure_section())

        # Important Notes
        sections.append(self._generate_important_notes_section())

        return "\n\n".join(sections)

    def generate_retry_context(self) -> str:
        """
        Generate context specifically for retry scenarios.

        Returns:
            Context focused on retry handling and recovery
        """
        sections = []

        sections.append("# CEREBRO OS - RETRY RECOVERY CONTEXT")
        sections.append("")
        sections.append("## RETRY SYSTEM OVERVIEW")
        sections.append("""
You are dealing with Cerebro OS, an AI-powered macOS automation system that has failed execution.
This context will help you understand the system and recover from failures.

Key characteristics:
- LangGraph-based multi-agent architecture
- Session-scoped memory with reasoning traces
- Comprehensive retry logging system
- Critic agent for failure analysis
- Tool-based execution with error handling
        """.strip())

        sections.append("")
        sections.append("## FAILURE RECOVERY PROCESS")
        sections.append("""
1. **Analyze the failure**: Review error messages, reasoning traces, and critic feedback
2. **Understand the context**: Check configuration, session state, and execution history
3. **Apply fixes**: Use suggested fixes from retry logs and critic feedback
4. **Execute carefully**: Pay attention to tool parameters and sandbox restrictions
5. **Document success**: Note what worked for future reference
        """.strip())

        # Add configuration context
        config_context = self._generate_configuration_section()
        sections.append(config_context)

        # Add agent capabilities
        agent_context = self._generate_agents_section()
        sections.append(agent_context)

        return "\n\n".join(sections)

    def _generate_overview_section(self) -> str:
        """Generate the overview section."""
        overview = CodebaseOverview()

        section = []
        section.append("# CEREBRO OS - CODEBASE OVERVIEW")
        section.append("")
        section.append(f"**Name**: {overview.name}")
        section.append(f"**Version**: {overview.version}")
        section.append(f"**Description**: {overview.description}")
        section.append(f"**Architecture**: {overview.architecture}")
        section.append("")
        section.append("## Entry Points")
        for entry in overview.entry_points:
            section.append(f"- `{entry}`")
        section.append("")
        section.append("## Key Directories")
        for directory, description in overview.key_directories.items():
            section.append(f"- `{directory}`: {description}")

        return "\n".join(section)

    def _generate_architecture_section(self) -> str:
        """Generate the architecture section."""
        section = []
        section.append("## ARCHITECTURE OVERVIEW")
        section.append("")
        section.append("### Core Components")
        section.append("""
- **LangGraph Automation Agent** (`src/agent/agent.py`): Plans and executes multi-step workflows
- **Agent Registry** (`src/agent/agent_registry.py`): Manages specialist agents and tool routing
- **Specialist Agents** (`src/agent/*.py`): Domain-focused agents (files, browser, email, etc.)
- **Session Memory** (`src/memory/`): Maintains conversation context and reasoning traces
- **Critic Agent** (`src/agent/critic_agent.py`): Handles verification and failure analysis
- **UI Layer** (`src/ui/`): Terminal interface and slash command handling
        """.strip())
        section.append("")
        section.append("### Execution Flow")
        section.append("""
1. **Planning**: LangGraph agent creates execution plan using prompts
2. **Execution**: Steps invoke tools through agent registry
3. **Verification**: Critic agent validates outputs and catches failures
4. **Recovery**: Retry system logs failures and provides recovery context
5. **Response**: Final result delivered via reply_to_user tool
        """.strip())

        return "\n".join(section)

    def _generate_configuration_section(self) -> str:
        """Generate the configuration section."""
        config_context = self._load_configuration_context()

        section = []
        section.append("## CONFIGURATION REQUIREMENTS")
        section.append("")
        section.append(f"**Config File**: `{config_context.config_file}`")
        section.append("")

        if config_context.required_env_vars:
            section.append("### Required Environment Variables")
            for var in config_context.required_env_vars:
                section.append(f"- `{var}`")
            section.append("")

        if config_context.optional_env_vars:
            section.append("### Optional Environment Variables")
            for var in config_context.optional_env_vars:
                section.append(f"- `{var}` (optional)")
            section.append("")

        if config_context.feature_flags:
            section.append("### Feature Flags")
            for flag, enabled in config_context.feature_flags.items():
                status = "enabled" if enabled else "disabled"
                section.append(f"- `{flag}`: {status}")
            section.append("")

        if config_context.key_settings:
            section.append("### Key Settings")
            for key, value in config_context.key_settings.items():
                section.append(f"- `{key}`: {value}")

        return "\n".join(section)

    def _generate_agents_section(self) -> str:
        """Generate the agents and tools section."""
        agents = self._load_agent_documentation()

        section = []
        section.append("## AGENTS AND TOOLS")
        section.append("")
        section.append("### Specialist Agents")

        for agent in agents:
            section.append(f"#### {agent.name}")
            section.append(f"**Domain**: {agent.domain}")
            section.append(f"**File**: `{agent.file_path}`")
            section.append(f"**Description**: {agent.description}")
            section.append("**Key Tools**:")
            for tool in agent.tools[:5]:  # Limit to top 5
                section.append(f"  - `{tool}`")
            if len(agent.tools) > 5:
                section.append(f"  - ... and {len(agent.tools) - 5} more")
            section.append("")

        return "\n".join(section)

    def _generate_patterns_section(self) -> str:
        """Generate the patterns and conventions section."""
        section = []
        section.append("## KEY PATTERNS AND CONVENTIONS")
        section.append("")
        section.append("### Tool Implementation")
        section.append("""
- Tools are LangChain `@tool` decorated functions
- Each tool defines a Pydantic schema via `args_schema`
- Tools delegate to deterministic helpers in `src/automation/` or `src/integrations/`
- Error handling: Return `{"error": True, ...}` for failures
        """.strip())
        section.append("")
        section.append("### Response Format")
        section.append("""
- Final results must use `reply_to_user` tool
- Payload structure: `{"type": "reply", "message": "...", "details": "...", "status": "..."}`
- Status values: "success", "partial_success", "error", "info"
        """.strip())
        section.append("")
        section.append("### Error Handling")
        section.append("""
- Use try/catch blocks around tool execution
- Log errors with appropriate context
- Return structured error responses
- Let retry system handle transient failures
        """.strip())
        section.append("")
        section.append("### Sandbox Restrictions")
        section.append("""
- File operations limited to configured folders
- Use `FolderTools.check_sandbox()` for validation
- External APIs require proper credentials
- Browser automation respects allowed domains
        """.strip())

        return "\n".join(section)

    def _generate_file_structure_section(self) -> str:
        """Generate the file structure section."""
        section = []
        section.append("## IMPORTANT FILE LOCATIONS")
        section.append("")
        section.append("### Configuration")
        section.append("- `config.yaml`: Main configuration file")
        section.append("- `.env`: Environment variables (auto-loaded)")
        section.append("")
        section.append("### Core Components")
        section.append("- `main.py`: Application entry point")
        section.append("- `src/agent/agent.py`: Main LangGraph agent")
        section.append("- `src/agent/agent_registry.py`: Agent and tool registry")
        section.append("- `src/memory/session_memory.py`: Session management")
        section.append("- `src/ui/chat.py`: Terminal interface")
        section.append("")
        section.append("### Prompts and Templates")
        section.append("- `prompts/system.md`: System prompt")
        section.append("- `prompts/task_decomposition.md`: Planning prompt")
        section.append("- `prompts/tool_definitions.md`: Tool specifications")
        section.append("")
        section.append("### Logs and Data")
        section.append("- `data/app.log`: Application logs")
        section.append("- `data/sessions/`: Session data")
        section.append("- `data/retry_logs/`: Retry attempt logs")
        section.append("")
        section.append("### Tests")
        section.append("- `tests/`: Unit and integration tests")
        section.append("- `tests/data/test_docs/`: Test documents")

        return "\n".join(section)

    def _generate_important_notes_section(self) -> str:
        """Generate the important notes section."""
        section = []
        section.append("## IMPORTANT NOTES FOR LLMs")
        section.append("")
        section.append("### Execution Context")
        section.append("""
- Always check if reasoning trace and retry logging are enabled
- Review session memory for conversation context
- Check critic feedback for previous failure analysis
- Validate tool parameters against their schemas
        """.strip())
        section.append("")
        section.append("### Error Recovery")
        section.append("""
- Use retry context to understand previous failures
- Apply suggested fixes from retry logs
- Check for patterns in repeated failures
- Escalate to human if critical operations fail repeatedly
        """.strip())
        section.append("")
        section.append("### Tool Usage")
        section.append("""
- Read tool definitions from `prompts/tool_definitions.md`
- Use exact parameter names from tool schemas
- Handle both successful responses and error responses
- Always include final `reply_to_user` call
        """.strip())
        section.append("")
        section.append("### Configuration Awareness")
        section.append("""
- Load config via `load_config()` utility
- Check feature flags before using experimental features
- Respect sandbox restrictions for file operations
- Use configured timeouts and limits
        """.strip())

        return "\n".join(section)

    def _load_configuration_context(self) -> ConfigurationContext:
        """Load configuration context from config files."""
        context = ConfigurationContext()

        # Try to load config.yaml
        config_path = self.project_root / "config.yaml"
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)

                # Extract environment variables
                for key, value in config.items():
                    if isinstance(value, dict):
                        for subkey, subvalue in value.items():
                            if isinstance(subvalue, str) and subvalue.startswith('${') and subvalue.endswith('}'):
                                env_var = subvalue[2:-1]  # Remove ${}
                                if key in ['openai', 'discord', 'twitter', 'bluesky', 'maps']:
                                    context.required_env_vars.append(env_var)
                                else:
                                    context.optional_env_vars.append(env_var)

                # Extract feature flags
                if 'reasoning_trace' in config:
                    rt_config = config['reasoning_trace']
                    if isinstance(rt_config, dict):
                        context.feature_flags['reasoning_trace'] = rt_config.get('enabled', False)

                if 'vision' in config:
                    vision_config = config['vision']
                    if isinstance(vision_config, dict):
                        context.feature_flags['vision'] = vision_config.get('enabled', False)

                # Extract key settings
                if 'openai' in config:
                    oa_config = config['openai']
                    if isinstance(oa_config, dict):
                        context.key_settings['openai_model'] = oa_config.get('model', 'gpt-4o')

            except Exception as e:
                logger.debug(f"Could not load config.yaml: {e}")

        return context

    def _load_agent_documentation(self) -> List[AgentDocumentation]:
        """Load documentation for agents."""
        agents = []

        # Read the MASTER_AGENT_GUIDE for agent information
        guide_path = self.project_root / "docs" / "MASTER_AGENT_GUIDE.md"
        if guide_path.exists():
            try:
                with open(guide_path, 'r') as f:
                    content = f.read()

                # Extract agent information from the table
                lines = content.split('\n')
                in_table = False
                for line in lines:
                    if '| Agent | File | Domain | Key Tools |' in line:
                        in_table = True
                        continue
                    elif in_table and line.startswith('| '):
                        parts = line.split('|')
                        if len(parts) >= 5:
                            agent_name = parts[1].strip()
                            file_path = parts[2].strip()
                            domain = parts[3].strip()
                            tools_str = parts[4].strip()

                            if agent_name and not agent_name.startswith('-'):
                                # Parse tools
                                tools = []
                                if tools_str and tools_str != '-':
                                    tools = [t.strip() for t in tools_str.split(',') if t.strip()]

                                # Get description from content
                                description = self._get_agent_description(content, agent_name)

                                agents.append(AgentDocumentation(
                                    name=agent_name,
                                    domain=domain,
                                    tools=tools,
                                    description=description,
                                    file_path=file_path
                                ))
                    elif in_table and not line.startswith('|'):
                        break

            except Exception as e:
                logger.debug(f"Could not load agent documentation: {e}")

        # Fallback if guide not found
        if not agents:
            agents = [
                AgentDocumentation(
                    name="FileAgent",
                    domain="Document search/extraction",
                    tools=["search_documents", "extract_section", "take_screenshot"],
                    description="Handles document operations and file management",
                    file_path="src/agent/file_agent.py"
                ),
                AgentDocumentation(
                    name="BrowserAgent",
                    domain="Web search and browsing",
                    tools=["google_search", "navigate_to_url", "extract_page_content"],
                    description="Manages web browsing and data extraction",
                    file_path="src/agent/browser_agent.py"
                ),
                AgentDocumentation(
                    name="CriticAgent",
                    domain="Verification and quality assurance",
                    tools=["verify_output", "reflect_on_failure", "validate_plan"],
                    description="Handles output verification and failure analysis",
                    file_path="src/agent/critic_agent.py"
                )
            ]

        return agents

    def _get_agent_description(self, content: str, agent_name: str) -> str:
        """Extract agent description from documentation content."""
        # Look for agent-specific sections
        lines = content.split('\n')
        in_agent_section = False
        description_lines = []

        for line in lines:
            if f'#### {agent_name}' in line:
                in_agent_section = True
                continue
            elif in_agent_section and line.startswith('#### ') and line != f'#### {agent_name}':
                break  # Next agent section
            elif in_agent_section and line.strip() and not line.startswith('|') and not line.startswith('**'):
                # Collect description lines
                if len(description_lines) < 3:  # Limit to first few lines
                    description_lines.append(line.strip())

        if description_lines:
            return ' '.join(description_lines)
        else:
            return f"Specialist agent for {agent_name.lower()} operations"
