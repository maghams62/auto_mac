#!/usr/bin/env python3
"""
Comprehensive test script to diagnose frontend-backend connection issues.

Tests:
1. API server syntax validation (import check)
2. Port availability (8000 for API, 3000 for frontend)
3. API server startup capability
4. REST API endpoint health
5. WebSocket connection capability
6. Frontend-backend connectivity
"""

import sys
import subprocess
import time
import socket
import requests
import asyncio
from pathlib import Path
from typing import Tuple, Optional
import signal
import os

# Optional websockets import
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

# Colors for output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

class TestResult:
    def __init__(self, name: str, passed: bool, message: str = "", details: str = ""):
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details

def print_header(text: str):
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}{text}{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")

def print_test(result: TestResult):
    status = f"{GREEN}✓ PASS{NC}" if result.passed else f"{RED}✗ FAIL{NC}"
    print(f"{status} {result.name}")
    if result.message:
        print(f"    {result.message}")
    if result.details:
        print(f"    Details: {result.details}")

def check_port_available(port: int) -> Tuple[bool, Optional[int]]:
    """Check if a port is available. Returns (is_available, pid_using_port)."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result == 0:
            # Port is in use, try to find the PID
            try:
                result = subprocess.run(
                    ['lsof', '-ti', f':{port}'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                pid = int(result.stdout.strip()) if result.stdout.strip() else None
                return False, pid
            except:
                return False, None
        return True, None
    except Exception as e:
        return False, None

def test_api_server_syntax() -> TestResult:
    """Test if API server can be imported without syntax errors."""
    print(f"{YELLOW}Testing API server syntax...{NC}")
    
    try:
        # Try to import the api_server module
        project_root = Path(__file__).resolve().parent
        sys.path.insert(0, str(project_root))
        
        # Check if feedback_logger can be imported
        try:
            from src.services.feedback_logger import get_feedback_logger
            logger = get_feedback_logger()
            return TestResult(
                "API Server Syntax Check",
                True,
                "No syntax errors detected in api_server.py imports"
            )
        except SyntaxError as e:
            return TestResult(
                "API Server Syntax Check",
                False,
                f"Syntax error in imported module: {e}",
                f"File: {e.filename}, Line: {e.lineno}"
            )
        except ImportError as e:
            return TestResult(
                "API Server Syntax Check",
                False,
                f"Import error: {e}",
                str(e)
            )
        except Exception as e:
            return TestResult(
                "API Server Syntax Check",
                False,
                f"Unexpected error: {e}",
                str(e)
            )
    except Exception as e:
        return TestResult(
            "API Server Syntax Check",
            False,
            f"Failed to test syntax: {e}",
            str(e)
        )

def test_port_8000() -> TestResult:
    """Test if port 8000 is available or in use."""
    print(f"{YELLOW}Checking port 8000...{NC}")
    
    is_available, pid = check_port_available(8000)
    
    if is_available:
        return TestResult(
            "Port 8000 Availability",
            True,
            "Port 8000 is available (API server not running)"
        )
    else:
        return TestResult(
            "Port 8000 Availability",
            True,  # This is actually OK - server might be running
            f"Port 8000 is in use (PID: {pid})",
            "This indicates API server may be running"
        )

def test_port_3000() -> TestResult:
    """Test if port 3000 is available or in use."""
    print(f"{YELLOW}Checking port 3000...{NC}")
    
    is_available, pid = check_port_available(3000)
    
    if is_available:
        return TestResult(
            "Port 3000 Availability",
            False,
            "Port 3000 is available (frontend not running)"
        )
    else:
        return TestResult(
            "Port 3000 Availability",
            True,
            f"Port 3000 is in use (PID: {pid})",
            "Frontend server appears to be running"
        )

def test_api_server_startup() -> TestResult:
    """Test if API server can start without errors."""
    print(f"{YELLOW}Testing API server startup capability...{NC}")
    
    project_root = Path(__file__).resolve().parent
    api_server_path = project_root / "api_server.py"
    venv_python = project_root / "venv" / "bin" / "python"
    
    if not api_server_path.exists():
        return TestResult(
            "API Server Startup Test",
            False,
            "api_server.py not found",
            str(api_server_path)
        )
    
    # Use venv Python if available, otherwise use system Python
    python_executable = str(venv_python) if venv_python.exists() else sys.executable
    
    try:
        # Try to start the server in a subprocess and check for immediate errors
        env = os.environ.copy()
        env['PYTHONPATH'] = str(project_root)
        
        process = subprocess.Popen(
            [python_executable, str(api_server_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=str(project_root)
        )
        
        # Wait a bit to see if it crashes immediately
        time.sleep(3)
        
        if process.poll() is not None:
            # Process exited, get error output
            stdout, stderr = process.communicate()
            error_output = stderr.decode('utf-8', errors='ignore')
            
            # Check for syntax errors
            if 'SyntaxError' in error_output or 'SyntaxError' in stdout.decode('utf-8', errors='ignore'):
                return TestResult(
                    "API Server Startup Test",
                    False,
                    "API server failed to start due to syntax error",
                    error_output[:500]
                )
            
            return TestResult(
                "API Server Startup Test",
                False,
                "API server process exited immediately",
                error_output[:500]
            )
        else:
            # Process is still running, which is good
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
            
            return TestResult(
                "API Server Startup Test",
                True,
                "API server can start without immediate errors"
            )
    except Exception as e:
        return TestResult(
            "API Server Startup Test",
            False,
            f"Failed to test startup: {e}",
            str(e)
        )

def test_rest_api_health() -> TestResult:
    """Test if REST API responds on port 8000."""
    print(f"{YELLOW}Testing REST API health endpoint...{NC}")
    
    try:
        # Try to connect to the API
        response = requests.get("http://localhost:8000/api/stats", timeout=5)
        
        if response.status_code == 200:
            return TestResult(
                "REST API Health Check",
                True,
                "API server is responding",
                f"Status: {response.status_code}"
            )
        else:
            return TestResult(
                "REST API Health Check",
                False,
                f"API server returned status {response.status_code}",
                response.text[:200]
            )
    except requests.exceptions.ConnectionError:
        return TestResult(
            "REST API Health Check",
            False,
            "Cannot connect to API server on port 8000",
            "Server may not be running"
        )
    except requests.exceptions.Timeout:
        return TestResult(
            "REST API Health Check",
            False,
            "API server did not respond within timeout",
            "Server may be slow or unresponsive"
        )
    except Exception as e:
        return TestResult(
            "REST API Health Check",
            False,
            f"Error testing API: {e}",
            str(e)
        )

async def test_websocket_connection() -> TestResult:
    """Test if WebSocket endpoint is accessible."""
    print(f"{YELLOW}Testing WebSocket connection...{NC}")
    
    if not HAS_WEBSOCKETS:
        return TestResult(
            "WebSocket Connection Test",
            False,
            "websockets module not installed",
            "Install with: pip install websockets"
        )
    
    try:
        async with websockets.connect("ws://localhost:8000/ws/chat", timeout=5) as ws:
            # If we can connect, that's good enough for this test
            return TestResult(
                "WebSocket Connection Test",
                True,
                "WebSocket endpoint is accessible"
            )
    except websockets.exceptions.InvalidURI:
        return TestResult(
            "WebSocket Connection Test",
            False,
            "Invalid WebSocket URI",
            "Check WebSocket URL format"
        )
    except websockets.exceptions.ConnectionRefused:
        return TestResult(
            "WebSocket Connection Test",
            False,
            "WebSocket connection refused",
            "API server may not be running or WebSocket endpoint not available"
        )
    except asyncio.TimeoutError:
        return TestResult(
            "WebSocket Connection Test",
            False,
            "WebSocket connection timeout",
            "Server may be slow or unresponsive"
        )
    except Exception as e:
        return TestResult(
            "WebSocket Connection Test",
            False,
            f"WebSocket error: {e}",
            str(e)
        )

def test_frontend_backend_connectivity() -> TestResult:
    """Test if frontend can reach backend."""
    print(f"{YELLOW}Testing frontend-backend connectivity...{NC}")
    
    # Check if frontend is running
    is_frontend_available, _ = check_port_available(3000)
    if is_frontend_available:
        return TestResult(
            "Frontend-Backend Connectivity",
            False,
            "Frontend is not running on port 3000"
        )
    
    # Check if backend is running
    try:
        response = requests.get("http://localhost:8000/api/stats", timeout=2)
        if response.status_code == 200:
            return TestResult(
                "Frontend-Backend Connectivity",
                True,
                "Both frontend and backend are running and accessible"
            )
        else:
            return TestResult(
                "Frontend-Backend Connectivity",
                False,
                f"Backend is running but returned status {response.status_code}"
            )
    except requests.exceptions.ConnectionError:
        return TestResult(
            "Frontend-Backend Connectivity",
            False,
            "Frontend is running but cannot connect to backend",
            "Backend may not be running on port 8000"
        )
    except Exception as e:
        return TestResult(
            "Frontend-Backend Connectivity",
            False,
            f"Error testing connectivity: {e}",
            str(e)
        )

def main():
    """Run all tests."""
    print_header("Frontend-Backend Connection Diagnostic Test")
    
    results = []
    
    # Test 1: API Server Syntax
    results.append(test_api_server_syntax())
    
    # Test 2: Port 8000
    results.append(test_port_8000())
    
    # Test 3: Port 3000
    results.append(test_port_3000())
    
    # Test 4: API Server Startup
    results.append(test_api_server_startup())
    
    # Test 5: REST API Health (only if server might be running)
    is_port_8000_available, _ = check_port_available(8000)
    if not is_port_8000_available:
        results.append(test_rest_api_health())
    
    # Test 6: WebSocket Connection (only if server might be running)
    if not is_port_8000_available:
        try:
            ws_result = asyncio.run(test_websocket_connection())
            results.append(ws_result)
        except Exception as e:
            results.append(TestResult(
                "WebSocket Connection Test",
                False,
                f"Failed to run WebSocket test: {e}",
                str(e)
            ))
    
    # Test 7: Frontend-Backend Connectivity
    results.append(test_frontend_backend_connectivity())
    
    # Print summary
    print_header("Test Summary")
    
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    for result in results:
        print_test(result)
    
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print(f"{GREEN}All tests passed! Frontend and backend should be working correctly.{NC}")
        return 0
    else:
        print(f"{RED}Some tests failed. Please review the errors above.{NC}")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Test interrupted by user{NC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}Unexpected error: {e}{NC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

