from src.slash_git.models import GitQueryMode
from src.slash_git.planner import GitQueryPlanner


BASE_CONFIG = {
    "slash_git": {
        "target_catalog_path": "config/slash_git_targets.yaml",
        "default_repo_id": "core-api",
        "default_time_window_days": 7,
        "component_time_window_days": 7,
        "graph_emit_enabled": False,
    }
}


def test_planner_resolves_component_alias():
    planner = GitQueryPlanner(BASE_CONFIG)
    plan = planner.plan("what changed in the payments api last week?")

    assert plan is not None
    assert plan.repo_id == "core-api"
    assert plan.component_id == "core.payments"
    assert plan.mode == GitQueryMode.COMPONENT_ACTIVITY


def test_planner_defaults_time_window_days():
    config = {
        "slash_git": {
            **BASE_CONFIG["slash_git"],
            "default_time_window_days": 9,
        }
    }
    planner = GitQueryPlanner(config)
    plan = planner.plan("summarize repo activity in core-api")

    assert plan is not None
    assert plan.time_window is not None
    assert plan.time_window.label == "last 9 days"

