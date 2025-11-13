"""
Knowledge Providers Models

Shared data models for knowledge provider functionality.
"""

from typing import Dict, Any, Optional


class KnowledgeResult:
    """
    Standardized result format for all knowledge providers.

    Attributes:
        title (str): Title/name of the knowledge item
        summary (str): Brief summary or description
        url (str): Source URL if available
        confidence (float): Confidence score (0.0-1.0)
        error (bool): Whether this represents an error
        error_type (str): Error type if error=True
        error_message (str): Error message if error=True
    """
    def __init__(
        self,
        title: str = "",
        summary: str = "",
        url: str = "",
        confidence: float = 0.0,
        error: bool = False,
        error_type: str = "",
        error_message: str = ""
    ):
        self.title = title
        self.summary = summary
        self.url = url
        self.confidence = confidence
        self.error = error
        self.error_type = error_type
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for tool returns."""
        return {
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "confidence": self.confidence,
            "error": self.error,
            "error_type": self.error_type,
            "error_message": self.error_message
        }
