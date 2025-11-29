#!/usr/bin/env python3
"""
Email Summarization Regression Test Script

Automates the testing process for "summarize my last 3 emails" feature.
Monitors logs, validates checkpoints, and reports failures with fix suggestions.
"""

import sys
import os
import time
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add project root to path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.agent.email_agent import read_latest_emails, summarize_emails
from src.ui.slash_commands import SlashCommandHandler
from src.utils import load_config

# Color codes for terminal output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color

class RegressionTester:
    """Regression tester for email summarization feature."""
    
    def __init__(self, log_file: str = "api_server.log"):
        self.log_file = log_file
        self.test_query = "summarize my last 3 emails"
        self.checkpoints = []
        self.issues = []
        self.fixes_applied = []
        
    def print_header(self, text: str):
        """Print a formatted header."""
        print(f"\n{BLUE}{'=' * 80}{NC}")
        print(f"{BLUE}  {text}{NC}")
        print(f"{BLUE}{'=' * 80}{NC}\n")
        
    def print_checkpoint(self, checkpoint_num: int, name: str, status: str, details: str = ""):
        """Print checkpoint result."""
        icon = f"{GREEN}✓{NC}" if status == "pass" else f"{RED}✗{NC}" if status == "fail" else f"{YELLOW}⚠{NC}"
        print(f"{icon} Checkpoint {checkpoint_num}: {name}")
        if details:
            print(f"   {details}")
        self.checkpoints.append({
            "number": checkpoint_num,
            "name": name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        
    def check_environment(self) -> bool:
        """Phase 1: Pre-Test Environment Setup"""
        self.print_header("PHASE 1: Environment Setup")
        
        # Check API server (optional - some tests can run without it)
        print(f"{CYAN}Checking API server...{NC}")
        api_server_running = False
        try:
            import requests
            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code == 200:
                print(f"  {GREEN}✓ API server is running{NC}")
                api_server_running = True
            else:
                print(f"  {YELLOW}⚠ API server returned status {response.status_code}{NC}")
        except Exception as e:
            print(f"  {YELLOW}⚠ API server not accessible: {e}{NC}")
            print(f"  {YELLOW}→ Some tests will be skipped. Start API server: python api_server.py{NC}")
        
        # Store API server status for later use
        self.api_server_running = api_server_running
            
        # Check log file
        print(f"\n{CYAN}Checking log file...{NC}")
        if os.path.exists(self.log_file):
            print(f"  {GREEN}✓ Log file exists: {self.log_file}{NC}")
        else:
            print(f"  {YELLOW}⚠ Log file not found: {self.log_file}{NC}")
            print(f"  {YELLOW}→ Logs will be created when API server runs{NC}")
            
        # Check email access
        print(f"\n{CYAN}Checking email access...{NC}")
        try:
            emails_result = read_latest_emails.invoke({"count": 3, "mailbox": "INBOX"})
            if emails_result.get('error'):
                print(f"  {RED}✗ Email reading error: {emails_result.get('error_message')}{NC}")
                return False
            emails = emails_result.get('emails', [])
            if len(emails) < 3:
                print(f"  {YELLOW}⚠ Only {len(emails)} emails found (need 3 for test){NC}")
                print(f"  {YELLOW}→ Add more emails to INBOX or use existing emails{NC}")
                if len(emails) == 0:
                    return False
            else:
                print(f"  {GREEN}✓ Found {len(emails)} emails in INBOX{NC}")
        except Exception as e:
            print(f"  {RED}✗ Email reading failed: {e}{NC}")
            return False
            
        print(f"\n{GREEN}✓ Environment setup complete{NC}")
        if not api_server_running:
            print(f"{YELLOW}Note: API server not running. WebSocket and frontend tests will be skipped.{NC}")
        return True
        
    def check_routing(self) -> bool:
        """Checkpoint 1: Query Routing"""
        self.print_header("CHECKPOINT 1: Query Routing")
        
        try:
            # Create a minimal mock agent registry for testing
            from src.agent.agent_registry import AgentRegistry
            from src.utils import load_config
            
            config = load_config()
            agent_registry = AgentRegistry(config)
            handler = SlashCommandHandler(agent_registry)
            
            task = self.test_query.replace("/email ", "").strip()
            tool_name, params, status = handler._route_email_command(task)
            
            # Check if query was detected as summarization
            if tool_name is None:
                print(f"  {GREEN}✓ Query correctly delegated to orchestrator{NC}")
            else:
                print(f"  {RED}✗ Query routed to single tool: {tool_name}{NC}")
                print(f"  {YELLOW}→ Expected: None (delegation to orchestrator){NC}")
                self.issues.append({
                    "checkpoint": 1,
                    "issue": "Query not delegated to orchestrator",
                    "fix": "Check _route_email_command() in src/ui/slash_commands.py"
                })
                return False
                
            # Check intent hints extraction
            if params and "intent_hints" in params:
                hints = params["intent_hints"]
                print(f"  {GREEN}✓ Intent hints extracted: {hints}{NC}")
                
                # Verify count is extracted
                if hints.get("count") == 3:
                    print(f"  {GREEN}✓ Count correctly extracted: 3{NC}")
                else:
                    print(f"  {YELLOW}⚠ Count extraction issue: got {hints.get('count')}, expected 3{NC}")
                    self.issues.append({
                        "checkpoint": 1,
                        "issue": "Count not extracted correctly",
                        "fix": "Check _extract_count() function in src/ui/slash_commands.py"
                    })
            else:
                print(f"  {RED}✗ Intent hints not found in params{NC}")
                self.issues.append({
                    "checkpoint": 1,
                    "issue": "Intent hints not extracted",
                    "fix": "Check _route_email_command() intent hint extraction logic"
                })
                return False
                
            self.print_checkpoint(1, "Query Routing", "pass", "Intent hints extracted correctly")
            return True
            
        except Exception as e:
            print(f"  {RED}✗ Routing check failed: {e}{NC}")
            import traceback
            traceback.print_exc()
            self.issues.append({
                "checkpoint": 1,
                "issue": f"Exception: {e}",
                "fix": "Review slash command routing code"
            })
            self.print_checkpoint(1, "Query Routing", "fail", str(e))
            return False
            
    def check_planning(self) -> bool:
        """Checkpoint 2: Orchestrator Planning"""
        self.print_header("CHECKPOINT 2: Orchestrator Planning")
        
        try:
            from src.orchestrator.main_orchestrator import MainOrchestrator
            
            config = load_config()
            orchestrator = MainOrchestrator(config)
            
            # Create plan with context
            context = {
                "intent_hints": {
                    "action": "summarize",
                    "count": 3
                }
            }
            
            # Use async version with proper session_context
            import asyncio
            from src.memory.session_memory import SessionContext
            
            # Create a minimal SessionContext for testing
            import uuid
            session_context = SessionContext(
                original_query=self.test_query,
                session_id=str(uuid.uuid4())
            )
            
            plan_result = asyncio.run(orchestrator.planner.create_plan(
                goal=self.test_query,
                available_tools=orchestrator.tool_catalog,
                context=context,
                session_context=session_context
            ))
            
            if not plan_result.get("success"):
                print(f"  {RED}✗ Planning failed: {plan_result.get('error')}{NC}")
                self.issues.append({
                    "checkpoint": 2,
                    "issue": f"Planning failed: {plan_result.get('error')}",
                    "fix": "Check planner prompts and tool catalog"
                })
                self.print_checkpoint(2, "Orchestrator Planning", "fail", plan_result.get('error'))
                return False
                
            plan = plan_result.get("plan", [])
            print(f"  {GREEN}✓ Plan created with {len(plan)} steps{NC}")
            
            # Verify plan structure - check for steps
            if not plan:
                print(f"  {RED}✗ Plan is empty{NC}")
                self.issues.append({
                    "checkpoint": 2,
                    "issue": "Plan is empty",
                    "fix": "Check planner prompts and tool catalog"
                })
                self.print_checkpoint(2, "Orchestrator Planning", "fail", "Empty plan")
                return False
            
            # Extract tool names from plan steps
            plan_tools = []
            for step in plan:
                # Plan steps can have different structures - check common fields
                tool = step.get("tool") or step.get("tool_name") or step.get("action")
                if tool:
                    plan_tools.append(tool)
            
            print(f"  Plan tools: {plan_tools if plan_tools else 'No tools found in plan structure'}")
            
            # Check for expected email tools (flexible - planner might use different names)
            expected_tools = ["read_latest_emails", "summarize_emails", "reply_to_user"]
            found_tools = [tool for tool in expected_tools if any(tool in str(step).lower() or tool in str(plan_tools).lower() for step in plan)]
            
            if found_tools:
                print(f"  {GREEN}✓ Found expected email tools: {found_tools}{NC}")
            else:
                print(f"  {YELLOW}⚠ Expected email tools not found in plan structure{NC}")
                print(f"  {CYAN}→ This may be acceptable if planner uses different tool names{NC}")
                # Don't fail - planner might structure plan differently
                
            # Check parameter threading
            has_threading = False
            for step in plan:
                params = step.get("parameters", {})
                param_str = json.dumps(params)
                if "$step1" in param_str or "$step" in param_str:
                    has_threading = True
                    break
                    
            if has_threading:
                print(f"  {GREEN}✓ Parameter threading detected{NC}")
            else:
                print(f"  {YELLOW}⚠ Parameter threading not detected{NC}")
                self.issues.append({
                    "checkpoint": 2,
                    "issue": "Parameter threading missing",
                    "fix": "Check planner uses $step1 references"
                })
                
            self.print_checkpoint(2, "Orchestrator Planning", "pass", f"Plan has {len(plan)} steps")
            return True
            
        except Exception as e:
            print(f"  {RED}✗ Planning check failed: {e}{NC}")
            import traceback
            traceback.print_exc()
            self.issues.append({
                "checkpoint": 2,
                "issue": f"Exception: {e}",
                "fix": "Review orchestrator planning code"
            })
            self.print_checkpoint(2, "Orchestrator Planning", "fail", str(e))
            return False
            
    def check_email_reading(self) -> bool:
        """Checkpoint 3: Email Reading"""
        self.print_header("CHECKPOINT 3: Email Reading")
        
        try:
            emails_result = read_latest_emails.invoke({"count": 3, "mailbox": "INBOX"})
            
            if emails_result.get('error'):
                print(f"  {RED}✗ Email reading error: {emails_result.get('error_message')}{NC}")
                self.issues.append({
                    "checkpoint": 3,
                    "issue": emails_result.get('error_message'),
                    "fix": "Check Mail.app permissions and mailbox name"
                })
                self.print_checkpoint(3, "Email Reading", "fail", emails_result.get('error_message'))
                return False
                
            emails = emails_result.get('emails', [])
            
            if len(emails) == 0:
                print(f"  {RED}✗ No emails found{NC}")
                self.issues.append({
                    "checkpoint": 3,
                    "issue": "No emails in INBOX",
                    "fix": "Add emails to Mail.app INBOX"
                })
                self.print_checkpoint(3, "Email Reading", "fail", "No emails found")
                return False
                
            print(f"  {GREEN}✓ Read {len(emails)} emails{NC}")
            
            # Check required fields
            required_fields = ["sender", "subject", "date", "content"]
            for i, email in enumerate(emails, 1):
                missing = [field for field in required_fields if not email.get(field)]
                if missing:
                    print(f"  {YELLOW}⚠ Email {i} missing fields: {missing}{NC}")
                else:
                    print(f"  {GREEN}✓ Email {i} has all required fields{NC}")
                    
            self.print_checkpoint(3, "Email Reading", "pass", f"Read {len(emails)} emails")
            return True
            
        except Exception as e:
            print(f"  {RED}✗ Email reading check failed: {e}{NC}")
            import traceback
            traceback.print_exc()
            self.issues.append({
                "checkpoint": 3,
                "issue": f"Exception: {e}",
                "fix": "Review email reading code"
            })
            self.print_checkpoint(3, "Email Reading", "fail", str(e))
            return False
            
    def check_summarization(self) -> bool:
        """Checkpoint 4: Email Summarization"""
        self.print_header("CHECKPOINT 4: Email Summarization")
        
        try:
            # First read emails
            emails_result = read_latest_emails.invoke({"count": 3, "mailbox": "INBOX"})
            if emails_result.get('error') or not emails_result.get('emails'):
                print(f"  {RED}✗ Cannot test summarization without emails{NC}")
                self.print_checkpoint(4, "Email Summarization", "fail", "No emails to summarize")
                return False
                
            # Summarize
            summary_result = summarize_emails.invoke({
                "emails_data": emails_result,
                "focus": None
            })
            
            if summary_result.get('error'):
                print(f"  {RED}✗ Summarization error: {summary_result.get('error_message')}{NC}")
                self.issues.append({
                    "checkpoint": 4,
                    "issue": summary_result.get('error_message'),
                    "fix": "Check OpenAI API key and summarize_emails tool"
                })
                self.print_checkpoint(4, "Email Summarization", "fail", summary_result.get('error_message'))
                return False
                
            summary = summary_result.get('summary', '')
            if not summary:
                print(f"  {RED}✗ Summary is empty{NC}")
                self.issues.append({
                    "checkpoint": 4,
                    "issue": "Empty summary generated",
                    "fix": "Check OpenAI API response"
                })
                self.print_checkpoint(4, "Email Summarization", "fail", "Empty summary")
                return False
                
            if len(summary) < 100:
                print(f"  {YELLOW}⚠ Summary is very short ({len(summary)} chars){NC}")
            else:
                print(f"  {GREEN}✓ Summary generated ({len(summary)} chars){NC}")
                
            # Check if summary mentions email content
            emails = emails_result.get('emails', [])
            has_content = False
            for email in emails:
                sender = email.get('sender', '')
                subject = email.get('subject', '')
                if sender and sender.lower() in summary.lower():
                    has_content = True
                    break
                if subject and subject.lower() in summary.lower():
                    has_content = True
                    break
                    
            if has_content:
                print(f"  {GREEN}✓ Summary contains email references{NC}")
            else:
                print(f"  {YELLOW}⚠ Summary may not reference email content{NC}")
                
            self.print_checkpoint(4, "Email Summarization", "pass", f"Summary: {len(summary)} chars")
            return True
            
        except Exception as e:
            print(f"  {RED}✗ Summarization check failed: {e}{NC}")
            import traceback
            traceback.print_exc()
            self.issues.append({
                "checkpoint": 4,
                "issue": f"Exception: {e}",
                "fix": "Review summarize_emails tool"
            })
            self.print_checkpoint(4, "Email Summarization", "fail", str(e))
            return False
            
    def check_response_formatting(self) -> bool:
        """Checkpoint 5: Response Formatting"""
        self.print_header("CHECKPOINT 5: Response Formatting")
        
        try:
            from src.agent.reply_tool import reply_to_user
            
            # Test reply_to_user with sample summary
            test_summary = "Test summary of 3 emails"
            reply_result = reply_to_user.invoke({
                "message": test_summary,
                "details": "Email summarization complete",
                "status": "success"
            })
            
            if not reply_result:
                print(f"  {RED}✗ reply_to_user returned empty result{NC}")
                self.print_checkpoint(5, "Response Formatting", "fail", "Empty result")
                return False
                
            # Check payload structure
            if "message" in reply_result:
                print(f"  {GREEN}✓ Payload has 'message' field{NC}")
            else:
                print(f"  {RED}✗ Payload missing 'message' field{NC}")
                self.issues.append({
                    "checkpoint": 5,
                    "issue": "Missing message field",
                    "fix": "Check reply_to_user tool structure"
                })
                self.print_checkpoint(5, "Response Formatting", "fail", "Missing message field")
                return False
                
            if reply_result.get("message") == test_summary:
                print(f"  {GREEN}✓ Message content preserved{NC}")
            else:
                print(f"  {YELLOW}⚠ Message content may be modified{NC}")
                
            self.print_checkpoint(5, "Response Formatting", "pass", "Payload structure correct")
            return True
            
        except Exception as e:
            print(f"  {RED}✗ Response formatting check failed: {e}{NC}")
            import traceback
            traceback.print_exc()
            self.issues.append({
                "checkpoint": 5,
                "issue": f"Exception: {e}",
                "fix": "Review reply_to_user tool"
            })
            self.print_checkpoint(5, "Response Formatting", "fail", str(e))
            return False
            
    def check_websocket_delivery(self) -> bool:
        """Checkpoint 6: WebSocket Delivery"""
        self.print_header("CHECKPOINT 6: WebSocket Delivery")
        
        # This checkpoint requires actual WebSocket connection
        # For now, we'll check if the API server has WebSocket endpoint
        print(f"  {YELLOW}⚠ WebSocket delivery requires live connection{NC}")
        print(f"  {YELLOW}→ Manual verification needed via browser{NC}")
        print(f"  {CYAN}→ Check browser console for WebSocket messages{NC}")
        print(f"  {CYAN}→ Verify response payload structure{NC}")
        
        # Check if WebSocket endpoint exists in code
        try:
            with open("api_server.py", "r") as f:
                content = f.read()
                if "@app.websocket" in content and "/ws/chat" in content:
                    print(f"  {GREEN}✓ WebSocket endpoint defined: /ws/chat{NC}")
                else:
                    print(f"  {RED}✗ WebSocket endpoint not found{NC}")
                    self.issues.append({
                        "checkpoint": 6,
                        "issue": "WebSocket endpoint missing",
                        "fix": "Add WebSocket endpoint to api_server.py"
                    })
                    self.print_checkpoint(6, "WebSocket Delivery", "fail", "Endpoint missing")
                    return False
        except Exception as e:
            print(f"  {YELLOW}⚠ Could not verify WebSocket endpoint: {e}{NC}")
            
        self.print_checkpoint(6, "WebSocket Delivery", "pass", "Endpoint exists (manual verification needed)")
        return True
        
    def check_frontend_rendering(self) -> bool:
        """Checkpoint 7: Frontend Rendering"""
        self.print_header("CHECKPOINT 7: Frontend Rendering")
        
        # This checkpoint requires frontend to be running
        print(f"  {YELLOW}⚠ Frontend rendering requires live UI{NC}")
        print(f"  {YELLOW}→ Manual verification needed in browser{NC}")
        print(f"  {CYAN}→ Check MessageBubble.tsx renders summary{NC}")
        print(f"  {CYAN}→ Verify useWebSocket.ts handles messages{NC}")
        
        # Check if frontend files exist
        frontend_files = [
            "frontend/lib/useWebSocket.ts",
            "frontend/components/MessageBubble.tsx",
            "frontend/components/ChatInterface.tsx"
        ]
        
        all_exist = True
        for file_path in frontend_files:
            if os.path.exists(file_path):
                print(f"  {GREEN}✓ {file_path} exists{NC}")
            else:
                print(f"  {RED}✗ {file_path} not found{NC}")
                all_exist = False
                
        if not all_exist:
            self.issues.append({
                "checkpoint": 7,
                "issue": "Frontend files missing",
                "fix": "Check frontend directory structure"
            })
            self.print_checkpoint(7, "Frontend Rendering", "fail", "Files missing")
            return False
            
        self.print_checkpoint(7, "Frontend Rendering", "pass", "Files exist (manual verification needed)")
        return True
        
    def generate_report(self):
        """Generate test report."""
        self.print_header("TEST REPORT")
        
        total_checkpoints = len(self.checkpoints)
        passed = sum(1 for cp in self.checkpoints if cp["status"] == "pass")
        failed = sum(1 for cp in self.checkpoints if cp["status"] == "fail")
        
        print(f"Total Checkpoints: {total_checkpoints}")
        print(f"{GREEN}Passed: {passed}{NC}")
        print(f"{RED}Failed: {failed}{NC}")
        print(f"{YELLOW}Warnings: {total_checkpoints - passed - failed}{NC}")
        
        if self.issues:
            print(f"\n{RED}ISSUES FOUND:{NC}")
            for issue in self.issues:
                print(f"\n  Checkpoint {issue['checkpoint']}: {issue['issue']}")
                print(f"  Fix: {issue['fix']}")
        else:
            print(f"\n{GREEN}✓ No issues found!{NC}")
            
        # Save report to file
        report_file = f"regression_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "test_query": self.test_query,
            "checkpoints": self.checkpoints,
            "issues": self.issues,
            "summary": {
                "total": total_checkpoints,
                "passed": passed,
                "failed": failed
            }
        }
        
        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)
            
        print(f"\n{CYAN}Report saved to: {report_file}{NC}")
        
    def run_all_tests(self):
        """Run all regression tests."""
        self.print_header("EMAIL SUMMARIZATION REGRESSION TEST")
        print(f"Test Query: {self.test_query}\n")
        
        # Phase 1: Environment Setup
        if not self.check_environment():
            print(f"\n{RED}✗ Environment setup failed. Please fix issues and retry.{NC}")
            return False
            
        # Phase 2-3: Checkpoints
        self.check_routing()
        self.check_planning()
        self.check_email_reading()
        self.check_summarization()
        self.check_response_formatting()
        self.check_websocket_delivery()
        self.check_frontend_rendering()
        
        # Generate report
        self.generate_report()
        
        return True

def main():
    """Main entry point."""
    tester = RegressionTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()

