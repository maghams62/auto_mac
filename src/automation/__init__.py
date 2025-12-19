"""Automation module for macOS integrations."""

from .mail_composer import MailComposer
from .mail_reader import MailReader
from .keynote_composer import KeynoteComposer
from .pages_composer import PagesComposer
from .maps_automation import MapsAutomation
from .spotify_automation import SpotifyAutomation
from .celebration_automation import CelebrationAutomation
from .calendar_automation import CalendarAutomation

__all__ = ["MailComposer", "MailReader", "KeynoteComposer", "PagesComposer", "MapsAutomation", "SpotifyAutomation", "CelebrationAutomation", "CalendarAutomation"]
