#!/usr/bin/env python3
"""Test the fix for 'zip all files starting with A and email it' request."""

import sys
sys.path.append('/Users/siddharthsuresh/Downloads/auto_mac')

from src.orchestrator.main_orchestrator import MainOrchestrator
from src.utils import load_config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_zip_and_email():
    """Test the workflow that previously failed."""
    config = load_config()
    orchestrator = MainOrchestrator(config)

    request = "zip all files starting with 'A' and email it to me"
    print(f"\n{'='*60}")
    print(f"Testing request: {request}")
    print(f"{'='*60}\n")

    result = orchestrator.execute(request)

    print(f"\n{'='*60}")
    print("RESULT:")
    print(f"{'='*60}")
    print(f"Status: {result.get('status')}")
    print(f"Goal: {result.get('goal')}")
    print(f"Steps executed: {result.get('steps_executed')}")

    if result.get('results'):
        print("\nStep Results:")
        for step_id, step_result in result['results'].items():
            print(f"\nStep {step_id}:")
            if step_result.get('error'):
                print(f"  ❌ Error: {step_result.get('error_type')}: {step_result.get('error_message')}")
            else:
                print(f"  ✓ Success")
                if step_result.get('message'):
                    print(f"  Message: {step_result['message']}")

    print(f"\n{'='*60}\n")

    return result

if __name__ == "__main__":
    result = test_zip_and_email()
    sys.exit(0 if result.get('status') == 'success' else 1)
