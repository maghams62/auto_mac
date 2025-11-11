"""
Help system data models.

Defines the structure for help entries, commands, agents, and tools.
"""

from typing import List, Optional, Literal, Dict, Any
from dataclasses import dataclass, field


@dataclass
class ParameterInfo:
    """Information about a tool/command parameter."""
    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None
    examples: List[str] = field(default_factory=list)


@dataclass
class HelpEntry:
    """
    A single help entry for a command, agent, or tool.

    This is the core data structure that powers the help system.
    """
    # Identity
    name: str
    type: Literal["slash_command", "agent", "tool"]
    category: str

    # Description
    description: str  # Short one-liner
    long_description: Optional[str] = None  # Detailed explanation

    # Usage
    examples: List[str] = field(default_factory=list)
    parameters: List[ParameterInfo] = field(default_factory=list)

    # Organization
    tags: List[str] = field(default_factory=list)  # For search
    related: List[str] = field(default_factory=list)  # Related commands
    agent: Optional[str] = None  # Which agent owns this
    aliases: List[str] = field(default_factory=list)

    # Visual
    icon: str = "•"  # Emoji for visual distinction

    # Metadata
    level: Literal["basic", "intermediate", "advanced"] = "basic"
    usage_count: int = 0  # Track popularity

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "type": self.type,
            "category": self.category,
            "description": self.description,
            "long_description": self.long_description,
            "examples": self.examples,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "examples": p.examples
                }
                for p in self.parameters
            ],
            "tags": self.tags,
            "related": self.related,
            "agent": self.agent,
            "aliases": self.aliases,
            "icon": self.icon,
            "level": self.level,
            "usage_count": self.usage_count
        }


@dataclass
class AgentHelp:
    """Help information for an agent."""
    name: str
    display_name: str
    description: str
    category: str
    icon: str
    tool_count: int
    tools: List[HelpEntry] = field(default_factory=list)
    slash_commands: List[str] = field(default_factory=list)
    common_tasks: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "icon": self.icon,
            "tool_count": self.tool_count,
            "tools": [t.to_dict() for t in self.tools],
            "slash_commands": self.slash_commands,
            "common_tasks": self.common_tasks,
            "examples": self.examples
        }


@dataclass
class CategoryInfo:
    """Information about a help category."""
    name: str
    display_name: str
    description: str
    icon: str
    command_count: int = 0
    agent_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "command_count": self.command_count,
            "agent_count": self.agent_count
        }
