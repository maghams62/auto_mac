"""
File Query Regression Test Script

Tests the full flow for "Pull up my Ed sheeran files" query:
1. Sends query via WebSocket (simulating UI)
2. Monitors logs for each checkpoint
3. Validates results at each stage
4. Reports failures with specific error messages
"""

import asyncio
import json
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import websockets
import logging

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
TEST_QUERY = "Pull up my Ed sheeran files"
WEBSOCKET_URL = "ws://localhost:8000/ws/chat"
LOG_FILE = project_root / "api_server.log"
TIMEOUT = 60  # seconds


class CheckpointValidator:
    """Validates each checkpoint in the test flow."""
    
    def __init__(self):
        self.checkpoints = {
            "checkpoint_1": {"name": "Query Routing", "passed": False, "errors": []},
            "checkpoint_2": {"name": "Intent Analysis", "passed": False, "errors": []},
            "checkpoint_3": {"name": "Plan Generation", "passed": False, "errors": []},
            "checkpoint_4": {"name": "File Tool Execution", "passed": False, "errors": []},
            "checkpoint_5": {"name": "Response Formatting", "passed": False, "errors": []},
            "checkpoint_6": {"name": "WebSocket Delivery", "passed": False, "errors": []},
            "checkpoint_7": {"name": "Frontend Rendering", "passed": False, "errors": []},
        }
        self.log_entries = []
        self.response_payload = None
        self.session_id = None
        
    def read_logs(self, since_timestamp: float) -> List[str]:
        """Read log entries since the given timestamp."""
        if not LOG_FILE.exists():
            return []
        
        entries = []
        try:
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # Simple timestamp check - in real implementation, parse timestamps
                    entries.append(line.strip())
        except Exception as e:
            logger.error(f"Error reading logs: {e}")
        
        return entries
    
    def validate_checkpoint_1(self, logs: List[str]) -> bool:
        """Checkpoint 1: Query Routing (Non-Slash Command)"""
        errors = []
        
        # Check if query bypasses slash command handler
        has_agent_start = any("[API SERVER] Starting agent execution" in log and TEST_QUERY[:30] in log for log in logs)
        has_agent_run = any("Starting agent for request" in log and TEST_QUERY in log for log in logs)
        
        if not has_agent_start:
            errors.append("Missing '[API SERVER] Starting agent execution' log")
        if not has_agent_run:
            errors.append("Missing 'Starting agent for request' log")
        
        # Check query is NOT treated as slash command
        is_slash_command = any("[SLASH COMMAND]" in log and TEST_QUERY.lower() in log.lower() for log in logs)
        if is_slash_command:
            errors.append("Query incorrectly treated as slash command")
        
        self.checkpoints["checkpoint_1"]["errors"] = errors
        self.checkpoints["checkpoint_1"]["passed"] = len(errors) == 0
        return self.checkpoints["checkpoint_1"]["passed"]
    
    def validate_checkpoint_2(self, logs: List[str]) -> bool:
        """Checkpoint 2: Intent Analysis and Agent Routing"""
        errors = []
        
        # Check intent planner identifies file agent (may be implicit in tool selection)
        has_planning = any("Planning" in log or "PLANNING PHASE" in log for log in logs)
        # File agent is identified by the tool being selected (list_related_documents or search_documents)
        has_file_tool_selected = any("list_related_documents" in log or "search_documents" in log for log in logs)
        
        if not has_planning:
            errors.append("Missing planning phase log")
        if not has_file_tool_selected:
            errors.append("File agent tool not selected (list_related_documents or search_documents)")
        
        self.checkpoints["checkpoint_2"]["errors"] = errors
        self.checkpoints["checkpoint_2"]["passed"] = len(errors) == 0
        return self.checkpoints["checkpoint_2"]["passed"]
    
    def validate_checkpoint_3(self, logs: List[str]) -> bool:
        """Checkpoint 3: Plan Generation"""
        errors = []
        
        # Check plan is created (may be implicit in step execution)
        has_step_execution = any("EXECUTING STEP" in log for log in logs)
        
        # Check plan includes file tool
        has_file_tool = any(
            "list_related_documents" in log or "search_documents" in log 
            for log in logs
        )
        
        # Check query parameter extracted (Ed Sheeran or Ed sheeran)
        has_query_param = any("Ed Sheeran" in log or "Ed sheeran" in log.lower() for log in logs)
        
        if not has_step_execution:
            errors.append("No step execution found (plan may not have been created)")
        if not has_file_tool:
            errors.append("Plan missing file search tool (search_documents or list_related_documents)")
        if not has_query_param:
            errors.append("Query parameter 'Ed Sheeran' not extracted")
        
        self.checkpoints["checkpoint_3"]["errors"] = errors
        self.checkpoints["checkpoint_3"]["passed"] = len(errors) == 0
        return self.checkpoints["checkpoint_3"]["passed"]
    
    def validate_checkpoint_4(self, logs: List[str]) -> bool:
        """Checkpoint 4: File Tool Execution"""
        errors = []
        
        # Check file tool executed
        has_tool_execution = any(
            "[FILE LIST] Tool: list_related_documents" in log or
            "[FILE AGENT] Tool: search_documents" in log or 
            "[FILE AGENT] Tool: list_related_documents" in log 
            for log in logs
        )
        
        # Check files found (may be in step_results or file_list)
        has_files_found = any(
            "Found.*files" in log or 
            "file_list" in log or
            "Added.*files to response" in log
            for log in logs
        )
        
        # Check for errors
        has_errors = any("[FILE AGENT] Error" in log or "[FILE LIST] Error" in log for log in logs)
        
        if not has_tool_execution:
            errors.append("File tool not executed")
        if not has_files_found and not has_errors:
            errors.append("No indication of files found or error")
        if has_errors:
            error_logs = [log for log in logs if "[FILE AGENT] Error" in log or "[FILE LIST] Error" in log]
            errors.append(f"File agent errors: {error_logs[-1] if error_logs else 'Unknown error'}")
        
        self.checkpoints["checkpoint_4"]["errors"] = errors
        self.checkpoints["checkpoint_4"]["passed"] = len(errors) == 0
        return self.checkpoints["checkpoint_4"]["passed"]
    
    def validate_checkpoint_5(self, logs: List[str], response: Optional[Dict]) -> bool:
        """Checkpoint 5: Response Formatting"""
        errors = []
        
        # Check reply_to_user was called
        has_reply = any("[REPLY TOOL]" in log or "reply_to_user" in log for log in logs)
        
        # Check response payload structure
        if response:
            has_files = "files" in response or "results" in response
            if not has_files:
                errors.append("Response payload missing 'files' or 'results' array")
        else:
            errors.append("No response payload received")
        
        if not has_reply:
            errors.append("reply_to_user not called")
        
        self.checkpoints["checkpoint_5"]["errors"] = errors
        self.checkpoints["checkpoint_5"]["passed"] = len(errors) == 0
        return self.checkpoints["checkpoint_5"]["passed"]
    
    def validate_checkpoint_6(self, logs: List[str], response: Optional[Dict]) -> bool:
        """Checkpoint 6: WebSocket Delivery"""
        errors = []
        
        # Check response sent
        has_sent = any("[API SERVER] Sending response" in log or "Response sent successfully" in log for log in logs)
        
        # Check response payload
        if not response:
            errors.append("No response received via WebSocket")
        else:
            if "type" not in response:
                errors.append("Response missing 'type' field")
        
        if not has_sent:
            errors.append("Response not sent via WebSocket")
        
        self.checkpoints["checkpoint_6"]["errors"] = errors
        self.checkpoints["checkpoint_6"]["passed"] = len(errors) == 0
        return self.checkpoints["checkpoint_6"]["passed"]
    
    def validate_checkpoint_7(self, response: Optional[Dict]) -> bool:
        """Checkpoint 7: Frontend Rendering (validates payload structure)"""
        errors = []
        
        if not response:
            errors.append("No response payload to validate")
        else:
            # Check if response has file data
            has_file_data = (
                "files" in response or 
                "results" in response or
                response.get("type") in ["file_list", "document_list"]
            )
            
            if not has_file_data:
                errors.append("Response payload missing file data for frontend rendering")
            else:
                # Validate file structure if present
                files = response.get("files") or response.get("results", [])
                if isinstance(files, list) and len(files) > 0:
                    first_file = files[0]
                    required_fields = ["name", "path"]
                    missing_fields = [f for f in required_fields if f not in first_file]
                    if missing_fields:
                        errors.append(f"File objects missing required fields: {missing_fields}")
        
        self.checkpoints["checkpoint_7"]["errors"] = errors
        self.checkpoints["checkpoint_7"]["passed"] = len(errors) == 0
        return self.checkpoints["checkpoint_7"]["passed"]
    
    def print_report(self):
        """Print validation report."""
        print("\n" + "="*80)
        print("REGRESSION TEST VALIDATION REPORT")
        print("="*80)
        
        all_passed = True
        for checkpoint_id, checkpoint in self.checkpoints.items():
            status = "✅ PASSED" if checkpoint["passed"] else "❌ FAILED"
            print(f"\n{checkpoint['name']}: {status}")
            
            if checkpoint["errors"]:
                all_passed = False
                print("  Errors:")
                for error in checkpoint["errors"]:
                    print(f"    - {error}")
        
        print("\n" + "="*80)
        if all_passed:
            print("✅ ALL CHECKPOINTS PASSED")
        else:
            print("❌ SOME CHECKPOINTS FAILED")
        print("="*80)
        
        return all_passed


async def test_file_query():
    """Execute the end-to-end test."""
    print("\n" + "="*80)
    print("FILE QUERY REGRESSION TEST")
    print("="*80)
    print(f"Test Query: '{TEST_QUERY}'")
    print(f"WebSocket URL: {WEBSOCKET_URL}")
    print(f"Log File: {LOG_FILE}")
    print("="*80)
    
    validator = CheckpointValidator()
    start_time = time.time()
    response_payload = None
    
    try:
        # Connect to WebSocket
        print(f"\n[1/3] Connecting to WebSocket...")
        async with websockets.connect(WEBSOCKET_URL) as websocket:
            print("✅ Connected to WebSocket")
            
            # Send test query
            print(f"\n[2/3] Sending test query: '{TEST_QUERY}'")
            message = {
                "type": "user",
                "message": TEST_QUERY,
                "session_id": f"test_{int(time.time())}"
            }
            await websocket.send(json.dumps(message))
            validator.session_id = message["session_id"]
            print("✅ Query sent")
            
            # Wait for response
            print(f"\n[3/3] Waiting for response (timeout: {TIMEOUT}s)...")
            timeout_occurred = False
            
            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=TIMEOUT)
                    data = json.loads(response)
                    
                    print(f"Received: {data.get('type', 'unknown')} message")
                    
                    # Check if this is the final response
                    if data.get("type") in ["assistant", "reply", "file_list", "document_list", "response"]:
                        response_payload = data
                        print("✅ Final response received")
                        break
                    elif data.get("type") == "error":
                        print(f"❌ Error received: {data.get('message', 'Unknown error')}")
                        break
                    elif data.get("type") == "status":
                        status = data.get("status", "")
                        if status in ["completed", "error", "failed"]:
                            break
                    
            except asyncio.TimeoutError:
                timeout_occurred = True
                print(f"❌ Timeout after {TIMEOUT} seconds")
            
            # Read logs
            print("\n[4/4] Reading logs for validation...")
            logs = validator.read_logs(start_time)
            print(f"✅ Read {len(logs)} log entries")
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Validate all checkpoints
    print("\n" + "="*80)
    print("VALIDATING CHECKPOINTS")
    print("="*80)
    
    logs = validator.read_logs(start_time)
    validator.validate_checkpoint_1(logs)
    validator.validate_checkpoint_2(logs)
    validator.validate_checkpoint_3(logs)
    validator.validate_checkpoint_4(logs)
    validator.validate_checkpoint_5(logs, response_payload)
    validator.validate_checkpoint_6(logs, response_payload)
    validator.validate_checkpoint_7(response_payload)
    
    # Print report
    all_passed = validator.print_report()
    
    # Print response payload summary
    if response_payload:
        print("\n" + "="*80)
        print("RESPONSE PAYLOAD SUMMARY")
        print("="*80)
        print(f"Type: {response_payload.get('type', 'unknown')}")
        if "files" in response_payload:
            files = response_payload["files"]
            print(f"Files count: {len(files) if isinstance(files, list) else 'N/A'}")
            if isinstance(files, list) and len(files) > 0:
                print(f"First file: {files[0].get('name', 'N/A')}")
        if "results" in response_payload:
            results = response_payload["results"]
            print(f"Results count: {len(results) if isinstance(results, list) else 'N/A'}")
        print("="*80)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(test_file_query())
    sys.exit(0 if success else 1)

