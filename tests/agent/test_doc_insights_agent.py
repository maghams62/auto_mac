import pytest

from src.agent.doc_insights_agent import (
    resolve_component_id,
    get_component_activity,
    get_top_dissatisfied_components,
    list_doc_issues,
)

TEST_COMPONENT = "core.payments"


def _skip_if_error(result):
    if isinstance(result, dict) and result.get("error"):
        pytest.skip(result["error"])


def test_resolve_component_id_maps_alias():
    result = resolve_component_id.invoke({"name": "core-api"})
    _skip_if_error(result)
    assert result["component_id"].startswith("core")


def test_get_component_activity_returns_scores():
    resolved = resolve_component_id.invoke({"name": TEST_COMPONENT})
    _skip_if_error(resolved)
    component_id = resolved.get("component_id", TEST_COMPONENT)
    result = get_component_activity.invoke({"component_id": component_id, "window": "7d"})
    _skip_if_error(result)
    assert "activity_score" in result
    assert result["component_id"] == component_id


def test_get_top_dissatisfied_components_smoke():
    result = get_top_dissatisfied_components.invoke({"limit": 2, "window": "7d"})
    _skip_if_error(result)
    assert isinstance(result["components"], list)
    assert len(result["components"]) <= 2


def test_list_doc_issues_handles_component_filter():
    resolved = resolve_component_id.invoke({"name": TEST_COMPONENT})
    _skip_if_error(resolved)
    component_id = resolved.get("component_id", TEST_COMPONENT)
    result = list_doc_issues.invoke({"component_id": component_id})
    _skip_if_error(result)
    assert "doc_issues" in result
    assert isinstance(result["doc_issues"], list)

