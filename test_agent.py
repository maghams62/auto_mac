#!/usr/bin/env python3
"""
Quick test script for the LangGraph agent.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.utils import load_config, setup_logging
from src.agent import AutomationAgent

def main():
    """Test the agent with a simple request."""
    print("🧪 Testing LangGraph Agent\n")

    # Load config
    config = load_config()
    setup_logging(config)

    # Initialize agent
    print("📦 Initializing agent...")
    agent = AutomationAgent(config)
    print("✓ Agent initialized\n")

    # Test request
    test_request = "Send me the Tesla Autopilot document"
    print(f"📝 Test request: \"{test_request}\"\n")

    # Run agent
    print("🤖 Agent planning and executing...\n")
    result = agent.run(test_request)

    # Display results
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)

    if result and not result.get("error"):
        print(f"✅ Status: {result.get('status', 'unknown')}")
        print(f"\n🎯 Goal: {result.get('goal', 'N/A')}")
        print(f"\n📊 Steps executed: {result.get('steps_executed', 0)}")

        print("\n📋 Step Results:")
        for step_id, step_result in result.get("results", {}).items():
            print(f"\n  Step {step_id}:")
            if step_result.get("error"):
                print(f"    ❌ Error: {step_result.get('message', 'Unknown error')}")
            else:
                # Show key fields
                for key, value in step_result.items():
                    if key not in ['error']:
                        if isinstance(value, str) and len(value) > 100:
                            print(f"    {key}: {value[:100]}...")
                        else:
                            print(f"    {key}: {value}")

    else:
        print(f"❌ Error: {result.get('message', 'Unknown error')}")

    print("\n" + "="*80)

if __name__ == "__main__":
    main()
