"""
Neo4j schema definitions and DTOs shared across the graph module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict


class NodeLabels(str, Enum):
    """Canonical node labels used in the Neo4j graph."""

    COMPONENT = "Component"
    SERVICE = "Service"
    API_ENDPOINT = "APIEndpoint"
    DOC = "Doc"
    ISSUE = "Issue"
    PR = "PR"
    SLACK_THREAD = "SlackThread"
    ACTIVITY_SIGNAL = "ActivitySignal"
    CODE_ARTIFACT = "CodeArtifact"
    SUPPORT_CASE = "SupportCase"
    SLACK_EVENT = "SlackEvent"
    GIT_EVENT = "GitEvent"


class RelationshipTypes(str, Enum):
    """Relationship types used between graph entities."""

    DESCRIBES_COMPONENT = "DESCRIBES_COMPONENT"
    DESCRIBES_ENDPOINT = "DESCRIBES_ENDPOINT"
    AFFECTS_COMPONENT = "AFFECTS_COMPONENT"
    REFERENCES_ENDPOINT = "REFERENCES_ENDPOINT"
    MODIFIES_COMPONENT = "MODIFIES_COMPONENT"
    MODIFIES_ENDPOINT = "MODIFIES_ENDPOINT"
    CALLS_ENDPOINT = "CALLS_ENDPOINT"
    DISCUSSES_COMPONENT = "DISCUSSES_COMPONENT"
    DISCUSSES_ISSUE = "DISCUSSES_ISSUE"
    EXPOSES_ENDPOINT = "EXPOSES_ENDPOINT"
    OWNS_CODE = "OWNS_CODE"
    DEPENDS_ON = "DEPENDS_ON"
    SIGNALS_COMPONENT = "SIGNALS_COMPONENT"
    SIGNALS_ENDPOINT = "SIGNALS_ENDPOINT"
    SUPPORTS_COMPONENT = "SUPPORTS_COMPONENT"
    SUPPORTS_ENDPOINT = "SUPPORTS_ENDPOINT"
    HAS_COMPONENT = "HAS_COMPONENT"
    COMPLAINS_ABOUT_API = "COMPLAINS_ABOUT_API"
    ABOUT_COMPONENT = "ABOUT_COMPONENT"
    MODIFIES_API = "MODIFIES_API"
    TOUCHES_COMPONENT = "TOUCHES_COMPONENT"


@dataclass
class GraphComponentSummary:
    """Structured response for component-centric graph queries."""

    component_id: str
    docs: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    pull_requests: List[str] = field(default_factory=list)
    slack_threads: List[str] = field(default_factory=list)
    api_endpoints: List[str] = field(default_factory=list)


@dataclass
class GraphApiImpactSummary:
    """Structured response for API impact queries."""

    api_id: str
    services: List[str] = field(default_factory=list)
    docs: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    pull_requests: List[str] = field(default_factory=list)


@dataclass
class GraphQueryResult:
    """Low-level container for raw query rows (for internal use)."""

    records: List[Dict[str, str]] = field(default_factory=list)
