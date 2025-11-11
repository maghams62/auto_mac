"""
WhatsApp Desktop automation using macOS accessibility (AppleScript/System Events).

This controller centralizes all interactions with the WhatsApp Desktop app:
- Session verification (ensure WhatsApp is running and logged in)
- Navigation to specific chats/groups
- Reading messages from chats/groups
- Detecting unread messages
- Filtering messages by sender

All actions go through macOS automation hooks (System Events, AppleScript) 
so they work within the broader Mac automation orchestration framework.
"""

from __future__ import annotations

import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .screen_capture import ScreenCapture

logger = logging.getLogger(__name__)


class WhatsAppController:
    """
    High-level helper for controlling the WhatsApp Desktop client via macOS APIs.
    
    The controller uses UI automation (System Events/AppleScript) to interact with
    WhatsApp Desktop, similar to the Discord controller pattern.
    """

    MESSAGE_DELIMITER = "||MSG||"
    UNREAD_DELIMITER = "||UNREAD||"

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.whatsapp_config = config.get("whatsapp", {}) or {}
        self.screenshot_dir = Path(self.whatsapp_config.get("screenshot_dir", "data/screenshots"))
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        self.screen_capture = ScreenCapture(config)

    # -------------------------------------------------------------------------
    # Public interface
    # -------------------------------------------------------------------------

    def ensure_session(self) -> Dict[str, Any]:
        """Bring WhatsApp to the foreground and verify it's running/logged in."""
        self._activate_whatsapp()
        return self._verify_session()

    def navigate_to_chat(
        self, 
        contact_name: str, 
        is_group: bool = False
    ) -> Dict[str, Any]:
        """
        Navigate to a specific chat or group in WhatsApp Desktop.
        
        Uses search functionality (Cmd+F) to find and open the chat.
        
        Args:
            contact_name: Name of contact or group to navigate to
            is_group: Whether this is a group chat (affects search behavior)
        """
        if not contact_name or not contact_name.strip():
            return self._error("Contact/group name cannot be empty", "MissingContact")
        
        escaped_name = self._escape(contact_name.strip())
        script = f'''
        set targetChat to "{escaped_name}"
        tell application "WhatsApp"
            activate
        end tell
        delay 0.5
        tell application "System Events"
            if not (exists process "WhatsApp") then
                return "PROCESS_NOT_FOUND"
            end if
            tell process "WhatsApp"
                set frontmost to true
                -- Use search (Cmd+F) to find the chat
                keystroke "f" using {{command down}}
                delay 0.5
                keystroke targetChat
                delay 0.8
                -- Press Enter to select the first result
                keystroke return
                delay 0.5
                -- Close search if still open
                key code 53
            end tell
        end tell
        return "NAVIGATED"
        '''
        
        result = self._run_applescript(script, timeout=10)
        stdout = result.stdout.strip()
        
        if result.returncode != 0:
            return self._error(f"Chat navigation failed: {result.stderr}", "NavigationError")
        
        logger.info(f"[WHATSAPP] Navigate result={stdout} target='{contact_name}'")
        time.sleep(0.8)  # Allow UI to settle
        
        return {
            "success": True,
            "status": stdout or "NAVIGATED",
            "contact": contact_name,
            "is_group": is_group,
        }

    def read_messages(
        self,
        contact_name: str,
        limit: int = 20,
        is_group: bool = False,
        skip_navigation: bool = False
    ) -> Dict[str, Any]:
        """
        Read recent messages from a WhatsApp chat/group via accessibility text scraping.
        
        Args:
            contact_name: Name of contact or group
            limit: Maximum number of messages to return (most recent)
            is_group: Whether this is a group chat
            skip_navigation: If True, assumes already navigated to the chat
        """
        if not contact_name or not contact_name.strip():
            return self._error("Contact/group name cannot be empty", "MissingContact")
        
        if not skip_navigation:
            navigation = self.navigate_to_chat(contact_name, is_group)
            if navigation.get("error"):
                return navigation
        
        # AppleScript to extract messages from WhatsApp UI
        # This will need to be adjusted based on actual WhatsApp Desktop UI structure
        script = f'''
        set collected to {{}}
        tell application "System Events"
            if not (exists process "WhatsApp") then
                return ""
            end if
            tell process "WhatsApp"
                set frontmost to true
                if not (exists window 1) then return ""
                
                set chatWindow to window 1
                -- Try to find message container elements
                -- WhatsApp Desktop structure may vary, so we try multiple approaches
                try
                    -- Approach 1: Look for scroll areas containing messages
                    repeat with scrollArea in (scroll areas of chatWindow)
                        try
                            set messageGroups to groups of scrollArea
                            repeat with msgGroup in messageGroups
                                try
                                    set senderName to ""
                                    set messageText to ""
                                    set timestamp to ""
                                    
                                    -- Try to extract sender name (for groups)
                                    try
                                        if exists static text 1 of msgGroup then
                                            set senderName to value of static text 1 of msgGroup
                                        end if
                                    end try
                                    
                                    -- Try to extract message text from static texts
                                    try
                                        set staticItems to (static texts of msgGroup)
                                        if (count of staticItems) > 0 then
                                            -- Skip first item if it's the sender name
                                            set startIdx to 1
                                            if senderName is not "" and (count of staticItems) > 1 then
                                                set firstText to value of item 1 of staticItems
                                                if firstText is senderName then
                                                    set startIdx to 2
                                                end if
                                            end if
                                            
                                            -- Collect remaining text elements
                                            repeat with idx from startIdx to count of staticItems
                                                set itemValue to value of item idx of staticItems
                                                if itemValue is not "" and itemValue is not senderName then
                                                    if messageText is "" then
                                                        set messageText to itemValue
                                                    else
                                                        set messageText to messageText & " " & itemValue
                                                    end if
                                                end if
                                            end repeat
                                        end if
                                    end try
                                    
                                    -- Try text areas as fallback
                                    if messageText is "" then
                                        try
                                            set textAreas to text areas of msgGroup
                                            if (count of textAreas) > 0 then
                                                set messageText to value of item 1 of textAreas
                                            end if
                                        end try
                                    end if
                                    
                                    -- Try getting value attribute directly as last resort
                                    if messageText is "" then
                                        try
                                            set msgValue to value of msgGroup as string
                                            if msgValue is not "" and msgValue is not senderName then
                                                set messageText to msgValue
                                            end if
                                        end try
                                    end if
                                    
                                    -- Build message string (only if we have content)
                                    if messageText is not "" then
                                        if senderName is not "" then
                                            set combined to senderName & ": " & messageText
                                        else
                                            set combined to messageText
                                        end if
                                        set end of collected to combined
                                    end if
                                end try
                            end repeat
                        end try
                    end repeat
                end try
            end tell
        end tell
        
        if (count of collected) = 0 then
            return ""
        else
            set AppleScript's text item delimiters to "{self.MESSAGE_DELIMITER}"
            return collected as text
        end if
        '''
        
        result = self._run_applescript(script, timeout=12)
        if result.returncode != 0:
            return self._error(f"Failed to read messages: {result.stderr}", "ReadError")
        
        raw = result.stdout.strip()
        if not raw:
            return {
                "success": True,
                "contact": contact_name,
                "messages": [],
                "note": "No accessible messages detected (chat may be empty or WhatsApp denied accessibility introspection)."
            }
        
        messages = self._parse_delimited(raw, self.MESSAGE_DELIMITER)
        trimmed = messages[-limit:] if limit and len(messages) > limit else messages
        
        return {
            "success": True,
            "contact": contact_name,
            "is_group": is_group,
            "messages": trimmed,
            "sample_size": len(trimmed),
        }

    def read_messages_from_sender(
        self,
        contact_name: str,
        sender_name: str,
        limit: int = 20,
        is_group: bool = True
    ) -> Dict[str, Any]:
        """
        Read messages from a specific sender within a group chat.
        
        Args:
            contact_name: Name of the group
            sender_name: Name of the sender to filter by
            limit: Maximum number of messages to return
            is_group: Whether this is a group (should be True for sender filtering)
        """
        result = self.read_messages(contact_name, limit=limit * 2, is_group=is_group)
        if result.get("error"):
            return result
        
        messages = result.get("messages", [])
        filtered = [
            msg for msg in messages 
            if msg.startswith(f"{sender_name}:") or f": {sender_name}" in msg
        ]
        
        # Limit to requested amount
        filtered = filtered[-limit:] if len(filtered) > limit else filtered
        
        return {
            "success": True,
            "contact": contact_name,
            "sender": sender_name,
            "messages": filtered,
            "sample_size": len(filtered),
            "total_messages": len(messages),
        }

    def detect_unread_chats(self) -> Dict[str, Any]:
        """Inspect the chat list for unread indicators."""
        script = f'''
        set unreadItems to {{}}
        tell application "System Events"
            if not (exists process "WhatsApp") then
                return ""
            end if
            tell process "WhatsApp"
                if not (exists window 1) then return ""
                set chatWindow to window 1
                
                -- Try to find chat list (left sidebar)
                try
                    -- Look for scroll areas that might contain chat list
                    repeat with scrollArea in (scroll areas of chatWindow)
                        try
                            repeat with rowItem in (UI elements of scrollArea)
                                try
                                    set titleValue to ""
                                    set descriptionValue to ""
                                    try
                                        set titleValue to value of attribute "AXTitle" of rowItem
                                    end try
                                    try
                                        set descriptionValue to value of attribute "AXDescription" of rowItem
                                    end try
                                    
                                    -- Check for unread indicators (bold text, badges, etc.)
                                    if (descriptionValue contains "unread") or (titleValue contains "•") or (titleValue contains "unread") then
                                        if titleValue is "" then
                                            set itemText to descriptionValue
                                        else
                                            set itemText to titleValue & " -- " & descriptionValue
                                        end if
                                        set end of unreadItems to itemText
                                    end if
                                end try
                            end repeat
                        end try
                    end repeat
                end try
            end tell
        end tell
        
        if (count of unreadItems) = 0 then
            return ""
        else
            set AppleScript's text item delimiters to "{self.UNREAD_DELIMITER}"
            return unreadItems as text
        end if
        '''
        
        result = self._run_applescript(script)
        if result.returncode != 0:
            return self._error(f"Unread detector failed: {result.stderr}", "UnreadCheckError")
        
        items = self._parse_delimited(result.stdout.strip(), self.UNREAD_DELIMITER)
        
        return {
            "success": True,
            "unread_chats": items,
            "total_detected": len(items),
        }

    def get_chat_list(self) -> Dict[str, Any]:
        """List all available chats/groups."""
        script = f'''
        set chatList to {{}}
        tell application "System Events"
            if not (exists process "WhatsApp") then
                return ""
            end if
            tell process "WhatsApp"
                if not (exists window 1) then return ""
                set chatWindow to window 1
                
                -- Try to extract chat list from sidebar
                try
                    repeat with scrollArea in (scroll areas of chatWindow)
                        try
                            repeat with rowItem in (UI elements of scrollArea)
                                try
                                    set titleValue to ""
                                    try
                                        set titleValue to value of attribute "AXTitle" of rowItem
                                    end try
                                    if titleValue is not "" then
                                        set end of chatList to titleValue
                                    end if
                                end try
                            end repeat
                        end try
                    end repeat
                end try
            end tell
        end tell
        
        if (count of chatList) = 0 then
            return ""
        else
            set AppleScript's text item delimiters to "{self.MESSAGE_DELIMITER}"
            return chatList as text
        end if
        '''
        
        result = self._run_applescript(script)
        if result.returncode != 0:
            return self._error(f"Failed to get chat list: {result.stderr}", "ChatListError")
        
        chats = self._parse_delimited(result.stdout.strip(), self.MESSAGE_DELIMITER)
        
        return {
            "success": True,
            "chats": chats,
            "total": len(chats),
        }

    def screenshot_chat(
        self,
        contact_name: str,
        is_group: bool = False,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Capture a screenshot of the current WhatsApp chat."""
        navigation = self.navigate_to_chat(contact_name, is_group)
        if navigation.get("error"):
            return navigation
        
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = contact_name.replace(" ", "_").replace("/", "_")
            output_path = str(self.screenshot_dir / f"whatsapp_{safe_name}_{timestamp}.png")
        
        capture = self.screen_capture.capture_screen(app_name="WhatsApp", output_path=output_path)
        if capture.get("error"):
            return capture
        
        return {
            "success": True,
            "contact": contact_name,
            "is_group": is_group,
            "screenshot_path": capture.get("screenshot_path"),
        }

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _activate_whatsapp(self):
        """Activate WhatsApp Desktop application."""
        script = '''
        tell application "WhatsApp"
            activate
        end tell
        '''
        self._run_applescript(script)
        time.sleep(0.5)

    def _verify_session(self) -> Dict[str, Any]:
        """Verify WhatsApp is running and user is logged in."""
        script = '''
        set sessionStatus to "LOGGED_IN"
        tell application "System Events"
            if not (exists process "WhatsApp") then
                return "PROCESS_NOT_FOUND"
            end if
            tell process "WhatsApp"
                if not (exists window 1) then return "WINDOW_NOT_AVAILABLE"
                set mainWindow to window 1
                
                -- Check for login screen indicators
                try
                    if exists button "Log In" of mainWindow then
                        set sessionStatus to "NOT_LOGGED_IN"
                    end if
                end try
                try
                    if exists static text "Scan this code" of mainWindow then
                        set sessionStatus to "QR_CODE_REQUIRED"
                    end if
                end try
            end tell
        end tell
        return sessionStatus
        '''
        
        result = self._run_applescript(script, timeout=5)
        stdout = result.stdout.strip()
        
        if result.returncode != 0:
            return self._error(f"Session verification failed: {result.stderr}", "SessionError")
        
        if stdout == "PROCESS_NOT_FOUND":
            return self._error("WhatsApp is not running", "ProcessNotFound")
        
        if stdout == "NOT_LOGGED_IN" or stdout == "QR_CODE_REQUIRED":
            return {
                "success": False,
                "error": True,
                "error_type": "NotLoggedIn",
                "error_message": f"WhatsApp session status: {stdout}",
                "retry_possible": True,
            }
        
        return {
            "success": True,
            "status": stdout or "LOGGED_IN",
            "needs_login": False,
        }

    def _parse_delimited(self, raw: str, delimiter: str) -> List[str]:
        """Parse delimited string into list."""
        if not raw:
            return []
        if delimiter not in raw:
            return [raw.strip()]
        return [item.strip() for item in raw.split(delimiter) if item.strip()]

    def _run_applescript(self, script: str, timeout: int = 6) -> subprocess.CompletedProcess:
        """Execute AppleScript and return result."""
        try:
            return subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=timeout
            )
        except subprocess.TimeoutExpired as exc:
            stderr = getattr(exc, "stderr", "") or "Timed out executing AppleScript"
            logger.error(f"[WHATSAPP] AppleScript timeout: {stderr}")
            fake = subprocess.CompletedProcess(args=["osascript"], returncode=1, stdout="", stderr=stderr)
            return fake

    def _escape(self, value: str) -> str:
        """Escape special characters for AppleScript."""
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _error(self, message: str, error_type: str) -> Dict[str, Any]:
        """Create standardized error response."""
        logger.error(f"[WHATSAPP] {error_type}: {message}")
        return {
            "error": True,
            "error_type": error_type,
            "error_message": message,
            "retry_possible": True,
        }

