"""
Test the enhanced context variable resolution.

Tests both standalone variables and inline string interpolation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.agent import AutomationAgent
from src.utils import load_config

def test_variable_resolution():
    """Test that variables are resolved correctly in all formats."""
    print("\n" + "="*80)
    print("TEST: Context Variable Resolution")
    print("="*80)

    config = load_config()
    agent = AutomationAgent(config)

    # Simulate step results
    step_results = {
        1: {
            "symbol": "AAPL",
            "company_name": "Apple Inc.",
            "current_price": 225.50,
            "change_percent": 2.5,
            "message": "Apple Inc. (AAPL): $225.50 (+2.5%)"
        },
        2: {
            "period": "1mo",
            "latest_price": 225.50,
            "period_change_percent": 5.2,
            "message": "AAPL history for 1mo: 20 data points"
        }
    }

    print("\n" + "="*80)
    print("Test 1: Standalone variable")
    print("="*80)
    params1 = {"content": "$step1.message"}
    resolved1 = agent._resolve_parameters(params1, step_results)
    print(f"Input:    {params1}")
    print(f"Output:   {resolved1}")
    print(f"Expected: {{'content': 'Apple Inc. (AAPL): $225.50 (+2.5%)'}}")
    assert resolved1["content"] == "Apple Inc. (AAPL): $225.50 (+2.5%)", "Standalone variable failed!"
    print("✅ PASSED")

    print("\n" + "="*80)
    print("Test 2: Inline interpolation (single variable)")
    print("="*80)
    params2 = {"content": "Current price: $step1.current_price"}
    resolved2 = agent._resolve_parameters(params2, step_results)
    print(f"Input:    {params2}")
    print(f"Output:   {resolved2}")
    print(f"Expected: {{'content': 'Current price: 225.5'}}")
    assert resolved2["content"] == "Current price: 225.5", "Inline interpolation failed!"
    print("✅ PASSED")

    print("\n" + "="*80)
    print("Test 3: Inline interpolation (multiple variables)")
    print("="*80)
    params3 = {
        "content": "Price: $step1.current_price, Change: $step1.change_percent%, Company: $step1.company_name"
    }
    resolved3 = agent._resolve_parameters(params3, step_results)
    print(f"Input:    {params3}")
    print(f"Output:   {resolved3}")
    expected = "Price: 225.5, Change: 2.5%, Company: Apple Inc."
    print(f"Expected: {{'content': '{expected}'}}")
    assert resolved3["content"] == expected, "Multiple variables failed!"
    print("✅ PASSED")

    print("\n" + "="*80)
    print("Test 4: List with mixed variables")
    print("="*80)
    params4 = {
        "source_contents": [
            "$step1.message",
            "Historical data: $step2.period_change_percent% change over $step2.period",
            "$step2.message"
        ]
    }
    resolved4 = agent._resolve_parameters(params4, step_results)
    print(f"Input:    {params4['source_contents']}")
    print(f"Output:   {resolved4['source_contents']}")
    print(f"Expected: [")
    print(f"  'Apple Inc. (AAPL): $225.50 (+2.5%)',")
    print(f"  'Historical data: 5.2% change over 1mo',")
    print(f"  'AAPL history for 1mo: 20 data points'")
    print(f"]")
    assert resolved4["source_contents"][0] == "Apple Inc. (AAPL): $225.50 (+2.5%)", "List item 1 failed!"
    assert resolved4["source_contents"][1] == "Historical data: 5.2% change over 1mo", "List item 2 failed!"
    assert resolved4["source_contents"][2] == "AAPL history for 1mo: 20 data points", "List item 3 failed!"
    print("✅ PASSED")

    print("\n" + "="*80)
    print("ALL TESTS PASSED!")
    print("="*80)
    print("\nVariable resolution now supports:")
    print("  ✓ Standalone variables: $step1.field")
    print("  ✓ Inline interpolation: Text with $step1.field embedded")
    print("  ✓ Multiple variables: $step1.field1 and $step2.field2")
    print("  ✓ Lists of any combination of the above")
    print("\nThis makes the system generic and flexible for all use cases!")
    print("="*80)


if __name__ == "__main__":
    test_variable_resolution()
