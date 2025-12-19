from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from ..slash_git.models import GitTargetCatalog
from ..utils import load_config
from ..utils.component_ids import resolve_component_id
from .slack_metadata import SlackMetadataService


@dataclass
class ResolvedTarget:
    """Structured representation of an extracted hashtag or tag-like token."""

    raw: str
    target_type: str
    identifier: Optional[str] = None
    label: Optional[str] = None
    graph_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw": self.raw,
            "type": self.target_type,
            "identifier": self.identifier,
            "label": self.label,
            "graph_refs": list(self.graph_refs),
            "metadata": dict(self.metadata),
        }


class HashtagResolver:
    """
    Resolve hashtag tokens into structured entities (components, repos, channels, incidents).

    The resolver is intentionally best-effort. It uses the slash git catalog for repo/component
    aliases, Slack metadata for channel hints, and deterministic heuristics for incidents.
    """

    TAG_PATTERN = re.compile(r"#([A-Za-z0-9:_\-/\.]+)")

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        slack_metadata_service: Optional[SlackMetadataService] = None,
        git_catalog: Optional[GitTargetCatalog] = None,
    ):
        self.config = config or load_config()
        self.slack_metadata = slack_metadata_service or SlackMetadataService(config=self.config)
        self._catalog = git_catalog or self._load_git_catalog()
        self._component_aliases = (
            dict(getattr(self._catalog, "component_aliases", {})) if self._catalog else {}
        )
        self._repo_aliases = (
            dict(getattr(self._catalog, "repo_aliases", {})) if self._catalog else {}
        )

    def extract_hashtags(self, text: str) -> List[str]:
        if not text:
            return []
        tags = []
        for match in self.TAG_PATTERN.finditer(text):
            token = match.group(1)
            if not token:
                continue
            normalized = token.strip()
            if not normalized:
                continue
            if normalized not in tags:
                tags.append(normalized)
        return tags

    def resolve_text(self, text: str) -> List[ResolvedTarget]:
        return self.resolve_many(self.extract_hashtags(text))

    def resolve_many(self, hashtags: Iterable[str]) -> List[ResolvedTarget]:
        results: List[ResolvedTarget] = []
        for tag in hashtags or []:
            resolved = self._resolve_tag(tag)
            if resolved:
                results.append(resolved)
        return results

    # ------------------------------------------------------------------ #
    # Internal helpers

    def _resolve_tag(self, tag: str) -> Optional[ResolvedTarget]:
        token = (tag or "").lstrip("#").strip()
        if not token:
            return None
        lowered = token.lower()

        incident = self._resolve_incident(lowered, raw=tag)
        if incident:
            return incident

        if ":" in lowered:
            scoped = self._resolve_scoped_token(lowered, raw=tag)
            if scoped:
                return scoped

        component = self._resolve_component(lowered, raw=tag)
        if component:
            return component

        repo = self._resolve_repo(lowered, raw=tag)
        if repo:
            return repo

        channel = self._resolve_channel(token)
        if channel:
            return channel

        return ResolvedTarget(raw=tag, target_type="tag", label=f"#{token}")

    def _resolve_incident(self, token: str, *, raw: str) -> Optional[ResolvedTarget]:
        if token.startswith("incident-") or token.startswith("incident"):
            identifier = token.replace("incident", "").lstrip("-:_") or token
            incident_id = f"incident-{identifier}".replace("--", "-")
            return ResolvedTarget(
                raw=raw,
                target_type="incident",
                identifier=incident_id,
                label=f"#{incident_id}",
                graph_refs=[f"incident:{incident_id}"],
            )
        if token.startswith("sev-") or token.startswith("sev"):
            incident_id = token.replace("sev", "incident", 1)
            return ResolvedTarget(
                raw=raw,
                target_type="incident",
                identifier=incident_id,
                label=f"#{incident_id}",
                graph_refs=[f"incident:{incident_id}"],
            )
        return None

    def _resolve_scoped_token(self, token: str, *, raw: str) -> Optional[ResolvedTarget]:
        prefix, suffix = token.split(":", 1)
        cleaned_suffix = suffix.strip()
        if not cleaned_suffix:
            return None
        if prefix in {"comp", "component"}:
            component_id = resolve_component_id(cleaned_suffix) or cleaned_suffix
            return ResolvedTarget(
                raw=raw,
                target_type="component",
                identifier=component_id,
                label=f"#comp:{component_id}",
                graph_refs=[f"component:{component_id}"],
            )
        if prefix in {"service", "svc"}:
            service_id = cleaned_suffix
            return ResolvedTarget(
                raw=raw,
                target_type="service",
                identifier=service_id,
                label=f"#service:{service_id}",
                graph_refs=[f"service:{service_id}"],
            )
        if prefix in {"repo", "git"}:
            repo = self._resolve_repo(cleaned_suffix, raw=raw)
            if repo:
                return repo
            return ResolvedTarget(
                raw=raw,
                target_type="repository",
                identifier=cleaned_suffix,
                label=f"#repo:{cleaned_suffix}",
                graph_refs=[f"repo:{cleaned_suffix}"],
            )
        if prefix in {"channel", "slack"}:
            channel = self._resolve_channel(cleaned_suffix)
            if channel:
                return channel
        return None

    def _resolve_component(self, token: str, *, raw: str) -> Optional[ResolvedTarget]:
        component_id = self._component_aliases.get(token)
        if not component_id:
            component_id = resolve_component_id(token)
        if not component_id:
            return None
        return ResolvedTarget(
            raw=raw,
            target_type="component",
            identifier=component_id,
            label=f"#{component_id}",
            graph_refs=[f"component:{component_id}"],
        )

    def _resolve_repo(self, token: str, *, raw: str) -> Optional[ResolvedTarget]:
        repo_id = self._repo_aliases.get(token)
        if not repo_id:
            return None
        label = token if token.startswith(repo_id) else repo_id
        return ResolvedTarget(
            raw=raw,
            target_type="repository",
            identifier=repo_id,
            label=f"#{label}",
            graph_refs=[f"repo:{repo_id}"],
        )

    def _resolve_channel(self, token: str) -> Optional[ResolvedTarget]:
        if not self.slack_metadata:
            return None
        channel_id = None
        try:
            channel = self.slack_metadata.get_channel(token)
            if channel:
                channel_id = channel.id
                channel_name = channel.name
            else:
                normalized = token.lower()
                channel = self.slack_metadata.get_channel(f"#{normalized}")
                if channel:
                    channel_id = channel.id
                    channel_name = channel.name
                else:
                    channel_name = token.lstrip("#")
        except Exception:
            channel = None
            channel_name = token.lstrip("#")
        if not (channel_id or channel):
            if re.fullmatch(r"C[0-9A-Z]{8,}", token):
                channel_id = token
                channel_name = token
            else:
                return None
        metadata = {}
        if channel_id:
            metadata["channel_id"] = channel_id
        if channel:
            metadata["channel_name"] = channel.name
            metadata["is_private"] = channel.is_private
        label = f"#{channel_name or token}"
        return ResolvedTarget(
            raw=f"#{token}",
            target_type="slack_channel",
            identifier=channel_id or channel_name,
            label=label,
            graph_refs=[f"slack_channel:{channel_id or channel_name}"],
            metadata=metadata,
        )

    def _load_git_catalog(self) -> Optional[GitTargetCatalog]:
        slash_git_cfg = (self.config.get("slash_git") or {}) if isinstance(self.config, dict) else {}
        catalog_path = (
            slash_git_cfg.get("target_catalog_path") or "config/slash_git_targets.yaml"
        )
        try:
            return GitTargetCatalog.from_file(catalog_path)
        except Exception:
            return None

