#!/usr/bin/env python3
"""
Test confetti slash command.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils import load_config
from src.agent.agent import AutomationAgent
from src.memory import SessionManager

def test_confetti():
    """Test /confetti slash command."""
    
    print("=" * 80)
    print("Testing /confetti Slash Command")
    print("=" * 80)
    print("\n⚠️  Note: This will trigger confetti effects on your Mac!")
    print("⚠️  Make sure notifications are enabled.\n")
    
    config = load_config()
    session_manager = SessionManager(storage_dir="data/sessions")
    agent = AutomationAgent(config, session_manager=session_manager)
    
    # Test /confetti command
    print("Testing: '/confetti'")
    print("-" * 80)
    
    try:
        result = agent.run("/confetti", session_id="test_confetti")
        
        print(f"\nResult type: {type(result)}")
        if isinstance(result, dict):
            print(f"Result keys: {list(result.keys())}")
            print(f"Message: {result.get('message', 'N/A')}")
            print(f"Status: {result.get('status', 'N/A')}")
        else:
            print(f"Result: {str(result)[:500]}")
        
        print("\n✅ Test completed!")
        print("Check your notifications - you should see confetti emojis! 🎉")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_confetti()

