"""
macOS Notes.app integration using AppleScript.

This module provides automation for Apple Notes on macOS, allowing programmatic
creation, modification, and organization of notes.
"""

import logging
import subprocess
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class NotesAutomation:
    """
    Automates Apple Notes app on macOS using AppleScript.

    Provides methods to:
    - Create new notes
    - Append content to existing notes
    - Organize notes into folders
    - Search and retrieve notes
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Notes automation.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

    def create_note(
        self,
        title: str,
        body: str,
        folder: str = "Notes"
    ) -> Dict[str, Any]:
        """
        Create a new note in Apple Notes.

        Args:
            title: Note title
            body: Note content/body text
            folder: Target folder name (default: "Notes")

        Returns:
            Dictionary with creation status:
            {
                "success": True,
                "note_title": str,
                "note_id": str,
                "folder": str,
                "created_at": str,
                "message": str
            }
        """
        logger.info(f"Creating note: {title} in folder: {folder}")

        try:
            # Build AppleScript to create note
            script = self._build_create_note_applescript(title, body, folder)

            # Execute AppleScript
            result = self._run_applescript(script)

            if result.returncode == 0:
                note_id = result.stdout.strip()
                logger.info(f"Successfully created note: {title} (ID: {note_id})")
                return {
                    "success": True,
                    "note_title": title,
                    "note_id": note_id,
                    "folder": folder,
                    "created_at": datetime.now().isoformat(),
                    "message": f"Created note '{title}' in folder '{folder}'"
                }
            else:
                error_msg = result.stderr or result.stdout or "Failed to create note"
                logger.error(f"AppleScript error: {error_msg}")
                return {
                    "success": False,
                    "error": True,
                    "error_message": error_msg,
                    "retry_possible": True
                }

        except Exception as e:
            logger.error(f"Error creating note: {e}")
            return {
                "success": False,
                "error": True,
                "error_message": str(e),
                "retry_possible": False
            }

    def append_note(
        self,
        note_title: str,
        content: str,
        folder: str = "Notes"
    ) -> Dict[str, Any]:
        """
        Append content to an existing note (or create if doesn't exist).

        Args:
            note_title: Title of note to append to
            content: Content to append
            folder: Folder containing the note (default: "Notes")

        Returns:
            Dictionary with append status:
            {
                "success": True,
                "note_title": str,
                "appended_content_length": int,
                "message": str
            }
        """
        logger.info(f"Appending to note: {note_title} in folder: {folder}")

        try:
            # Build AppleScript to append to note
            script = self._build_append_note_applescript(note_title, content, folder)

            # Execute AppleScript
            result = self._run_applescript(script)

            if result.returncode == 0:
                output = result.stdout.strip()
                logger.info(f"Successfully appended to note: {note_title}")
                return {
                    "success": True,
                    "note_title": note_title,
                    "appended_content_length": len(content),
                    "folder": folder,
                    "message": f"Appended content to note '{note_title}'"
                }
            else:
                error_msg = result.stderr or result.stdout or "Failed to append to note"
                logger.error(f"AppleScript error: {error_msg}")
                return {
                    "success": False,
                    "error": True,
                    "error_message": error_msg,
                    "retry_possible": True
                }

        except Exception as e:
            logger.error(f"Error appending to note: {e}")
            return {
                "success": False,
                "error": True,
                "error_message": str(e),
                "retry_possible": False
            }

    def get_note(
        self,
        note_title: str,
        folder: str = "Notes"
    ) -> Dict[str, Any]:
        """
        Retrieve a note by title.

        Args:
            note_title: Title of note to retrieve
            folder: Folder containing the note (default: "Notes")

        Returns:
            Dictionary with note content:
            {
                "success": True,
                "note_title": str,
                "note_body": str,
                "folder": str,
                "modified_at": str
            }
        """
        logger.info(f"Retrieving note: {note_title} from folder: {folder}")

        try:
            # Build AppleScript to get note content
            script = self._build_get_note_applescript(note_title, folder)

            # Execute AppleScript
            result = self._run_applescript(script)

            if result.returncode == 0:
                note_body = result.stdout.strip()
                logger.info(f"Successfully retrieved note: {note_title}")
                return {
                    "success": True,
                    "note_title": note_title,
                    "note_body": note_body,
                    "folder": folder,
                    "message": f"Retrieved note '{note_title}'"
                }
            else:
                error_msg = result.stderr or result.stdout or "Failed to retrieve note"
                logger.error(f"AppleScript error: {error_msg}")
                return {
                    "success": False,
                    "error": True,
                    "error_message": error_msg,
                    "retry_possible": True
                }

        except Exception as e:
            logger.error(f"Error retrieving note: {e}")
            return {
                "success": False,
                "error": True,
                "error_message": str(e),
                "retry_possible": False
            }

    def _build_create_note_applescript(
        self,
        title: str,
        body: str,
        folder: str
    ) -> str:
        """
        Build AppleScript for creating a new note.

        Args:
            title: Note title
            body: Note body
            folder: Target folder

        Returns:
            AppleScript string
        """
        # Escape strings
        title_escaped = self._escape_applescript_string(title)
        body_escaped = self._escape_applescript_string(body)
        folder_escaped = self._escape_applescript_string(folder)

        script = f'''
        tell application "Notes"
            -- Create or get folder
            set targetFolder to missing value
            try
                set targetFolder to folder "{folder_escaped}"
            on error
                -- Folder doesn't exist, use default account's Notes folder
                set targetFolder to folder "Notes" of default account
            end try

            -- Create note with title and body
            set newNote to make new note at targetFolder with properties {{name:"{title_escaped}", body:"{title_escaped}\\n\\n{body_escaped}"}}

            -- Return note ID
            return id of newNote
        end tell
        '''

        return script

    def _build_append_note_applescript(
        self,
        note_title: str,
        content: str,
        folder: str
    ) -> str:
        """
        Build AppleScript for appending to an existing note.

        Args:
            note_title: Note title
            content: Content to append
            folder: Folder containing note

        Returns:
            AppleScript string
        """
        # Escape strings
        title_escaped = self._escape_applescript_string(note_title)
        content_escaped = self._escape_applescript_string(content)
        folder_escaped = self._escape_applescript_string(folder)

        script = f'''
        tell application "Notes"
            set targetFolder to missing value
            try
                set targetFolder to folder "{folder_escaped}"
            on error
                set targetFolder to folder "Notes" of default account
            end try

            -- Find existing note or create new one
            set foundNote to missing value
            try
                set foundNote to first note of targetFolder whose name is "{title_escaped}"
            on error
                -- Note doesn't exist, create it
                set foundNote to make new note at targetFolder with properties {{name:"{title_escaped}", body:"{title_escaped}\\n\\n"}}
            end try

            -- Append content
            set oldBody to body of foundNote
            set body of foundNote to oldBody & "\\n" & "{content_escaped}"

            return "Success"
        end tell
        '''

        return script

    def _build_get_note_applescript(
        self,
        note_title: str,
        folder: str
    ) -> str:
        """
        Build AppleScript for retrieving note content.

        Args:
            note_title: Note title
            folder: Folder containing note

        Returns:
            AppleScript string
        """
        # Escape strings
        title_escaped = self._escape_applescript_string(note_title)
        folder_escaped = self._escape_applescript_string(folder)

        script = f'''
        tell application "Notes"
            set targetFolder to missing value
            try
                set targetFolder to folder "{folder_escaped}"
            on error
                set targetFolder to folder "Notes" of default account
            end try

            -- Find note
            set foundNote to first note of targetFolder whose name is "{title_escaped}"

            -- Return body
            return body of foundNote
        end tell
        '''

        return script

    def _escape_applescript_string(self, s: str) -> str:
        """
        Escape string for use in AppleScript.

        Args:
            s: String to escape

        Returns:
            Escaped string
        """
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

    def test_notes_integration(self) -> bool:
        """
        Test if Notes app is accessible.

        Returns:
            True if Notes app is accessible, False otherwise
        """
        try:
            script = '''
            tell application "Notes"
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
            logger.error(f"Notes integration test failed: {e}")
            return False
