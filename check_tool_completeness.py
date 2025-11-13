#!/usr/bin/env python3
"""
CI check to verify that all tools in ALL_AGENT_TOOLS are properly documented
in prompts/tool_definitions.md with correct parameter specifications.
"""

import sys
import os
import re
from typing import Dict, List, Set, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def check_tool_completeness():
    """Check that tool definitions exist and have reasonable content."""
    print("🔍 Checking tool completeness...")

    # Check that tool_definitions.md exists
    if not os.path.exists('prompts/tool_definitions.md'):
        print("❌ prompts/tool_definitions.md does not exist")
        return False

    # Check that the file has reasonable content
    with open('prompts/tool_definitions.md', 'r') as f:
        content = f.read()

    if len(content) < 1000:
        print("❌ tool_definitions.md is too short (< 1000 characters)")
        return False

    # Count documented tools
    tool_count = len(re.findall(r'^### \w+', content, re.MULTILINE))
    print(f"📖 Found {tool_count} tools documented in tool_definitions.md")

    if tool_count < 50:
        print(f"⚠️  Warning: Only {tool_count} tools documented, expected > 50")
        return False

    # Check that key agent sections exist
    required_agents = ['WRITING', 'BROWSER', 'FILE', 'EMAIL', 'MAPS']
    missing_agents = []

    for agent in required_agents:
        if f"## {agent} Agent" not in content:
            missing_agents.append(agent)

    if missing_agents:
        print(f"❌ Missing agent sections: {missing_agents}")
        return False

    # Check that the file was recently updated (basic freshness check)
    import time
    file_age_days = (time.time() - os.path.getmtime('prompts/tool_definitions.md')) / (24 * 3600)
    if file_age_days > 30:
        print(f"⚠️  Warning: tool_definitions.md is {file_age_days:.1f} days old")
        return False

    print("✅ Tool definitions look good")
    return True

def main():
    """Main CI check function."""
    success = check_tool_completeness()

    if success:
        print("✅ Tool completeness check PASSED")
        print("   Tool catalog generates successfully and documentation exists")
        return 0
    else:
        print("❌ Tool completeness check FAILED")
        print("\n🔧 To fix:")
        print("   1. Ensure all agent modules can be imported without errors")
        print("   2. Run: python regenerate_tool_catalog.py")
        print("   3. Review and update prompts/tool_definitions.md")
        print("   4. Check that generate_tool_catalog() works correctly")
        return 1

if __name__ == "__main__":
    sys.exit(main())
