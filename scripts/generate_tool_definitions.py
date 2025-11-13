#!/usr/bin/env python3
"""
Generate tool definitions markdown from the tool catalog.

This script generates prompts/tool_definitions.md from the current tool catalog
to ensure it stays in sync with ALL_AGENT_TOOLS.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.orchestrator.tools_catalog import generate_tool_catalog, get_tool_specs_as_dicts, build_tool_parameter_index
from src.agent import ALL_AGENT_TOOLS


def generate_tool_definitions_markdown():
    """Generate the tool definitions markdown file."""

    # Generate the catalog
    catalog = generate_tool_catalog()
    tool_specs = get_tool_specs_as_dicts(catalog)
    param_index = build_tool_parameter_index()

    # Sort tools by name for consistent output
    tool_specs.sort(key=lambda x: x.get('name', ''))

    # Generate header
    lines = [
        "# Tool Definitions",
        "",
        "Complete specification of available tools for the automation agent.",
        "",
        f"**Generated from tool catalog with {len(tool_specs)} tools.**",
        "",
        "**CRITICAL INSTRUCTIONS FOR TOOL USAGE:**",
        "1. **Tool Validation**: Before using ANY tool, verify it exists in this list",
        "2. **Parameter Requirements**: All REQUIRED parameters must be provided",
        "3. **Type Safety**: Match parameter types exactly (string, int, list, etc.)",
        "4. **Error Handling**: Check return values for \"error\": true field",
        "5. **Early Rejection**: If a needed tool doesn't exist, reject the task immediately with complexity=\"impossible\"",
        "",
        "---",
        "",
    ]

    # Group tools by agent for better organization
    from src.agent.agent_registry import get_agent_tool_mapping
    tool_to_agent = get_agent_tool_mapping()

    # Get agent names and sort them
    agents = sorted(set(tool_to_agent.values()))
    agent_tools = {}
    for agent in agents:
        agent_tools[agent] = [tool for tool, agent_name in tool_to_agent.items() if agent_name == agent]

    # Generate sections by agent
    for agent in agents:
        agent_name_upper = agent.upper().replace('_', ' ')
        lines.extend([
            f"## {agent_name_upper} Agent ({len(agent_tools[agent])} tools)",
            "",
        ])

        # Sort tools within agent
        agent_tool_specs = [spec for spec in tool_specs if spec['name'] in agent_tools[agent]]
        agent_tool_specs.sort(key=lambda x: x['name'])

        for tool_spec in agent_tool_specs:
            tool_name = tool_spec['name']

            # Get parameter info
            param_info = param_index.get(tool_name, {})
            required_params = param_info.get('required', [])
            optional_params = param_info.get('optional', [])

            lines.extend([
                f"### {tool_name}",
                f"**Purpose:** {tool_spec.get('description', 'No description available')}",
                "",
            ])

            # Generate call example
            example_params = {}
            if required_params:
                # Add example values for required params
                for param in required_params[:3]:  # Limit to first 3 for brevity
                    if 'path' in param.lower() or 'file' in param.lower():
                        example_params[param] = "/path/to/example"
                    elif 'url' in param.lower():
                        example_params[param] = "https://example.com"
                    elif 'query' in param.lower():
                        example_params[param] = "example search query"
                    elif 'content' in param.lower():
                        example_params[param] = "example content"
                    elif 'title' in param.lower():
                        example_params[param] = "Example Title"
                    else:
                        example_params[param] = "example_value"

            lines.extend([
                "**Complete Call Example:**",
                "```json",
                "{",
                '  "action": "' + tool_name + '",',
                '  "parameters": {',
            ])

            for i, (param, value) in enumerate(example_params.items()):
                comma = ',' if i < len(example_params) - 1 else ''
                if isinstance(value, str):
                    lines.append(f'    "{param}": "{value}"{comma}')
                else:
                    lines.append(f'    "{param}": {value}{comma}')

            lines.extend([
                '  }',
                '}',
                '```',
                '',
            ])

            # Parameter details
            if required_params or optional_params:
                lines.append("**Parameters:**")
                for param in required_params:
                    lines.append(f"- `{param}` (required)")
                for param in optional_params:
                    lines.append(f"- `{param}` (optional)")
                lines.append("")

            # Strengths and limitations
            strengths = tool_spec.get('strengths', [])
            limits = tool_spec.get('limits', [])

            if strengths:
                lines.append("**Strengths:**")
                for strength in strengths:
                    lines.append(f"- {strength}")
                lines.append("")

            if limits:
                lines.append("**Limitations:**")
                for limit in limits:
                    lines.append(f"- {limit}")
                lines.append("")

            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def main():
    """Main function to generate the tool definitions."""
    try:
        content = generate_tool_definitions_markdown()

        # Write to file
        output_path = project_root / "prompts" / "tool_definitions.md"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"Generated tool definitions with {len(get_tool_specs_as_dicts(generate_tool_catalog()))} tools")
        print(f"Written to: {output_path}")

        # Verify no tools are missing
        catalog_tools = set(tool.name for tool in generate_tool_catalog())
        all_tools = set(tool.name for tool in ALL_AGENT_TOOLS)

        if catalog_tools == all_tools:
            print("✅ All tools from ALL_AGENT_TOOLS are documented")
        else:
            missing = all_tools - catalog_tools
            extra = catalog_tools - all_tools
            if missing:
                print(f"❌ Missing tools: {missing}")
            if extra:
                print(f"⚠️  Extra tools in catalog: {extra}")

    except Exception as e:
        print(f"Error generating tool definitions: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
