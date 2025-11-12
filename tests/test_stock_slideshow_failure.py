"""
Diagnostic test to reproduce and diagnose the stock slideshow planning failure.

This test reproduces the exact user request and captures:
1. Which tools exist in ALL_AGENT_TOOLS
2. Which tools are visible to the planner
3. Whether stock tools are missing from the catalog
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
from src.agent import ALL_AGENT_TOOLS, STOCK_AGENT_TOOLS
from src.orchestrator.tools_catalog import generate_tool_catalog
from src.orchestrator.main_orchestrator import MainOrchestrator
from src.utils import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_tool_discovery():
    """Test which tools are discovered vs. which exist."""
    print("\n" + "="*80)
    print("DIAGNOSTIC TEST: Tool Discovery")
    print("="*80)
    
    # Check what stock tools exist
    print("\n1. Stock Tools in ALL_AGENT_TOOLS:")
    stock_tool_names = {tool.name for tool in STOCK_AGENT_TOOLS}
    print(f"   Found {len(stock_tool_names)} stock tools:")
    for name in sorted(stock_tool_names):
        print(f"     - {name}")
    
    # Check what tools are in ALL_AGENT_TOOLS
    all_tool_names = {tool.name for tool in ALL_AGENT_TOOLS}
    print(f"\n2. Total tools in ALL_AGENT_TOOLS: {len(all_tool_names)}")
    
    # Check what tools are in the catalog
    catalog = generate_tool_catalog()
    catalog_tool_names = {tool.name for tool in catalog}
    print(f"3. Tools in generated catalog: {len(catalog_tool_names)}")
    
    # Find missing stock tools
    missing_stock_tools = stock_tool_names - catalog_tool_names
    if missing_stock_tools:
        print(f"\n❌ MISSING STOCK TOOLS ({len(missing_stock_tools)}):")
        for name in sorted(missing_stock_tools):
            print(f"     - {name}")
    else:
        print("\n✅ All stock tools are in catalog")
    
    # Find all missing tools
    missing_tools = all_tool_names - catalog_tool_names
    if missing_tools:
        print(f"\n⚠️  TOTAL MISSING TOOLS ({len(missing_tools)}):")
        for name in sorted(missing_tools):
            print(f"     - {name}")
    else:
        print("\n✅ All tools are in catalog")
    
    return {
        "stock_tools_exist": stock_tool_names,
        "catalog_tools": catalog_tool_names,
        "missing_stock_tools": missing_stock_tools,
        "missing_all_tools": missing_tools
    }


def test_planning_failure():
    """Test the actual planning failure with the user request."""
    print("\n" + "="*80)
    print("DIAGNOSTIC TEST: Planning Failure Reproduction")
    print("="*80)
    
    user_request = "create a slideshow about the stock price of Costco over the past five days into a slideshow and email it to me"
    
    print(f"\nUser Request: {user_request}")
    
    try:
        config = load_config()
        orchestrator = MainOrchestrator(config)
        
        print("\nAttempting to create plan...")
        result = orchestrator.execute(user_request)
        
        if result.get("status") == "failed":
            error = result.get("error", "Unknown error")
            print(f"\n❌ PLANNING FAILED: {error}")
            return False
        else:
            print(f"\n✅ Planning succeeded!")
            plan = result.get("plan", [])
            print(f"   Plan has {len(plan)} steps")
            for i, step in enumerate(plan, 1):
                action = step.get("action", "unknown")
                print(f"   Step {i}: {action}")
            return True
            
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "="*80)
    print("STOCK SLIDESHOW FAILURE DIAGNOSTIC TEST")
    print("="*80)
    
    # Test 1: Tool discovery
    discovery_results = test_tool_discovery()
    
    # Test 2: Planning failure
    planning_success = test_planning_failure()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Missing stock tools: {len(discovery_results['missing_stock_tools'])}")
    print(f"Total missing tools: {len(discovery_results['missing_all_tools'])}")
    print(f"Planning success: {planning_success}")
    
    if discovery_results['missing_stock_tools']:
        print("\n⚠️  ROOT CAUSE: Stock tools are missing from tool catalog!")
        print("   This prevents the planner from creating plans that use stock tools.")
    else:
        print("\n✅ All stock tools are available in catalog")
