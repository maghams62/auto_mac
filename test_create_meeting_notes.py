#!/usr/bin/env python3
"""
Test script for create_meeting_notes functionality
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from src.agent.writing_agent import create_meeting_notes

def test_create_meeting_notes():
    """Test create_meeting_notes with the agent atomicity audit document"""

    # Read the test document
    doc_path = "/Users/siddharthsuresh/Downloads/auto_mac/docs/changelog/AGENT_ATOMICITY_AUDIT.md"

    try:
        with open(doc_path, 'r') as f:
            content = f.read()

        print(f"Testing create_meeting_notes with document: {doc_path}")
        print(f"Content length: {len(content)} characters")
        print("=" * 80)

        # Call create_meeting_notes as a tool
        result = create_meeting_notes.invoke({
            "content": content,
            "meeting_title": "Agent Atomicity Audit Review",
            "include_action_items": True
        })

        print("RESULT:")
        print("=" * 80)

        # Print the structured output
        if 'formatted_notes' in result:
            print("FORMATTED NOTES:")
            print(result['formatted_notes'])
            print()

        if 'discussion_points' in result:
            print("DISCUSSION POINTS:")
            for i, point in enumerate(result['discussion_points'], 1):
                print(f"{i}. {point}")
            print()

        if 'decisions' in result:
            print("DECISIONS:")
            for i, decision in enumerate(result['decisions'], 1):
                print(f"{i}. {decision}")
            print()

        if 'action_items' in result:
            print("ACTION ITEMS:")
            for i, item in enumerate(result['action_items'], 1):
                print(f"{i}. {item}")
            print()

        print("Raw result structure:")
        print(f"Keys: {list(result.keys())}")

        return result

    except Exception as e:
        print(f"Error testing create_meeting_notes: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_create_meeting_notes()
