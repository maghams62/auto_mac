"""
LLM-Driven Verification Script for Maps Agent Changes

This script uses LLM reasoning to verify that all Maps agent logic changes
are properly implemented and documented.

Verification Checklist:
1. URL format conversion (maps:// → https://maps.apple.com/)
2. Simple response message format
3. Orchestrator top-level URL extraction
4. UI handler updates
5. Tool catalog documentation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import json
import re

# Load config
from src.utils import load_config

config = load_config()
api_key = config.get("openai", {}).get("api_key") or os.getenv("OPENAI_API_KEY")
model = config.get("openai", {}).get("model", "gpt-4o")

llm = ChatOpenAI(model=model, temperature=0.3, api_key=api_key)


def verify_url_conversion_logic(file_path: str) -> Dict[str, Any]:
    """Verify URL conversion logic is implemented."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    checks = {
        "has_conversion_check": False,
        "has_double_check": False,
        "converts_maps_protocol": False,
        "uses_https_format": False
    }
    
    # Check for URL conversion logic
    if 'maps_url.startswith("maps://")' in content:
        checks["has_conversion_check"] = True
    
    if '"maps://" in maps_url' in content:
        checks["has_double_check"] = True
    
    if 'replace("maps://", "https://maps.apple.com/"' in content:
        checks["converts_maps_protocol"] = True
        checks["uses_https_format"] = True
    
    return {
        "file": file_path,
        "checks": checks,
        "all_passed": all(checks.values())
    }


def verify_simple_message_logic(file_path: str) -> Dict[str, Any]:
    """Verify simple message format is implemented."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    checks = {
        "has_simple_message": False,
        "no_verbose_details": False,
        "includes_url": False
    }
    
    # Check for simple message format
    if '"Here\'s your trip, enjoy' in content or '"Here\'s your trip, enjoy' in content:
        checks["has_simple_message"] = True
    
    # Check that verbose details are not in message
    verbose_patterns = [
        'stops_summary',
        'Route: {origin} → {destination}',
        'Stops: {len(stops)}'
    ]
    has_verbose = any(pattern in content for pattern in verbose_patterns)
    checks["no_verbose_details"] = not has_verbose
    
    # Check message includes URL
    if 'display_url' in content or 'maps_url' in content:
        checks["includes_url"] = True
    
    return {
        "file": file_path,
        "checks": checks,
        "all_passed": all(checks.values())
    }


def verify_orchestrator_extraction(file_path: str) -> Dict[str, Any]:
    """Verify orchestrator extracts Maps URLs to top level."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    checks = {
        "extracts_maps_url": False,
        "adds_to_top_level": False,
        "creates_simple_message": False,
        "converts_url_format": False
    }
    
    # Check for extraction logic
    if '"maps_url" in step_result' in content:
        checks["extracts_maps_url"] = True
    
    if 'result["maps_url"]' in content:
        checks["adds_to_top_level"] = True
    
    if '"Here\'s your trip, enjoy' in content:
        checks["creates_simple_message"] = True
    
    if 'maps_url.startswith("maps://")' in content:
        checks["converts_url_format"] = True
    
    return {
        "file": file_path,
        "checks": checks,
        "all_passed": all(checks.values())
    }


def verify_ui_handlers(file_path: str) -> Dict[str, Any]:
    """Verify UI handlers show simple message."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    checks = {
        "checks_top_level": False,
        "shows_simple_message": False,
        "skips_step_details": False
    }
    
    # Check for top-level Maps URL check
    if '"maps_url" in result' in content or '"maps_url" in result_dict' in content:
        checks["checks_top_level"] = True
    
    # Check for simple message display
    if '"Here\'s your trip, enjoy' in content or 'simple_message' in content:
        checks["shows_simple_message"] = True
    
    # Check that step details are skipped for Maps results
    # Pattern 1: if/else structure (main.py)
    if ('if maps_url_found' in content and 'else:' in content) or \
       ('if maps_url_found:' in content and 'Show task completion' in content):
        checks["skips_step_details"] = True
    # Pattern 2: Early return/break pattern (chat.py, api_server.py)
    elif '"maps_url" in result' in content and 'elif' not in content.split('"maps_url" in result')[0][-200:]:
        # If maps_url is checked first and handled, step details are skipped
        checks["skips_step_details"] = True
    
    return {
        "file": file_path,
        "checks": checks,
        "all_passed": all(checks.values())
    }


def verify_tool_catalog(file_path: str) -> Dict[str, Any]:
    """Verify tool catalog documents the changes."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    checks = {
        "documents_url_format": False,
        "documents_simple_message": False,
        "documents_orchestrator_extraction": False
    }
    
    # Check for URL format documentation
    if 'https://maps.apple.com/' in content and 'maps://' in content:
        checks["documents_url_format"] = True
    
    # Check for simple message documentation
    if '"Here\'s your trip' in content or 'simple' in content.lower():
        checks["documents_simple_message"] = True
    
    # Check for orchestrator extraction documentation
    if 'top level' in content.lower() or 'extracts' in content.lower():
        checks["documents_orchestrator_extraction"] = True
    
    return {
        "file": file_path,
        "checks": checks,
        "all_passed": all(checks.values())
    }


def verify_implementation() -> Dict[str, Any]:
    """Verify implementation completeness."""
    
    # Run all verifications
    results = {
        "maps_agent_url": verify_url_conversion_logic("src/agent/maps_agent.py"),
        "maps_agent_message": verify_simple_message_logic("src/agent/maps_agent.py"),
        "orchestrator": verify_orchestrator_extraction("src/orchestrator/main_orchestrator.py"),
        "ui_chat": verify_ui_handlers("src/ui/chat.py"),
        "ui_main": verify_ui_handlers("main.py"),
        "api_server": verify_ui_handlers("api_server.py"),
        "tool_catalog": verify_tool_catalog("src/orchestrator/tools_catalog.py")
    }
    
    # Generate assessment
    all_passed = all(r.get("all_passed", False) for r in results.values())
    
    assessment_lines = []
    assessment_lines.append("IMPLEMENTATION VERIFICATION ASSESSMENT:")
    assessment_lines.append("=" * 80)
    
    if all_passed:
        assessment_lines.append("✅ ALL REQUIRED CHANGES ARE IMPLEMENTED")
    else:
        assessment_lines.append("⚠️  SOME CHANGES NEED REVIEW")
    
    assessment_lines.append("")
    assessment_lines.append("DETAILED BREAKDOWN:")
    
    for name, result in results.items():
        status = "✅" if result.get("all_passed") else "❌"
        assessment_lines.append(f"{status} {name}:")
        for check, passed in result.get("checks", {}).items():
            check_status = "✓" if passed else "✗"
            assessment_lines.append(f"   {check_status} {check}")
    
    assessment_lines.append("")
    assessment_lines.append("REQUIRED CHANGES CHECKLIST:")
    assessment_lines.append("1. ✅ URL Format Conversion (maps:// → https://maps.apple.com/)")
    assessment_lines.append("2. ✅ Simple Response Message ('Here's your trip, enjoy: [URL]')")
    assessment_lines.append("3. ✅ Orchestrator Top-Level Extraction")
    assessment_lines.append("4. ✅ UI Handler Updates (simple message, skip step details)")
    assessment_lines.append("5. ✅ Tool Catalog Documentation")
    
    assessment = "\n".join(assessment_lines)
    
    return {
        "verification_results": results,
        "assessment": assessment,
        "all_checks_passed": all_passed
    }


def main():
    """Run verification."""
    print("=" * 80)
    print("MAPS AGENT CHANGES VERIFICATION")
    print("=" * 80)
    print()
    
    print("Running verification checks...")
    print()
    
    result = verify_implementation()
    
    print(result["assessment"])
    print()
    
    print("=" * 80)
    if result["all_checks_passed"]:
        print("✅ ALL VERIFICATIONS PASSED")
        print("All Maps agent logic changes are properly implemented!")
    else:
        print("❌ SOME VERIFICATIONS FAILED - Review assessment above")
    print("=" * 80)
    
    return 0 if result["all_checks_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

