#!/usr/bin/env python3
"""
Functional test for Spotify integration - actually tests play/pause commands.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils import load_config
from src.ui.slash_commands import SlashCommandHandler
from src.agent.agent_registry import AgentRegistry

def test_spotify_functional():
    """Test actual Spotify command execution."""
    
    print("=" * 80)
    print("Functional Spotify Test")
    print("=" * 80)
    print("\n⚠️  This test will attempt to control Spotify.")
    print("   Make sure Spotify is installed and running (or it will fail gracefully).\n")
    
    # Load config
    config = load_config()
    
    # Initialize handler
    registry = AgentRegistry(config)
    handler = SlashCommandHandler(registry)
    
    # Test play command
    print("1. Testing '/spotify play' command...")
    is_cmd, result = handler.handle("/spotify play")
    
    if is_cmd:
        print(f"   ✅ Command recognized")
        if isinstance(result, dict):
            if result.get('type') == 'result':
                tool_result = result.get('result', {})
                if tool_result.get('success'):
                    print(f"   ✅ Play command executed successfully!")
                    print(f"   Message: {tool_result.get('message', 'N/A')}")
                elif tool_result.get('error'):
                    print(f"   ⚠️  Play command failed (expected if Spotify not running):")
                    print(f"   Error: {tool_result.get('error_message', 'Unknown error')}")
                else:
                    print(f"   Result: {tool_result}")
            else:
                print(f"   Result type: {result.get('type')}")
                print(f"   Content: {result.get('content', 'N/A')[:200]}")
        else:
            print(f"   Result: {result}")
    else:
        print(f"   ❌ Command NOT recognized")
        return False
    
    # Test pause command
    print("\n2. Testing '/spotify pause' command...")
    is_cmd, result = handler.handle("/spotify pause")
    
    if is_cmd:
        print(f"   ✅ Command recognized")
        if isinstance(result, dict):
            if result.get('type') == 'result':
                tool_result = result.get('result', {})
                if tool_result.get('success'):
                    print(f"   ✅ Pause command executed successfully!")
                    print(f"   Message: {tool_result.get('message', 'N/A')}")
                elif tool_result.get('error'):
                    print(f"   ⚠️  Pause command failed (expected if Spotify not running):")
                    print(f"   Error: {tool_result.get('error_message', 'Unknown error')}")
                else:
                    print(f"   Result: {tool_result}")
            else:
                print(f"   Result type: {result.get('type')}")
    else:
        print(f"   ❌ Command NOT recognized")
        return False
    
    # Test status command
    print("\n3. Testing '/spotify status' command...")
    is_cmd, result = handler.handle("/spotify status")
    
    if is_cmd:
        print(f"   ✅ Command recognized")
        if isinstance(result, dict):
            if result.get('type') == 'result':
                tool_result = result.get('result', {})
                if tool_result.get('success'):
                    print(f"   ✅ Status command executed successfully!")
                    print(f"   Status: {tool_result.get('status', 'N/A')}")
                    if tool_result.get('track'):
                        print(f"   Track: {tool_result.get('track')} by {tool_result.get('artist', 'Unknown')}")
                elif tool_result.get('error'):
                    print(f"   ⚠️  Status command failed (expected if Spotify not running):")
                    print(f"   Error: {tool_result.get('error_message', 'Unknown error')}")
                else:
                    print(f"   Result: {tool_result}")
    
    print("\n" + "=" * 80)
    print("✅ Functional test completed!")
    print("=" * 80)
    print("\nNote: If commands failed, make sure:")
    print("  1. Spotify desktop app is installed")
    print("  2. Spotify is running")
    print("  3. You have granted necessary permissions")
    print("=" * 80)
    
    return True

if __name__ == "__main__":
    try:
        success = test_spotify_functional()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

