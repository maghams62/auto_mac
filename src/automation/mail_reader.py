"""
macOS Mail.app email reading integration using AppleScript.
"""

import subprocess
import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class MailReader:
    """
    Reads emails from macOS Mail.app using AppleScript.
    """

    def __init__(self, config: dict):
        """
        Initialize the mail reader.

        Args:
            config: Configuration dictionary
        """
        self.config = config

    def read_latest_emails(
        self,
        count: int = 10,
        account_name: Optional[str] = None,
        mailbox_name: str = "INBOX"
    ) -> List[Dict[str, Any]]:
        """
        Read the latest emails from Mail.app.

        Args:
            count: Number of emails to retrieve (default: 10)
            account_name: Specific account name (optional)
            mailbox_name: Mailbox name (default: INBOX)

        Returns:
            List of email dictionaries with sender, subject, date, content
        """
        logger.info(f"[MAIL READER] Reading {count} latest emails from {mailbox_name}")

        try:
            script = self._build_read_latest_script(count, account_name, mailbox_name)
            result = self._execute_applescript(script)

            if result:
                emails = self._parse_email_list(result)
                logger.info(f"[MAIL READER] Retrieved {len(emails)} emails")
                return emails
            return []

        except Exception as e:
            logger.error(f"[MAIL READER] Error reading latest emails: {e}")
            return []

    def read_emails_by_sender(
        self,
        sender_email: str,
        count: int = 10,
        account_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Read emails from a specific sender.

        Args:
            sender_email: Email address or name of sender
            count: Maximum number of emails to retrieve
            account_name: Specific account name (optional)

        Returns:
            List of email dictionaries
        """
        logger.info(f"[MAIL READER] Reading emails from sender: {sender_email}")

        try:
            script = self._build_read_by_sender_script(sender_email, count, account_name)
            result = self._execute_applescript(script)

            if result:
                emails = self._parse_email_list(result)
                logger.info(f"[MAIL READER] Retrieved {len(emails)} emails from {sender_email}")
                return emails
            return []

        except Exception as e:
            logger.error(f"[MAIL READER] Error reading emails by sender: {e}")
            return []

    def read_emails_by_time_range(
        self,
        hours: Optional[int] = None,
        minutes: Optional[int] = None,
        since_date: Optional[datetime] = None,
        account_name: Optional[str] = None,
        mailbox_name: str = "INBOX"
    ) -> List[Dict[str, Any]]:
        """
        Read emails within a specific time range.

        Args:
            hours: Number of hours to look back (e.g., 1 for last hour)
            minutes: Number of minutes to look back
            since_date: Specific datetime to start from
            account_name: Specific account name (optional)
            mailbox_name: Mailbox name (default: INBOX)

        Returns:
            List of email dictionaries
        """
        # Calculate the cutoff time
        if since_date:
            cutoff_time = since_date
        elif hours is not None:
            cutoff_time = datetime.now() - timedelta(hours=hours)
        elif minutes is not None:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
        else:
            cutoff_time = datetime.now() - timedelta(hours=24)  # Default: last 24 hours

        logger.info(f"[MAIL READER] Reading emails since {cutoff_time}")

        try:
            script = self._build_read_by_time_script(cutoff_time, account_name, mailbox_name)
            result = self._execute_applescript(script)

            if result:
                emails = self._parse_email_list(result)
                logger.info(f"[MAIL READER] Retrieved {len(emails)} emails in time range")
                return emails
            return []

        except Exception as e:
            logger.error(f"[MAIL READER] Error reading emails by time range: {e}")
            return []

    def _build_read_latest_script(
        self,
        count: int,
        account_name: Optional[str],
        mailbox_name: str
    ) -> str:
        """Build AppleScript to read latest emails."""
        # If account_name is provided, scope to that account; otherwise read from all accounts
        if account_name:
            account_escaped = self._escape_applescript_string(account_name)
            mailbox_ref = f'mailbox "{mailbox_name}" of account "{account_escaped}"'
        else:
            mailbox_ref = f'mailbox "{mailbox_name}"'

        script = f'''
tell application "Mail"
    set emailList to {{}}
    set messageCount to 0

    try
        set targetMailbox to {mailbox_ref}
        set allMessages to messages of targetMailbox

        repeat with msg in (items 1 thru (count of allMessages) of allMessages)
            if messageCount ≥ {count} then exit repeat

            try
                set msgSender to sender of msg
                set msgSubject to subject of msg
                set msgDate to date received of msg
                set msgContent to content of msg

                set emailData to "EMAILSTART|||" & msgSender & "|||" & msgSubject & "|||" & (msgDate as string) & "|||" & msgContent & "|||EMAILEND"
                set end of emailList to emailData
                set messageCount to messageCount + 1
            end try
        end repeat
    end try

    set AppleScript's text item delimiters to "\\n"
    return emailList as text
end tell
'''
        return script

    def _build_read_by_sender_script(
        self,
        sender_email: str,
        count: int,
        account_name: Optional[str]
    ) -> str:
        """Build AppleScript to read emails by sender."""
        sender_escaped = self._escape_applescript_string(sender_email)

        # If account_name is provided, scope to that account; otherwise read from all accounts
        if account_name:
            account_escaped = self._escape_applescript_string(account_name)
            mailbox_ref = f'mailbox "INBOX" of account "{account_escaped}"'
        else:
            mailbox_ref = 'mailbox "INBOX"'

        script = f'''
tell application "Mail"
    set emailList to {{}}
    set messageCount to 0

    try
        -- Search in specified mailbox
        set allMessages to messages of {mailbox_ref}

        repeat with msg in allMessages
            if messageCount ≥ {count} then exit repeat

            try
                set msgSender to sender of msg

                -- Check if sender matches (case insensitive)
                if msgSender contains "{sender_escaped}" then
                    set msgSubject to subject of msg
                    set msgDate to date received of msg
                    set msgContent to content of msg

                    set emailData to "EMAILSTART|||" & msgSender & "|||" & msgSubject & "|||" & (msgDate as string) & "|||" & msgContent & "|||EMAILEND"
                    set end of emailList to emailData
                    set messageCount to messageCount + 1
                end if
            end try
        end repeat
    end try

    set AppleScript's text item delimiters to "\\n"
    return emailList as text
end tell
'''
        return script

    def _build_read_by_time_script(
        self,
        cutoff_time: datetime,
        account_name: Optional[str],
        mailbox_name: str
    ) -> str:
        """Build AppleScript to read emails by time range."""
        # Format datetime for AppleScript
        cutoff_str = cutoff_time.strftime("%m/%d/%Y %I:%M:%S %p")

        # If account_name is provided, scope to that account; otherwise read from all accounts
        if account_name:
            account_escaped = self._escape_applescript_string(account_name)
            mailbox_ref = f'mailbox "{mailbox_name}" of account "{account_escaped}"'
        else:
            mailbox_ref = f'mailbox "{mailbox_name}"'

        script = f'''
tell application "Mail"
    set emailList to {{}}

    try
        set targetMailbox to {mailbox_ref}
        set allMessages to messages of targetMailbox

        -- Parse cutoff date
        set cutoffDate to date "{cutoff_str}"

        repeat with msg in allMessages
            try
                set msgDate to date received of msg

                -- Check if message is newer than cutoff
                if msgDate ≥ cutoffDate then
                    set msgSender to sender of msg
                    set msgSubject to subject of msg
                    set msgContent to content of msg

                    set emailData to "EMAILSTART|||" & msgSender & "|||" & msgSubject & "|||" & (msgDate as string) & "|||" & msgContent & "|||EMAILEND"
                    set end of emailList to emailData
                end if
            end try
        end repeat
    end try

    set AppleScript's text item delimiters to "\\n"
    return emailList as text
end tell
'''
        return script

    def _execute_applescript(self, script: str) -> str:
        """Execute AppleScript and return result."""
        import tempfile
        import os

        # Write to temporary file
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

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"[MAIL READER] AppleScript error: {result.stderr}")
                return ""

        finally:
            # Clean up temp file
            try:
                os.unlink(script_file)
            except:
                pass

    def _parse_email_list(self, raw_output: str) -> List[Dict[str, Any]]:
        """Parse AppleScript output into list of email dictionaries."""
        emails = []

        if not raw_output:
            return emails

        # Split by email delimiter
        email_blocks = raw_output.split("EMAILSTART|||")

        for block in email_blocks:
            if "|||EMAILEND" not in block:
                continue

            try:
                # Remove the end delimiter
                block = block.replace("|||EMAILEND", "")

                # Split by field delimiter
                parts = block.split("|||")

                if len(parts) >= 4:
                    sender = parts[0].strip()
                    subject = parts[1].strip()
                    date_str = parts[2].strip()
                    content = parts[3].strip() if len(parts) > 3 else ""

                    # Clean up content (remove excessive whitespace)
                    content = ' '.join(content.split())

                    # Truncate very long content
                    if len(content) > 2000:
                        content = content[:2000] + "... [truncated]"

                    emails.append({
                        "sender": sender,
                        "subject": subject,
                        "date": date_str,
                        "content": content,
                        "content_preview": content[:200] + "..." if len(content) > 200 else content
                    })
            except Exception as e:
                logger.warning(f"[MAIL READER] Error parsing email block: {e}")
                continue

        return emails

    def _escape_applescript_string(self, s: str) -> str:
        """Escape string for use in AppleScript."""
        s = s.replace('\\', '\\\\')
        s = s.replace('"', '\\"')
        return s

    def test_mail_access(self) -> bool:
        """
        Test if Mail.app is accessible.

        Returns:
            True if accessible, False otherwise
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
            logger.error(f"[MAIL READER] Mail access test failed: {e}")
            return False
