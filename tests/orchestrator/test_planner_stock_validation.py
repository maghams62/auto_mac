from src.orchestrator.planner import Planner


def make_planner():
    """Create a planner instance without running full init (avoid heavy deps)."""
    planner = Planner.__new__(Planner)
    planner.tool_parameters = {}
    return planner


def base_tool_catalog():
    """Minimal tool catalog covering stock + slideshow actions."""
    tool_names = [
        "hybrid_stock_brief",
        "hybrid_search_stock_symbol",
        "get_stock_price",
        "get_stock_history",
        "capture_stock_chart",
        "create_slide_deck_content",
        "create_keynote",
        "create_keynote_with_images",
        "synthesize_content",
        "compose_email",
        "reply_to_user",
    ]
    return [{"name": name} for name in tool_names]


def test_stock_slideshow_with_hybrid_passes_validation():
    planner = make_planner()
    plan = [
        {
            "id": 0,
            "action": "hybrid_stock_brief",
            "dependencies": [],
            "parameters": {"symbol": "NKE", "period": "past week"},
        },
        {
            "id": 1,
            "action": "synthesize_content",
            "dependencies": [0],
            "parameters": {"source_contents": ["$step0.history"]},
        },
        {
            "id": 2,
            "action": "create_slide_deck_content",
            "dependencies": [1],
            "parameters": {"title": "Nike weekly move", "outline": "$step1.synthesized_content"},
        },
        {
            "id": 3,
            "action": "create_keynote",
            "dependencies": [2],
            "parameters": {"slide_content": "$step2.slide_deck"},
        },
        {
            "id": 4,
            "action": "compose_email",
            "dependencies": [3],
            "parameters": {"subject": "Nike deck", "body": "$step2.summary", "send": True},
        },
        {
            "id": 5,
            "action": "reply_to_user",
            "dependencies": [4],
            "parameters": {"message": "Sent the Nike slideshow."},
        },
    ]

    validation = planner.validate_plan(plan, base_tool_catalog())
    assert validation["valid"], f"Expected validation to pass, issues: {validation['issues']}"
    assert validation["issues"] == []


def test_stock_slideshow_with_legacy_tools_is_rejected():
    planner = make_planner()
    plan = [
        {
            "id": 0,
            "action": "get_stock_price",
            "dependencies": [],
            "parameters": {"symbol": "NKE"},
        },
        {
            "id": 1,
            "action": "create_slide_deck_content",
            "dependencies": [0],
            "parameters": {"title": "Nike weekly move", "outline": "$step0.price"},
        },
        {
            "id": 2,
            "action": "create_keynote",
            "dependencies": [1],
            "parameters": {"slide_content": "$step1.slide_deck"},
        },
        {
            "id": 3,
            "action": "reply_to_user",
            "dependencies": [2],
            "parameters": {"message": "Done"},
        },
    ]

    validation = planner.validate_plan(plan, base_tool_catalog())
    assert not validation["valid"]
    assert any("hybrid_stock_brief" in issue for issue in validation["issues"])
    assert any("get_stock_price" in issue for issue in validation["issues"])

