#!/usr/bin/env python3
"""
Browser-based test for BlueSky integration following TESTING_METHODOLOGY.md
Tests:
1. Summarize the last three tweets on BlueSky
2. Send a tweet on BlueSky
"""

import time
import subprocess
import sys
from pathlib import Path

# Start API server
print("=" * 60)
print("Starting API server...")
print("=" * 60)

project_root = Path(__file__).resolve().parent
api_server_process = subprocess.Popen(
    ["python3", "api_server.py"],
    cwd=str(project_root),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Start frontend
print("\n" + "=" * 60)
print("Starting frontend...")
print("=" * 60)

frontend_process = subprocess.Popen(
    ["npm", "run", "dev"],
    cwd=str(project_root / "frontend"),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Wait for services to be ready
print("\nWaiting for services to start...")
time.sleep(8)

print("\n" + "=" * 60)
print("Services started. Now testing in browser...")
print("=" * 60)
print("\nPlease manually test the following in your browser at http://localhost:3000:")
print("\n1. Test: 'Summarize the last three tweets on BlueSky'")
print("   Expected: Should return a summary of your last 3 BlueSky posts")
print("\n2. Test: 'Send a tweet on BlueSky saying Hello from Mac Automation Assistant'")
print("   Expected: Should post a tweet to BlueSky")
print("\nPress Enter when done testing...")
input()

# Cleanup
print("\nStopping services...")
api_server_process.terminate()
frontend_process.terminate()
api_server_process.wait()
frontend_process.wait()
print("✅ Services stopped")

