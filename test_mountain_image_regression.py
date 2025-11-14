"""
Mountain Image Semantic Search Regression Test

Tests the full flow for "pull up the picture of a mountain" query:
1. Sends query via WebSocket (simulating UI)
2. Monitors logs for LLM reasoning checkpoints
3. Validates semantic search (not filename matching)
4. Validates similarity scores are meaningful
5. Validates results structure for UI display
6. Reports failures with specific error messages
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
TEST_QUERY = "pull up the picture of a mountain"
WEBSOCKET_URL = "ws://localhost:8000/ws/chat"
LOG_FILE = project_root / "api_server.log"
TIMEOUT = 90  # seconds (longer for LLM calls)


class MountainImageCheckpointValidator:
    """Validates each checkpoint in the mountain image search test flow."""
    
    def __init__(self):
        self.checkpoints = {
            "checkpoint_1": {"name": "Query Routing", "passed": False, "errors": []},
            "checkpoint_2": {"name": "File Agent Selection", "passed": False, "errors": []},
            "checkpoint_3": {"name": "LLM Query Enhancement", "passed": False, "errors": []},
            "checkpoint_4": {"name": "Image Search Execution", "passed": False, "errors": []},
            "checkpoint_5": {"name": "Semantic Matching (Not Filename)", "passed": False, "errors": []},
            "checkpoint_6": {"name": "Similarity Score Validation", "passed": False, "errors": []},
            "checkpoint_7": {"name": "Response Format", "passed": False, "errors": []},
            "checkpoint_8": {"name": "UI Display Fields", "passed": False, "errors": []},
        }
        self.log_entries = []
        self.response_payload = None
        self.session_id = None
        self.enhanced_query = None
        self.image_results = []
        
    def read_logs(self, since_timestamp: float) -> List[str]:
        """Read log entries since the given timestamp."""
        if not LOG_FILE.exists():
            return []
        
        entries = []
        try:
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
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
        """Checkpoint 2: File Agent Selection"""
        errors = []
        
        # Check file agent tool selected
        has_file_tool = any(
            "search_documents" in log or "list_related_documents" in log 
            for log in logs
        )
        
        # Check image search is enabled
        has_image_search = any(
            "[FILE AGENT] Searching images" in log or 
            "[FILE LIST] Searching images" in log or
            "include_images" in log.lower()
            for log in logs
        )
        
        if not has_file_tool:
            errors.append("File agent tool not selected (search_documents or list_related_documents)")
        if not has_image_search:
            errors.append("Image search not enabled or executed")
        
        self.checkpoints["checkpoint_2"]["errors"] = errors
        self.checkpoints["checkpoint_2"]["passed"] = len(errors) == 0
        return self.checkpoints["checkpoint_2"]["passed"]
    
    def validate_checkpoint_3(self, logs: List[str]) -> bool:
        """Checkpoint 3: LLM Query Enhancement"""
        errors = []
        
        # Check for query enhancement logs
        has_enhancement = any(
            "[IMAGE INDEXER] Query enhancement" in log or
            "Enhanced query" in log
            for log in logs
        )
        
        # Extract enhanced query if present
        for log in logs:
            if "[IMAGE INDEXER] Query enhancement" in log or "Enhanced query" in log:
                # Try to extract enhanced query from log
                if "→" in log:
                    parts = log.split("→")
                    if len(parts) > 1:
                        self.enhanced_query = parts[1].strip().strip("'\"")
        
        if not has_enhancement:
            errors.append("LLM query enhancement not executed (should see '[IMAGE INDEXER] Query enhancement' log)")
        
        # Check that enhanced query is different from original (shows LLM reasoning)
        if self.enhanced_query and self.enhanced_query.lower() == TEST_QUERY.lower():
            errors.append("Enhanced query is identical to original (LLM reasoning may not be working)")
        
        self.checkpoints["checkpoint_3"]["errors"] = errors
        self.checkpoints["checkpoint_3"]["passed"] = len(errors) == 0
        return self.checkpoints["checkpoint_3"]["passed"]
    
    def validate_checkpoint_4(self, logs: List[str]) -> bool:
        """Checkpoint 4: Image Search Execution"""
        errors = []
        
        # Check image search executed
        has_search = any(
            "[IMAGE INDEXER] Searching images for query" in log
            for log in logs
        )
        
        # Check semantic embedding generation
        has_embedding = any(
            "[IMAGE INDEXER] Generated query embedding" in log or
            "query embedding" in log.lower()
            for log in logs
        )
        
        # Check FAISS search
        has_faiss = any(
            "[IMAGE INDEXER] FAISS search returned" in log
            for log in logs
        )
        
        if not has_search:
            errors.append("Image search not executed")
        if not has_embedding:
            errors.append("Query embedding not generated (should use OpenAI embeddings, not hash)")
        if not has_faiss:
            errors.append("FAISS search not executed")
        
        self.checkpoints["checkpoint_4"]["errors"] = errors
        self.checkpoints["checkpoint_4"]["passed"] = len(errors) == 0
        return self.checkpoints["checkpoint_4"]["passed"]
    
    def validate_checkpoint_5(self, logs: List[str], response: Optional[Dict]) -> bool:
        """Checkpoint 5: Semantic Matching (Not Filename)"""
        errors = []
        
        # Extract image results from response
        if response:
            files = response.get("files", [])
            results = response.get("results", [])
            all_items = files if files else results
            
            image_items = [item for item in all_items if item.get("result_type") == "image"]
            self.image_results = image_items
            
            if not image_items:
                errors.append("No image results returned")
            else:
                # Check that results don't rely solely on filename matching
                # If all results have "mountain" in filename, that's suspicious
                filenames_with_mountain = [
                    item.get("name", "") or item.get("doc_title", "") or item.get("path", "")
                    for item in image_items
                ]
                all_have_mountain = all("mountain" in fname.lower() for fname in filenames_with_mountain if fname)
                
                if all_have_mountain and len(image_items) > 0:
                    errors.append(
                        "All results have 'mountain' in filename - may be using filename matching instead of semantic search"
                    )
                
                # Check for LLM-generated captions (shows semantic analysis)
                has_llm_captions = any(
                    "[IMAGE INDEXER] LLM-generated caption" in log
                    for log in logs
                )
                if not has_llm_captions:
                    errors.append("No LLM-generated captions found (may be using fallback filename-based captions)")
        else:
            errors.append("No response payload to validate")
        
        self.checkpoints["checkpoint_5"]["errors"] = errors
        self.checkpoints["checkpoint_5"]["passed"] = len(errors) == 0
        return self.checkpoints["checkpoint_5"]["passed"]
    
    def validate_checkpoint_6(self, logs: List[str], response: Optional[Dict]) -> bool:
        """Checkpoint 6: Similarity Score Validation"""
        errors = []
        
        if not self.image_results:
            errors.append("No image results to validate similarity scores")
        else:
            top_result = self.image_results[0]
            similarity = top_result.get("score") or top_result.get("similarity_score") or top_result.get("relevance_score", 0.0)
            
            # Similarity should be > 0.6 for good semantic match (not hash collision)
            if similarity < 0.6:
                errors.append(
                    f"Top result similarity score too low: {similarity:.4f} "
                    f"(expected > 0.6 for semantic match, may indicate hash-based matching)"
                )
            
            # Check that scores are logged
            has_score_logs = any(
                "similarity:" in log.lower() and "IMAGE INDEXER" in log
                for log in logs
            )
            if not has_score_logs:
                errors.append("Similarity scores not logged (should see '[IMAGE INDEXER] Result X: ... similarity: ...')")
            
            # Check that scores are meaningful (not all the same, which would indicate hash collision)
            if len(self.image_results) > 1:
                scores = [
                    item.get("score") or item.get("similarity_score") or item.get("relevance_score", 0.0)
                    for item in self.image_results
                ]
                if len(set(scores)) == 1 and len(scores) > 1:
                    errors.append("All similarity scores are identical (may indicate hash-based matching)")
        
        self.checkpoints["checkpoint_6"]["errors"] = errors
        self.checkpoints["checkpoint_6"]["passed"] = len(errors) == 0
        return self.checkpoints["checkpoint_6"]["passed"]
    
    def validate_checkpoint_7(self, logs: List[str], response: Optional[Dict]) -> bool:
        """Checkpoint 7: Response Format"""
        errors = []
        
        if not response:
            errors.append("No response payload received")
        else:
            # Check response has proper structure
            has_files = "files" in response
            has_results = "results" in response
            has_type = "type" in response
            
            if not (has_files or has_results):
                errors.append("Response missing 'files' or 'results' array")
            if not has_type:
                errors.append("Response missing 'type' field")
            
            # Validate image result structure
            files = response.get("files", [])
            results = response.get("results", [])
            all_items = files if files else results
            
            image_items = [item for item in all_items if item.get("result_type") == "image"]
            if image_items:
                first_image = image_items[0]
                required_fields = ["name", "path", "score"]
                missing_fields = [f for f in required_fields if f not in first_image]
                if missing_fields:
                    errors.append(f"Image result missing required fields: {missing_fields}")
        
        self.checkpoints["checkpoint_7"]["errors"] = errors
        self.checkpoints["checkpoint_7"]["passed"] = len(errors) == 0
        return self.checkpoints["checkpoint_7"]["passed"]
    
    def validate_checkpoint_8(self, response: Optional[Dict]) -> bool:
        """Checkpoint 8: UI Display Fields"""
        errors = []
        
        if not self.image_results:
            errors.append("No image results to validate UI fields")
        else:
            for i, item in enumerate(self.image_results):
                # Check thumbnail_url
                if not item.get("thumbnail_url"):
                    errors.append(f"Image result {i+1} missing 'thumbnail_url' (required for UI display)")
                
                # Check preview_url
                if not item.get("preview_url"):
                    errors.append(f"Image result {i+1} missing 'preview_url' (required for UI display)")
                
                # Check result_type
                if item.get("result_type") != "image":
                    errors.append(f"Image result {i+1} missing or incorrect 'result_type' (should be 'image')")
        
        self.checkpoints["checkpoint_8"]["errors"] = errors
        self.checkpoints["checkpoint_8"]["passed"] = len(errors) == 0
        return self.checkpoints["checkpoint_8"]["passed"]
    
    def print_report(self):
        """Print validation report."""
        print("\n" + "="*80)
        print("MOUNTAIN IMAGE SEMANTIC SEARCH REGRESSION TEST REPORT")
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
            print("✅ ALL CHECKPOINTS PASSED - Semantic search is working correctly!")
        else:
            print("❌ SOME CHECKPOINTS FAILED - Review errors above")
        print("="*80)
        
        # Print summary
        if self.enhanced_query:
            print(f"\nEnhanced Query: '{self.enhanced_query}'")
        if self.image_results:
            print(f"\nImage Results Found: {len(self.image_results)}")
            for i, result in enumerate(self.image_results[:3]):
                name = result.get("name") or result.get("doc_title", "unknown")
                score = result.get("score") or result.get("similarity_score", 0.0)
                print(f"  {i+1}. {name} (similarity: {score:.4f})")
        
        return all_passed


async def test_mountain_image_query():
    """Execute the end-to-end test."""
    print("\n" + "="*80)
    print("MOUNTAIN IMAGE SEMANTIC SEARCH REGRESSION TEST")
    print("="*80)
    print(f"Test Query: '{TEST_QUERY}'")
    print(f"WebSocket URL: {WEBSOCKET_URL}")
    print(f"Log File: {LOG_FILE}")
    print("="*80)
    print("\nThis test validates:")
    print("1. LLM reasoning is used (not hardcoded logic)")
    print("2. Semantic matching works (not just filename matching)")
    print("3. Similarity scores are meaningful (>0.6)")
    print("4. Results include UI display fields")
    print("="*80)
    
    validator = MountainImageCheckpointValidator()
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
                "session_id": f"test_mountain_{int(time.time())}"
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
    validator.validate_checkpoint_7(logs, response_payload)
    validator.validate_checkpoint_8(response_payload)
    
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
            image_files = [f for f in files if f.get("result_type") == "image"]
            print(f"Total files: {len(files) if isinstance(files, list) else 'N/A'}")
            print(f"Image files: {len(image_files)}")
            if image_files:
                print(f"Top image: {image_files[0].get('name', 'N/A')} (score: {image_files[0].get('score', 0.0):.4f})")
        if "results" in response_payload:
            results = response_payload["results"]
            image_results = [r for r in results if r.get("result_type") == "image"]
            print(f"Total results: {len(results) if isinstance(results, list) else 'N/A'}")
            print(f"Image results: {len(image_results)}")
        print("="*80)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(test_mountain_image_query())
    sys.exit(0 if success else 1)

