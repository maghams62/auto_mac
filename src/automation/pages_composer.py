"""
macOS Pages integration using AppleScript.
"""

import subprocess
import logging
from typing import Optional, List, Dict, Any


logger = logging.getLogger(__name__)


class PagesComposer:
    """
    Creates documents in macOS Pages using AppleScript.
    """

    def __init__(self, config: dict):
        """
        Initialize the Pages composer.

        Args:
            config: Configuration dictionary
        """
        self.config = config

    def create_document(
        self,
        title: str,
        sections: List[Dict[str, Any]],
        output_path: Optional[str] = None,
    ) -> bool:
        """
        Create a new document in Pages.

        Args:
            title: Document title
            sections: List of section dictionaries with 'heading' and 'content' keys
            output_path: Path to save the document (optional)

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Creating Pages document: {title}")

        try:
            # Build AppleScript
            script = self._build_applescript(
                title=title,
                sections=sections,
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
                logger.info("Pages document created successfully")
                return True
            else:
                logger.error(f"AppleScript error: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error creating Pages document: {e}")
            return False

    def _build_applescript(
        self,
        title: str,
        sections: List[Dict[str, Any]],
        output_path: Optional[str] = None,
    ) -> str:
        """
        Build AppleScript for creating Pages document.

        Args:
            title: Document title
            sections: List of section dictionaries
            output_path: Optional path to save

        Returns:
            AppleScript string
        """
        # Escape strings
        title = self._escape_applescript_string(title)

        script_parts = [
            'tell application "Pages"',
            '    activate',
            '    set newDoc to make new document',
            '    tell newDoc',
            '        tell body text',
        ]

        # Add title
        script_parts.extend([
            f'            set titlePara to make new paragraph at end with properties {{font:"{self._get_title_font()}", size:{self._get_title_size()}}}',
            f'            set text of titlePara to "{title}\\n"',
        ])

        # Add sections
        for section in sections:
            heading = self._escape_applescript_string(section.get('heading', ''))
            content = self._escape_applescript_string(section.get('content', ''))

            if heading:
                script_parts.extend([
                    f'            set headingPara to make new paragraph at end with properties {{font:"{self._get_heading_font()}", size:{self._get_heading_size()}}}',
                    f'            set text of headingPara to "{heading}\\n"',
                ])

            if content:
                script_parts.extend([
                    f'            set contentPara to make new paragraph at end',
                    f'            set text of contentPara to "{content}\\n\\n"',
                ])

        script_parts.extend([
            '        end tell',
            '    end tell',
        ])

        # Save if path provided
        if output_path:
            escaped_path = self._escape_applescript_string(output_path)
            script_parts.extend([
                f'    save newDoc in POSIX file "{escaped_path}"',
            ])

        script_parts.extend([
            'end tell',
        ])

        return '\n'.join(script_parts)

    def _get_title_font(self) -> str:
        """Get font for title."""
        return "Helvetica Neue"

    def _get_title_size(self) -> int:
        """Get font size for title."""
        return 28

    def _get_heading_font(self) -> str:
        """Get font for headings."""
        return "Helvetica Neue"

    def _get_heading_size(self) -> int:
        """Get font size for headings."""
        return 18

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
        # Keep newlines but escape them properly
        s = s.replace('\n', '\\n')
        return s

    def test_pages_integration(self) -> bool:
        """
        Test if Pages is accessible.

        Returns:
            True if Pages is accessible, False otherwise
        """
        try:
            script = '''
            tell application "Pages"
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
            logger.error(f"Pages integration test failed: {e}")
            return False
