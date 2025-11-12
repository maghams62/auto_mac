"""
macOS Calendar.app integration using AppleScript.

This module provides automation for Apple Calendar on macOS, allowing programmatic
reading of calendar events, attendees, and notes.
"""

import logging
import subprocess
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CalendarAutomation:
    """
    Automates Apple Calendar app on macOS using AppleScript.

    Provides methods to:
    - List upcoming events
    - Get event details by title/time
    - Export event context for LLM consumption
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Calendar automation.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.fake_data_path = os.getenv("CALENDAR_FAKE_DATA_PATH")

    def list_events(
        self,
        days_ahead: int = 7,
        calendar_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List upcoming calendar events.

        Args:
            days_ahead: Number of days to look ahead (default: 7)
            calendar_name: Optional calendar name to filter by

        Returns:
            List of normalized event dictionaries with:
            - title: Event title/summary
            - start_time: ISO format datetime string
            - end_time: ISO format datetime string
            - location: Event location (if any)
            - notes: Event notes (if any)
            - attendees: List of attendee names/emails
            - calendar_name: Calendar containing the event
            - event_id: Unique event identifier
        """
        logger.info(f"Listing events for next {days_ahead} days (calendar: {calendar_name})")

        # Check for fake data path for testing
        if self.fake_data_path and os.path.exists(self.fake_data_path):
            logger.info(f"Using fake calendar data from: {self.fake_data_path}")
            return self._load_fake_data()

        try:
            script = self._build_list_events_applescript(days_ahead, calendar_name)
            result = self._run_applescript(script)

            if result.returncode == 0:
                events = self._parse_event_list(result.stdout)
                logger.info(f"Retrieved {len(events)} events")
                return events
            else:
                error_msg = result.stderr or result.stdout or "Failed to list events"
                logger.error(f"AppleScript error: {error_msg}")
                return []

        except Exception as e:
            logger.error(f"Error listing events: {e}")
            return []

    def get_event_details(
        self,
        event_title: str,
        start_time_window: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get details for a specific event by title and optional time window.

        Args:
            event_title: Title/summary of the event to find
            start_time_window: Optional datetime to narrow search window

        Returns:
            Dictionary with event details (same structure as list_events items)
            or empty dict if not found
        """
        logger.info(f"Getting event details for: {event_title}")

        # Check for fake data path for testing
        if self.fake_data_path and os.path.exists(self.fake_data_path):
            logger.info(f"Using fake calendar data from: {self.fake_data_path}")
            fake_events = self._load_fake_data()
            # Find matching event with fuzzy matching
            event_title_lower = event_title.lower()
            for event in fake_events:
                event_title_match = event.get("title", "").lower()
                # Try exact match first
                if event_title_lower == event_title_match:
                    if start_time_window:
                        try:
                            event_start = datetime.fromisoformat(event.get("start_time", "").replace('Z', '+00:00'))
                            if abs((event_start.replace(tzinfo=None) - start_time_window.replace(tzinfo=None)).total_seconds()) < 86400:  # Within 24 hours
                                return event
                        except:
                            return event
                    else:
                        return event
                # Try partial match (fuzzy)
                elif event_title_lower in event_title_match or event_title_match in event_title_lower:
                    if start_time_window:
                        try:
                            event_start = datetime.fromisoformat(event.get("start_time", "").replace('Z', '+00:00'))
                            if abs((event_start.replace(tzinfo=None) - start_time_window.replace(tzinfo=None)).total_seconds()) < 86400:
                                return event
                        except:
                            return event
                    else:
                        return event
            return {}

        try:
            script = self._build_get_event_applescript(event_title, start_time_window)
            result = self._run_applescript(script)

            if result.returncode == 0:
                event = self._parse_event_details(result.stdout)
                if event:
                    logger.info(f"Found event: {event.get('title')}")
                return event
            else:
                error_msg = result.stderr or result.stdout or "Failed to get event details"
                logger.error(f"AppleScript error: {error_msg}")
                return {}

        except Exception as e:
            logger.error(f"Error getting event details: {e}")
            return {}

    def export_event_context(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize event data for LLM consumption.

        Args:
            event: Event dictionary from list_events or get_event_details

        Returns:
            Normalized dictionary optimized for LLM processing
        """
        if not event:
            return {}

        return {
            "title": event.get("title", ""),
            "start_time": event.get("start_time", ""),
            "end_time": event.get("end_time", ""),
            "location": event.get("location", ""),
            "notes": event.get("notes", ""),
            "attendees": event.get("attendees", []),
            "calendar_name": event.get("calendar_name", ""),
            "summary": self._build_event_summary(event)
        }

    def _build_event_summary(self, event: Dict[str, Any]) -> str:
        """Build a text summary of the event for LLM context."""
        parts = [f"Event: {event.get('title', 'Untitled')}"]
        
        if event.get("start_time"):
            parts.append(f"Time: {event.get('start_time')}")
        
        if event.get("location"):
            parts.append(f"Location: {event.get('location')}")
        
        if event.get("attendees"):
            attendees_str = ", ".join(event.get("attendees", []))
            parts.append(f"Attendees: {attendees_str}")
        
        if event.get("notes"):
            parts.append(f"Notes: {event.get('notes')}")
        
        return " | ".join(parts)

    def _load_fake_data(self) -> List[Dict[str, Any]]:
        """Load fake calendar data from JSON file for testing."""
        try:
            with open(self.fake_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "events" in data:
                    return data["events"]
                else:
                    logger.warning(f"Unexpected fake data format in {self.fake_data_path}")
                    return []
        except Exception as e:
            logger.error(f"Error loading fake calendar data: {e}")
            return []

    def _build_list_events_applescript(
        self,
        days_ahead: int,
        calendar_name: Optional[str]
    ) -> str:
        """Build AppleScript to list upcoming events."""
        end_date = datetime.now() + timedelta(days=days_ahead)
        end_date_str = end_date.strftime("%m/%d/%Y %I:%M:%S %p")
        
        calendar_filter = ""
        if calendar_name:
            calendar_escaped = self._escape_applescript_string(calendar_name)
            calendar_filter = f'of calendar "{calendar_escaped}"'

        script = f'''
        tell application "Calendar"
            set eventList to {{}}
            set nowDate to current date
            
            -- Get all calendars or specific calendar
            set calendarsToSearch to calendars
            if "{calendar_name}" is not "" then
                try
                    set calendarsToSearch to {{calendar "{calendar_name}"}}
                on error
                    set calendarsToSearch to calendars
                end try
            end if
            
            repeat with cal in calendarsToSearch
                try
                    set calEvents to events of cal whose start date ≥ nowDate and start date ≤ date "{end_date_str}"
                    repeat with evt in calEvents
                        try
                            set eventTitle to summary of evt
                            set eventStart to start date of evt
                            set eventEnd to end date of evt
                            set eventLocation to location of evt
                            set eventNotes to notes of evt
                            set eventCalendar to name of cal
                            set eventId to id of evt
                            
                            -- Get attendees
                            set attendeeList to {{}}
                            try
                                set eventAttendees to attendees of evt
                                repeat with att in eventAttendees
                                    try
                                        set attName to display name of att
                                        if attName is "" then
                                            set attName to email of att
                                        end if
                                        set end of attendeeList to attName
                                    end try
                                end repeat
                            end try
                            
                            -- Format dates as ISO strings
                            set startISO to (year of eventStart as string) & "-" & (my pad((month of eventStart as integer), 2)) & "-" & (my pad((day of eventStart as integer), 2)) & "T" & (my pad((hours of eventStart as integer), 2)) & ":" & (my pad((minutes of eventStart as integer), 2)) & ":00"
                            set endISO to (year of eventEnd as string) & "-" & (my pad((month of eventEnd as integer), 2)) & "-" & (my pad((day of eventEnd as integer), 2)) & "T" & (my pad((hours of eventEnd as integer), 2)) & ":" & (my pad((minutes of eventEnd as integer), 2)) & ":00"
                            
                            set eventData to "EVENTSTART|||" & eventTitle & "|||" & startISO & "|||" & endISO & "|||" & eventLocation & "|||" & eventNotes & "|||" & eventCalendar & "|||" & eventId & "|||" & (my join(attendeeList, "|||")) & "|||EVENTEND"
                            set end of eventList to eventData
                        end try
                    end repeat
                end try
            end repeat
            
            set AppleScript's text item delimiters to "\\n"
            return eventList as text
        end tell
        
        on pad(n, width)
            set textNum to n as string
            repeat while (length of textNum) < width
                set textNum to "0" & textNum
            end repeat
            return textNum
        end on
        
        on join(lst, delimiter)
            set AppleScript's text item delimiters to delimiter
            set result to lst as string
            set AppleScript's text item delimiters to ""
            return result
        end on
        '''
        
        return script

    def _build_get_event_applescript(
        self,
        event_title: str,
        start_time_window: Optional[datetime]
    ) -> str:
        """Build AppleScript to get a specific event by title."""
        title_escaped = self._escape_applescript_string(event_title)
        
        time_filter = ""
        if start_time_window:
            window_start = start_time_window - timedelta(days=1)
            window_end = start_time_window + timedelta(days=1)
            window_start_str = window_start.strftime("%m/%d/%Y %I:%M:%S %p")
            window_end_str = window_end.strftime("%m/%d/%Y %I:%M:%S %p")
            time_filter = f' and start date ≥ date "{window_start_str}" and start date ≤ date "{window_end_str}"'

        script = f'''
        tell application "Calendar"
            set foundEvent to missing value
            
            repeat with cal in calendars
                try
                    set calEvents to events of cal whose summary contains "{title_escaped}"{time_filter}
                    if (count of calEvents) > 0 then
                        set foundEvent to item 1 of calEvents
                        exit repeat
                    end if
                end try
            end repeat
            
            if foundEvent is not missing value then
                set eventTitle to summary of foundEvent
                set eventStart to start date of foundEvent
                set eventEnd to end date of foundEvent
                set eventLocation to location of foundEvent
                set eventNotes to notes of foundEvent
                set eventCalendar to name of calendar of foundEvent
                set eventId to id of foundEvent
                
                -- Get attendees
                set attendeeList to {{}}
                try
                    set eventAttendees to attendees of foundEvent
                    repeat with att in eventAttendees
                        try
                            set attName to display name of att
                            if attName is "" then
                                set attName to email of att
                            end if
                            set end of attendeeList to attName
                        end try
                    end repeat
                end try
                
                -- Format dates as ISO strings
                set startISO to (year of eventStart as string) & "-" & (my pad((month of eventStart as integer), 2)) & "-" & (my pad((day of eventStart as integer), 2)) & "T" & (my pad((hours of eventStart as integer), 2)) & ":" & (my pad((minutes of eventStart as integer), 2)) & ":00"
                set endISO to (year of eventEnd as string) & "-" & (my pad((month of eventEnd as integer), 2)) & "-" & (my pad((day of eventEnd as integer), 2)) & "T" & (my pad((hours of eventEnd as integer), 2)) & ":" & (my pad((minutes of eventEnd as integer), 2)) & ":00"
                
                return "EVENTSTART|||" & eventTitle & "|||" & startISO & "|||" & endISO & "|||" & eventLocation & "|||" & eventNotes & "|||" & eventCalendar & "|||" & eventId & "|||" & (my join(attendeeList, "|||")) & "|||EVENTEND"
            else
                return ""
            end if
        end tell
        
        on pad(n, width)
            set textNum to n as string
            repeat while (length of textNum) < width
                set textNum to "0" & textNum
            end repeat
            return textNum
        end on
        
        on join(lst, delimiter)
            set AppleScript's text item delimiters to delimiter
            set result to lst as string
            set AppleScript's text item delimiters to ""
            return result
        end on
        '''
        
        return script

    def _parse_event_list(self, output: str) -> List[Dict[str, Any]]:
        """Parse AppleScript output into list of event dictionaries."""
        events = []
        
        if not output or not output.strip():
            return events
        
        # Split by EVENTEND markers
        event_strings = output.split("EVENTEND")
        
        for event_str in event_strings:
            if "EVENTSTART|||" not in event_str:
                continue
            
            # Extract event data
            event_data = event_str.split("EVENTSTART|||")[-1].strip()
            parts = event_data.split("|||")
            
            if len(parts) >= 7:
                try:
                    event = {
                        "title": parts[0] if len(parts) > 0 else "",
                        "start_time": parts[1] if len(parts) > 1 else "",
                        "end_time": parts[2] if len(parts) > 2 else "",
                        "location": parts[3] if len(parts) > 3 else "",
                        "notes": parts[4] if len(parts) > 4 else "",
                        "calendar_name": parts[5] if len(parts) > 5 else "",
                        "event_id": parts[6] if len(parts) > 6 else "",
                        "attendees": parts[7:-1] if len(parts) > 7 else []
                    }
                    events.append(event)
                except Exception as e:
                    logger.warning(f"Error parsing event: {e}")
                    continue
        
        # Sort by start_time
        events.sort(key=lambda x: x.get("start_time", ""))
        
        return events

    def _parse_event_details(self, output: str) -> Dict[str, Any]:
        """Parse AppleScript output for single event details."""
        events = self._parse_event_list(output)
        return events[0] if events else {}

    def _escape_applescript_string(self, s: str) -> str:
        """
        Escape string for use in AppleScript.

        Args:
            s: String to escape

        Returns:
            Escaped string
        """
        if not s:
            return ""
        
        # Replace backslash first
        s = s.replace('\\', '\\\\')
        # Replace quotes
        s = s.replace('"', '\\"')
        # Replace newlines
        s = s.replace('\n', '\\n')
        return s

    def _run_applescript(self, script: str, timeout: int = 10) -> subprocess.CompletedProcess:
        """
        Execute AppleScript using osascript.

        Args:
            script: AppleScript code to execute
            timeout: Timeout in seconds (default: 10)

        Returns:
            CompletedProcess with returncode, stdout, stderr
        """
        try:
            result = subprocess.run(
                ['osascript', '-'],
                input=script,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
            )
            return result

        except subprocess.TimeoutExpired:
            logger.error(f"AppleScript execution timed out after {timeout}s")
            return subprocess.CompletedProcess(
                args=['osascript', '-'],
                returncode=1,
                stdout='',
                stderr=f'Timeout after {timeout}s'
            )
        except Exception as e:
            logger.error(f"Error running AppleScript: {e}")
            return subprocess.CompletedProcess(
                args=['osascript', '-'],
                returncode=1,
                stdout='',
                stderr=str(e)
            )

    def test_calendar_integration(self) -> bool:
        """
        Test if Calendar app is accessible.

        Returns:
            True if Calendar app is accessible, False otherwise
        """
        try:
            script = '''
            tell application "Calendar"
                return name
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5,
            )

            return result.returncode == 0

        except Exception as e:
            logger.error(f"Calendar integration test failed: {e}")
            return False

