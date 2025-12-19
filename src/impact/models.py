"""
Dataclasses and enums shared across the impact analysis pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ImpactEntityType(str, Enum):
    COMPONENT = "component"
    SERVICE = "service"
    API = "api"
    DOC = "doc"
    SLACK_THREAD = "slack_thread"


class ImpactLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ImpactedEntity:
    entity_id: str
    entity_type: ImpactEntityType
    confidence: float
    reason: str
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.entity_id,
            "type": self.entity_type.value,
            "confidence": self.confidence,
            "impact_level": self.impact_level.value,
            "reason": self.reason,
            "metadata": self.metadata,
        }


@dataclass
class ImpactEvidence:
    statement: str
    related_entities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement": self.statement,
            "related_entities": self.related_entities,
        }


@dataclass
class ImpactRecommendation:
    description: str
    reason: str
    confidence: float
    related_entities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "reason": self.reason,
            "confidence": self.confidence,
            "related_entities": self.related_entities,
        }


@dataclass
class GitFileChange:
    path: str
    repo: Optional[str] = None
    change_type: str = "modified"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "repo": self.repo,
            "change_type": self.change_type,
        }


@dataclass
class GitChangePayload:
    identifier: str
    title: str
    repo: str
    files: List[GitFileChange]
    author: Optional[str] = None
    description: Optional[str] = None
    merged: bool = False
    base_ref: Optional[str] = None
    head_ref: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identifier": self.identifier,
            "title": self.title,
            "repo": self.repo,
            "files": [f.to_dict() for f in self.files],
            "author": self.author,
            "description": self.description,
            "merged": self.merged,
            "base_ref": self.base_ref,
            "head_ref": self.head_ref,
            "metadata": self.metadata,
        }


@dataclass
class SlackComplaintContext:
    thread_id: str
    channel: str
    component_ids: List[str] = field(default_factory=list)
    api_ids: List[str] = field(default_factory=list)
    text: Optional[str] = None
    permalink: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "channel": self.channel,
            "component_ids": self.component_ids,
            "api_ids": self.api_ids,
            "text": self.text,
            "permalink": self.permalink,
        }


@dataclass
class ImpactReport:
    change_id: str
    change_title: Optional[str] = None
    change_summary: Optional[str] = None
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    changed_components: List[ImpactedEntity] = field(default_factory=list)
    changed_apis: List[ImpactedEntity] = field(default_factory=list)
    impacted_components: List[ImpactedEntity] = field(default_factory=list)
    impacted_services: List[ImpactedEntity] = field(default_factory=list)
    impacted_docs: List[ImpactedEntity] = field(default_factory=list)
    impacted_apis: List[ImpactedEntity] = field(default_factory=list)
    slack_threads: List[ImpactedEntity] = field(default_factory=list)
    recommendations: List[ImpactRecommendation] = field(default_factory=list)
    evidence: List[ImpactEvidence] = field(default_factory=list)
    evidence_summary: Optional[str] = None
    evidence_mode: str = "deterministic"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_id": self.change_id,
            "change_title": self.change_title,
            "change_summary": self.change_summary,
            "impact_level": self.impact_level.value,
            "changed_components": [entity.to_dict() for entity in self.changed_components],
            "changed_apis": [entity.to_dict() for entity in self.changed_apis],
            "impacted_components": [entity.to_dict() for entity in self.impacted_components],
            "impacted_services": [entity.to_dict() for entity in self.impacted_services],
            "impacted_docs": [entity.to_dict() for entity in self.impacted_docs],
            "impacted_apis": [entity.to_dict() for entity in self.impacted_apis],
            "slack_threads": [entity.to_dict() for entity in self.slack_threads],
            "recommendations": [rec.to_dict() for rec in self.recommendations],
            "evidence": [ev.to_dict() for ev in self.evidence],
            "evidence_summary": self.evidence_summary,
            "evidence_mode": self.evidence_mode,
            "metadata": self.metadata,
        }

