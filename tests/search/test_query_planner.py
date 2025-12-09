from src.search.config import load_search_config
from src.search.query_planner import plan_modalities


def _planner_config():
    return {
        "search": {
            "enabled": True,
            "workspace_id": "acme",
            "planner": {
                "rules": [
                    {
                        "name": "code",
                        "keywords": ["stack trace", ".py"],
                        "include": ["git", "files"],
                    },
                    {
                        "name": "chat",
                        "keywords": ["slack", "channel"],
                        "include": ["slack"],
                    },
                    {
                        "name": "video",
                        "keywords": ["video", "youtube"],
                        "include": ["youtube"],
                    },
                ]
            },
            "modalities": {
                "slack": {"enabled": True},
                "git": {"enabled": True},
                "files": {"enabled": True},
                "youtube": {"enabled": True},
                "web_search": {"enabled": True, "fallback_only": True},
            },
        }
    }


def test_plan_modalities_code_query():
    cfg = load_search_config(_planner_config())
    planned = plan_modalities("Stack trace in auth.py failing", cfg)
    assert planned == ["git", "files"]


def test_plan_modalities_chat_query():
    cfg = load_search_config(_planner_config())
    planned = plan_modalities("Find the slack channel discussion", cfg)
    assert planned == ["slack"]


def test_plan_modalities_video_query():
    cfg = load_search_config(_planner_config())
    planned = plan_modalities("What did that youtube video say?", cfg)
    assert planned == ["youtube"]


def test_plan_modalities_fallback_to_all():
    cfg = load_search_config(_planner_config())
    planned = plan_modalities("general question", cfg)
    assert planned == ["slack", "git", "files", "youtube"]


def test_plan_modalities_returns_fallback_modalities():
    cfg = load_search_config(_planner_config())
    planned = plan_modalities("whatever", cfg, include_fallback=True)
    assert planned == ["web_search"]

