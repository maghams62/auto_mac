#!/usr/bin/env python3
"""
Regression tests for stock slideshow workflow.
Validates that stock slideshow requests use DuckDuckGo (google_search) instead of stock app tools,
and always include reply_to_user as the final step.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.orchestrator.planner import Planner
from src.orchestrator.tools_catalog import generate_tool_catalog


def test_stock_slideshow_uses_duckduckgo():
    """Test that stock slideshow plans use google_search (DuckDuckGo) instead of stock tools."""
    # Load config from file
    from src.utils import load_config
    config = load_config()
    planner = Planner(config=config)
    tool_catalog = generate_tool_catalog()
    
    # Convert ToolSpec objects to dict format for validate_plan
    tool_specs = [{"name": tool.name} for tool in tool_catalog]
    
    # Test query that should trigger stock slideshow workflow
    test_query = "Create a slideshow on NVIDIA's stock over the past 4 days and email it to me"
    
    # Create plan (this would normally use LLM, but we'll validate the result)
    # For now, we'll test the validation logic directly
    
    # Simulate a BAD plan that uses stock tools (should fail validation)
    bad_plan = [
        {"id": "step_1", "action": "get_stock_history", "parameters": {"symbol": "NVDA", "period": "4d"}},
        {"id": "step_2", "action": "synthesize_content", "parameters": {"source_contents": ["$step1"]}},
        {"id": "step_3", "action": "create_slide_deck_content", "parameters": {"content": "$step2"}},
        {"id": "step_4", "action": "create_keynote", "parameters": {"content": "$step3"}},
        {"id": "step_5", "action": "compose_email", "parameters": {"attachments": ["$step4"]}}
    ]
    
    validation = planner.validate_plan(bad_plan, tool_specs)
    
    assert not validation["valid"], "Plan using stock tools should fail validation"
    assert any("google_search" in issue.lower() or "duckduckgo" in issue.lower() 
               for issue in validation["issues"]), "Validation should mention DuckDuckGo requirement"
    
    # Simulate a BAD plan that's missing reply_to_user (should fail validation)
    bad_plan_no_reply = [
        {"id": "step_1", "action": "google_search", "parameters": {"query": "NVIDIA stock price past 4 days"}},
        {"id": "step_2", "action": "synthesize_content", "parameters": {"source_contents": ["$step1"]}},
        {"id": "step_3", "action": "create_slide_deck_content", "parameters": {"content": "$step2"}},
        {"id": "step_4", "action": "create_keynote", "parameters": {"content": "$step3"}},
        {"id": "step_5", "action": "compose_email", "parameters": {"attachments": ["$step4"]}}
    ]
    
    validation_no_reply = planner.validate_plan(bad_plan_no_reply, tool_specs)
    
    assert not validation_no_reply["valid"], "Plan missing reply_to_user should fail validation"
    assert any("reply_to_user" in issue.lower() for issue in validation_no_reply["issues"]), \
        "Validation should require reply_to_user as final step"
    
    # Simulate a GOOD plan (should pass validation)
    good_plan = [
        {"id": "step_1", "action": "google_search", "parameters": {"query": "NVIDIA stock price past 4 days", "num_results": 5}},
        {"id": "step_2", "action": "synthesize_content", "parameters": {"source_contents": ["$step1.results"], "topic": "NVIDIA Stock Analysis"}},
        {"id": "step_3", "action": "create_slide_deck_content", "parameters": {"content": "$step2.synthesized_content", "title": "NVIDIA Stock Analysis"}},
        {"id": "step_4", "action": "create_keynote", "parameters": {"title": "NVIDIA Stock Analysis", "content": "$step3.formatted_content"}},
        {"id": "step_5", "action": "compose_email", "parameters": {"subject": "NVIDIA Stock Analysis", "body": "Attached is the NVIDIA stock analysis slideshow.", "attachments": ["$step4.keynote_path"], "send": True}},
        {"id": "step_6", "action": "reply_to_user", "parameters": {"message": "Created and sent the NVIDIA stock analysis slideshow.", "status": "success"}}
    ]
    
    validation_good = planner.validate_plan(good_plan, tool_specs)
    
    # Good plan should pass validation (no issues)
    assert validation_good["valid"], f"Good plan should pass validation. Issues: {validation_good['issues']}"
    
    print("✅ All stock slideshow workflow validation tests passed!")


def test_stock_slideshow_no_screenshots():
    """Test that stock slideshow plans don't include screenshot steps."""
    # Load config from file
    from src.utils import load_config
    config = load_config()
    planner = Planner(config=config)
    tool_catalog = generate_tool_catalog()
    
    # Convert ToolSpec objects to dict format for validate_plan
    tool_specs = [{"name": tool.name} for tool in tool_catalog]
    
    # Plan with screenshot (should fail or warn)
    plan_with_screenshot = [
        {"id": "step_1", "action": "google_search", "parameters": {"query": "NVIDIA stock price"}},
        {"id": "step_2", "action": "capture_stock_chart", "parameters": {"symbol": "NVDA"}},
        {"id": "step_3", "action": "create_keynote_with_images", "parameters": {"images": ["$step2"]}},
        {"id": "step_4", "action": "compose_email", "parameters": {"attachments": ["$step3"]}},
        {"id": "step_5", "action": "reply_to_user", "parameters": {"message": "Done"}}
    ]
    
    validation = planner.validate_plan(plan_with_screenshot, tool_specs)
    
    # Should fail because it uses capture_stock_chart AND create_keynote (slideshow workflow)
    assert not validation["valid"], "Plan with capture_stock_chart in slideshow workflow should fail validation"
    
    print("✅ Screenshot validation test passed!")


if __name__ == "__main__":
    print("="*70)
    print("STOCK SLIDESHOW WEB WORKFLOW REGRESSION TESTS")
    print("="*70)
    print()
    
    try:
        test_stock_slideshow_uses_duckduckgo()
        test_stock_slideshow_no_screenshots()
        
        print()
        print("="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

