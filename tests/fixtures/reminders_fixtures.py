"""
Reminders test fixtures and utilities for testing reminders functionality.

Provides mock reminders data and helper functions for testing.
"""

import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta


def get_mock_reminders() -> List[Dict[str, Any]]:
    """
    Get mock reminders from JSON file.
    
    Returns:
        List of reminder dictionaries matching the format
        returned by list_reminders tool.
    """
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "reminders_mock.json"
    )
    
    try:
        with open(fixture_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "reminders" in data:
                return data["reminders"]
            else:
                return []
    except Exception as e:
        print(f"Error loading mock reminders: {e}")
        return []


def create_mock_reminders_response(list_name: Optional[str] = None, include_completed: bool = False) -> Dict[str, Any]:
    """
    Create a mock reminders response matching list_reminders output format.
    
    Args:
        list_name: Optional list name to filter by
        include_completed: Whether to include completed reminders
    
    Returns:
        Dictionary matching list_reminders output:
        {
            "reminders": [...],
            "count": int,
            "list_name": Optional[str]
        }
    """
    all_reminders = get_mock_reminders()
    
    # Filter by list_name if specified
    if list_name:
        all_reminders = [r for r in all_reminders if r.get("list_name") == list_name]
    
    # Filter completed if needed
    if not include_completed:
        all_reminders = [r for r in all_reminders if not r.get("completed", False)]
    
    return {
        "reminders": all_reminders,
        "count": len(all_reminders),
        "list_name": list_name
    }


def get_mock_reminders_fixture_path() -> str:
    """
    Get the absolute path to the mock reminders JSON file.
    
    Returns:
        Absolute path to reminders_mock.json
    """
    return os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "reminders_mock.json"
        )
    )


def setup_mock_reminders_env() -> str:
    """
    Set REMINDERS_FAKE_DATA_PATH environment variable and return the path.
    
    Returns:
        Path to mock reminders data file
    """
    fixture_path = get_mock_reminders_fixture_path()
    os.environ['REMINDERS_FAKE_DATA_PATH'] = fixture_path
    return fixture_path

