"""
macOS Mail.app integration using AppleScript.
"""

import subprocess
import logging
from typing import Optional, List


logger = logging.getLogger(__name__)


class MailComposer:
    """
    Composes emails in macOS Mail.app using AppleScript.
    """

    def __init__(self, config: dict):
        """
        Initialize the mail composer.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.signature = config.get('email', {}).get('signature', '')

    def compose_email(
        self,
        subject: str,
        body: str,
        recipient: Optional[str] = None,
        attachment_path: Optional[str] = None,
        attachment_paths: Optional[List[str]] = None,
        send_immediately: bool = False,
    ) -> bool:
        """
        Compose a new email in Mail.app.

        Args:
            subject: Email subject
            body: Email body
            recipient: Recipient email address (optional)
            attachment_path: Path to single file to attach (optional, deprecated)
            attachment_paths: List of paths to files to attach (optional)
            send_immediately: If True, send the email immediately (default: False)

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Composing email: {subject}")

        try:
            # Add signature to body
            full_body = body + self.signature

            # Handle attachments with validation
            all_attachments = []
            invalid_attachments = []

            if attachment_path:
                all_attachments.append(attachment_path)
            if attachment_paths:
                all_attachments.extend(attachment_paths)

            # Validate all attachment paths exist
            import os
            validated_attachments = []
            for att_path in all_attachments:
                if os.path.exists(att_path) and os.path.isfile(att_path):
                    validated_attachments.append(att_path)
                else:
                    logger.warning(f"[MAIL COMPOSER] Attachment file not found, skipping: {att_path}")
                    invalid_attachments.append(att_path)

            # Log warning if some attachments were invalid
            if invalid_attachments:
                logger.warning(f"[MAIL COMPOSER] {len(invalid_attachments)} attachment(s) not found: {invalid_attachments}")

            all_attachments = validated_attachments

            # Build AppleScript
            script = self._build_applescript(
                subject=subject,
                body=full_body,
                recipient=recipient,
                attachment_paths=all_attachments if all_attachments else None,
                send_immediately=send_immediately,
            )

            # Execute AppleScript
            # Write to a temporary file for reliable execution
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.scpt', delete=False) as f:
                f.write(script)
                script_file = f.name

            try:
                result = subprocess.run(
                    ['osascript', script_file],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            finally:
                # Clean up temp file
                import os
                try:
                    os.unlink(script_file)
                except:
                    pass

            if result.returncode == 0:
                if send_immediately:
                    logger.info("Email sent successfully")
                else:
                    logger.info("Email composed successfully")
                return True
            else:
                logger.error(f"AppleScript error: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error composing email: {e}")
            return False

    def _build_applescript(
        self,
        subject: str,
        body: str,
        recipient: Optional[str] = None,
        attachment_paths: Optional[List[str]] = None,
        send_immediately: bool = False,
    ) -> str:
        """
        Build AppleScript for composing email.

        Args:
            subject: Email subject
            body: Email body
            recipient: Recipient email address
            attachment_paths: List of paths to attachments
            send_immediately: If True, send the email immediately

        Returns:
            AppleScript string
        """
        # Escape quotes and backslashes in strings
        subject = self._escape_applescript_string(subject)
        body = self._escape_applescript_string(body)

        # Start building script
        # Use a simpler approach: set content separately to avoid long property lines
        script_parts = [
            'tell application "Mail"',
            f'    set newMessage to make new outgoing message with properties {{subject:"{subject}"}}',
            f'    set content of newMessage to "{body}"',
        ]

        # Add recipient if provided
        if recipient:
            recipient = self._escape_applescript_string(recipient)
            script_parts.extend([
                '    tell newMessage',
                f'        make new to recipient with properties {{address:"{recipient}"}}',
                '    end tell',
            ])

        # Add attachments if provided
        has_attachments = bool(attachment_paths)
        if attachment_paths:
            for attachment_path in attachment_paths:
                escaped_path = self._escape_applescript_string(attachment_path)
                script_parts.extend([
                    '    tell newMessage',
                    f'        make new attachment with properties {{file name:POSIX file "{escaped_path}"}} at after the last paragraph',
                    '    end tell',
                ])

        # Either send immediately or show as draft
        if send_immediately:
            # Add delay if we have attachments to ensure they're fully loaded
            if has_attachments:
                script_parts.append('    -- Wait for attachments to load before sending')
                script_parts.append('    delay 1')
            script_parts.extend([
                '    send newMessage',
                'end tell',
            ])
        else:
            # Show the message as draft
            script_parts.extend([
                '    set visible of newMessage to true',
                '    activate',
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
        # For AppleScript, we need to handle special characters carefully
        # Replace backslash first
        s = s.replace('\\', '\\\\')
        # Replace quotes
        s = s.replace('"', '\\"')
        # Replace newlines with a space and line break for now (simplified)
        # This ensures AppleScript doesn't break on multi-line content
        s = s.replace('\n', ' ')
        # Remove multiple spaces
        s = ' '.join(s.split())
        return s

    def send_quick_email(
        self,
        subject: str,
        body: str,
        recipient: str,
        send_immediately: bool = False,
    ) -> bool:
        """
        Compose and optionally send email immediately.

        Args:
            subject: Email subject
            body: Email body
            recipient: Recipient email address
            send_immediately: If True, send without user confirmation

        Returns:
            True if successful, False otherwise
        """
        if send_immediately:
            logger.warning("Immediate sending not implemented for safety")
            # For safety, we don't auto-send emails
            # User must manually click send

        return self.compose_email(
            subject=subject,
            body=body,
            recipient=recipient,
        )

    def test_mail_integration(self) -> bool:
        """
        Test if Mail.app is accessible.

        Returns:
            True if Mail.app is accessible, False otherwise
        """
        try:
            script = '''
            tell application "Mail"
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
            logger.error(f"Mail integration test failed: {e}")
            return False
