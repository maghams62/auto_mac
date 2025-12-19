#!/usr/bin/env python3
"""
Test script for the Oqoqo self-evolving API documentation feature.

Tests the full flow:
1. Check if a GitHub branch has changes to the monitored file (api_server.py)
2. If changes detected, compare against docs/api-spec.yaml
3. Report drift and proposed updates
4. Optionally apply the updates

Usage:
    # Test with a specific branch
    python scripts/test_apidocs_branch.py --branch feature-xyz
    
    # Test the local drift check (no branch)
    python scripts/test_apidocs_branch.py --local
    
    # Apply proposed changes after review
    python scripts/test_apidocs_branch.py --branch feature-xyz --apply
    
    # List available branches
    python scripts/test_apidocs_branch.py --list-branches

Environment variables:
    GITHUB_TOKEN - GitHub personal access token (required for private repos)
    GITHUB_REPO_OWNER - Repository owner (default: maghams62)
    GITHUB_REPO_NAME - Repository name (default: auto_mac)
    GITHUB_MONITORED_FILE - File to monitor (default: api_server.py)
    GITHUB_BASE_BRANCH - Base branch to compare against (default: main)
"""

import argparse
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

API_BASE = "http://localhost:8000"


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_section(text: str):
    """Print a section header."""
    print(f"\n--- {text} ---")


def test_health():
    """Test if the API server is running."""
    print_section("Testing API Server Health")
    try:
        response = httpx.get(f"{API_BASE}/health", timeout=5.0)
        if response.status_code == 200:
            print("✅ API server is running")
            return True
        else:
            print(f"❌ API server returned status {response.status_code}")
            return False
    except httpx.ConnectError:
        print("❌ Cannot connect to API server at localhost:8000")
        print("   Start the server with: python api_server.py")
        return False


def test_local_drift():
    """Test local drift detection (no branch comparison)."""
    print_section("Testing Local Drift Detection")
    
    try:
        response = httpx.post(
            f"{API_BASE}/api/apidocs/check-drift",
            json={"include_proposed_spec": True},
            timeout=120.0
        )
        response.raise_for_status()
        result = response.json()
        
        print(f"Has drift: {result.get('has_drift', False)}")
        print(f"Change count: {result.get('change_count', 0)}")
        print(f"Breaking changes: {result.get('breaking_changes', 0)}")
        
        if result.get('summary'):
            print(f"\nSummary:\n{result['summary'][:500]}...")
        
        if result.get('proposed_spec'):
            print(f"\n✅ Proposed spec generated ({len(result['proposed_spec'])} bytes)")
        
        return result
        
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP error: {e.response.status_code}")
        print(f"   {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_branch_check(branch_name: str):
    """Test branch-based drift detection."""
    print_section(f"Testing Branch Drift Detection: {branch_name}")
    
    try:
        response = httpx.post(
            f"{API_BASE}/api/apidocs/check-branch",
            json={"branch_name": branch_name, "include_proposed_spec": True},
            timeout=120.0
        )
        response.raise_for_status()
        result = response.json()
        
        print(f"Branch: {result.get('branch', branch_name)}")
        print(f"Base branch: {result.get('base_branch', 'main')}")
        print(f"Has API changes: {result.get('has_api_changes', False)}")
        print(f"Monitored file: {result.get('monitored_file', 'api_server.py')}")
        
        if result.get('has_api_changes'):
            print(f"Total files changed: {result.get('total_files_changed', 0)}")
            print(f"Ahead by commits: {result.get('ahead_by', 0)}")
            print(f"\nHas drift: {result.get('has_drift', False)}")
            print(f"Change count: {result.get('change_count', 0)}")
            print(f"Breaking changes: {result.get('breaking_changes', 0)}")
            
            if result.get('summary'):
                print(f"\nSummary:\n{result['summary'][:500]}...")
            
            if result.get('proposed_spec'):
                print(f"\n✅ Proposed spec generated ({len(result['proposed_spec'])} bytes)")
        else:
            print(f"\n✅ No changes to monitored file in this branch")
        
        return result
        
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP error: {e.response.status_code}")
        try:
            error_detail = e.response.json()
            print(f"   Detail: {error_detail.get('detail', e.response.text[:200])}")
        except:
            print(f"   {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def apply_spec_update(proposed_spec: str):
    """Apply a proposed spec update."""
    print_section("Applying Spec Update")
    
    try:
        response = httpx.post(
            f"{API_BASE}/api/apidocs/apply",
            json={"proposed_spec": proposed_spec, "create_backup": True},
            timeout=30.0
        )
        response.raise_for_status()
        result = response.json()
        
        if result.get('success'):
            print("✅ Spec updated successfully!")
            if result.get('backup_path'):
                print(f"   Backup created at: {result['backup_path']}")
            return True
        else:
            print(f"❌ Failed to apply update: {result.get('error', 'Unknown error')}")
            return False
            
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP error: {e.response.status_code}")
        print(f"   {e.response.text[:200]}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def list_branches():
    """List available branches from the GitHub repo."""
    print_section("Listing Available Branches")
    
    # Import the service directly to list branches
    try:
        from src.services.github_pr_service import get_github_pr_service
        
        service = get_github_pr_service()
        branches = service.list_branches()
        
        print(f"Found {len(branches)} branches:")
        for branch in branches:
            marker = " (base)" if branch == service.base_branch else ""
            print(f"  - {branch}{marker}")
        
        return branches
        
    except Exception as e:
        print(f"❌ Error listing branches: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(
        description="Test the Oqoqo self-evolving API documentation feature",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--branch", "-b",
        help="GitHub branch name to check for API drift"
    )
    parser.add_argument(
        "--local", "-l",
        action="store_true",
        help="Test local drift detection (no branch comparison)"
    )
    parser.add_argument(
        "--apply", "-a",
        action="store_true",
        help="Apply proposed spec changes (requires --branch or --local)"
    )
    parser.add_argument(
        "--list-branches",
        action="store_true",
        help="List available branches from the GitHub repo"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    
    args = parser.parse_args()
    
    print_header("Oqoqo API Docs Self-Evolution Test")
    
    # Check API server health first
    if not args.list_branches:
        if not test_health():
            sys.exit(1)
    
    result = None
    
    if args.list_branches:
        branches = list_branches()
        if args.json:
            print(json.dumps({"branches": branches}, indent=2))
        sys.exit(0 if branches else 1)
    
    elif args.branch:
        result = test_branch_check(args.branch)
        
    elif args.local:
        result = test_local_drift()
        
    else:
        # Default: run local drift check
        print("\nNo branch specified, running local drift check...")
        print("Use --branch <name> to check a specific branch")
        print("Use --list-branches to see available branches\n")
        result = test_local_drift()
    
    if args.json and result:
        print("\n" + json.dumps(result, indent=2))
    
    # Apply if requested and drift was found
    if args.apply and result:
        proposed_spec = result.get('proposed_spec')
        if proposed_spec:
            print("\n" + "=" * 60)
            confirm = input("Apply the proposed spec update? [y/N]: ")
            if confirm.lower() == 'y':
                apply_spec_update(proposed_spec)
            else:
                print("Update cancelled.")
        else:
            print("\nNo proposed spec to apply (no drift detected or error occurred)")
    
    print_header("Test Complete")
    
    # Exit with appropriate code
    if result is None:
        sys.exit(1)
    elif result.get('has_drift') or result.get('has_api_changes'):
        sys.exit(0)  # Success - drift detected
    else:
        sys.exit(0)  # Success - no drift


if __name__ == "__main__":
    main()

