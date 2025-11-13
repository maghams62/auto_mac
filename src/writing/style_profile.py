"""
Style Profile - Centralized writing style management.

This module provides a StyleProfile class that can merge different sources of style
information including on-the-fly user hints, session memory preferences, and
deliverable defaults. It normalizes tone, cadence, structure, and other stylistic
elements into a consistent format.
"""

from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum


class CadenceModifier(Enum):
    """Cadence modifiers for writing style."""
    EXECUTIVE = "executive"
    NARRATIVE = "narrative"
    TECHNICAL = "technical"
    CONVERSATIONAL = "conversational"
    FORMAL = "formal"
    CREATIVE = "creative"


class DeliverableType(Enum):
    """Supported deliverable types with their default style profiles."""
    EMAIL = "email"
    REPORT = "report"
    SUMMARY = "summary"
    PRESENTATION = "presentation"
    NOTE = "note"
    GENERAL = "general"


@dataclass
class StyleProfile:
    """
    Centralized writing style profile that merges multiple style sources.

    This class manages the complex merging logic for:
    - On-the-fly user hints from query
    - Session memory preferences
    - Deliverable type defaults
    - Explicit must-hit facts and constraints
    """

    # Core style attributes
    deliverable_type: str = "general"
    tone: str = "professional"
    audience: str = "general"
    cadence: str = "balanced"
    cadence_modifiers: List[str] = field(default_factory=list)

    # Structural preferences
    target_structure: Optional[Dict[str, Any]] = None
    must_include_facts: List[str] = field(default_factory=list)
    must_include_data: Dict[str, Any] = field(default_factory=dict)

    # Style preferences
    style_preferences: Dict[str, Any] = field(default_factory=dict)

    # Source tracking for transparency
    sources_used: List[str] = field(default_factory=list)

    # Metadata
    confidence_score: float = 1.0
    last_updated: Optional[str] = None

    @classmethod
    def from_deliverable_defaults(cls, deliverable_type: Union[str, DeliverableType]) -> "StyleProfile":
        """Create a profile from deliverable type defaults."""
        if isinstance(deliverable_type, DeliverableType):
            deliverable_type = deliverable_type.value

        defaults = cls._get_deliverable_defaults(deliverable_type)
        profile = cls(**defaults)
        profile.sources_used = ["deliverable_defaults"]
        return profile

    @classmethod
    def from_user_hints(cls, user_query: str, context_hints: Optional[Dict[str, Any]] = None) -> "StyleProfile":
        """Extract style hints from user query and context."""
        profile = cls()

        # Analyze user query for style indicators
        query_lower = user_query.lower()

        # Tone detection
        if any(word in query_lower for word in ["executive", "leadership", "board", "ceo"]):
            profile.tone = "executive"
            profile.cadence_modifiers.append(CadenceModifier.EXECUTIVE.value)
        elif any(word in query_lower for word in ["technical", "detailed", "specific", "precise"]):
            profile.tone = "technical"
            profile.cadence_modifiers.append(CadenceModifier.TECHNICAL.value)
        elif any(word in query_lower for word in ["casual", "friendly", "chat", "informal"]):
            profile.tone = "conversational"
            profile.cadence_modifiers.append(CadenceModifier.CONVERSATIONAL.value)

        # Audience detection
        if any(word in query_lower for word in ["executive", "board", "leadership", "ceo"]):
            profile.audience = "executive"
        elif any(word in query_lower for word in ["technical", "engineer", "developer", "expert"]):
            profile.audience = "technical"

        # Extract explicit facts and data from context hints
        if context_hints:
            if "must_include_facts" in context_hints:
                profile.must_include_facts = context_hints["must_include_facts"]
            if "must_include_data" in context_hints:
                profile.must_include_data = context_hints["must_include_data"]

        profile.sources_used = ["user_hints"]
        profile.confidence_score = 0.8  # Lower confidence for extracted hints
        return profile

    @classmethod
    def from_session_memory(cls, session_context: Any) -> "StyleProfile":
        """Extract style preferences from session memory."""
        profile = cls()

        if not session_context:
            return profile

        # Extract from session context objects
        user_context = session_context.context_objects.get("user_context", {})
        if user_context.get("tone_hint"):
            profile.tone = user_context["tone_hint"]
            profile.cadence_modifiers.append(profile.tone)

        if user_context.get("audience_hint"):
            profile.audience = user_context["audience_hint"]

        # Extract from derived topic or recent interactions
        if session_context.derived_topic:
            # Use topic to influence structure
            profile.target_structure = {"focus_areas": [session_context.derived_topic]}

        profile.sources_used = ["session_memory"]
        profile.confidence_score = 0.9  # Higher confidence for stored preferences
        return profile

    def merge(self, other: "StyleProfile", priority: str = "other") -> "StyleProfile":
        """
        Merge another StyleProfile into this one.

        Args:
            other: The profile to merge in
            priority: Which profile takes priority ("self", "other", or "combine")

        Returns:
            New merged StyleProfile
        """
        merged = StyleProfile()

        # Merge core attributes with priority logic
        if priority == "self":
            merged.deliverable_type = self.deliverable_type or other.deliverable_type
            merged.tone = self.tone or other.tone
            merged.audience = self.audience or other.audience
            merged.cadence = self.cadence or other.cadence
        elif priority == "other":
            merged.deliverable_type = other.deliverable_type or self.deliverable_type
            merged.tone = other.tone or self.tone
            merged.audience = other.audience or self.audience
            merged.cadence = other.cadence or self.cadence
        else:  # combine - use other for non-empty values, self for empty
            merged.deliverable_type = other.deliverable_type or self.deliverable_type
            merged.tone = other.tone or self.tone
            merged.audience = other.audience or self.audience
            merged.cadence = other.cadence or self.cadence

        # Combine cadence modifiers (no priority - merge all)
        merged.cadence_modifiers = list(set(self.cadence_modifiers + other.cadence_modifiers))

        # Merge target structure
        merged.target_structure = self._merge_dicts(
            self.target_structure or {},
            other.target_structure or {}
        )

        # Combine must-include items
        merged.must_include_facts = list(set(self.must_include_facts + other.must_include_facts))
        merged.must_include_data = self._merge_dicts(self.must_include_data, other.must_include_data)

        # Merge style preferences
        merged.style_preferences = self._merge_dicts(self.style_preferences, other.style_preferences)

        # Combine sources and update metadata
        merged.sources_used = list(set(self.sources_used + other.sources_used))
        merged.confidence_score = min(self.confidence_score, other.confidence_score)  # Conservative confidence

        return merged

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "deliverable_type": self.deliverable_type,
            "tone": self.tone,
            "audience": self.audience,
            "cadence": self.cadence,
            "cadence_modifiers": self.cadence_modifiers,
            "target_structure": self.target_structure,
            "must_include_facts": self.must_include_facts,
            "must_include_data": self.must_include_data,
            "style_preferences": self.style_preferences,
            "sources_used": self.sources_used,
            "confidence_score": self.confidence_score,
            "last_updated": self.last_updated
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StyleProfile":
        """Create from dictionary format."""
        return cls(**data)

    def get_summary(self) -> str:
        """Get a human-readable summary of the style profile."""
        summary_parts = [
            f"Deliverable: {self.deliverable_type}",
            f"Tone: {self.tone}",
            f"Audience: {self.audience}"
        ]

        if self.cadence_modifiers:
            summary_parts.append(f"Cadence: {', '.join(self.cadence_modifiers)}")

        if self.sources_used:
            summary_parts.append(f"Sources: {', '.join(self.sources_used)}")

        return " | ".join(summary_parts)

    @staticmethod
    def _merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = dict1.copy()
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = StyleProfile._merge_dicts(result[key], value)
            else:
                result[key] = value
        return result

    @staticmethod
    def _get_deliverable_defaults(deliverable_type: str) -> Dict[str, Any]:
        """Get default style profile for a deliverable type."""
        defaults = {
            "email": {
                "deliverable_type": "email",
                "tone": "professional",
                "audience": "general",
                "cadence": "concise",
                "cadence_modifiers": ["conversational"],
                "style_preferences": {
                    "use_bullets": False,
                    "include_greeting": True,
                    "include_closing": True
                }
            },
            "report": {
                "deliverable_type": "report",
                "tone": "professional",
                "audience": "general",
                "cadence": "formal",
                "cadence_modifiers": ["technical"],
                "style_preferences": {
                    "use_bullets": False,
                    "include_sections": True,
                    "include_executive_summary": True
                }
            },
            "summary": {
                "deliverable_type": "summary",
                "tone": "professional",
                "audience": "general",
                "cadence": "concise",
                "cadence_modifiers": ["conversational"],
                "style_preferences": {
                    "use_bullets": True,
                    "focus_on_key_points": True
                }
            },
            "presentation": {
                "deliverable_type": "presentation",
                "tone": "professional",
                "audience": "general",
                "cadence": "concise",
                "cadence_modifiers": ["executive"],
                "style_preferences": {
                    "use_bullets": True,
                    "max_bullets_per_slide": 5,
                    "include_speaker_notes": True
                }
            },
            "note": {
                "deliverable_type": "note",
                "tone": "conversational",
                "audience": "personal",
                "cadence": "concise",
                "cadence_modifiers": ["narrative"],
                "style_preferences": {
                    "use_bullets": True,
                    "include_timestamps": True
                }
            },
            "general": {
                "deliverable_type": "general",
                "tone": "professional",
                "audience": "general",
                "cadence": "balanced",
                "cadence_modifiers": [],
                "style_preferences": {}
            }
        }

        return defaults.get(deliverable_type, defaults["general"])
