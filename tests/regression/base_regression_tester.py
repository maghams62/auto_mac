#!/usr/bin/env python3
"""
Base Regression Tester Framework

A reusable framework for regression testing workflows.
Can be extended for specific test scenarios.
"""

import sys
import os
import time
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from abc import ABC, abstractmethod

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Color codes for terminal output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color


class Checkpoint:
    """Represents a single checkpoint in the test workflow."""
    
    def __init__(self, number: int, name: str, status: str = "pending", details: str = "", metadata: Optional[Dict[str, Any]] = None):
        self.number = number
        self.name = name
        self.status = status  # pending, pass, fail, warning
        self.details = details
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "name": self.name,
            "status": self.status,
            "details": self.details,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }


class BaseRegressionTester(ABC):
    """Base class for regression testing workflows."""
    
    def __init__(self, test_name: str, test_query: str, log_file: str = "api_server.log"):
        self.test_name = test_name
        self.test_query = test_query
        self.log_file = log_file
        self.checkpoints: List[Checkpoint] = []
        self.issues: List[Dict[str, Any]] = []
        self.fixes_applied: List[Dict[str, Any]] = []
        self.api_server_running = False
        
    def print_header(self, text: str):
        """Print a formatted header."""
        print(f"\n{BLUE}{'=' * 80}{NC}")
        print(f"{BLUE}  {text}{NC}")
        print(f"{BLUE}{'=' * 80}{NC}\n")
        
    def print_checkpoint(self, checkpoint_num: int, name: str, status: str, details: str = "", metadata: Optional[Dict[str, Any]] = None):
        """Print checkpoint result."""
        icon = f"{GREEN}✓{NC}" if status == "pass" else f"{RED}✗{NC}" if status == "fail" else f"{YELLOW}⚠{NC}"
        print(f"{icon} Checkpoint {checkpoint_num}: {name}")
        if details:
            print(f"   {details}")
        
        # Find existing checkpoint or create new
        checkpoint = next((cp for cp in self.checkpoints if cp.number == checkpoint_num), None)
        if checkpoint:
            checkpoint.status = status
            checkpoint.details = details
            if metadata:
                checkpoint.metadata.update(metadata)
        else:
            self.checkpoints.append(Checkpoint(checkpoint_num, name, status, details, metadata))
    
    def add_issue(self, checkpoint: int, issue: str, fix: str, severity: str = "error"):
        """Add an issue to the issues list."""
        self.issues.append({
            "checkpoint": checkpoint,
            "issue": issue,
            "fix": fix,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        })
    
    def check_api_server(self) -> bool:
        """Check if API server is running."""
        print(f"{CYAN}Checking API server...{NC}")
        try:
            import requests
            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code == 200:
                print(f"  {GREEN}✓ API server is running{NC}")
                self.api_server_running = True
                return True
            else:
                print(f"  {YELLOW}⚠ API server returned status {response.status_code}{NC}")
                return False
        except Exception as e:
            print(f"  {YELLOW}⚠ API server not accessible: {e}{NC}")
            print(f"  {YELLOW}→ Some tests will be skipped. Start API server: python api_server.py{NC}")
            return False
    
    def check_log_file(self) -> bool:
        """Check if log file exists."""
        print(f"\n{CYAN}Checking log file...{NC}")
        if os.path.exists(self.log_file):
            print(f"  {GREEN}✓ Log file exists: {self.log_file}{NC}")
            return True
        else:
            print(f"  {YELLOW}⚠ Log file not found: {self.log_file}{NC}")
            print(f"  {YELLOW}→ Logs will be created when API server runs{NC}")
            return False
    
    def search_logs(self, pattern: str, context_lines: int = 0) -> List[str]:
        """Search for pattern in log file."""
        if not os.path.exists(self.log_file):
            return []
        
        matches = []
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    if re.search(pattern, line, re.IGNORECASE):
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)
                        matches.append(''.join(lines[start:end]))
        except Exception as e:
            print(f"  {YELLOW}⚠ Error reading log file: {e}{NC}")
        
        return matches
    
    def check_websocket_endpoint(self) -> bool:
        """Check if WebSocket endpoint exists in code."""
        print(f"\n{CYAN}Checking WebSocket endpoint...{NC}")
        try:
            with open("api_server.py", "r") as f:
                content = f.read()
                if "@app.websocket" in content and "/ws/chat" in content:
                    print(f"  {GREEN}✓ WebSocket endpoint defined: /ws/chat{NC}")
                    return True
                else:
                    print(f"  {RED}✗ WebSocket endpoint not found{NC}")
                    self.add_issue(0, "WebSocket endpoint missing", "Add WebSocket endpoint to api_server.py")
                    return False
        except Exception as e:
            print(f"  {YELLOW}⚠ Could not verify WebSocket endpoint: {e}{NC}")
            return False
    
    def check_frontend_files(self, required_files: List[str]) -> bool:
        """Check if frontend files exist."""
        print(f"\n{CYAN}Checking frontend files...{NC}")
        all_exist = True
        for file_path in required_files:
            if os.path.exists(file_path):
                print(f"  {GREEN}✓ {file_path} exists{NC}")
            else:
                print(f"  {RED}✗ {file_path} not found{NC}")
                all_exist = False
        
        if not all_exist:
            self.add_issue(0, "Frontend files missing", "Check frontend directory structure")
        
        return all_exist
    
    @abstractmethod
    def check_environment(self) -> bool:
        """Phase 1: Pre-Test Environment Setup - Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def run_checkpoints(self) -> bool:
        """Run all checkpoints - Must be implemented by subclasses."""
        pass
    
    def generate_report(self, output_file: Optional[str] = None):
        """Generate test report."""
        self.print_header("TEST REPORT")
        
        total_checkpoints = len(self.checkpoints)
        passed = sum(1 for cp in self.checkpoints if cp.status == "pass")
        failed = sum(1 for cp in self.checkpoints if cp.status == "fail")
        warnings = sum(1 for cp in self.checkpoints if cp.status == "warning")
        
        print(f"Total Checkpoints: {total_checkpoints}")
        print(f"{GREEN}Passed: {passed}{NC}")
        print(f"{RED}Failed: {failed}{NC}")
        print(f"{YELLOW}Warnings: {warnings}{NC}")
        
        if self.issues:
            print(f"\n{RED}ISSUES FOUND:{NC}")
            for issue in self.issues:
                severity_icon = f"{RED}✗{NC}" if issue['severity'] == 'error' else f"{YELLOW}⚠{NC}"
                print(f"\n  {severity_icon} Checkpoint {issue['checkpoint']}: {issue['issue']}")
                print(f"  Fix: {issue['fix']}")
        else:
            print(f"\n{GREEN}✓ No issues found!{NC}")
        
        # Save report to file
        if not output_file:
            output_file = f"regression_test_report_{self.test_name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report_data = {
            "test_name": self.test_name,
            "test_query": self.test_query,
            "timestamp": datetime.now().isoformat(),
            "checkpoints": [cp.to_dict() for cp in self.checkpoints],
            "issues": self.issues,
            "fixes_applied": self.fixes_applied,
            "summary": {
                "total": total_checkpoints,
                "passed": passed,
                "failed": failed,
                "warnings": warnings
            }
        }
        
        with open(output_file, "w") as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n{CYAN}Report saved to: {output_file}{NC}")
        return output_file
    
    def run_all_tests(self):
        """Run all regression tests."""
        self.print_header(f"{self.test_name.upper()} REGRESSION TEST")
        print(f"Test Query: {self.test_query}\n")
        
        # Phase 1: Environment Setup
        if not self.check_environment():
            print(f"\n{RED}✗ Environment setup failed. Please fix issues and retry.{NC}")
            return False
        
        # Phase 2-3: Checkpoints
        success = self.run_checkpoints()
        
        # Generate report
        self.generate_report()
        
        return success

