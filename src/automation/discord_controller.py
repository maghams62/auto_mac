"""
Discord desktop automation using macOS accessibility (MacMCP) primitives.

This controller centralizes all interactions with the Discord Electron app:
- Login workflows driven by credentials stored in the .env file
- Navigation to servers/channels via the quick switcher
- Reading and posting channel messages
- Detecting unread indicators
- Capturing screenshots for audit/debug traces

All actions go through macOS automation hooks (System Events, AppleScript, clipboard)
so they work within the broader MacMCP orchestration framework.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .screen_capture import ScreenCapture

logger = logging.getLogger(__name__)


class DiscordController:
    """
    High-level helper for controlling the Discord desktop client via macOS APIs.

    The controller intentionally avoids any network API usage – every action is
    performed through UI automation so it can be orchestrated alongside other
    MacMCP-native agents (Keynote, Mail, iMessage, etc.).
    """

    MESSAGE_DELIMITER = "||MSG||"
    UNREAD_DELIMITER = "||UNREAD||"

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.discord_config = config.get("discord", {}) or {}
        self.default_server = self.discord_config.get("default_server")
        self.default_channel = self.discord_config.get("default_channel")
        self.switcher_delay = float(self.discord_config.get("switcher_delay_seconds", 0.6))
        self.screenshot_dir = Path(self.discord_config.get("screenshot_dir", "data/screenshots"))
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        credentials_cfg = self.discord_config.get("credentials", {}) or {}
        self.credentials = {
            "email": credentials_cfg.get("email") or os.getenv("DISCORD_EMAIL"),
            "password": credentials_cfg.get("password") or os.getenv("DISCORD_PASSWORD"),
            "mfa": credentials_cfg.get("mfa_code") or os.getenv("DISCORD_MFA_CODE"),
        }

        self.screen_capture = ScreenCapture(config)

    # -------------------------------------------------------------------------
    # Public interface
    # -------------------------------------------------------------------------

    def ensure_session(self) -> Dict[str, Any]:
        """Bring Discord to the foreground and authenticate if necessary."""
        self._activate_discord()
        return self._login_if_needed()

    def navigate_to_channel(self, channel_name: Optional[str], server_name: Optional[str] = None) -> Dict[str, Any]:
        """Open the requested channel using the Cmd+K quick switcher."""
        resolved_channel = self._resolve_channel(channel_name)
        if not resolved_channel:
            return self._error("Channel name not provided and no default configured", "MissingChannel")

        target_phrase = self._build_target_phrase(resolved_channel, server_name)
        script = f'''
        set targetChannel to "{self._escape(target_phrase)}"
        tell application "Discord"
            activate
        end tell
        delay 0.3
        tell application "System Events"
            if not (exists process "Discord") then
                return "PROCESS_NOT_FOUND"
            end if
            tell process "Discord"
                set frontmost to true
                keystroke "k" using {{command down}}
                delay {self.switcher_delay}
                keystroke targetChannel
                delay {self.switcher_delay}
                keystroke return
            end tell
        end tell
        return "NAVIGATED"
        '''

        result = self._run_applescript(script)
        stdout = result.stdout.strip()
        if result.returncode != 0:
            return self._error(f"Channel navigation failed: {result.stderr}", "NavigationError")

        logger.info(f"[DISCORD] Navigate result={stdout} target='{target_phrase}'")
        time.sleep(0.8)  # allow UI to settle
        return {
            "success": True,
            "status": stdout or "NAVIGATED",
            "channel": resolved_channel,
            "server": server_name or self.default_server,
        }

    def send_message(
        self,
        channel_name: Optional[str],
        message: str,
        server_name: Optional[str] = None,
        confirm_delivery: bool = True
    ) -> Dict[str, Any]:
        """Post a message into the given Discord channel."""
        if not message or not message.strip():
            return self._error("Message text cannot be empty", "EmptyMessage")

        navigation = self.navigate_to_channel(channel_name, server_name)
        if navigation.get("error"):
            return navigation

        type_result = self._type_and_submit_message(message)
        if type_result.get("error"):
            return type_result

        delivery_confirmation = None
        if confirm_delivery:
            # Re-read last few messages to confirm text landed in channel history
            readback = self.read_messages(channel_name, limit=5, server_name=server_name, skip_navigation=True)
            messages = readback.get("messages", [])
            delivery_confirmation = any(message.strip() in (m or "") for m in messages)

        return {
            "success": True,
            "channel": navigation.get("channel"),
            "server": navigation.get("server"),
            "message_preview": message[:120],
            "delivery_confirmed": delivery_confirmation,
        }

    def read_messages(
        self,
        channel_name: Optional[str],
        limit: int = 10,
        server_name: Optional[str] = None,
        skip_navigation: bool = False
    ) -> Dict[str, Any]:
        """Return recent textual messages from the active channel via accessibility text scraping."""
        resolved_channel = self._resolve_channel(channel_name)
        if not resolved_channel:
            return self._error("Channel name not provided and no default configured", "MissingChannel")

        if not skip_navigation:
            navigation = self.navigate_to_channel(resolved_channel, server_name)
            if navigation.get("error"):
                return navigation

        script = f'''
        set collected to {{}}
        tell application "System Events"
            if not (exists process "Discord") then
                return ""
            end if
            tell process "Discord"
                set frontmost to true
                if not (exists window 1) then return ""
                set chatWindow to window 1
                set targetScrollArea to missing value
                try
                    repeat with s in (scroll areas of chatWindow)
                        try
                            if (count of groups of s) > 0 then
                                set targetScrollArea to s
                                exit repeat
                            end if
                        end try
                    end repeat
                end try

                if targetScrollArea is not missing value then
                    set messageGroups to groups of targetScrollArea
                    repeat with msgGroup in messageGroups
                        try
                            set author to ""
                            set bodyText to ""
                            if exists static text 1 of msgGroup then
                                set author to value of static text 1 of msgGroup
                            end if

                            set staticItems to (static texts of msgGroup)
                            if (count of staticItems) > 1 then
                                repeat with idx from 2 to count of staticItems
                                    set bodyText to bodyText & value of item idx of staticItems & " "
                                end repeat
                            end if

                            if bodyText is "" then
                                try
                                    set bodyText to value of text area 1 of msgGroup
                                end try
                            end if

                            if bodyText is not "" then
                                if author is "" then
                                    set combined to bodyText
                                else
                                    set combined to author & ": " & bodyText
                                end if
                                set end of collected to combined
                            end if
                        end try
                    end repeat
                end if
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
                "channel": resolved_channel,
                "messages": [],
                "note": "No accessible messages detected (channel may be empty or Discord denied accessibility introspection)."
            }

        messages = self._parse_delimited(raw, self.MESSAGE_DELIMITER)
        trimmed = messages[-limit:] if limit and len(messages) > limit else messages

        return {
            "success": True,
            "channel": resolved_channel,
            "server": server_name or self.default_server,
            "messages": trimmed,
            "sample_size": len(trimmed),
        }

    def detect_unread_channels(self, server_name: Optional[str] = None) -> Dict[str, Any]:
        """Inspect the guild/channel list for unread indicators."""
        script = f'''
        set unreadItems to {{}}
        tell application "System Events"
            if not (exists process "Discord") then
                return ""
            end if
            tell process "Discord"
                if not (exists window 1) then return ""
                set chatWindow to window 1
                set paneCandidates to {{
                    try scroll area 1 of splitter group 1 of chatWindow on error missing value,
                    try outline 1 of scroll area 1 of splitter group 1 of chatWindow on error missing value
                }}

                repeat with candidate in paneCandidates
                    if candidate is missing value then
                        -- skip invalid UI references
                    else
                        try
                            repeat with rowItem in (UI elements of candidate)
                                set titleValue to ""
                                set descriptionValue to ""
                                try
                                    set titleValue to value of attribute "AXTitle" of rowItem
                                end try
                                try
                                    set descriptionValue to value of attribute "AXDescription" of rowItem
                                end try
                                if (descriptionValue contains "unread") or (titleValue contains "•") then
                                    if titleValue is "" then
                                        set itemText to descriptionValue
                                    else
                                        set itemText to titleValue & " -- " & descriptionValue
                                    end if
                                    set end of unreadItems to itemText
                                end if
                            end repeat
                        end try
                    end if
                end repeat
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
        filtered = self._filter_by_server(items, server_name)

        return {
            "success": True,
            "unread_channels": filtered,
            "total_detected": len(items),
            "filtered": server_name or None,
        }

    def screenshot_recent_messages(
        self,
        channel_name: Optional[str],
        server_name: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Capture the currently focused Discord window for audit or verification."""
        navigation = self.navigate_to_channel(channel_name, server_name)
        if navigation.get("error"):
            return navigation

        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.screenshot_dir / f"discord_{navigation['channel']}_{timestamp}.png")

        capture = self.screen_capture.capture_screen(app_name="Discord", output_path=output_path)
        if capture.get("error"):
            return capture

        return {
            "success": True,
            "channel": navigation.get("channel"),
            "server": navigation.get("server"),
            "screenshot_path": capture.get("screenshot_path"),
        }

    def verify_channel_interaction(
        self,
        channel_name: Optional[str],
        server_name: Optional[str] = None,
        send_test_message: bool = False,
        test_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run a quick capability check:
        - Ensure Discord is logged in
        - Navigate to the channel and read history
        - Optionally post a test message and confirm it echoes back
        """
        session = self.ensure_session()
        if session.get("error"):
            return session

        read_result = self.read_messages(channel_name, limit=5, server_name=server_name)
        if read_result.get("error"):
            return read_result

        verification_details = {
            "login_status": session.get("status"),
            "able_to_read": True,
            "messages_sampled": read_result.get("sample_size", 0),
            "message_preview": read_result.get("messages", []),
        }

        post_result = None
        if send_test_message:
            probe = test_message or f"automation-check {datetime.now().isoformat(timespec='seconds')}"
            post_result = self.send_message(channel_name, probe, server_name=server_name)
            verification_details["post_check"] = post_result
            verification_details["message_confirmation"] = post_result.get("delivery_confirmed")

        return {
            "success": True,
            "channel": read_result.get("channel"),
            "server": read_result.get("server"),
            "verification": verification_details,
            "test_message_posted": bool(post_result),
        }

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _resolve_channel(self, channel_name: Optional[str]) -> Optional[str]:
        return channel_name or self.default_channel

    def _build_target_phrase(self, channel_name: str, server_name: Optional[str]) -> str:
        if server_name:
            return f"{server_name} {channel_name}"
        if self.default_server:
            return f"{self.default_server} {channel_name}"
        return channel_name

    def _activate_discord(self):
        script = '''
        tell application "Discord"
            activate
        end tell
        '''
        self._run_applescript(script)
        time.sleep(0.3)

    def _login_if_needed(self) -> Dict[str, Any]:
        email = self.credentials.get("email")
        password = self.credentials.get("password")

        if not email or not password:
            logger.warning("[DISCORD] Credentials missing; assuming session already authenticated.")
            return {
                "success": True,
                "status": "skipped",
                "needs_login": False,
                "reason": "DISCORD_EMAIL/DISCORD_PASSWORD not provided; assuming pre-authenticated session."
            }

        script = f'''
        set loginResult to "ALREADY_LOGGED_IN"
        tell application "Discord"
            activate
        end tell
        delay 0.6
        tell application "System Events"
            if not (exists process "Discord") then
                return "PROCESS_NOT_FOUND"
            end if
            tell process "Discord"
                if not (exists window 1) then return "WINDOW_NOT_AVAILABLE"
                set loginWindow to window 1
                set loginNeeded to false
                try
                    if exists button "Log In" of loginWindow then set loginNeeded to true
                end try
                try
                    if exists button "Login" of loginWindow then set loginNeeded to true
                end try
                try
                    if exists static text "Welcome back!" of loginWindow then set loginNeeded to true
                end try

                if loginNeeded then
                    set loginResult to "LOGIN_SUBMITTED"
                    try
                        set value of text field 1 of loginWindow to "{self._escape(email)}"
                    on error
                        try
                            keystroke "a" using {{command down}}
                            keystroke "{self._escape(email)}"
                        end try
                    end try

                    delay 0.2
                    try
                        set value of text field 2 of loginWindow to "{self._escape(password)}"
                    on error
                        try
                            keystroke tab
                            delay 0.1
                            keystroke "{self._escape(password)}"
                        end try
                    end try

                    delay 0.2
                    if exists button "Log In" of loginWindow then
                        click button "Log In" of loginWindow
                    else if exists button "Login" of loginWindow then
                        click button "Login" of loginWindow
                    else
                        try
                            keystroke return
                        end try
                    end if
                end if
            end tell
        end tell
        return loginResult
        '''

        result = self._run_applescript(script, timeout=10)
        stdout = result.stdout.strip()
        if result.returncode != 0:
            return self._error(f"Discord login automation failed: {result.stderr}", "LoginError")

        status_map = {
            "LOGIN_SUBMITTED": ("login_submitted", True),
            "ALREADY_LOGGED_IN": ("already_logged_in", False)
        }
        status, needs_login = status_map.get(stdout, ("unknown", False))

        return {
            "success": True,
            "status": status,
            "needs_login": needs_login,
            "raw_response": stdout or "ALREADY_LOGGED_IN"
        }

    def _type_and_submit_message(self, message: str) -> Dict[str, Any]:
        """Injects message text via clipboard to preserve formatting and send it."""
        original_clipboard = self._read_clipboard()
        try:
            self._write_clipboard(message)
            script = '''
            tell application "Discord"
                activate
            end tell
            delay 0.2
            tell application "System Events"
                if not (exists process "Discord") then
                    return "PROCESS_NOT_FOUND"
                end if
                tell process "Discord"
                    set frontmost to true
                    try
                        set composer to text area 1 of group 2 of splitter group 1 of window 1
                        try
                            perform action "AXRaise" of composer
                        end try
                        try
                            set value of composer to ""
                        end try
                    on error
                        try
                            click text area 1 of group 2 of splitter group 1 of window 1
                        end try
                    end try
                    delay 0.1
                    keystroke "a" using {command down}
                    delay 0.05
                    keystroke (ASCII character 127)
                    delay 0.05
                    keystroke "v" using {command down}
                    delay 0.2
                    key code 36
                end tell
            end tell
            return "SENT"
            '''

            result = self._run_applescript(script, timeout=8)
            if result.returncode != 0:
                return self._error(f"Failed to type Discord message: {result.stderr}", "MessageSendError")

            return {"success": True, "status": result.stdout.strip() or "SENT"}
        finally:
            self._write_clipboard(original_clipboard or "")

    def _filter_by_server(self, items: List[str], server_name: Optional[str]) -> List[str]:
        if not server_name:
            return items
        lower = server_name.lower()
        return [item for item in items if lower in item.lower()]

    def _parse_delimited(self, raw: str, delimiter: str) -> List[str]:
        if not raw:
            return []
        if delimiter not in raw:
            return [raw.strip()]
        return [item.strip() for item in raw.split(delimiter) if item.strip()]

    def _read_clipboard(self) -> Optional[str]:
        try:
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                return result.stdout
        except Exception as exc:
            logger.debug(f"[DISCORD] Failed to read clipboard: {exc}")
        return None

    def _write_clipboard(self, value: str):
        try:
            subprocess.run(["pbcopy"], input=value, text=True, check=True, timeout=2)
        except Exception as exc:
            logger.warning(f"[DISCORD] Failed to write clipboard: {exc}")

    def _run_applescript(self, script: str, timeout: int = 6) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=timeout
            )
        except subprocess.TimeoutExpired as exc:
            stderr = getattr(exc, "stderr", "") or "Timed out executing AppleScript"
            logger.error(f"[DISCORD] AppleScript timeout: {stderr}")
            fake = subprocess.CompletedProcess(args=["osascript"], returncode=1, stdout="", stderr=stderr)
            return fake

    def _escape(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _error(self, message: str, error_type: str) -> Dict[str, Any]:
        logger.error(f"[DISCORD] {error_type}: {message}")
        return {
            "error": True,
            "error_type": error_type,
            "error_message": message,
            "retry_possible": True,
        }
