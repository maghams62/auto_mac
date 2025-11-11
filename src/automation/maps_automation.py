"""
macOS Maps.app integration using AppleScript.

This module provides automation for Apple Maps on macOS, allowing programmatic
control of directions, waypoints, and route planning.
"""

import logging
import subprocess
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class MapsAutomation:
    """
    Automates Apple Maps app on macOS using AppleScript.

    Provides methods to:
    - Open Maps app with directions
    - Set origin and destination
    - Add waypoints/stops
    - Start navigation
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Maps automation.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

    def open_directions(
        self,
        origin: str,
        destination: str,
        stops: Optional[List[str]] = None,
        start_navigation: bool = False
    ) -> Dict[str, Any]:
        """
        Open Apple Maps with directions from origin to destination, optionally with stops.

        Args:
            origin: Starting location (e.g., "Los Angeles, CA")
            destination: End location (e.g., "San Diego, CA")
            stops: Optional list of waypoint stops (e.g., ["Irvine, CA", "Carlsbad, CA"])
            start_navigation: If True, automatically start navigation (default: False)

        Returns:
            Dictionary with success status and details
        """
        logger.info(f"Opening Maps directions: {origin} -> {destination} (stops: {stops})")

        try:
            stops = stops or []
            
            # Build AppleScript
            script = self._build_directions_applescript(
                origin=origin,
                destination=destination,
                stops=stops,
                start_navigation=start_navigation
            )
            
            logger.debug(f"Generated AppleScript:\n{script}")

            # Execute AppleScript
            result = self._run_applescript(script)

            if result.returncode == 0:
                logger.info("Successfully opened Maps with directions")
                return {
                    "success": True,
                    "origin": origin,
                    "destination": destination,
                    "stops": stops,
                    "message": f"Opened Maps directions from {origin} to {destination}"
                }
            else:
                error_msg = result.stderr or result.stdout or "Failed to open Maps directions"
                logger.error(f"AppleScript error (returncode={result.returncode}): {error_msg}")
                logger.debug(f"AppleScript stdout: {result.stdout}")
                logger.debug(f"AppleScript stderr: {result.stderr}")
                return {
                    "success": False,
                    "error": True,
                    "error_message": error_msg,
                    "retry_possible": True
                }

        except Exception as e:
            logger.error(f"Error opening Maps directions: {e}")
            return {
                "success": False,
                "error": True,
                "error_message": str(e),
                "retry_possible": False
            }

    def _build_directions_applescript(
        self,
        origin: str,
        destination: str,
        stops: List[str],
        start_navigation: bool = False
    ) -> str:
        """
        Build AppleScript for opening Maps with directions.

        Uses the proper AppleScript 'open location' command to open Apple Maps
        with directions URL. This is the correct and reliable way to open URLs
        in macOS applications.

        Args:
            origin: Starting location
            destination: End location
            stops: List of waypoint stops
            start_navigation: Whether to start navigation automatically

        Returns:
            AppleScript string
        """
        # Build URL with waypoints
        # Apple Maps web URL format: https://maps.apple.com/?saddr=ORIGIN&daddr=STOP1&daddr=STOP2&daddr=DEST
        from urllib.parse import quote
        url = f"https://maps.apple.com/?saddr={quote(origin)}"
        for stop in stops:
            url += f"&daddr={quote(stop)}"
        url += f"&daddr={quote(destination)}&dirflg=d"
        
        # Escape URL for AppleScript string literal
        # In AppleScript, we need to escape backslashes and quotes
        url_escaped = url.replace('\\', '\\\\').replace('"', '\\"')
        
        # AppleScript to open Maps with the URL using 'open location' command
        # This is the proper way to open URLs in macOS - it will open in the default handler
        # which for Apple Maps URLs will be the Maps app
        # We use 'open location' which is a standard AppleScript command that works system-wide
        script = f'''
        -- Open the directions URL using open location command
        -- This will automatically open in Maps app on macOS
        -- The 'open location' command is a system command that opens URLs in their default handler
        open location "{url_escaped}"
        '''
        
        # If we want to start navigation automatically, we need to interact with Maps UI
        if start_navigation:
            script += '''
        delay 2
        
        -- Try to start navigation by clicking the "Go" button
        tell application "System Events"
            tell process "Maps"
                try
                    -- Look for "Go" button in the directions interface
                    set goButton to button "Go" of window 1
                    click goButton
                    delay 0.5
                on error
                    -- Alternative: try keyboard shortcut
                    try
                        keystroke "d" using {{command down, shift down}}
                        delay 0.5
                    on error
                        -- If both fail, directions are still open, just not started
                        log "Could not automatically start navigation, but directions are loaded"
                    end try
                end try
            end tell
        end tell
        '''
        
        return script

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
            # Execute AppleScript directly using osascript with stdin
            # This is more reliable than using temp files
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
            logger.error(f"AppleScript timeout after {timeout}s")
            return subprocess.CompletedProcess(
                args=['osascript'],
                returncode=1,
                stdout="",
                stderr=f"Timeout after {timeout} seconds"
            )
        except Exception as e:
            logger.error(f"Error running AppleScript: {e}")
            return subprocess.CompletedProcess(
                args=['osascript'],
                returncode=1,
                stdout="",
                stderr=str(e)
            )

    def _escape_applescript_string(self, s: str) -> str:
        """
        Escape string for use in AppleScript.

        Args:
            s: String to escape

        Returns:
            Escaped string safe for AppleScript
        """
        if not s:
            return ""
        
        # Escape backslashes first
        s = s.replace('\\', '\\\\')
        # Escape quotes
        s = s.replace('"', '\\"')
        # Escape newlines
        s = s.replace('\n', '\\n')
        # Escape carriage returns
        s = s.replace('\r', '\\r')
        
        return s

    def open_location(self, location: str) -> Dict[str, Any]:
        """
        Open Apple Maps and show a specific location.

        Args:
            location: Location to show (e.g., "San Francisco, CA")

        Returns:
            Dictionary with success status
        """
        logger.info(f"Opening Maps location: {location}")

        try:
            location_escaped = self._escape_applescript_string(location)
            
            script = f'''
            tell application "Maps"
                activate
            end tell
            
            delay 0.5
            
            -- Search for the location
            tell application "System Events"
                tell process "Maps"
                    -- Click in search field
                    try
                        set searchField to text field 1 of group 1 of toolbar 1 of window 1
                        click searchField
                        delay 0.3
                        
                        -- Clear and enter location
                        keystroke "a" using command down
                        delay 0.1
                        keystroke "{location_escaped}"
                        delay 0.5
                        keystroke return
                        delay 1
                    on error
                        -- Fallback: use URL scheme
                        open location "https://maps.apple.com/?q={location_escaped}"
                    end try
                end tell
            end tell
            '''
            
            result = self._run_applescript(script)
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "location": location,
                    "message": f"Opened Maps location: {location}"
                }
            else:
                return {
                    "success": False,
                    "error": True,
                    "error_message": result.stderr or "Failed to open Maps location"
                }

        except Exception as e:
            logger.error(f"Error opening Maps location: {e}")
            return {
                "success": False,
                "error": True,
                "error_message": str(e)
            }

