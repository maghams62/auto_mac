"""
Location Service for Mac Automation Assistant.

Provides current location detection using multiple methods:
1. macOS Shortcuts (primary, built-in)
2. CoreLocationCLI (fallback, requires installation)
3. Manual coordinates (user-provided lat/long)

Usage:
    service = LocationService()
    location = service.get_current_location()
    # Returns: {"latitude": 37.7749, "longitude": -122.4194, "formatted": "37.7749,-122.4194", "source": "shortcuts"}
"""

import subprocess
import re
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class LocationService:
    """Service for detecting current location on macOS."""

    # Aliases for "current location"
    CURRENT_LOCATION_ALIASES = [
        "here",
        "current",
        "current location",
        "my location",
        "where i am",
        "my current location"
    ]

    def __init__(self):
        """Initialize the location service."""
        self._shortcuts_available = self._check_shortcuts()
        self._corelocationcli_available = self._check_corelocationcli()

        logger.info(f"Location service initialized - Shortcuts: {self._shortcuts_available}, CoreLocationCLI: {self._corelocationcli_available}")

    def _check_shortcuts(self) -> bool:
        """Check if macOS Shortcuts is available."""
        try:
            result = subprocess.run(
                ["shortcuts", "list"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _check_corelocationcli(self) -> bool:
        """Check if CoreLocationCLI is installed."""
        try:
            result = subprocess.run(
                ["which", "CoreLocationCLI"],
                capture_output=True,
                text=True,
                timeout=2
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _get_location_via_shortcuts(self) -> Optional[Dict[str, any]]:
        """
        Get current location using macOS Shortcuts.

        Uses built-in "Get Current Location" shortcut action.
        Requires Location Services permission.
        """
        try:
            # Create a temporary shortcut to get location
            # Using osascript to run shortcuts
            script = '''
            tell application "Shortcuts Events"
                run shortcut "Get Current Location"
            end tell
            '''

            # Try direct shortcuts command with inline shortcut
            result = subprocess.run(
                ["shortcuts", "run", "Get Current Location"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout:
                # Parse output - shortcuts may return various formats
                output = result.stdout.strip()

                # Try to extract coordinates
                coords = self._parse_coordinates(output)
                if coords:
                    lat, lon = coords
                    return {
                        "latitude": lat,
                        "longitude": lon,
                        "formatted": f"{lat},{lon}",
                        "source": "shortcuts"
                    }

            logger.warning(f"Shortcuts returned no location: {result.stderr}")
            return None

        except subprocess.TimeoutExpired:
            logger.warning("Shortcuts location request timed out")
            return None
        except Exception as e:
            logger.warning(f"Shortcuts location failed: {e}")
            return None

    def _get_location_via_corelocationcli(self) -> Optional[Dict[str, any]]:
        """
        Get current location using CoreLocationCLI.

        CoreLocationCLI must be installed: brew install corelocationcli
        """
        try:
            result = subprocess.run(
                ["CoreLocationCLI", "-json"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout:
                import json
                data = json.loads(result.stdout)

                if "latitude" in data and "longitude" in data:
                    lat = float(data["latitude"])
                    lon = float(data["longitude"])

                    return {
                        "latitude": lat,
                        "longitude": lon,
                        "formatted": f"{lat},{lon}",
                        "source": "corelocationcli"
                    }

            logger.warning(f"CoreLocationCLI returned no location: {result.stderr}")
            return None

        except subprocess.TimeoutExpired:
            logger.warning("CoreLocationCLI timed out")
            return None
        except Exception as e:
            logger.warning(f"CoreLocationCLI failed: {e}")
            return None

    def _parse_coordinates(self, text: str) -> Optional[Tuple[float, float]]:
        """
        Parse latitude and longitude from text.

        Handles formats like:
        - "37.7749, -122.4194"
        - "37.7749,-122.4194"
        - "Lat: 37.7749, Lon: -122.4194"
        """
        # Try standard comma-separated format
        pattern = r'(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)'
        match = re.search(pattern, text)

        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))

                # Validate coordinates
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return (lat, lon)
            except ValueError:
                pass

        return None

    def is_current_location_alias(self, location_str: str) -> bool:
        """
        Check if a string is an alias for "current location".

        Args:
            location_str: String to check

        Returns:
            True if it's a current location alias
        """
        return location_str.lower().strip() in self.CURRENT_LOCATION_ALIASES

    def parse_location(self, location_str: str) -> Optional[Dict[str, any]]:
        """
        Parse a location string into coordinates.

        Handles:
        1. Current location aliases ("here", "current", etc.)
        2. Explicit coordinates ("37.7749,-122.4194")
        3. Returns None for place names (to be geocoded separately)

        Args:
            location_str: Location string from user

        Returns:
            Location dict or None if place name
        """
        location_str = location_str.strip()

        # Check if it's a current location alias
        if self.is_current_location_alias(location_str):
            return self.get_current_location()

        # Try to parse as coordinates
        coords = self._parse_coordinates(location_str)
        if coords:
            lat, lon = coords
            return {
                "latitude": lat,
                "longitude": lon,
                "formatted": f"{lat},{lon}",
                "source": "manual"
            }

        # It's a place name - return None to signal geocoding needed
        return None

    def get_current_location(self) -> Optional[Dict[str, any]]:
        """
        Get the device's current location.

        Tries methods in order:
        1. macOS Shortcuts (primary)
        2. CoreLocationCLI (fallback)

        Returns:
            Dict with latitude, longitude, formatted, and source
            or None if location cannot be determined
        """
        # Try Shortcuts first (built-in, better UX)
        if self._shortcuts_available:
            logger.info("Attempting to get location via Shortcuts...")
            location = self._get_location_via_shortcuts()
            if location:
                return location

        # Fall back to CoreLocationCLI
        if self._corelocationcli_available:
            logger.info("Attempting to get location via CoreLocationCLI...")
            location = self._get_location_via_corelocationcli()
            if location:
                return location

        # No method available
        logger.error("No location service available. Install CoreLocationCLI or enable Shortcuts.")
        return None

    def format_for_maps_url(self, location: Dict[str, any]) -> str:
        """
        Format location for Apple Maps URL.

        Args:
            location: Location dict from get_current_location() or parse_location()

        Returns:
            Formatted string for Maps URL (e.g., "37.7749,-122.4194")
        """
        return location.get("formatted", "")

    def get_setup_instructions(self) -> str:
        """
        Get setup instructions if no location service is available.

        Returns:
            Human-readable setup instructions
        """
        if not self._shortcuts_available and not self._corelocationcli_available:
            return """
Location services not available. Please install CoreLocationCLI:

    brew install corelocationcli

Or enable macOS Shortcuts and create a "Get Current Location" shortcut.

Alternatively, provide your location manually:
- "from 37.7749,-122.4194 to Berkeley"
- Provide latitude and longitude coordinates
"""
        elif not self._shortcuts_available:
            return "Shortcuts not available, using CoreLocationCLI as fallback."
        elif not self._corelocationcli_available:
            return "CoreLocationCLI not installed, using Shortcuts."
        else:
            return "Location services ready."


# Singleton instance
_location_service = None


def get_location_service() -> LocationService:
    """Get the global LocationService instance."""
    global _location_service
    if _location_service is None:
        _location_service = LocationService()
    return _location_service
