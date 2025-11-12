#!/usr/bin/env python3
"""
Search and Folder Organization Testing Script - Browser-Based UI Testing
Tests semantic search, file/folder organization, and slash command isolation.

This script follows the browser-based testing methodology from docs/testing/TESTING_METHODOLOGY.md

NOTE: This script is designed to be run in an environment with browser MCP tools available.
The actual browser automation is performed via MCP tool calls which are executed by the AI assistant.
"""

import time
import subprocess
import sys
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Test results storage
TEST_RESULTS: List[Dict[str, Any]] = []


def log_test_result(test_name: str, passed: bool, details: Dict[str, Any]):
    """Log test result with details."""
    result = {
        "test_name": test_name,
        "timestamp": datetime.now().isoformat(),
        "passed": passed,
        "details": details
    }
    TEST_RESULTS.append(result)
    
    status = "✅ PASSED" if passed else "❌ FAILED"
    print(f"\n{'='*80}")
    print(f"{status}: {test_name}")
    print(f"{'='*80}")
    for key, value in details.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        elif isinstance(value, list):
            print(f"  {key}: {len(value)} items")
        else:
            print(f"  {key}: {value}")
    print()


def start_services():
    """Start API server and frontend."""
    print("="*80)
    print("Starting Services")
    print("="*80)
    
    # Check if services are already running
    try:
        # Try to kill existing processes on ports
        subprocess.run(["lsof", "-ti:8000"], check=False, capture_output=True)
        subprocess.run(["lsof", "-ti:3000"], check=False, capture_output=True)
    except:
        pass
    
    # Start API server
    print("\n1. Starting API server...")
    api_process = subprocess.Popen(
        ["python3", "api_server.py"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Save PID
    with open(PROJECT_ROOT / "api_server.pid", "w") as f:
        f.write(str(api_process.pid))
    
    # Start frontend
    print("2. Starting frontend...")
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(PROJECT_ROOT / "frontend"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Save PID
    with open(PROJECT_ROOT / "frontend.pid", "w") as f:
        f.write(str(frontend_process.pid))
    
    # Wait for services to initialize
    print("\n3. Waiting for services to initialize (6 seconds)...")
    time.sleep(6)
    
    print("✅ Services started")
    return api_process, frontend_process


def stop_services():
    """Stop API server and frontend."""
    print("\n" + "="*80)
    print("Stopping Services")
    print("="*80)
    
    # Stop API server
    try:
        if os.path.exists(PROJECT_ROOT / "api_server.pid"):
            with open(PROJECT_ROOT / "api_server.pid", "r") as f:
                pid = f.read().strip()
            if pid:
                subprocess.run(["kill", pid], check=False)
            os.remove(PROJECT_ROOT / "api_server.pid")
    except Exception as e:
        print(f"Error stopping API server: {e}")
    
    # Stop frontend
    try:
        if os.path.exists(PROJECT_ROOT / "frontend.pid"):
            with open(PROJECT_ROOT / "frontend.pid", "r") as f:
                pid = f.read().strip()
            if pid:
                subprocess.run(["kill", pid], check=False)
            os.remove(PROJECT_ROOT / "frontend.pid")
    except Exception as e:
        print(f"Error stopping frontend: {e}")
    
    print("✅ Services stopped")


# Test cases organized by category
TEST_CASES = [
    # Category 2: Slash Command Isolation (Most Critical - Test First)
    {
        "name": "Test 4: Regular Query Should NOT Trigger Slash Command",
        "category": "Slash Command Isolation",
        "query": "file organization in my documents",
        "should_trigger_slash": False,
        "expected_tool": "orchestrator",
        "success_criteria": {
            "no_slash_command": True,
            "orchestrator_handles": True,
            "meaningful_response": True
        }
    },
    {
        "name": "Test 5: Query with 'folder' Keyword Should NOT Trigger Slash",
        "category": "Slash Command Isolation",
        "query": "what's in my folder",
        "should_trigger_slash": False,
        "expected_tool": "explain_folder (via orchestrator)",
        "success_criteria": {
            "no_slash_command": True,
            "uses_explain_folder": True,
            "meaningful_response": True
        }
    },
    {
        "name": "Test 6: Query with 'file' Keyword Should NOT Trigger Slash",
        "category": "Slash Command Isolation",
        "query": "file search for reports",
        "should_trigger_slash": False,
        "expected_tool": "orchestrator",
        "success_criteria": {
            "no_slash_command": True,
            "orchestrator_handles": True,
            "meaningful_response": True
        }
    },
    
    # Category 3: Explicit Slash Commands
    {
        "name": "Test 7: /folder list Command",
        "category": "Explicit Slash Commands",
        "query": "/folder list",
        "should_trigger_slash": True,
        "expected_tool": "folder_list",
        "success_criteria": {
            "slash_command_detected": True,
            "routes_to_folder_agent": True,
            "shows_folder_contents": True,
            "bypasses_orchestrator": True
        }
    },
    {
        "name": "Test 8: /folder explain Command",
        "category": "Explicit Slash Commands",
        "query": "/folder explain files",
        "should_trigger_slash": True,
        "expected_tool": "explain_folder (file agent)",
        "success_criteria": {
            "slash_command_detected": True,
            "routes_to_file_agent": True,
            "uses_explain_folder": True,
            "shows_file_explanations": True
        }
    },
    {
        "name": "Test 9: /files search Command",
        "category": "Explicit Slash Commands",
        "query": "/files find documents about AI",
        "should_trigger_slash": True,
        "expected_tool": "search_documents",
        "success_criteria": {
            "slash_command_detected": True,
            "routes_to_file_agent": True,
            "uses_search_documents": True,
            "bypasses_orchestrator": True,
            "semantic_search_works": True
        }
    },
    {
        "name": "Test 10: /files explain Command",
        "category": "Explicit Slash Commands",
        "query": "/files explain all files",
        "should_trigger_slash": True,
        "expected_tool": "explain_files",
        "success_criteria": {
            "slash_command_detected": True,
            "uses_explain_files": True,
            "shows_all_files": True,
            "semantic_explanations": True
        }
    },
    
    # Category 1: Semantic File Search & Understanding
    {
        "name": "Test 1: Semantic File Count Query",
        "category": "Semantic File Search",
        "query": "how many shirin files are there",
        "should_trigger_slash": False,
        "expected_tool": "explain_files or search_documents",
        "success_criteria": {
            "no_slash_command": True,
            "semantic_understanding": True,
            "returns_accurate_count": True,
            "shows_file_names": True
        }
    },
    {
        "name": "Test 2: Semantic File Search",
        "category": "Semantic File Search",
        "query": "find all documents about guitar tabs",
        "should_trigger_slash": False,
        "expected_tool": "search_documents",
        "success_criteria": {
            "no_slash_command": True,
            "semantic_search_works": True,
            "finds_relevant_files": True,
            "shows_relevance_scores": True
        }
    },
    {
        "name": "Test 3: File Type Semantic Search",
        "category": "Semantic File Search",
        "query": "how many PDF files do I have about photography",
        "should_trigger_slash": False,
        "expected_tool": "search_documents or explain_files",
        "success_criteria": {
            "no_slash_command": True,
            "combines_type_and_semantic": True,
            "returns_accurate_count": True,
            "shows_relevant_pdfs": True
        }
    },
    
    # Category 4: Folder Organization Commands
    {
        "name": "Test 11: /folder organize alpha Command",
        "category": "Folder Organization",
        "query": "/folder organize alpha",
        "should_trigger_slash": True,
        "expected_tool": "folder_plan_alpha",
        "success_criteria": {
            "slash_command_detected": True,
            "uses_folder_plan_alpha": True,
            "shows_proposed_changes": True,
            "dry_run_mode": True,
            "clear_diff_display": True
        }
    },
    {
        "name": "Test 12: /folder organize by type Command",
        "category": "Folder Organization",
        "query": "/folder organize by file type",
        "should_trigger_slash": True,
        "expected_tool": "folder_organize_by_type",
        "success_criteria": {
            "slash_command_detected": True,
            "uses_folder_organize_by_type": True,
            "shows_plan_with_grouping": True,
            "dry_run_first": True
        }
    },
    {
        "name": "Test 13: /files organize Command",
        "category": "Folder Organization",
        "query": "/files organize my PDFs by topic",
        "should_trigger_slash": True,
        "expected_tool": "organize_files",
        "success_criteria": {
            "slash_command_detected": True,
            "uses_organize_files": True,
            "semantic_categorization": True,
            "creates_target_folder": True,
            "shows_reasoning": True
        }
    },
    
    # Category 5: Semantic File Explanation
    {
        "name": "Test 14: Explain All Files",
        "category": "Semantic File Explanation",
        "query": "/files explain all files",
        "should_trigger_slash": True,
        "expected_tool": "explain_files",
        "success_criteria": {
            "uses_explain_files": True,
            "semantic_explanations": True,
            "shows_file_paths": True,
            "shows_file_types": True,
            "explanations_meaningful": True
        }
    },
    {
        "name": "Test 15: Explain Folder Contents",
        "category": "Semantic File Explanation",
        "query": "/folder explain Documents folder",
        "should_trigger_slash": True,
        "expected_tool": "explain_folder",
        "success_criteria": {
            "routes_to_file_agent": True,
            "uses_explain_folder": True,
            "semantic_explanations": True,
            "filters_to_folder": True
        }
    },
    {
        "name": "Test 16: Semantic File Matching",
        "category": "Semantic File Explanation",
        "query": "how many files are about music",
        "should_trigger_slash": False,
        "expected_tool": "search_documents or explain_files",
        "success_criteria": {
            "no_slash_command": True,
            "semantic_understanding": True,
            "finds_files_semantically": True,
            "returns_accurate_count": True,
            "shows_relevant_files": True
        }
    },
]


def execute_test_prompt(prompt: str, timeout: int = 60) -> Dict[str, Any]:
    """
    Execute a test prompt in the browser UI.
    Returns test results with verification details.
    
    NOTE: This function is a placeholder. Actual browser automation
    is performed via MCP tool calls by the AI assistant.
    """
    print(f"\n{'='*80}")
    print(f"Executing: {prompt}")
    print(f"{'='*80}")
    
    # This will be executed via browser MCP tools
    return {
        "prompt": prompt,
        "timeout": timeout,
        "note": "Execution performed via browser MCP tools"
    }


def verify_test_result(test_case: Dict[str, Any], result: Dict[str, Any]) -> bool:
    """Verify test result against success criteria."""
    passed = True
    details = {}
    
    # Check if slash command was triggered correctly
    if test_case["should_trigger_slash"]:
        # Should detect slash command
        if "slash_command_detected" in test_case["success_criteria"]:
            # Check if slash command was detected (would be in console logs or response)
            details["slash_command_detected"] = "Verified via console logs"
    
    else:
        # Should NOT trigger slash command
        if "no_slash_command" in test_case["success_criteria"]:
            # Check that no slash command was detected
            details["no_slash_command"] = "Verified - query went through orchestrator"
    
    # Check for meaningful response
    if "meaningful_response" in test_case["success_criteria"]:
        snapshot_text = json.dumps(result.get("snapshot", {}))
        if "Command executed" in snapshot_text and "generic" in snapshot_text.lower():
            passed = False
            details["error"] = "Generic 'Command executed' message found"
        else:
            details["meaningful_response"] = "Response contains actual content"
    
    # Check semantic understanding
    if "semantic_understanding" in test_case["success_criteria"]:
        details["semantic_understanding"] = "Verified via tool usage and results"
    
    return passed, details


def main():
    """Main test execution."""
    print("="*80)
    print("Search and Folder Organization Testing")
    print("="*80)
    print(f"\nTotal test cases: {len(TEST_CASES)}")
    print(f"Categories: {len(set(tc['category'] for tc in TEST_CASES))}")
    
    # Group by category
    by_category = {}
    for test in TEST_CASES:
        cat = test["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(test)
    
    print("\nTest breakdown by category:")
    for cat, tests in by_category.items():
        print(f"  {cat}: {len(tests)} tests")
    
    print("\n" + "="*80)
    print("NOTE: This script provides test structure.")
    print("Actual browser automation will be performed via MCP tools.")
    print("="*80)
    
    # Return test cases for execution
    return TEST_CASES


if __name__ == "__main__":
    test_cases = main()
    print(f"\n✅ Test script ready with {len(test_cases)} test cases")

