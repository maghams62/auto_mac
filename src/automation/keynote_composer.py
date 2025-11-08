"""
macOS Keynote integration using AppleScript.
"""

import subprocess
import logging
from typing import Optional, List, Dict, Any
import json
from pathlib import Path


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
            slides: List of slide dictionaries (can have 'title', 'content', and/or 'image_path')
            output_path: Optional path to save

        Returns:
            AppleScript string
        """
        # Escape strings
        title = self._escape_applescript_string(title)
        if output_path:
            output_path = str(Path(output_path).expanduser().resolve())

        script_parts = [
            'tell application "Keynote"',
            '    activate',
            '    set newDoc to make new document',
            '    delay 0.5',
            '    tell newDoc',
        ]

        # Add title slide
        script_parts.extend([
            '        -- Set up title slide',
            '        tell slide 1',
            '            try',
            f'                set object text of default title item to "{title}"',
            '            end try',
            '        end tell',
        ])

        # Add content slides
        for i, slide in enumerate(slides, start=2):
            slide_title = self._escape_applescript_string(slide.get('title', f'Slide {i}'))
            slide_content = self._escape_applescript_string(slide.get('content', ''))
            image_path = slide.get('image_path')

            script_parts.extend([
                f'        -- Add slide {i}',
                '        set newSlide to make new slide',
                '        tell newSlide',
            ])

            # If there's an image, add it; otherwise add text
            if image_path:
                escaped_image_path = self._escape_applescript_string(image_path)
                script_parts.extend([
                    f'            -- Add image to slide',
                    f'            set imagePath to POSIX file "{escaped_image_path}"',
                    '            try',
                    '                set imgObj to make new image with properties {file:imagePath}',
                    '                set width of imgObj to 900',
                    '                set position of imgObj to {62, 120}',
                    '            on error errMsg',
                    '                -- If sizing fails, keep Keynote defaults',
                    '            end try',
                ])
            else:
                script_parts.extend([
                    '            try',
                    f'                set object text of default title item to "{slide_title}"',
                    '            end try',
                    '            try',
                    f'                set object text of default body item to "{slide_content}"',
                    '            end try',
                ])

            script_parts.append('        end tell')

        # Save if path provided
        script_parts.append('    end tell')

        if output_path:
            escaped_path = self._escape_applescript_string(output_path)
            script_parts.append(f'    save newDoc in POSIX file "{escaped_path}"')

        script_parts.append('end tell')

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
