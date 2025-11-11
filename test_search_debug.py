#!/usr/bin/env python3
"""
Test script to debug search command output issue.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.agent.agent import AutomationAgent
from src.utils import load_config
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_search_command():
    """Test the /search slash command."""
    # Load config
    config = load_config()

    # Create agent
    agent = AutomationAgent(config)

    # Test slash command
    print("\n" + "="*80)
    print("TEST 1: Slash Command - /search what's arsenal's last score")
    print("="*80)
    result = agent.run("/search what's arsenal's last score", session_id="test-debug-session")

    print("\n--- RESULT ---")
    print(f"Status: {result.get('status')}")
    print(f"Message: {result.get('message')}")
    print(f"\nFull Result Structure:")
    import json
    print(json.dumps(result, indent=2, default=str))

    # Test natural language
    print("\n" + "="*80)
    print("TEST 2: Natural Language - search arsenal's latest score")
    print("="*80)
    result2 = agent.run("search arsenal's latest score", session_id="test-debug-session-2")

    print("\n--- RESULT ---")
    print(f"Status: {result2.get('status')}")
    print(f"Message: {result2.get('message')}")
    print(f"\nFull Result Structure:")
    print(json.dumps(result2, indent=2, default=str))

if __name__ == "__main__":
    test_search_command()
