"""
Calendar test fixtures and utilities for testing calendar summarization.

Provides mock calendar event data and helper functions for testing.
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


def get_mock_calendar_events() -> List[Dict[str, Any]]:
    """
    Get mock calendar events from JSON file.
    
    Returns:
        List of calendar event dictionaries matching the format
        returned by list_calendar_events tool.
    """
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "calendar_events_mock.json"
    )
    
    try:
        with open(fixture_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "events" in data:
                return data["events"]
            else:
                return []
    except Exception as e:
        print(f"Error loading mock calendar events: {e}")
        return []


def create_mock_calendar_response(days_ahead: int = 7) -> Dict[str, Any]:
    """
    Create a mock calendar response matching list_calendar_events output format.
    
    Args:
        days_ahead: Number of days to look ahead (filters events)
    
    Returns:
        Dictionary matching list_calendar_events output:
        {
            "events": [...],
            "count": int,
            "days_ahead": int
        }
    """
    all_events = get_mock_calendar_events()
    filtered_events = filter_events_by_days(all_events, days_ahead)
    
    return {
        "events": filtered_events,
        "count": len(filtered_events),
        "days_ahead": days_ahead
    }


def filter_events_by_days(events: List[Dict[str, Any]], days_ahead: int) -> List[Dict[str, Any]]:
    """
    Filter events to only include those within the specified days ahead.
    
    Args:
        events: List of calendar event dictionaries
        days_ahead: Number of days to look ahead from now
    
    Returns:
        Filtered list of events within the time window
    """
    now = datetime.now()
    end_date = now + timedelta(days=days_ahead)
    
    filtered = []
    for event in events:
        start_time_str = event.get("start_time")
        if not start_time_str:
            continue
        
        try:
            # Parse ISO format datetime
            event_start = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            # Handle timezone-naive datetimes
            if event_start.tzinfo is None:
                event_start = event_start.replace(tzinfo=None)
            
            # Compare with timezone-naive now
            if now.replace(tzinfo=None) <= event_start <= end_date.replace(tzinfo=None):
                filtered.append(event)
        except (ValueError, AttributeError) as e:
            # Skip events with invalid dates
            continue
    
    return filtered


def get_events_by_type(events: List[Dict[str, Any]], event_type: str) -> List[Dict[str, Any]]:
    """
    Filter events by type (meeting, all-day, personal, work, etc.).
    
    Args:
        events: List of calendar event dictionaries
        event_type: Type to filter by:
            - "meeting": Events with attendees
            - "all-day": Events that span entire day (start_time at 00:00:00)
            - "personal": Events from Personal calendar
            - "work": Events from Work calendar
    
    Returns:
        Filtered list of events matching the type
    """
    filtered = []
    
    for event in events:
        if event_type == "meeting":
            # Meeting events have attendees
            if event.get("attendees") and len(event.get("attendees", [])) > 0:
                filtered.append(event)
        elif event_type == "all-day":
            # All-day events start at 00:00:00
            start_time = event.get("start_time", "")
            if start_time and "T00:00:00" in start_time:
                filtered.append(event)
        elif event_type == "personal":
            # Personal calendar events
            if event.get("calendar_name", "").lower() == "personal":
                filtered.append(event)
        elif event_type == "work":
            # Work calendar events
            if event.get("calendar_name", "").lower() == "work":
                filtered.append(event)
    
    return filtered


def get_events_by_title_keyword(events: List[Dict[str, Any]], keyword: str) -> List[Dict[str, Any]]:
    """
    Filter events by title keyword (case-insensitive).
    
    Args:
        events: List of calendar event dictionaries
        keyword: Keyword to search for in event titles
    
    Returns:
        Filtered list of events containing keyword in title
    """
    keyword_lower = keyword.lower()
    return [
        event for event in events
        if keyword_lower in event.get("title", "").lower()
    ]


def format_events_for_synthesis(events: List[Dict[str, Any]]) -> str:
    """
    Format events as JSON string for passing to synthesize_content.
    
    Args:
        events: List of calendar event dictionaries
    
    Returns:
        JSON string representation of events
    """
    return json.dumps({"events": events, "count": len(events)}, indent=2)


def get_mock_calendar_fixture_path() -> str:
    """
    Get the absolute path to the mock calendar events JSON file.
    
    Returns:
        Absolute path to calendar_events_mock.json
    """
    return os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "calendar_events_mock.json"
        )
    )


def setup_mock_calendar_env() -> str:
    """
    Set CALENDAR_FAKE_DATA_PATH environment variable and return the path.
    
    Returns:
        Path to mock calendar data file
    """
    fixture_path = get_mock_calendar_fixture_path()
    os.environ['CALENDAR_FAKE_DATA_PATH'] = fixture_path
    return fixture_path

