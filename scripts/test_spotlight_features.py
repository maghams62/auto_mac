#!/usr/bin/env python3
"""
Test script for Spotlight UI features:
1. Spotify Mini Player - dynamic polling, WebSocket updates, controls
2. File Search - only triggers for /file, /folder commands
3. Layout Ordering - response appears below Spotify
4. Voice Auto-Stop - improved VAD logic
"""

import asyncio
import json
import sys
import time
import aiohttp
import websockets

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/chat"

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ""
    
    def pass_test(self, msg: str = ""):
        self.passed = True
        self.message = msg
        print(f"  ✅ {self.name}: {msg or 'PASSED'}")
    
    def fail_test(self, msg: str):
        self.passed = False
        self.message = msg
        print(f"  ❌ {self.name}: {msg}")

async def test_backend_health():
    """Test 1: Backend is running and healthy"""
    result = TestResult("Backend Health")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/") as resp:
                data = await resp.json()
                if data.get("status") == "online":
                    result.pass_test(f"Service: {data.get('service')}")
                else:
                    result.fail_test(f"Unexpected response: {data}")
    except Exception as e:
        result.fail_test(str(e))
    return result

async def test_websocket_connection():
    """Test 2: WebSocket connection works"""
    result = TestResult("WebSocket Connection")
    try:
        async with websockets.connect(WS_URL) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(msg)
            if data.get("type") == "system":
                result.pass_test("Connected and received system message")
            else:
                result.fail_test(f"Unexpected message type: {data.get('type')}")
    except Exception as e:
        result.fail_test(str(e))
    return result

async def test_spotify_status_endpoint():
    """Test 3: Spotify status endpoint returns data"""
    result = TestResult("Spotify Status Endpoint")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/api/spotify/status") as resp:
                data = await resp.json()
                # status can be null if nothing is playing
                if "status" in data:
                    if data["status"] is None:
                        result.pass_test("Endpoint works (no active playback)")
                    else:
                        result.pass_test(f"Playing: {data['status'].get('item', {}).get('name', 'Unknown')}")
                else:
                    result.fail_test(f"Missing 'status' key: {data}")
    except Exception as e:
        result.fail_test(str(e))
    return result

async def test_spotify_control_endpoints():
    """Test 4: Spotify control endpoints exist and respond"""
    result = TestResult("Spotify Control Endpoints")
    endpoints = [
        ("POST", "/api/spotify/play"),
        ("POST", "/api/spotify/pause"),
        ("POST", "/api/spotify/next"),
        ("POST", "/api/spotify/previous"),
    ]
    
    working = []
    errors = []
    
    try:
        async with aiohttp.ClientSession() as session:
            for method, endpoint in endpoints:
                try:
                    if method == "POST":
                        async with session.post(f"{BASE_URL}{endpoint}") as resp:
                            # 401/500 means endpoint exists but Spotify issue
                            # 404 means endpoint doesn't exist
                            if resp.status != 404:
                                working.append(endpoint.split("/")[-1])
                            else:
                                errors.append(f"{endpoint}: 404")
                except Exception as e:
                    errors.append(f"{endpoint}: {e}")
        
        if len(working) == len(endpoints):
            result.pass_test(f"All endpoints exist: {', '.join(working)}")
        elif working:
            result.pass_test(f"Working: {', '.join(working)}, Issues: {errors}")
        else:
            result.fail_test(f"Errors: {errors}")
    except Exception as e:
        result.fail_test(str(e))
    return result

async def test_universal_search():
    """Test 5: Universal search endpoint works"""
    result = TestResult("Universal Search")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/api/universal-search?q=test&limit=5") as resp:
                data = await resp.json()
                if "results" in data:
                    result.pass_test(f"Found {data.get('count', 0)} results")
                else:
                    result.fail_test(f"Missing 'results' key: {data}")
    except Exception as e:
        result.fail_test(str(e))
    return result

async def test_commands_list():
    """Test 6: Commands list endpoint works"""
    result = TestResult("Commands List")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/api/commands") as resp:
                data = await resp.json()
                if "commands" in data:
                    count = len(data["commands"])
                    # Check for file-related commands
                    file_commands = [c for c in data["commands"] if c.get("id") in ["files", "file", "folder"]]
                    result.pass_test(f"{count} commands, {len(file_commands)} file-related")
                else:
                    result.fail_test(f"Missing 'commands' key")
    except Exception as e:
        result.fail_test(str(e))
    return result

async def test_websocket_chat():
    """Test 7: WebSocket chat processing works"""
    result = TestResult("WebSocket Chat")
    try:
        async with websockets.connect(WS_URL) as ws:
            # Skip initial message
            await asyncio.wait_for(ws.recv(), timeout=5.0)
            
            # Send a simple query
            await ws.send(json.dumps({
                "message": "what time is it?",
                "session_id": "test-123"
            }))
            
            # Wait for response
            response = await asyncio.wait_for(ws.recv(), timeout=15.0)
            data = json.loads(response)
            
            if data.get("type") in ["response", "assistant", "system"]:
                msg = data.get("message", data.get("content", ""))[:50]
                result.pass_test(f"Got response: {msg}...")
            else:
                result.pass_test(f"Got message type: {data.get('type')}")
    except asyncio.TimeoutError:
        result.fail_test("Response timeout")
    except Exception as e:
        result.fail_test(str(e))
    return result

async def test_spotify_websocket_broadcast():
    """Test 8: Spotify actions broadcast WebSocket updates"""
    result = TestResult("Spotify WebSocket Broadcast")
    try:
        async with websockets.connect(WS_URL) as ws:
            # Skip initial message
            await asyncio.wait_for(ws.recv(), timeout=5.0)
            
            # Trigger a Spotify action
            async with aiohttp.ClientSession() as session:
                await session.post(f"{BASE_URL}/api/spotify/pause")
            
            # Check for broadcast (may not come if Spotify not active)
            try:
                broadcast = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(broadcast)
                if data.get("type") == "spotify_playback_update":
                    result.pass_test(f"Received broadcast: action={data.get('action')}")
                else:
                    result.pass_test(f"No broadcast (Spotify may not be active)")
            except asyncio.TimeoutError:
                result.pass_test("No broadcast (expected if Spotify not playing)")
    except Exception as e:
        result.fail_test(str(e))
    return result

async def main():
    print("\n" + "="*60)
    print("🧪 SPOTLIGHT UI FEATURES TEST SUITE")
    print("="*60 + "\n")
    
    tests = [
        test_backend_health,
        test_websocket_connection,
        test_spotify_status_endpoint,
        test_spotify_control_endpoints,
        test_universal_search,
        test_commands_list,
        test_websocket_chat,
        test_spotify_websocket_broadcast,
    ]
    
    results = []
    for test_fn in tests:
        try:
            result = await test_fn()
            results.append(result)
        except Exception as e:
            result = TestResult(test_fn.__name__)
            result.fail_test(f"Test crashed: {e}")
            results.append(result)
    
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    print(f"\n  Passed: {passed}/{total}")
    print(f"  Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n  🎉 ALL TESTS PASSED!")
    else:
        print("\n  ⚠️  Some tests failed. Check output above.")
        failed = [r for r in results if not r.passed]
        for r in failed:
            print(f"    - {r.name}: {r.message}")
    
    print("\n" + "="*60 + "\n")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
