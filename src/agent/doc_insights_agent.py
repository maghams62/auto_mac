"""
Doc Insights Agent – shared tooling for Activity Graph (Option 1) and
Context Resolution / Impact (Option 2) workflows.
"""

from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from src.activity_graph.models import TimeWindow
from src.activity_graph.service import ActivityGraphService
from src.config.context import ConfigContext
from src.config.validator import ConfigAccessor
from src.graph import GraphService
from src.impact.service import ImpactService
from src.reasoners import DocDriftReasoner
from src.services.context_resolution_service import ContextResolutionService
from src.slash_git.models import alias_key_variants, normalize_alias_token
from src.slash_git.planner import GitQueryPlanner
from src.utils import load_config


# ---------------------------------------------------------------------------
# Cached singletons
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _config() -> Dict[str, Any]:
    return load_config()


@lru_cache(maxsize=1)
def _graph_service() -> GraphService:
    return GraphService(_config())


@lru_cache(maxsize=1)
def _activity_service() -> ActivityGraphService:
    return ActivityGraphService(_config())


@lru_cache(maxsize=1)
def _impact_service() -> ImpactService:
    cfg = _config()
    return ImpactService(
        ConfigContext(data=cfg, accessor=ConfigAccessor(cfg)),
        graph_service=_graph_service(),
    )


@lru_cache(maxsize=1)
def _context_service() -> ContextResolutionService:
    cfg = _config()
    context_cfg = cfg.get("context_resolution") or {}
    impact_settings = (context_cfg.get("impact") or {})
    return ContextResolutionService(
        _graph_service(),
        default_max_depth=impact_settings.get("default_max_depth", 2),
        context_config=context_cfg,
    )


@lru_cache(maxsize=1)
def _doc_drift_reasoner() -> DocDriftReasoner:
    return DocDriftReasoner(_config())


@lru_cache(maxsize=1)
def _target_catalog():
    return GitQueryPlanner(_config()).catalog


def _error(message: str) -> Dict[str, Any]:
    return {"error": message}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool("resolve_component_id")
def resolve_component_id(name: str) -> Dict[str, Any]:
    """
    Normalize a human component/service name (e.g., "core-api", "billing service")
    into the canonical component_id used by Activity Graph / Impact.
    """
    if not name or not name.strip():
        return _error("name is required")

    catalog = _target_catalog()
    component = catalog.get_component(name)
    if component:
        return {
            "input": name,
            "component_id": component.id,
            "component_name": component.name,
            "repo_id": component.repo_id,
            "aliases": component.aliases,
            "topics": component.topics,
        }

    # Provide helpful suggestions (repo match or alias hints)
    repo = catalog.get_repo(name)
    suggestions: List[str] = []
    if repo:
        suggestions = sorted(repo.components.keys())
    else:
        normalized = normalize_alias_token(name)
        for alias in alias_key_variants(name):
            hinted = catalog.component_aliases.get(alias)
            if hinted:
                suggestions.append(hinted)
        hinted = catalog.component_aliases.get(normalized)
        if hinted:
            suggestions.append(hinted)

    if not suggestions:
        suggestions = sorted(list({comp_id for comp_id in catalog.component_aliases.values()}))[:5]

    return {
        "input": name,
        "error": f"No component matched '{name}'",
        "suggestions": suggestions[:5],
    }


@tool("get_component_activity")
def get_component_activity(
    component_id: str,
    window: str = "7d",
    include_debug: bool = False,
) -> Dict[str, Any]:
    """
    Option 1 – Fetch activity + dissatisfaction scores, doc issues, and Slack signals
    for a single component over the requested window (e.g., "7d", "24h").
    """
    if not component_id:
        return _error("component_id is required")

    service = _activity_service()
    try:
        time_window = TimeWindow.from_label(window)
        result = service.compute_component_activity(
            component_id,
            time_window,
            include_debug=include_debug,
        )
        payload = asdict(result)
        payload["window"] = time_window.label
        return payload
    except Exception as exc:
        return _error(f"Failed to fetch component activity: {exc}")


@tool("get_top_dissatisfied_components")
def get_top_dissatisfied_components(limit: int = 5, window: str = "7d") -> Dict[str, Any]:
    """
    Option 1 – Highlight the most dissatisfied components in the Activity Graph.
    """
    service = _activity_service()
    try:
        window_obj = TimeWindow.from_label(window)
        results = service.top_dissatisfied_components(limit=limit, time_window=window_obj)
        return {
            "window": window_obj.label,
            "components": [asdict(item) for item in results],
        }
    except Exception as exc:
        return _error(f"Failed to compute dissatisfaction leaderboard: {exc}")


@tool("list_doc_issues")
def list_doc_issues(
    component_id: Optional[str] = None,
    repo_id: Optional[str] = None,
    source: str = "impact-report",
) -> Dict[str, Any]:
    """
    Option 1 / Option 2 – Retrieve persisted DocIssues for a component or repo.
    """
    if not component_id and not repo_id:
        return _error("component_id or repo_id is required")

    service = _impact_service()
    if not service.doc_issue_service:
        return _error("DocIssue store is disabled or unavailable")

    try:
        issues = service.list_doc_issues(
            source=source,
            component_id=component_id,
            repo_id=repo_id,
        )
        return {
            "filters": {
                "component_id": component_id,
                "repo_id": repo_id,
                "source": source,
            },
            "doc_issues": issues,
        }
    except Exception as exc:
        return _error(f"Failed to list doc issues: {exc}")


@tool("get_context_impacts")
def get_context_impacts(
    component_id: Optional[str] = None,
    api_id: Optional[str] = None,
    depth: int = 2,
    include_docs: bool = True,
    include_services: bool = True,
) -> Dict[str, Any]:
    """
    Option 2 – Run blast-radius analysis to find downstream docs/services/components
    impacted by a component or API change.
    """
    if not component_id and not api_id:
        return _error("component_id or api_id is required")

    service = _context_service()
    if not service.is_available():
        return _error("Context resolution service is disabled. Enable Neo4j in config.yaml.")

    try:
        return service.resolve_impacts(
            component_id=component_id,
            api_id=api_id,
            max_depth=depth,
            include_docs=include_docs,
            include_services=include_services,
        )
    except Exception as exc:
        return _error(f"Failed to resolve impacts: {exc}")


@tool("analyze_doc_drift")
def analyze_doc_drift(question: str) -> Dict[str, Any]:
    """
    Doc drift reasoner – mirrors the slash /git pipeline so NL requests share the same prompt.
    """
    if not question or not question.strip():
        return _error("question is required")

    try:
        answer = _doc_drift_reasoner().answer_question(question, source="doc_insights_tool")
        return {
            "summary": answer.summary,
            "sections": answer.sections,
            "impacted": answer.impacted,
            "doc_drift": answer.doc_drift,
            "doc_drift_facts": answer.doc_drift_facts,
            "next_steps": answer.next_steps,
            "warnings": answer.warnings,
        }
    except Exception as exc:
        return _error(f"Doc drift reasoner failed: {exc}")


DOC_INSIGHTS_AGENT_TOOLS = [
    resolve_component_id,
    get_component_activity,
    get_top_dissatisfied_components,
    list_doc_issues,
    get_context_impacts,
    analyze_doc_drift,
]

DOC_INSIGHTS_AGENT_HIERARCHY = """
DOC INSIGHTS AGENT
==================
LEVEL 1 – Option 1 (Activity / Dissatisfaction)
  • resolve_component_id(name)
  • get_component_activity(component_id, window)
  • get_top_dissatisfied_components(limit, window)

LEVEL 2 – Option 2 (Context / Impact)
  • list_doc_issues(component_id|repo_id)
  • get_context_impacts(component_id|api_id, depth)

LEVEL 3 – Doc Drift Reasoning
  • analyze_doc_drift(question)
"""


class DocInsightsAgent:
    """Mini agent wrapper exposing the doc insights tool collection."""

    def __init__(self, config: Dict[str, Any], *_, **__):
        self.config = config

    def get_tools(self) -> List:
        return DOC_INSIGHTS_AGENT_TOOLS

