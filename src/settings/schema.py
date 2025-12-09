"""Pydantic models describing Cerebros settings structures."""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict

AutomationMode = Literal["off", "suggest_only", "pr_only", "pr_and_auto_merge"]


class BaseSettingsModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class DomainPolicy(BaseSettingsModel):
    priority: List[str] = Field(default_factory=list)
    hints: List[str] = Field(default_factory=list)


class SourceOfTruthSettings(BaseSettingsModel):
    domains: Dict[str, DomainPolicy] = Field(default_factory=dict)


class RepoBranchOverride(BaseSettingsModel):
    repo_id: str = Field(..., alias="repoId")
    branch: str


class GitMonitorSettings(BaseSettingsModel):
    default_branch: Optional[str] = Field(default=None, alias="defaultBranch")
    projects: Dict[str, List[RepoBranchOverride]] = Field(default_factory=dict)


class DomainAutomationSettings(BaseSettingsModel):
    mode: AutomationMode = Field(default="off")


class AutomationSettings(BaseSettingsModel):
    doc_updates: Dict[str, DomainAutomationSettings] = Field(
        default_factory=dict, alias="docUpdates"
    )


class SettingsOverrides(BaseSettingsModel):
    version: int = Field(default=1)
    source_of_truth: Optional[SourceOfTruthSettings] = Field(
        default=None, alias="sourceOfTruth"
    )
    git_monitor: Optional[GitMonitorSettings] = Field(
        default=None, alias="gitMonitor"
    )
    automation: Optional[AutomationSettings] = None


class SettingsEffective(BaseSettingsModel):
    version: int = Field(default=1)
    source_of_truth: SourceOfTruthSettings = Field(
        default_factory=SourceOfTruthSettings, alias="sourceOfTruth"
    )
    git_monitor: GitMonitorSettings = Field(
        default_factory=GitMonitorSettings, alias="gitMonitor"
    )
    automation: AutomationSettings = Field(default_factory=AutomationSettings)

