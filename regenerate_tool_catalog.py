#!/usr/bin/env python3
"""
Script to regenerate tool definitions documentation from the actual tool catalog.
"""

import sys
import os
import json
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def safe_import_tools():
    """Import tools avoiding problematic LangGraph imports."""
    try:
        # Try to import ALL_AGENT_TOOLS directly
        from agent.agent_registry import ALL_AGENT_TOOLS
        return ALL_AGENT_TOOLS
    except Exception as e:
        print(f"Failed to import ALL_AGENT_TOOLS: {e}")
        return []

def generate_tool_catalog_markdown():
    """Generate markdown documentation from tool catalog."""

    tools = safe_import_tools()
    if not tools:
        print("No tools found, cannot generate catalog")
        return ""

    # Group tools by agent type based on naming patterns
    agent_groups = {
        "BROWSER": [],
        "CRITIC": [],
        "DISCORD": [],
        "EMAIL": [],
        "FILE": [],
        "FOLDER": [],
        "GOOGLE": [],
        "GOOGLE FINANCE": [],
        "IMESSAGE": [],
        "MAPS": [],
        "MICRO ACTIONS": [],
        "NOTIFICATIONS": [],
        "PRESENTATION": [],
        "REDDIT": [],
        "REPORT": [],
        "SCREEN": [],
        "STOCK": [],
        "TWITTER": [],
        "VOICE": [],
        "WRITING": [],
        "BLUESKY": [],
        "VISION": [],
        "WHATSAPP": [],
        "SPOTIFY": [],
        "WEATHER": [],
        "NOTES": [],
        "REMINDERS": [],
        "CALENDAR": [],
        "DAILY_OVERVIEW": [],
        "REPLY": [],
        "CELEBRATION": []
    }

    # Categorize tools by name patterns
    for tool in tools:
        tool_name = tool.name.upper()

        if any(keyword in tool_name for keyword in ['BROWSER', 'NAVIGATE', 'EXTRACT', 'SCREENSHOT', 'SEARCH']):
            agent_groups["BROWSER"].append(tool)
        elif 'CRITIC' in tool_name or 'VERIFY' in tool_name:
            agent_groups["CRITIC"].append(tool)
        elif 'DISCORD' in tool_name:
            agent_groups["DISCORD"].append(tool)
        elif any(keyword in tool_name for keyword in ['EMAIL', 'MAIL']):
            agent_groups["EMAIL"].append(tool)
        elif any(keyword in tool_name for keyword in ['FILE', 'READ', 'WRITE', 'EDIT', 'CREATE']) and 'FOLDER' not in tool_name:
            agent_groups["FILE"].append(tool)
        elif 'FOLDER' in tool_name or 'DIRECTORY' in tool_name:
            agent_groups["FOLDER"].append(tool)
        elif 'GOOGLE' in tool_name and 'FINANCE' not in tool_name:
            agent_groups["GOOGLE"].append(tool)
        elif 'GOOGLE_FINANCE' in tool_name or ('GOOGLE' in tool_name and 'FINANCE' in tool_name):
            agent_groups["GOOGLE FINANCE"].append(tool)
        elif 'IMESSAGE' in tool_name:
            agent_groups["IMESSAGE"].append(tool)
        elif any(keyword in tool_name for keyword in ['MAP', 'TRIP', 'ROUTE', 'NAVIGATION']):
            agent_groups["MAPS"].append(tool)
        elif 'MICRO' in tool_name or 'ACTION' in tool_name:
            agent_groups["MICRO ACTIONS"].append(tool)
        elif 'NOTIFICATION' in tool_name:
            agent_groups["NOTIFICATIONS"].append(tool)
        elif any(keyword in tool_name for keyword in ['PRESENTATION', 'SLIDE', 'KEYNOTE', 'POWERPOINT']):
            agent_groups["PRESENTATION"].append(tool)
        elif 'REDDIT' in tool_name:
            agent_groups["REDDIT"].append(tool)
        elif 'REPORT' in tool_name:
            agent_groups["REPORT"].append(tool)
        elif 'SCREEN' in tool_name and 'SHOT' not in tool_name:
            agent_groups["SCREEN"].append(tool)
        elif any(keyword in tool_name for keyword in ['STOCK', 'FINANCE', 'TICKER', 'PRICE']):
            agent_groups["STOCK"].append(tool)
        elif 'TWITTER' in tool_name:
            agent_groups["TWITTER"].append(tool)
        elif 'VOICE' in tool_name:
            agent_groups["VOICE"].append(tool)
        elif any(keyword in tool_name for keyword in ['WRITING', 'SUMMARIZE', 'SYNTHESIZE', 'BRIEF']):
            agent_groups["WRITING"].append(tool)
        elif 'BLUESKY' in tool_name:
            agent_groups["BLUESKY"].append(tool)
        elif 'VISION' in tool_name:
            agent_groups["VISION"].append(tool)
        elif 'WHATSAPP' in tool_name:
            agent_groups["WHATSAPP"].append(tool)
        elif 'SPOTIFY' in tool_name:
            agent_groups["SPOTIFY"].append(tool)
        elif 'WEATHER' in tool_name:
            agent_groups["WEATHER"].append(tool)
        elif 'NOTE' in tool_name:
            agent_groups["NOTES"].append(tool)
        elif 'REMINDER' in tool_name:
            agent_groups["REMINDERS"].append(tool)
        elif 'CALENDAR' in tool_name:
            agent_groups["CALENDAR"].append(tool)
        elif 'DAILY' in tool_name or 'OVERVIEW' in tool_name:
            agent_groups["DAILY_OVERVIEW"].append(tool)
        elif 'REPLY' in tool_name:
            agent_groups["REPLY"].append(tool)
        elif 'CELEBRATION' in tool_name:
            agent_groups["CELEBRATION"].append(tool)
        else:
            # Default to WRITING for unrecognized tools
            agent_groups["WRITING"].append(tool)

    # Generate markdown
    lines = ["# Tool Definitions\n"]

    for agent_name, agent_tools in agent_groups.items():
        if not agent_tools:
            continue

        lines.append(f"## {agent_name} Agent ({len(agent_tools)} tools)")
        lines.append("")

        for tool in sorted(agent_tools, key=lambda t: t.name):
            lines.append(f"### {tool.name}")
            lines.append(f"**Description:** {tool.description}")
            lines.append("")

            # Try to get args schema
            try:
                if hasattr(tool, 'args_schema') and tool.args_schema:
                    schema = tool.args_schema.schema()
                    if 'properties' in schema:
                        lines.append("**Parameters:**")
                        required = set(schema.get('required', []))
                        for param_name, param_info in schema['properties'].items():
                            req_marker = " (required)" if param_name in required else ""
                            param_type = param_info.get('type', 'any')
                            description = param_info.get('description', '')
                            lines.append(f"- `{param_name}` ({param_type}){req_marker}: {description}")
                        lines.append("")
            except Exception:
                lines.append("**Parameters:** (Unable to parse schema)")
                lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)

if __name__ == "__main__":
    print("Regenerating tool catalog documentation...")
    markdown = generate_tool_catalog_markdown()

    if markdown:
        output_path = "/Users/siddharthsuresh/Downloads/auto_mac/prompts/tool_definitions.md"
        with open(output_path, 'w') as f:
            f.write(markdown)
        print(f"Updated {output_path}")
    else:
        print("Failed to generate tool catalog")
