#!/usr/bin/env python3
"""
Test script for the Branch Watcher Service (Oqoqo API Docs Self-Evolution).

This script tests the full flow without requiring the UI:
1. Check watcher status
2. List pending drift reports
3. Trigger a branch check manually
4. Simulate user approval
5. Verify spec update

Usage:
    python scripts/test_branch_watcher.py --status        # Check watcher status
    python scripts/test_branch_watcher.py --pending       # List pending reports
    python scripts/test_branch_watcher.py --check <branch> # Check a specific branch
    python scripts/test_branch_watcher.py --approve       # Approve pending drift fix
    python scripts/test_branch_watcher.py --reject        # Reject pending drift fix
    python scripts/test_branch_watcher.py --full          # Run full flow test
    
Environment Variables:
    GITHUB_TOKEN - GitHub personal access token
    GITHUB_REPO_OWNER - Repository owner (default: tiangolo)
    GITHUB_REPO_NAME - Repository name (default: fastapi)
"""

import argparse
import asyncio
import json
import sys
import os
from datetime import datetime

import httpx
import websockets

# API base URL
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
WS_URL = os.getenv("WS_URL", "ws://localhost:8000/ws/chat")

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{Colors.HEADER}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{title}{Colors.END}")
    print(f"{Colors.HEADER}{'='*60}{Colors.END}\n")


def print_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")


def print_error(msg: str):
    print(f"{Colors.FAIL}✗ {msg}{Colors.END}")


def print_info(msg: str):
    print(f"{Colors.CYAN}ℹ {msg}{Colors.END}")


def print_warning(msg: str):
    print(f"{Colors.WARNING}⚠ {msg}{Colors.END}")


async def check_api_health() -> bool:
    """Check if the API server is running."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE}/health", timeout=5.0)
            if response.status_code == 200:
                print_success("API server is running")
                return True
            else:
                print_error(f"API server returned {response.status_code}")
                return False
    except Exception as e:
        print_error(f"Cannot connect to API server: {e}")
        return False


async def get_watcher_status():
    """Get the branch watcher service status."""
    print_header("Branch Watcher Status")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/api/apidocs/watcher/status")
        
        if response.status_code != 200:
            print_error(f"Failed to get status: {response.status_code}")
            print(response.text)
            return
        
        status = response.json()
        
        print(f"  Running: {Colors.GREEN if status['running'] else Colors.FAIL}{status['running']}{Colors.END}")
        print(f"  Poll Interval: {status['poll_interval']}s")
        print(f"  Watched Branches: {status['watched_branches']}")
        print(f"  Pending Reports: {status['pending_reports']}")
        
        if status['pending_branches']:
            print(f"\n  Pending Branches:")
            for branch in status['pending_branches']:
                print(f"    - {branch}")


async def get_pending_reports():
    """Get all pending drift reports."""
    print_header("Pending Drift Reports")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/api/apidocs/watcher/pending")
        
        if response.status_code != 200:
            print_error(f"Failed to get pending reports: {response.status_code}")
            print(response.text)
            return
        
        data = response.json()
        
        if data['pending_count'] == 0:
            print_info("No pending drift reports")
            return
        
        print(f"  Found {data['pending_count']} pending report(s):\n")
        
        for report in data['reports']:
            print(f"  {Colors.BOLD}Branch: {report['branch']}{Colors.END}")
            print(f"    Has Drift: {report['has_drift']}")
            print(f"    Changes: {report['change_count']} ({report['breaking_changes']} breaking)")
            print(f"    Detected: {report['detected_at']}")
            print(f"    Has Proposed Spec: {report['has_proposed_spec']}")
            print(f"\n    Summary:\n    {report['summary'][:200]}...")
            print()


async def check_branch(branch_name: str):
    """Manually check a branch for drift."""
    print_header(f"Checking Branch: {branch_name}")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        print_info(f"Sending request to check branch '{branch_name}'...")
        
        response = await client.post(
            f"{API_BASE}/api/apidocs/check-branch",
            json={"branch_name": branch_name, "include_proposed_spec": True}
        )
        
        if response.status_code != 200:
            print_error(f"Failed to check branch: {response.status_code}")
            print(response.text)
            return
        
        result = response.json()
        
        print(f"\n  {Colors.BOLD}Results:{Colors.END}")
        print(f"    Branch: {result.get('branch')}")
        print(f"    Base Branch: {result.get('base_branch')}")
        print(f"    Has API Changes: {result.get('has_api_changes')}")
        print(f"    Has Drift: {result.get('has_drift')}")
        
        if result.get('has_drift'):
            print(f"    Change Count: {result.get('change_count')}")
            print(f"    Breaking Changes: {result.get('breaking_changes')}")
            print(f"\n    Summary:\n    {result.get('summary', 'N/A')}")
            
            if result.get('proposed_spec'):
                print_success("Proposed spec update generated")
        else:
            print_info("No drift detected")


async def approve_drift(branch: str = None):
    """Approve a pending drift fix."""
    print_header("Approving Drift Fix")
    
    async with httpx.AsyncClient() as client:
        payload = {"approved": True}
        if branch:
            payload["branch"] = branch
        
        print_info(f"Sending approval request{f' for branch {branch}' if branch else ''}...")
        
        response = await client.post(
            f"{API_BASE}/api/apidocs/watcher/approve",
            json=payload
        )
        
        if response.status_code == 404:
            print_warning("No pending drift report found")
            return
        
        if response.status_code != 200:
            print_error(f"Failed to approve: {response.status_code}")
            print(response.text)
            return
        
        result = response.json()
        
        if result.get('success'):
            print_success(result.get('message'))
            print(f"\n  {Colors.BOLD}Updated Files:{Colors.END}")
            print(f"    Spec Path: {result.get('spec_path')}")
            print(f"    Backup Path: {result.get('backup_path')}")
            print(f"\n  {Colors.BOLD}View Updated Docs:{Colors.END}")
            print(f"    Swagger UI: {result.get('swagger_url')}")
            print(f"    ReDoc: {result.get('redoc_url')}")
        else:
            print_error(result.get('message', 'Unknown error'))


async def reject_drift(branch: str = None):
    """Reject a pending drift fix."""
    print_header("Rejecting Drift Fix")
    
    async with httpx.AsyncClient() as client:
        payload = {"approved": False}
        if branch:
            payload["branch"] = branch
        
        print_info(f"Sending rejection request{f' for branch {branch}' if branch else ''}...")
        
        response = await client.post(
            f"{API_BASE}/api/apidocs/watcher/approve",
            json=payload
        )
        
        if response.status_code == 404:
            print_warning("No pending drift report found")
            return
        
        if response.status_code != 200:
            print_error(f"Failed to reject: {response.status_code}")
            print(response.text)
            return
        
        result = response.json()
        
        if result.get('success'):
            print_success(result.get('message'))
        else:
            print_error(result.get('message', 'Unknown error'))


async def listen_for_websocket_messages(duration: int = 30):
    """Listen for WebSocket messages to see drift notifications."""
    print_header(f"Listening for WebSocket Messages ({duration}s)")
    
    try:
        async with websockets.connect(WS_URL) as ws:
            print_success("Connected to WebSocket")
            print_info("Waiting for messages...")
            
            try:
                while True:
                    message = await asyncio.wait_for(ws.recv(), timeout=duration)
                    data = json.loads(message)
                    
                    msg_type = data.get('type', 'unknown')
                    timestamp = data.get('timestamp', datetime.now().isoformat())
                    
                    print(f"\n  [{timestamp}] {Colors.BOLD}Type: {msg_type}{Colors.END}")
                    
                    if msg_type == 'apidocs_drift':
                        print_warning("API DOCS DRIFT DETECTED!")
                        drift_data = data.get('apidocs_drift', {})
                        print(f"    Branch: {drift_data.get('branch', 'N/A')}")
                        print(f"    Changes: {drift_data.get('change_count', 0)}")
                        print(f"    Breaking: {drift_data.get('breaking_changes', 0)}")
                        print(f"    Message: {data.get('message', 'N/A')[:200]}...")
                    elif msg_type == 'apidocs_sync':
                        print_success("API DOCS SYNCED!")
                        sync_data = data.get('apidocs_sync', {})
                        print(f"    Branch: {sync_data.get('branch', 'N/A')}")
                        print(f"    Swagger: {sync_data.get('swagger_url', 'N/A')}")
                    else:
                        print(f"    Message: {data.get('message', 'N/A')[:100]}...")
                        
            except asyncio.TimeoutError:
                print_info(f"No messages received in {duration}s")
                
    except Exception as e:
        print_error(f"WebSocket error: {e}")


async def run_full_test(branch_name: str = None):
    """Run the full flow test."""
    print_header("Full Flow Test - Oqoqo API Docs Self-Evolution")
    
    # Step 1: Check API health
    if not await check_api_health():
        print_error("API server not running. Start it with: python api_server.py")
        return
    
    # Step 2: Check watcher status
    await get_watcher_status()
    
    # Step 3: Check for pending reports
    await get_pending_reports()
    
    # Step 4: If a branch is specified, check it
    if branch_name:
        await check_branch(branch_name)
        
        # Wait a moment for the report to be processed
        print_info("Waiting for drift report to be processed...")
        await asyncio.sleep(2)
        
        # Check pending again
        await get_pending_reports()
    
    print_header("Test Complete")
    print(f"""
{Colors.BOLD}Next Steps:{Colors.END}

1. If drift was detected, approve it:
   python scripts/test_branch_watcher.py --approve

2. Or reject it:
   python scripts/test_branch_watcher.py --reject

3. Listen for real-time notifications:
   python scripts/test_branch_watcher.py --listen

4. View updated docs (after approval):
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc
""")


async def main():
    parser = argparse.ArgumentParser(
        description="Test the Branch Watcher Service for API Docs Self-Evolution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --status                    Check watcher service status
  %(prog)s --pending                   List pending drift reports
  %(prog)s --check feature-branch      Check a specific branch for drift
  %(prog)s --approve                   Approve the most recent drift fix
  %(prog)s --approve --branch xyz      Approve drift fix for specific branch
  %(prog)s --reject                    Reject the most recent drift fix
  %(prog)s --listen                    Listen for WebSocket notifications
  %(prog)s --full                      Run full flow test
  %(prog)s --full --branch feature-x   Run full test with specific branch
        """
    )
    
    parser.add_argument('--status', action='store_true', help='Check watcher status')
    parser.add_argument('--pending', action='store_true', help='List pending drift reports')
    parser.add_argument('--check', type=str, metavar='BRANCH', help='Check a specific branch for drift')
    parser.add_argument('--approve', action='store_true', help='Approve pending drift fix')
    parser.add_argument('--reject', action='store_true', help='Reject pending drift fix')
    parser.add_argument('--branch', type=str, help='Specify branch for approve/reject')
    parser.add_argument('--listen', action='store_true', help='Listen for WebSocket messages')
    parser.add_argument('--listen-duration', type=int, default=60, help='Duration to listen (seconds)')
    parser.add_argument('--full', action='store_true', help='Run full flow test')
    
    args = parser.parse_args()
    
    # Check API health first
    if not await check_api_health():
        print_error("API server not running. Start it with: python api_server.py")
        sys.exit(1)
    
    if args.status:
        await get_watcher_status()
    elif args.pending:
        await get_pending_reports()
    elif args.check:
        await check_branch(args.check)
    elif args.approve:
        await approve_drift(args.branch)
    elif args.reject:
        await reject_drift(args.branch)
    elif args.listen:
        await listen_for_websocket_messages(args.listen_duration)
    elif args.full:
        await run_full_test(args.branch)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())

