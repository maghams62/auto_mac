#!/usr/bin/env python3
"""
Test natural language "play music" command.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils import load_config
from src.agent.agent import AutomationAgent
from src.memory import SessionManager

def test_play_music():
    """Test 'play music' natural language command."""
    
    print("=" * 80)
    print("Testing 'play music' Natural Language Command")
    print("=" * 80)
    
    # Load config
    config = load_config()
    
    # Initialize session manager
    session_manager = SessionManager(storage_dir="data/sessions")
    
    # Initialize agent
    agent = AutomationAgent(config, session_manager=session_manager)
    
    # Test "play music"
    print("\nTesting: 'play music'")
    print("-" * 80)
    
    try:
        result = agent.run("play music", session_id="test_spotify")
        
        print(f"\nResult status: {result.get('status', 'unknown')}")
        print(f"Full result keys: {list(result.keys())}")
        print(f"Message: {result.get('message', 'N/A')}")
        
        # Check results
        results = result.get('results', [])
        if isinstance(results, list):
            print(f"\nResults array: {len(results)} items")
            for i, res in enumerate(results):
                print(f"\n  Result {i}:")
                if isinstance(res, dict):
                    print(f"    Keys: {list(res.keys())}")
                    print(f"    Content: {str(res)[:300]}")
                else:
                    print(f"    Value: {str(res)[:200]}")
        else:
            print(f"\nResults (not a list): {results}")
        
        # Check step results
        step_results = result.get('step_results', {})
        print(f"\nStep results: {len(step_results)} steps executed")
        for step_id, step_result in step_results.items():
            print(f"\n  Step {step_id}:")
            if isinstance(step_result, dict):
                print(f"    Tool: {step_result.get('tool', 'N/A')}")
                print(f"    Success: {step_result.get('success', 'N/A')}")
                if step_result.get('output'):
                    output = step_result['output']
                    if isinstance(output, dict):
                        print(f"    Output keys: {list(output.keys())}")
                        print(f"    Message: {output.get('message', 'N/A')}")
                        print(f"    Success: {output.get('success', 'N/A')}")
                    else:
                        print(f"    Output: {str(output)[:200]}")
        
        # Check steps_executed
        steps_executed = result.get('steps_executed', [])
        if isinstance(steps_executed, list):
            print(f"\nSteps executed: {len(steps_executed)}")
            for step in steps_executed:
                print(f"  - {step.get('action', 'N/A')}: {step.get('tool', 'N/A')}")
        else:
            print(f"\nSteps executed (count): {steps_executed}")
        
        if result.get('status') == 'completed' or result.get('status') == 'success':
            final_result = result.get('final_result', {})
            if final_result.get('success'):
                print("\n✅ SUCCESS: Music should be playing!")
                print(f"Message: {final_result.get('message', 'N/A')}")
            elif final_result.get('error'):
                print("\n⚠️  Command executed but may have failed")
                print(f"Error: {final_result.get('error', 'N/A')}")
            else:
                print(f"\nFinal result: {final_result}")
        elif result.get('status') == 'error':
            print("\n❌ ERROR:")
            print(f"Error: {result.get('final_result', {}).get('error', 'Unknown error')}")
        else:
            print(f"\nStatus: {result.get('status')}")
            print(f"Final result: {result.get('final_result', {})}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 80)
    return True

if __name__ == "__main__":
    success = test_play_music()
    sys.exit(0 if success else 1)

