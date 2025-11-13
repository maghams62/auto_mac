#!/usr/bin/env python3
"""
CI check to ensure tool_definitions.md is up to date with ALL_AGENT_TOOLS.

This script verifies that prompts/tool_definitions.md contains documentation
for all tools in ALL_AGENT_TOOLS and no extra tools.
"""

import sys
import os
from pathlib import Path
import difflib

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.orchestrator.tools_catalog import generate_tool_catalog
from src.agent import ALL_AGENT_TOOLS
from scripts.generate_tool_definitions import generate_tool_definitions_markdown


def check_tool_definitions():
    """Check if tool definitions are up to date."""

    # Generate current catalog
    catalog = generate_tool_catalog()
    catalog_tools = set(tool.name for tool in catalog)
    all_tools = set(tool.name for tool in ALL_AGENT_TOOLS)

    # Check for missing tools
    missing_tools = all_tools - catalog_tools
    if missing_tools:
        print(f"❌ ERROR: {len(missing_tools)} tools missing from catalog:")
        for tool in sorted(missing_tools):
            print(f"  - {tool}")
        return False

    # Check for extra tools in catalog
    extra_tools = catalog_tools - all_tools
    if extra_tools:
        print(f"⚠️  WARNING: {len(extra_tools)} extra tools in catalog:")
        for tool in sorted(extra_tools):
            print(f"  - {tool}")

    # Generate expected content
    expected_content = generate_tool_definitions_markdown()

    # Read current content
    tool_defs_path = project_root / "prompts" / "tool_definitions.md"
    if not tool_defs_path.exists():
        print(f"❌ ERROR: {tool_defs_path} does not exist")
        return False

    with open(tool_defs_path, 'r', encoding='utf-8') as f:
        current_content = f.read()

    # Check if content matches
    if current_content == expected_content:
        print(f"✅ Tool definitions are up to date ({len(catalog_tools)} tools documented)")
        return True
    else:
        print("❌ ERROR: Tool definitions are out of date")
        print("\nDiff:")
        diff = difflib.unified_diff(
            current_content.splitlines(keepends=True),
            expected_content.splitlines(keepends=True),
            fromfile="current",
            tofile="expected",
            lineterm=""
        )
        sys.stdout.writelines(diff)
        print(f"\nTo fix, run: python scripts/generate_tool_definitions.py")
        return False


def main():
    """Main function."""
    try:
        success = check_tool_definitions()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
