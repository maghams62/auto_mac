#!/usr/bin/env python3
"""
Test script for Spotify slash command functionality.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils import load_config
from src.ui.slash_commands import SlashCommandHandler, SlashCommandParser
from src.agent.agent_registry import AgentRegistry

def test_spotify_slash_command():
    """Test Spotify slash command parsing and execution."""
    
    print("=" * 80)
    print("Testing Spotify Slash Command")
    print("=" * 80)
    
    # Load config
    print("\n1. Loading config...")
    try:
        config = load_config()
        print("   ✅ Config loaded")
    except Exception as e:
        print(f"   ❌ Config load failed: {e}")
        return False
    
    # Initialize parser
    print("\n2. Initializing slash command parser...")
    parser = SlashCommandParser()
    
    # Test command parsing
    test_commands = [
        "/spotify play",
        "/spotify pause",
        "/music play",
        "/music pause",
    ]
    
    print("\n3. Testing command parsing...")
    for cmd in test_commands:
        parsed = parser.parse(cmd)
        if parsed:
            print(f"   ✅ '{cmd}' → agent: {parsed.get('agent')}, task: {parsed.get('task')}")
        else:
            print(f"   ❌ '{cmd}' → Failed to parse")
            return False
    
    # Initialize agent registry
    print("\n4. Initializing agent registry...")
    try:
        registry = AgentRegistry(config)
        print("   ✅ Agent registry initialized")
        
        # Check if Spotify agent is registered
        spotify_agent = registry.get_agent("spotify")
        if spotify_agent:
            print("   ✅ Spotify agent found in registry")
        else:
            print("   ❌ Spotify agent NOT found in registry")
            return False
            
    except Exception as e:
        print(f"   ❌ Agent registry initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Initialize slash command handler
    print("\n5. Initializing slash command handler...")
    try:
        handler = SlashCommandHandler(registry)
        print("   ✅ Slash command handler initialized")
    except Exception as e:
        print(f"   ❌ Handler initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test command execution (dry run - don't actually play/pause)
    print("\n6. Testing command execution (dry run)...")
    test_cmd = "/spotify play"
    is_command, result = handler.handle(test_cmd)
    
    if is_command:
        print(f"   ✅ Command recognized: {test_cmd}")
        print(f"   Result type: {result.get('type') if isinstance(result, dict) else type(result)}")
        if isinstance(result, dict) and result.get('type') == 'result':
            print(f"   Agent: {result.get('agent')}")
            print(f"   Command: {result.get('command')}")
    else:
        print(f"   ❌ Command NOT recognized: {test_cmd}")
        return False
    
    # Check if tools are available
    print("\n7. Checking Spotify tools availability...")
    try:
        from src.agent.spotify_agent import SPOTIFY_AGENT_TOOLS
        print(f"   ✅ Found {len(SPOTIFY_AGENT_TOOLS)} Spotify tools:")
        for tool in SPOTIFY_AGENT_TOOLS:
            print(f"      - {tool.name}")
    except Exception as e:
        print(f"   ❌ Failed to import Spotify tools: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Check if tools are in ALL_AGENT_TOOLS
    print("\n8. Checking if Spotify tools are in ALL_AGENT_TOOLS...")
    try:
        from src.agent.agent_registry import ALL_AGENT_TOOLS
        spotify_tool_names = [tool.name for tool in SPOTIFY_AGENT_TOOLS]
        all_tool_names = [tool.name for tool in ALL_AGENT_TOOLS]
        
        found_tools = [name for name in spotify_tool_names if name in all_tool_names]
        if len(found_tools) == len(spotify_tool_names):
            print(f"   ✅ All {len(found_tools)} Spotify tools found in ALL_AGENT_TOOLS")
            for name in found_tools:
                print(f"      - {name}")
        else:
            missing = set(spotify_tool_names) - set(found_tools)
            print(f"   ❌ Missing tools in ALL_AGENT_TOOLS: {missing}")
            return False
    except Exception as e:
        print(f"   ❌ Failed to check ALL_AGENT_TOOLS: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 80)
    print("✅ All tests passed! Spotify slash command should be working.")
    print("=" * 80)
    
    return True

if __name__ == "__main__":
    success = test_spotify_slash_command()
    sys.exit(0 if success else 1)

