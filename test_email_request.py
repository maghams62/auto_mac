#!/usr/bin/env python3
"""
Test the agent with a real email + screenshot request.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.utils import load_config, setup_logging
from src.agent import AutomationAgent

def main():
    print("🧪 Testing: Screenshot + Email Workflow\n")

    config = load_config()
    setup_logging(config)

    agent = AutomationAgent(config)

    # Your request
    request = "send just the pre-chorus of the night we met to spamstuff062@gmail.com this should take a screenshot and send to the email"

    print(f"📝 Request: {request}\n")
    print("🤖 Agent processing...\n")

    result = agent.run(request)

    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)

    if result and not result.get("error"):
        print(f"✅ Goal: {result.get('goal', 'N/A')}")
        print(f"\n📊 Steps executed: {result.get('steps_executed', 0)}\n")

        for step_id, step_result in result.get("results", {}).items():
            print(f"Step {step_id}:")
            if step_result.get("error"):
                print(f"  ❌ {step_result.get('message', 'Error')}")
            else:
                # Show key info
                if 'doc_title' in step_result:
                    print(f"  ✓ Found: {step_result['doc_title']}")
                elif 'screenshot_paths' in step_result:
                    print(f"  ✓ Screenshots: {len(step_result['screenshot_paths'])} captured")
                elif 'status' in step_result:
                    print(f"  ✓ Email: {step_result['status']}")
                else:
                    print(f"  ✓ Completed")
            print()
    else:
        print(f"❌ Error: {result.get('message', 'Unknown error')}")

    print("="*80)

if __name__ == "__main__":
    main()
