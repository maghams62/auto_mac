"""
macOS Keynote integration using AppleScript.
"""

import subprocess
import logging
from typing import Optional, List, Dict, Any
import json


logger = logging.getLogger(__name__)


class KeynoteComposer:
    """
    Creates presentations in macOS Keynote using AppleScript.
    """

    def __init__(self, config: dict):
        """
        Initialize the Keynote composer.

        Args:
            config: Configuration dictionary
        """
        self.config = config

    def create_presentation(
        self,
        title: str,
        slides: List[Dict[str, Any]],
        output_path: Optional[str] = None,
    ) -> bool:
        """
        Create a new presentation in Keynote.

        Args:
            title: Presentation title
            slides: List of slide dictionaries with 'title' and 'content' keys
            output_path: Path to save the presentation (optional)

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Creating Keynote presentation: {title}")

        try:
            # Build AppleScript
            script = self._build_applescript(
                title=title,
                slides=slides,
                output_path=output_path,
            )

            # Execute AppleScript
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.scpt', delete=False) as f:
                f.write(script)
                script_file = f.name

            try:
                result = subprocess.run(
                    ['osascript', script_file],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            finally:
                # Clean up temp file
                import os
                try:
                    os.unlink(script_file)
                except:
                    pass

            if result.returncode == 0:
                logger.info("Keynote presentation created successfully")
                return True
            else:
                logger.error(f"AppleScript error: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error creating Keynote presentation: {e}")
            return False

    def _build_applescript(
        self,
        title: str,
        slides: List[Dict[str, Any]],
        output_path: Optional[str] = None,
    ) -> str:
        """
        Build AppleScript for creating Keynote presentation.

        Args:
            title: Presentation title
            slides: List of slide dictionaries
            output_path: Optional path to save

        Returns:
            AppleScript string
        """
        # Escape strings
        title = self._escape_applescript_string(title)

        script_parts = [
            'tell application "Keynote"',
            '    activate',
            '    set newDoc to make new document',
            '    tell newDoc',
        ]

        # Add title slide
        script_parts.extend([
            '        -- Set up title slide',
            '        tell slide 1',
            f'            set body text of default title item to "{title}"',
            '        end tell',
        ])

        # Add content slides
        for i, slide in enumerate(slides, start=2):
            slide_title = self._escape_applescript_string(slide.get('title', f'Slide {i}'))
            slide_content = self._escape_applescript_string(slide.get('content', ''))

            script_parts.extend([
                f'        -- Add slide {i}',
                '        set newSlide to make new slide',
                '        tell newSlide',
                f'            set body text of default title item to "{slide_title}"',
                f'            set body text of default body item to "{slide_content}"',
                '        end tell',
            ])

        # Save if path provided
        if output_path:
            escaped_path = self._escape_applescript_string(output_path)
            script_parts.extend([
                f'        save in POSIX file "{escaped_path}"',
            ])

        script_parts.extend([
            '    end tell',
            'end tell',
        ])

        return '\n'.join(script_parts)

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
        # Replace newlines with spaces for now (Keynote text boxes handle formatting)
        s = s.replace('\n', ' ')
        # Remove multiple spaces
        s = ' '.join(s.split())
        return s

    def test_keynote_integration(self) -> bool:
        """
        Test if Keynote is accessible.

        Returns:
            True if Keynote is accessible, False otherwise
        """
        try:
            script = '''
            tell application "Keynote"
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
            logger.error(f"Keynote integration test failed: {e}")
            return False
