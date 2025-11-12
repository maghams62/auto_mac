#!/usr/bin/env python3
"""
Test email intent detection for send vs draft behavior.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.workflow import WorkflowPlanner
from src.config import Config

def test_email_intent():
    """Test that the planner correctly identifies send vs draft intent."""

    config = Config.from_yaml()
    planner = WorkflowPlanner(config.data)

    test_cases = [
        {
            "query": "Summarize the last 5 tweets on Bluesky and email it to me",
            "expected_send": True,
            "description": "Should auto-send when user says 'email it to me'"
        },
        {
            "query": "Get the latest news and send it to me",
            "expected_send": True,
            "description": "Should auto-send when user says 'send it to me'"
        },
        {
            "query": "Create an email with the meeting summary",
            "expected_send": False,
            "description": "Should draft when user says 'create an email'"
        },
        {
            "query": "Draft an email about the project",
            "expected_send": False,
            "description": "Should draft when user says 'draft an email'"
        }
    ]

    print("\n" + "="*80)
    print("EMAIL INTENT DETECTION TEST")
    print("="*80 + "\n")

    passed = 0
    failed = 0

    for i, test_case in enumerate(test_cases, 1):
        query = test_case["query"]
        expected_send = test_case["expected_send"]
        description = test_case["description"]

        print(f"Test {i}: {description}")
        print(f"Query: '{query}'")
        print(f"Expected send={expected_send}")

        try:
            # Plan the workflow
            result = planner.plan(query)

            # Check if planning was successful
            if result.get("error"):
                print(f"❌ FAILED: Planning error - {result.get('error_message', 'Unknown error')}")
                failed += 1
                print()
                continue

            # Look for compose_email in the plan
            plan = result.get("plan", [])
            compose_email_step = None

            for step in plan:
                if step.get("action") == "compose_email":
                    compose_email_step = step
                    break

            if not compose_email_step:
                print(f"⚠️  WARNING: No compose_email step found in plan")
                print(f"Plan: {json.dumps(plan, indent=2)}")
                failed += 1
                print()
                continue

            # Check the send parameter
            actual_send = compose_email_step.get("parameters", {}).get("send", False)

            if actual_send == expected_send:
                print(f"✅ PASSED: send={actual_send} (correct)")
                passed += 1
            else:
                print(f"❌ FAILED: send={actual_send} (expected {expected_send})")
                print(f"Full step: {json.dumps(compose_email_step, indent=2)}")
                failed += 1

        except Exception as e:
            print(f"❌ FAILED: Exception - {e}")
            failed += 1

        print()

    print("="*80)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("="*80 + "\n")

    return failed == 0

if __name__ == "__main__":
    success = test_email_intent()
    sys.exit(0 if success else 1)
