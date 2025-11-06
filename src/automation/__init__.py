"""Automation module for macOS integrations."""

from .mail_composer import MailComposer
from .keynote_composer import KeynoteComposer
from .pages_composer import PagesComposer

__all__ = ["MailComposer", "KeynoteComposer", "PagesComposer"]
