"""
WebSocket integration tests for file/document responses and Bluesky posting.
Tests the 4 critical scenarios via WebSocket API.
"""

import asyncio
import json
import websockets
import time
from datetime import datetime
from typing import Dict, List, Any

TEST_RESULTS = []


async def test_websocket_scenario(scenario_name: str, message: str, expected_keys: List[str] = None):
    """Test a single WebSocket scenario."""
    print(f"\n{'='*60}")
    print(f"Testing: {scenario_name}")
    print(f"Message: {message}")
    print(f"{'='*60}")
    
    uri = "ws://localhost:8000/ws/chat"
    session_id = f"test_{int(time.time())}"
    
    result = {
        "scenario": scenario_name,
        "message": message,
        "passed": False,
        "response_received": False,
        "has_files": False,
        "has_documents": False,
        "has_message": False,
        "message_text": "",
        "files_count": 0,
        "documents_count": 0,
        "errors": [],
        "logs": []
    }
    
    try:
        async with websockets.connect(uri) as websocket:
            # Send initial connection message
            await websocket.send(json.dumps({
                "session_id": session_id,
                "message": message
            }))
            
            # Wait for response (with timeout)
            timeout = 120  # 2 minutes
            start_time = time.time()
            response_received = False
            
            while time.time() - start_time < timeout:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(response)
                    
                    result["logs"].append({
                        "timestamp": datetime.now().isoformat(),
                        "type": data.get("type", "unknown"),
                        "keys": list(data.keys())
                    })
                    
                    # Check for response type
                    if data.get("type") == "response":
                        result["response_received"] = True
                        result["has_message"] = bool(data.get("message"))
                        result["message_text"] = data.get("message", "")[:200]
                        
                        if "files" in data:
                            result["has_files"] = True
                            files = data["files"]
                            if isinstance(files, list):
                                result["files_count"] = len(files)
                                result["logs"].append({
                                    "files": [f.get("name", "unknown") for f in files[:3]]
                                })
                        
                        if "documents" in data:
                            result["has_documents"] = True
                            documents = data["documents"]
                            if isinstance(documents, list):
                                result["documents_count"] = len(documents)
                        
                        # Check expected keys
                        if expected_keys:
                            missing_keys = [k for k in expected_keys if k not in data]
                            if missing_keys:
                                result["errors"].append(f"Missing expected keys: {missing_keys}")
                        
                        response_received = True
                        break
                    
                    # Check for error type
                    elif data.get("type") == "error":
                        result["errors"].append(f"Error response: {data.get('message', 'Unknown error')}")
                        break
                    
                except asyncio.TimeoutError:
                    continue
            
            if not response_received:
                result["errors"].append("Timeout waiting for response")
    
    except Exception as e:
        result["errors"].append(f"WebSocket error: {str(e)}")
        import traceback
        result["errors"].append(traceback.format_exc())
    
    # Determine if test passed
    result["passed"] = (
        result["response_received"] and
        result["has_message"] and
        len(result["errors"]) == 0
    )
    
    # Print results
    print(f"\nResults:")
    print(f"  Response received: {result['response_received']}")
    print(f"  Has message: {result['has_message']}")
    print(f"  Has files: {result['has_files']} (count: {result['files_count']})")
    print(f"  Has documents: {result['has_documents']} (count: {result['documents_count']})")
    if result["errors"]:
        print(f"  Errors: {len(result['errors'])}")
        for error in result["errors"]:
            print(f"    - {error}")
    print(f"  Status: {'✓ PASSED' if result['passed'] else '✗ FAILED'}")
    
    TEST_RESULTS.append(result)
    return result


async def main():
    """Run all WebSocket integration tests."""
    print("="*60)
    print("WebSocket Integration Tests")
    print("="*60)
    
    # Test 1: Image Search
    await test_websocket_scenario(
        "Image Search",
        "picture of a mountain",
        expected_keys=["type", "message"]
    )
    
    # Wait a bit between tests
    await asyncio.sleep(2)
    
    # Test 2: Document Search
    await test_websocket_scenario(
        "Document Search",
        "files about Ed Sheeran",
        expected_keys=["type", "message"]
    )
    
    # Wait a bit between tests
    await asyncio.sleep(2)
    
    # Test 3: Deal Status (with potential failures)
    await test_websocket_scenario(
        "Deal Status",
        "How's my deal looking?",
        expected_keys=["type", "message"]
    )
    
    # Wait a bit between tests
    await asyncio.sleep(2)
    
    # Test 4: Bluesky Post
    await test_websocket_scenario(
        "Bluesky Post",
        "Can you post on blue sky saying hello world, this is AI tweeting",
        expected_keys=["type", "message"]
    )
    
    # Print summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for r in TEST_RESULTS if r["passed"])
    total = len(TEST_RESULTS)
    
    for result in TEST_RESULTS:
        status = "✓" if result["passed"] else "✗"
        print(f"{status} {result['scenario']}: {result['message_text'][:50]}...")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

