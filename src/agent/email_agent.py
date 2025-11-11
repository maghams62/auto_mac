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

logger = logging.getLogger(__name__)


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

    try:
        from src.automation import MailComposer
        from src.utils import load_config

        config = load_config()
        
        # Handle "email to me" logic - use default recipient if recipient is None or contains "me"
        if recipient is None or not recipient or recipient.lower().strip() in ["me", "my email", "to me", "myself"]:
            default_recipient = config.get('email', {}).get('default_recipient')
            if default_recipient:
                recipient = default_recipient
                logger.info(f"[EMAIL AGENT] Using default recipient: {recipient}")
            elif recipient is None or not recipient:
                # If no default configured and recipient is None, create draft
                logger.info("[EMAIL AGENT] No recipient specified and no default configured - creating draft")
        
        mail_composer = MailComposer(config)

        success = mail_composer.compose_email(
            subject=subject,
            body=body,
            recipient=recipient,
            attachment_paths=attachments,
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
    Use this to retrieve recent emails.

    Args:
        count: Number of emails to retrieve (default: 10, max: 50)
        mailbox: Mailbox name (default: INBOX)

    Returns:
        Dictionary with list of emails containing sender, subject, date, content

    Security:
        Only reads from the email account specified in config.yaml (email.account_email)
    """
    logger.info(f"[EMAIL AGENT] Tool: read_latest_emails(count={count}, mailbox='{mailbox}')")

    try:
        from src.automation import MailReader
        from src.utils import load_config
        from src.config_validator import ConfigAccessor

        config = load_config()
        config_accessor = ConfigAccessor(config)
        email_config = config_accessor.get_email_config()

        # SECURITY: Get configured account to constrain email reading
        account_email = email_config.get("account_email")
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
    Use this to find emails from a particular person or email address.

    Args:
        sender: Email address or name of sender (can be partial match)
        count: Maximum number of emails to retrieve (default: 10, max: 50)

    Returns:
        Dictionary with list of emails from the specified sender

    Security:
        Only reads from the email account specified in config.yaml (email.account_email)
    """
    logger.info(f"[EMAIL AGENT] Tool: read_emails_by_sender(sender='{sender}', count={count})")

    try:
        from src.automation import MailReader
        from src.utils import load_config
        from src.config_validator import ConfigAccessor

        config = load_config()
        config_accessor = ConfigAccessor(config)
        email_config = config_accessor.get_email_config()

        # SECURITY: Get configured account to constrain email reading
        account_email = email_config.get("account_email")
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
        from src.utils import load_config
        from src.config_validator import ConfigAccessor

        config = load_config()
        config_accessor = ConfigAccessor(config)
        email_config = config_accessor.get_email_config()

        # SECURITY: Get configured account to constrain email reading
        account_email = email_config.get("account_email")
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
        from src.utils import load_config

        config = load_config()
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

    Args:
        emails_data: Dictionary containing 'emails' list from read_* tools
        focus: Optional focus area (e.g., "action items", "deadlines", "important updates")

    Returns:
        Dictionary with summary text and structured data
    """
    logger.info(f"[EMAIL AGENT] Tool: summarize_emails(focus='{focus}')")

    try:
        from openai import OpenAI
        import os

        emails = emails_data.get("emails", [])
        if not emails:
            return {
                "summary": "No emails to summarize.",
                "count": 0
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

        # Use OpenAI to generate summary
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes emails clearly and concisely."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
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

Typical Workflows:

1. Check recent emails:
   read_latest_emails(count=10) → summarize_emails()

2. Find emails from someone:
   read_emails_by_sender(sender="john@example.com") → summarize_emails()

3. Review last hour's emails:
   read_emails_by_time(hours=1) → summarize_emails(focus="action items")

4. Read and reply to an email:
   read_latest_emails(count=5) → reply_to_email(original_sender="...", original_subject="...", reply_body="...", send=False)

5. Compose new email:
   compose_email(subject="...", body="...", recipient="...", send=True)
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
