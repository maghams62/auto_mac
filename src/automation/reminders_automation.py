"""
macOS Reminders.app integration using AppleScript.

This module provides automation for Apple Reminders on macOS, allowing programmatic
creation and management of reminders and tasks.
"""

import logging
import subprocess
import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)


class RemindersAutomation:
    """
    Automates Apple Reminders app on macOS using AppleScript.

    Provides methods to:
    - Create new reminders
    - Set due dates and times
    - Organize reminders into lists
    - Mark reminders as complete
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Reminders automation.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.fake_data_path = os.getenv("REMINDERS_FAKE_DATA_PATH")

    def create_reminder(
        self,
        title: str,
        due_time: Optional[str] = None,
        list_name: str = "Reminders",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new reminder in Apple Reminders.

        Args:
            title: Reminder title/description
            due_time: Due date/time in natural language or ISO format
                Examples:
                - "tomorrow at 9am"
                - "today at 5pm"
                - "2024-12-25 10:00"
                - "in 2 hours"
                - None (no due date)
            list_name: Target list name (default: "Reminders")
            notes: Optional notes/details for reminder

        Returns:
            Dictionary with creation status:
            {
                "success": True,
                "reminder_title": str,
                "reminder_id": str,
                "list_name": str,
                "due_date": str,  # ISO format
                "created_at": str,
                "message": str
            }
        """
        logger.info(f"Creating reminder: {title} in list: {list_name}")

        try:
            # Parse due_time into date object
            due_date = None
            if due_time:
                due_date = self._parse_due_time(due_time)

            # Build AppleScript to create reminder
            script = self._build_create_reminder_applescript(
                title, due_date, list_name, notes
            )

            # Execute AppleScript
            result = self._run_applescript(script)

            if result.returncode == 0:
                reminder_id = result.stdout.strip()
                logger.info(f"Successfully created reminder: {title} (ID: {reminder_id})")
                return {
                    "success": True,
                    "reminder_title": title,
                    "reminder_id": reminder_id,
                    "list_name": list_name,
                    "due_date": due_date.isoformat() if due_date else None,
                    "created_at": datetime.now().isoformat(),
                    "message": f"Created reminder '{title}' in list '{list_name}'" +
                              (f" due {due_date.strftime('%Y-%m-%d %H:%M')}" if due_date else "")
                }
            else:
                from ..utils.applescript_utils import format_applescript_error
                error_info = format_applescript_error(
                    result,
                    "create reminder",
                    "Reminders.app"
                )
                logger.error(f"AppleScript error: {error_info.get('user_friendly_message', result.stderr)}")
                return {
                    "success": False,
                    "error": True,
                    "error_type": error_info.get("error_type", "AppleScriptError"),
                    "error_message": error_info.get("error_message", result.stderr or result.stdout or "Failed to create reminder"),
                    "user_friendly_message": error_info.get("user_friendly_message"),
                    "retry_possible": error_info.get("retry_possible", True)
                }

        except Exception as e:
            logger.error(f"Error creating reminder: {e}")
            return {
                "success": False,
                "error": True,
                "error_message": str(e),
                "retry_possible": False
            }

    def complete_reminder(
        self,
        reminder_title: str,
        list_name: str = "Reminders"
    ) -> Dict[str, Any]:
        """
        Mark a reminder as complete.

        Args:
            reminder_title: Title of reminder to complete
            list_name: List containing the reminder (default: "Reminders")

        Returns:
            Dictionary with completion status
        """
        logger.info(f"Completing reminder: {reminder_title} in list: {list_name}")

        try:
            # Build AppleScript to complete reminder
            script = self._build_complete_reminder_applescript(reminder_title, list_name)

            # Execute AppleScript
            result = self._run_applescript(script)

            if result.returncode == 0:
                logger.info(f"Successfully completed reminder: {reminder_title}")
                return {
                    "success": True,
                    "reminder_title": reminder_title,
                    "list_name": list_name,
                    "message": f"Completed reminder '{reminder_title}'"
                }
            else:
                error_msg = result.stderr or result.stdout or "Failed to complete reminder"
                logger.error(f"AppleScript error: {error_msg}")
                return {
                    "success": False,
                    "error": True,
                    "error_message": error_msg,
                    "retry_possible": True
                }

        except Exception as e:
            logger.error(f"Error completing reminder: {e}")
            return {
                "success": False,
                "error": True,
                "error_message": str(e),
                "retry_possible": False
            }

    def list_reminders(
        self,
        list_name: Optional[str] = None,
        include_completed: bool = False
    ) -> Dict[str, Any]:
        """
        List reminders from Apple Reminders.

        Args:
            list_name: Optional list name to filter by (None = all lists)
            include_completed: Whether to include completed reminders (default: False)

        Returns:
            Dictionary with reminders list:
            {
                "reminders": List[Dict],  # Each dict has: title, due_date, notes, list_name, completed
                "count": int,
                "list_name": Optional[str]
            }
        """
        logger.info(f"Listing reminders (list: {list_name}, include_completed: {include_completed})")

        # Check for fake data path for testing
        if self.fake_data_path and os.path.exists(self.fake_data_path):
            logger.info(f"Using fake reminders data from: {self.fake_data_path}")
            return self._load_fake_data(list_name, include_completed)

        try:
            # Build AppleScript to list reminders
            script = self._build_list_reminders_applescript(list_name, include_completed)

            # Execute AppleScript
            result = self._run_applescript(script, timeout=30)  # Increased timeout

            if result.returncode == 0:
                # Parse the output
                reminders = self._parse_reminders_list(result.stdout)
                logger.info(f"Retrieved {len(reminders)} reminders")
                return {
                    "reminders": reminders,
                    "count": len(reminders),
                    "list_name": list_name
                }
            else:
                error_msg = result.stderr or result.stdout or "Failed to list reminders"
                logger.error(f"AppleScript error: {error_msg}")
                return {
                    "reminders": [],
                    "count": 0,
                    "list_name": list_name,
                    "error": True,
                    "error_message": error_msg
                }

        except Exception as e:
            logger.error(f"Error listing reminders: {e}")
            return {
                "reminders": [],
                "count": 0,
                "list_name": list_name,
                "error": True,
                "error_message": str(e)
            }

    def _parse_due_time(self, due_time: str) -> Optional[datetime]:
        """
        Parse due time string into datetime object.

        Supports natural language and ISO format:
        - "tomorrow at 9am" -> tomorrow at 9:00
        - "today at 5pm" -> today at 17:00
        - "in 2 hours" -> 2 hours from now
        - "2024-12-25 10:00" -> specific datetime

        Args:
            due_time: Due time string

        Returns:
            datetime object or None if parsing fails
        """
        if not due_time:
            return None

        try:
            # Try ISO format first
            if re.match(r'^\d{4}-\d{2}-\d{2}', due_time):
                return datetime.fromisoformat(due_time)

            # Parse natural language
            now = datetime.now()
            due_time_lower = due_time.lower().strip()

            # Handle "tomorrow"
            if 'tomorrow' in due_time_lower:
                base_date = now + timedelta(days=1)
                time_match = re.search(r'(\d{1,2})\s*(am|pm)', due_time_lower)
                if time_match:
                    hour = int(time_match.group(1))
                    if time_match.group(2) == 'pm' and hour != 12:
                        hour += 12
                    elif time_match.group(2) == 'am' and hour == 12:
                        hour = 0
                    return base_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                else:
                    return base_date.replace(hour=9, minute=0, second=0, microsecond=0)

            # Handle "today"
            if 'today' in due_time_lower:
                base_date = now
                time_match = re.search(r'(\d{1,2})\s*(am|pm)', due_time_lower)
                if time_match:
                    hour = int(time_match.group(1))
                    if time_match.group(2) == 'pm' and hour != 12:
                        hour += 12
                    elif time_match.group(2) == 'am' and hour == 12:
                        hour = 0
                    return base_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                else:
                    return base_date.replace(hour=17, minute=0, second=0, microsecond=0)

            # Handle "in X hours/minutes"
            hours_match = re.search(r'in\s+(\d+)\s+hour', due_time_lower)
            if hours_match:
                hours = int(hours_match.group(1))
                return now + timedelta(hours=hours)

            minutes_match = re.search(r'in\s+(\d+)\s+minute', due_time_lower)
            if minutes_match:
                minutes = int(minutes_match.group(1))
                return now + timedelta(minutes=minutes)

            # Default: parse as time today
            time_match = re.search(r'(\d{1,2})\s*(am|pm)', due_time_lower)
            if time_match:
                hour = int(time_match.group(1))
                if time_match.group(2) == 'pm' and hour != 12:
                    hour += 12
                elif time_match.group(2) == 'am' and hour == 12:
                    hour = 0
                return now.replace(hour=hour, minute=0, second=0, microsecond=0)

            # Fallback: return None
            logger.warning(f"Could not parse due_time: {due_time}")
            return None

        except Exception as e:
            logger.warning(f"Error parsing due_time '{due_time}': {e}")
            return None

    def _build_create_reminder_applescript(
        self,
        title: str,
        due_date: Optional[datetime],
        list_name: str,
        notes: Optional[str]
    ) -> str:
        """
        Build AppleScript for creating a reminder.

        Args:
            title: Reminder title
            due_date: Due date as datetime object
            list_name: Target list
            notes: Optional notes

        Returns:
            AppleScript string
        """
        # Escape strings
        title_escaped = self._escape_applescript_string(title)
        list_escaped = self._escape_applescript_string(list_name)
        notes_escaped = self._escape_applescript_string(notes) if notes else ""

        # Build properties
        properties = f'{{name:"{title_escaped}"'
        if notes:
            properties += f', body:"{notes_escaped}"'
        if due_date:
            # Format date for AppleScript
            date_str = due_date.strftime('%m/%d/%Y %I:%M:%S %p')
            properties += f', due date:date "{date_str}"'
        properties += '}'

        script = f'''
        tell application "Reminders"
            activate

            -- Get or create list
            set targetList to missing value
            try
                set targetList to list "{list_escaped}"
            on error
                -- List doesn't exist, create it
                set targetList to make new list with properties {{name:"{list_escaped}"}}
            end try

            -- Create reminder
            set newReminder to make new reminder at end of targetList with properties {properties}

            -- Return reminder ID
            return id of newReminder
        end tell
        '''

        return script

    def _build_complete_reminder_applescript(
        self,
        reminder_title: str,
        list_name: str
    ) -> str:
        """
        Build AppleScript for completing a reminder.

        Args:
            reminder_title: Reminder title
            list_name: List containing reminder

        Returns:
            AppleScript string
        """
        # Escape strings
        title_escaped = self._escape_applescript_string(reminder_title)
        list_escaped = self._escape_applescript_string(list_name)

        script = f'''
        tell application "Reminders"
            set targetList to list "{list_escaped}"
            set foundReminder to first reminder of targetList whose name is "{title_escaped}"
            set completed of foundReminder to true
            return "Success"
        end tell
        '''

        return script

    def _build_list_reminders_applescript(
        self,
        list_name: Optional[str],
        include_completed: bool
    ) -> str:
        """
        Build AppleScript for listing reminders.

        Args:
            list_name: Optional list name to filter by
            include_completed: Whether to include completed reminders

        Returns:
            AppleScript string
        """
        if list_name:
            list_escaped = self._escape_applescript_string(list_name)
            script = f'''
            tell application "Reminders"
                set targetList to list "{list_escaped}"
                set remindersList to {{}}
                repeat with aReminder in reminders of targetList
                    if completed of aReminder is {str(include_completed).lower()} then
                        set reminderInfo to name of aReminder & "|" & (body of aReminder as string) & "|" & (due date of aReminder as string) & "|" & (completed of aReminder as string) & "|" & name of targetList
                        set end of remindersList to reminderInfo
                    end if
                end repeat
                return remindersList
            end tell
            '''
        else:
            script = f'''
            tell application "Reminders"
                set remindersList to {{}}
                repeat with aList in lists
                    repeat with aReminder in reminders of aList
                        if completed of aReminder is {str(include_completed).lower()} then
                            set reminderInfo to name of aReminder & "|" & (body of aReminder as string) & "|" & (due date of aReminder as string) & "|" & (completed of aReminder as string) & "|" & name of aList
                            set end of remindersList to reminderInfo
                        end if
                    end repeat
                end repeat
                return remindersList
            end tell
            '''

        return script

    def _parse_reminders_list(self, output: str) -> List[Dict[str, Any]]:
        """
        Parse AppleScript output into list of reminder dictionaries.

        Args:
            output: AppleScript output string

        Returns:
            List of reminder dictionaries
        """
        reminders = []
        
        if not output or not output.strip():
            return reminders

        # AppleScript returns a list like: {"title|notes|due_date|completed|list_name", "title2|...", ...}
        # The output might be on one line or multiple lines
        # Remove surrounding braces and split by comma or newline
        cleaned = output.strip()
        
        # Remove outer braces if present
        if cleaned.startswith('{') and cleaned.endswith('}'):
            cleaned = cleaned[1:-1].strip()
        
        # Split by comma (AppleScript list separator) or newline
        items = []
        if ',' in cleaned:
            # Split by comma, handling quoted strings
            import re
            # Match items separated by commas, handling quoted strings
            items = re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', cleaned)
        else:
            # Split by newline
            items = cleaned.split('\n')
        
        for item in items:
            item = item.strip()
            if not item or item == '{}':
                continue
            
            # Remove surrounding quotes if present
            item = item.strip('"').strip("'").strip()
            
            # Split by pipe delimiter
            parts = item.split('|')
            if len(parts) >= 5:
                title = parts[0].strip()
                notes = parts[1].strip() if parts[1].strip() != 'missing value' else None
                due_date_str = parts[2].strip() if parts[2].strip() != 'missing value' else None
                completed_str = parts[3].strip()
                list_name = parts[4].strip()
                
                # Parse due date
                due_date = None
                if due_date_str and due_date_str != 'missing value':
                    try:
                        # Try ISO format first
                        due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                    except Exception:
                        try:
                            # AppleScript date format: "Monday, January 1, 2024 at 12:00:00 PM"
                            # Try to parse it with dateutil if available
                            try:
                                from dateutil import parser
                                due_date = parser.parse(due_date_str)
                            except ImportError:
                                # dateutil not available, try basic parsing
                                logger.warning(f"dateutil not available, skipping date parsing: {due_date_str}")
                        except Exception:
                            logger.warning(f"Could not parse due_date: {due_date_str}")
                
                # Parse completed status
                completed = completed_str.lower() == 'true'
                
                reminders.append({
                    "title": title,
                    "notes": notes,
                    "due_date": due_date.isoformat() if due_date else None,
                    "completed": completed,
                    "list_name": list_name
                })
        
        return reminders

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

    def test_reminders_integration(self) -> bool:
        """
        Test if Reminders app is accessible.

        Returns:
            True if Reminders app is accessible, False otherwise
        """
        try:
            script = '''
            tell application "Reminders"
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
            logger.error(f"Reminders integration test failed: {e}")
            return False

    def _load_fake_data(self, list_name: Optional[str] = None, include_completed: bool = False) -> Dict[str, Any]:
        """Load fake reminders data from JSON file for testing."""
        try:
            with open(self.fake_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    reminders = data
                elif isinstance(data, dict) and "reminders" in data:
                    reminders = data["reminders"]
                else:
                    logger.warning(f"Unexpected fake data format in {self.fake_data_path}")
                    return {"reminders": [], "count": 0, "list_name": list_name}
                
                # Filter by list_name if specified
                if list_name:
                    reminders = [r for r in reminders if r.get("list_name") == list_name]
                
                # Filter completed if needed
                if not include_completed:
                    reminders = [r for r in reminders if not r.get("completed", False)]
                
                return {
                    "reminders": reminders,
                    "count": len(reminders),
                    "list_name": list_name
                }
        except Exception as e:
            logger.error(f"Error loading fake reminders data: {e}")
            return {"reminders": [], "count": 0, "list_name": list_name}
