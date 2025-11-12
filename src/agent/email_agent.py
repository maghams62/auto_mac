"""
Email Agent - Handles all email operations.

This agent is responsible for:
- Composing emails
- Sending emails
- Managing attachments
- Reading emails
- Summarizing emails

Acts as a mini-orchestrator for email-related operations.
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
import logging
from datetime import datetime

from src.config import get_config_context
from src.config_validator import ConfigValidationError
from ..utils import get_temperature_for_model

logger = logging.getLogger(__name__)


def _load_email_runtime():
    """
    Load config, accessor, and email settings for email operations.

    Raises:
        ConfigValidationError if required email settings are missing.
    """
    context = get_config_context()
    accessor = context.accessor
    email_settings = accessor.get_email_config()
    return context.data, accessor, email_settings


@tool
def compose_email(
    subject: str,
    body: str,
    recipient: Optional[str] = None,
    attachments: Optional[List[str]] = None,
    send: bool = False
) -> Dict[str, Any]:
    """
    Create and optionally send an email via Mail.app.

    EMAIL AGENT - LEVEL 1: Email Composition
    Use this to create and send emails.

    Args:
        subject: Email subject
        body: Email body (supports markdown)
        recipient: Email address. If None, empty, or contains "me"/"to me"/"my email", will use default_recipient from config.yaml
        attachments: List of file paths to attach
        send: If True, send immediately; if False, open draft

    Returns:
        Dictionary with status ('sent' or 'draft')
    """
    logger.info(f"[EMAIL AGENT] Tool: compose_email(subject='{subject}', recipient='{recipient}', send={send})")

    # Validate email content
    if not body or not body.strip():
        if not attachments or len(attachments) == 0:
            logger.error("[EMAIL AGENT] ⚠️  VALIDATION FAILED: Email has empty body and no attachments!")
            return {
                "error": True,
                "error_type": "ValidationError",
                "error_message": "Email must have either body content or attachments (both cannot be empty)",
                "retry_possible": True
            }
        else:
            logger.warning("[EMAIL AGENT] Email body is empty but attachments are present - proceeding")

    # Validate and normalize attachments BEFORE composing email
    validated_attachments = []
    invalid_attachments = []
    
    if attachments:
        import os
        from pathlib import Path
        
        logger.info(f"[EMAIL AGENT] Validating {len(attachments)} attachment(s)...")
        
        for att_path in attachments:
            if not att_path or not isinstance(att_path, str):
                logger.warning(f"[EMAIL AGENT] Invalid attachment path (not a string): {att_path}")
                invalid_attachments.append(str(att_path))
                continue
            
            # Convert to absolute path
            try:
                abs_path = os.path.abspath(os.path.expanduser(att_path))
            except Exception as e:
                logger.warning(f"[EMAIL AGENT] Failed to convert path to absolute: {att_path}, error: {e}")
                invalid_attachments.append(att_path)
                continue
            
            # Verify file exists and is a file (not a directory)
            if not os.path.exists(abs_path):
                logger.error(f"[EMAIL AGENT] ⚠️  ATTACHMENT FILE NOT FOUND: {abs_path}")
                invalid_attachments.append(abs_path)
                continue
            
            if not os.path.isfile(abs_path):
                logger.warning(f"[EMAIL AGENT] Attachment path is not a file (directory?): {abs_path}")
                invalid_attachments.append(abs_path)
                continue
            
            # Verify file is readable
            if not os.access(abs_path, os.R_OK):
                logger.warning(f"[EMAIL AGENT] Attachment file is not readable: {abs_path}")
                invalid_attachments.append(abs_path)
                continue
            
            validated_attachments.append(abs_path)
            logger.info(f"[EMAIL AGENT] ✅ Validated attachment: {abs_path}")
        
        # If user requested attachments but none are valid, return error
        if len(attachments) > 0 and len(validated_attachments) == 0:
            error_details = []
            for inv_path in invalid_attachments:
                abs_path = os.path.abspath(os.path.expanduser(inv_path)) if isinstance(inv_path, str) else str(inv_path)
                if not os.path.exists(abs_path):
                    error_details.append(f"'{inv_path}' - file not found")
                elif not os.path.isfile(abs_path):
                    error_details.append(f"'{inv_path}' - not a file (may be a directory)")
                elif not os.access(abs_path, os.R_OK):
                    error_details.append(f"'{inv_path}' - file not readable")
                else:
                    error_details.append(f"'{inv_path}' - validation failed")
            
            error_msg = f"All {len(attachments)} attachment(s) failed validation: {', '.join(error_details)}"
            logger.error(f"[EMAIL AGENT] ⚠️  {error_msg}")
            return {
                "error": True,
                "error_type": "AttachmentError",
                "error_message": error_msg,
                "invalid_attachments": invalid_attachments,
                "retry_possible": True
            }
        
        # Log warning if some attachments were invalid but we have valid ones
        if invalid_attachments:
            logger.warning(f"[EMAIL AGENT] ⚠️  {len(invalid_attachments)} attachment(s) failed validation: {invalid_attachments}")
            logger.info(f"[EMAIL AGENT] Proceeding with {len(validated_attachments)} valid attachment(s)")
        
        logger.info(f"[EMAIL AGENT] Email will have {len(validated_attachments)} attachment(s): {validated_attachments}")

    try:
        from src.automation import MailComposer

        try:
            config, _, email_settings = _load_email_runtime()
        except ConfigValidationError as exc:
            logger.error(f"[EMAIL AGENT] Configuration error: {exc}")
            return {
                "error": True,
                "error_type": "ConfigurationError",
                "error_message": str(exc),
                "retry_possible": False
            }

        # Handle "email to me" logic - use default recipient if recipient is None or contains "me"
        if recipient is None or not recipient or recipient.lower().strip() in ["me", "my email", "to me", "myself"]:
            if email_settings.default_recipient:
                recipient = email_settings.default_recipient
                logger.info(f"[EMAIL AGENT] Using default recipient: {recipient}")
            else:
                logger.info("[EMAIL AGENT] No default recipient configured - creating draft without recipient")

        mail_composer = MailComposer(config)

        success = mail_composer.compose_email(
            subject=subject,
            body=body,
            recipient=recipient,
            attachment_paths=validated_attachments if validated_attachments else None,
            send_immediately=send
        )

        if success:
            return {
                "status": "sent" if send else "draft",
                "message": f"Email {'sent' if send else 'drafted'} successfully"
            }
        else:
            return {
                "error": True,
                "error_type": "MailError",
                "error_message": "Failed to compose email",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"[EMAIL AGENT] Error in compose_email: {e}")
        return {
            "error": True,
            "error_type": "MailError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def read_latest_emails(
    count: int = 10,
    mailbox: str = "INBOX"
) -> Dict[str, Any]:
    """
    Read the latest emails from Mail.app.

    EMAIL AGENT - LEVEL 2: Email Reading
    Use this to retrieve recent emails. Often used before summarize_emails().
    
    Typical use cases:
    - "summarize my last 3 emails" → read_latest_emails(count=3) → summarize_emails()
    - "what are my recent emails" → read_latest_emails(count=10)

    Args:
        count: Number of emails to retrieve (default: 10, max: 50)
        mailbox: Mailbox name (default: INBOX)

    Returns:
        Dictionary with:
        - emails: List of email dictionaries (sender, subject, date, content, content_preview)
        - count: Number of emails retrieved
        - mailbox: Mailbox name used
        - account: Account email used
        
    Note: The result can be passed directly to summarize_emails() for summarization.

    Security:
        Only reads from the email account specified in config.yaml (email.account_email)
    """
    logger.info(f"[EMAIL AGENT] Tool: read_latest_emails(count={count}, mailbox='{mailbox}')")

    try:
        from src.automation import MailReader

        try:
            config, _, email_settings = _load_email_runtime()
        except ConfigValidationError as exc:
            logger.error(f"[EMAIL AGENT] Configuration error: {exc}")
            return {
                "error": True,
                "error_type": "ConfigurationError",
                "error_message": str(exc),
                "retry_possible": False
            }

        # SECURITY: Get configured account to constrain email reading
        account_email = email_settings.account_email
        if not account_email:
            logger.warning("[EMAIL AGENT] No account_email configured - reading may not be constrained!")

        mail_reader = MailReader(config)

        # Limit count to reasonable maximum
        count = min(count, 50)

        emails = mail_reader.read_latest_emails(
            count=count,
            account_name=account_email,  # SECURITY: Constrain to configured account
            mailbox_name=mailbox
        )

        return {
            "emails": emails,
            "count": len(emails),
            "mailbox": mailbox,
            "account": account_email
        }

    except Exception as e:
        logger.error(f"[EMAIL AGENT] Error in read_latest_emails: {e}")
        return {
            "error": True,
            "error_type": "MailReadError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def read_emails_by_sender(
    sender: str,
    count: int = 10
) -> Dict[str, Any]:
    """
    Read emails from a specific sender.

    EMAIL AGENT - LEVEL 2: Email Reading
    Use this to find emails from a particular person or email address. Often used before summarize_emails().
    
    Typical use cases:
    - "summarize the last 3 emails sent by John Doe" → read_emails_by_sender(sender="John Doe", count=3) → summarize_emails()
    - "can you summarize emails from [person]" → read_emails_by_sender(sender="[person]", count=10) → summarize_emails()

    Args:
        sender: Email address or name of sender (can be partial match, e.g., "John Doe" or "john@example.com")
        count: Maximum number of emails to retrieve (default: 10, max: 50)

    Returns:
        Dictionary with:
        - emails: List of email dictionaries from the specified sender
        - count: Number of emails retrieved
        - sender: Sender identifier used
        - account: Account email used
        
    Note: The result can be passed directly to summarize_emails() for summarization.

    Security:
        Only reads from the email account specified in config.yaml (email.account_email)
    """
    logger.info(f"[EMAIL AGENT] Tool: read_emails_by_sender(sender='{sender}', count={count})")

    try:
        from src.automation import MailReader

        try:
            config, _, email_settings = _load_email_runtime()
        except ConfigValidationError as exc:
            logger.error(f"[EMAIL AGENT] Configuration error: {exc}")
            return {
                "error": True,
                "error_type": "ConfigurationError",
                "error_message": str(exc),
                "retry_possible": False
            }

        # SECURITY: Get configured account to constrain email reading
        account_email = email_settings.account_email
        if not account_email:
            logger.warning("[EMAIL AGENT] No account_email configured - reading may not be constrained!")

        mail_reader = MailReader(config)

        # Limit count to reasonable maximum
        count = min(count, 50)

        emails = mail_reader.read_emails_by_sender(
            sender_email=sender,
            count=count,
            account_name=account_email  # SECURITY: Constrain to configured account
        )

        return {
            "emails": emails,
            "count": len(emails),
            "sender": sender,
            "account": account_email
        }

    except Exception as e:
        logger.error(f"[EMAIL AGENT] Error in read_emails_by_sender: {e}")
        return {
            "error": True,
            "error_type": "MailReadError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def read_emails_by_time(
    hours: Optional[int] = None,
    minutes: Optional[int] = None,
    mailbox: str = "INBOX"
) -> Dict[str, Any]:
    """
    Read emails within a specific time range.

    EMAIL AGENT - LEVEL 2: Email Reading
    Use this to retrieve emails from the last N hours or minutes.

    Args:
        hours: Number of hours to look back (e.g., 1 for last hour, 24 for last day)
        minutes: Number of minutes to look back (alternative to hours)
        mailbox: Mailbox name (default: INBOX)

    Returns:
        Dictionary with list of emails within the time range

    Security:
        Only reads from the email account specified in config.yaml (email.account_email)
    """
    logger.info(f"[EMAIL AGENT] Tool: read_emails_by_time(hours={hours}, minutes={minutes})")

    try:
        from src.automation import MailReader

        try:
            config, _, email_settings = _load_email_runtime()
        except ConfigValidationError as exc:
            logger.error(f"[EMAIL AGENT] Configuration error: {exc}")
            return {
                "error": True,
                "error_type": "ConfigurationError",
                "error_message": str(exc),
                "retry_possible": False
            }

        # SECURITY: Get configured account to constrain email reading
        account_email = email_settings.account_email
        if not account_email:
            logger.warning("[EMAIL AGENT] No account_email configured - reading may not be constrained!")

        mail_reader = MailReader(config)

        emails = mail_reader.read_emails_by_time_range(
            hours=hours,
            minutes=minutes,
            account_name=account_email,  # SECURITY: Constrain to configured account
            mailbox_name=mailbox
        )

        return {
            "emails": emails,
            "count": len(emails),
            "time_range": f"{hours} hours" if hours else f"{minutes} minutes",
            "mailbox": mailbox,
            "account": account_email
        }

    except Exception as e:
        logger.error(f"[EMAIL AGENT] Error in read_emails_by_time: {e}")
        return {
            "error": True,
            "error_type": "MailReadError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def reply_to_email(
    original_sender: str,
    original_subject: str,
    reply_body: str,
    send: bool = False
) -> Dict[str, Any]:
    """
    Reply to a specific email.

    EMAIL AGENT - LEVEL 1: Email Composition
    Use this to reply to an email you've read. The subject will automatically have "Re: " prepended.

    Args:
        original_sender: Email address of the person who sent the original email
        original_subject: Subject line of the original email
        reply_body: Your reply message (supports markdown)
        send: If True, send immediately; if False, open as draft (default: False)

    Returns:
        Dictionary with status ('sent' or 'draft')
    """
    logger.info(f"[EMAIL AGENT] Tool: reply_to_email(to='{original_sender}', subject='{original_subject}', send={send})")

    try:
        from src.automation import MailComposer

        try:
            config, _, _ = _load_email_runtime()
        except ConfigValidationError as exc:
            logger.error(f"[EMAIL AGENT] Configuration error: {exc}")
            return {
                "error": True,
                "error_type": "ConfigurationError",
                "error_message": str(exc),
                "retry_possible": False
            }

        mail_composer = MailComposer(config)

        # Add "Re: " prefix if not already present
        subject = original_subject if original_subject.startswith("Re: ") else f"Re: {original_subject}"

        success = mail_composer.compose_email(
            subject=subject,
            body=reply_body,
            recipient=original_sender,
            send_immediately=send
        )

        if success:
            return {
                "status": "sent" if send else "draft",
                "message": f"Reply {'sent' if send else 'drafted'} to {original_sender}",
                "recipient": original_sender,
                "subject": subject
            }
        else:
            return {
                "error": True,
                "error_type": "MailError",
                "error_message": "Failed to compose reply",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"[EMAIL AGENT] Error in reply_to_email: {e}")
        return {
            "error": True,
            "error_type": "MailError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def summarize_emails(
    emails_data: Dict[str, Any],
    focus: Optional[str] = None
) -> Dict[str, Any]:
    """
    Summarize a list of emails with key information.

    EMAIL AGENT - LEVEL 3: Email Summarization
    Use this to create a concise summary of emails, highlighting key information.
    
    This tool should be used AFTER reading emails with one of the read_* tools:
    - read_latest_emails() → summarize_emails() - for summarizing recent emails
    - read_emails_by_sender() → summarize_emails() - for summarizing emails from a specific person
    - read_emails_by_time() → summarize_emails() - for summarizing emails from a time range
    
    The emails_data parameter should be the result dictionary from a read_* tool call.

    Args:
        emails_data: Dictionary containing 'emails' list from read_* tools (required).
                     Must be the output from read_latest_emails, read_emails_by_sender, or read_emails_by_time.
        focus: Optional focus area (e.g., "action items", "deadlines", "important updates", "key decisions")

    Returns:
        Dictionary with:
        - summary: Text summary of the emails
        - email_count: Number of emails summarized
        - focus: The focus area used (if any)
        - emails_summarized: List of email metadata (sender, subject, date)
    """
    logger.info(f"[EMAIL AGENT] Tool: summarize_emails(focus='{focus}')")

    try:
        from openai import OpenAI
        import os

        emails = emails_data.get("emails", [])
        if not emails:
            return {
                "summary": "No emails to summarize.",
                "count": 0,
                "message": "The emails_data dictionary did not contain any emails. Make sure to call a read_* tool first (read_latest_emails, read_emails_by_sender, or read_emails_by_time) and pass its result to summarize_emails."
            }

        # Build prompt for summarization
        email_text = []
        for i, email in enumerate(emails, 1):
            email_text.append(f"""
Email #{i}:
From: {email.get('sender', 'Unknown')}
Subject: {email.get('subject', 'No subject')}
Date: {email.get('date', 'Unknown')}
Content: {email.get('content_preview', email.get('content', ''))}
---
""")

        prompt = f"""Summarize the following {len(emails)} emails clearly and concisely.

For each email, indicate:
- Who sent it
- What the subject/topic is
- Key points or action items

{f"Focus especially on: {focus}" if focus else ""}

Emails:
{"".join(email_text)}

Provide a well-structured summary that's easy to scan."""

        # Load config for temperature settings
        try:
            config, _, _ = _load_email_runtime()
        except ConfigValidationError as exc:
            logger.warning(f"[EMAIL AGENT] Config error, using defaults: {exc}")
            config = {}

        # Use OpenAI to generate summary
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes emails clearly and concisely."},
                {"role": "user", "content": prompt}
            ],
            temperature=get_temperature_for_model(config, default_temperature=0.3),
            max_tokens=1500
        )

        summary = response.choices[0].message.content

        return {
            "summary": summary,
            "email_count": len(emails),
            "focus": focus,
            "emails_summarized": [
                {
                    "sender": e.get("sender"),
                    "subject": e.get("subject"),
                    "date": e.get("date")
                }
                for e in emails
            ]
        }

    except Exception as e:
        logger.error(f"[EMAIL AGENT] Error in summarize_emails: {e}")
        return {
            "error": True,
            "error_type": "SummarizationError",
            "error_message": str(e),
            "retry_possible": False
        }


# Email Agent Tool Registry
EMAIL_AGENT_TOOLS = [
    compose_email,
    reply_to_email,
    read_latest_emails,
    read_emails_by_sender,
    read_emails_by_time,
    summarize_emails,
]


# Email Agent Hierarchy
EMAIL_AGENT_HIERARCHY = """
Email Agent Hierarchy:
=====================

LEVEL 1: Email Composition
├─ compose_email → Create and send new emails via Mail.app
└─ reply_to_email → Reply to a specific email

LEVEL 2: Email Reading
├─ read_latest_emails → Retrieve recent emails from inbox
├─ read_emails_by_sender → Find emails from specific sender
└─ read_emails_by_time → Get emails from last N hours/minutes

LEVEL 3: Email Analysis
└─ summarize_emails → AI-powered summarization of email content

Domain: Email operations including reading, summarizing, composing, and replying to emails via macOS Mail.app

Typical Workflows:

1. Summarize recent emails:
   read_latest_emails(count=3) → summarize_emails()
   Example: "summarize my last 3 emails"

2. Summarize emails from specific sender:
   read_emails_by_sender(sender="john@example.com", count=3) → summarize_emails()
   Example: "summarize the last 3 emails sent by John Doe"
   Example: "can you summarize emails from [person's name]"

3. Summarize emails by time range:
   read_emails_by_time(hours=1) → summarize_emails(focus="action items")
   Example: "summarize emails from the last hour"

4. Read and reply to an email:
   read_latest_emails(count=5) → reply_to_email(original_sender="...", original_subject="...", reply_body="...", send=False)

5. Compose new email:
   compose_email(subject="...", body="...", recipient="...", send=True)

Summarization Patterns:
- "summarize my last N emails" → read_latest_emails(count=N) → summarize_emails()
- "summarize emails from [person]" → read_emails_by_sender(sender="[person]", count=10) → summarize_emails()
- "summarize the last N emails sent by [person]" → read_emails_by_sender(sender="[person]", count=N) → summarize_emails()
"""


class EmailAgent:
    """
    Email Agent - Mini-orchestrator for email operations.

    Responsibilities:
    - Composing emails
    - Sending emails
    - Managing attachments

    This agent acts as a sub-orchestrator that handles all email-related tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in EMAIL_AGENT_TOOLS}
        logger.info(f"[EMAIL AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        """Get all email agent tools."""
        return EMAIL_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get email agent hierarchy documentation."""
        return EMAIL_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an email agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Email agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[EMAIL AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[EMAIL AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
