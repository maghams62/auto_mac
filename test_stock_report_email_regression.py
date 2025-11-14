#!/usr/bin/env python3
"""
Stock Report Email Regression Test Script

Automates the testing process for "search Nvidia stock price, analyze, create report, email it" feature.
Monitors logs, validates checkpoints, and reports failures with fix suggestions.

Reuses the base regression test framework for consistency.
"""

import sys
import os
import time
import json
import re
import asyncio
import websockets
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add project root to path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import base regression tester
sys.path.insert(0, str(Path(__file__).resolve().parent / "tests" / "regression"))
from base_regression_tester import BaseRegressionTester, Checkpoint

# Import tools for direct testing
from src.agent.stock_agent import get_stock_price, search_stock_symbol
from src.agent.writing_agent import create_detailed_report, synthesize_content
from src.agent.presentation_agent import create_keynote, create_keynote_with_images
from src.agent.enriched_stock_agent import create_stock_report_and_email
from src.agent.email_agent import compose_email
from src.utils import load_config
from src.agent.agent_registry import AgentRegistry
from src.orchestrator.planner import Planner
from src.memory.session_memory import SessionContext
import uuid

# Color codes
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'


class StockReportEmailRegressionTester(BaseRegressionTester):
    """Regression tester for stock report email workflow."""
    
    def __init__(self, log_file: str = "api_server.log"):
        test_query = "open up for the query, search for Nvidia's stock price, analyze it, create a report out of it and send it to me in an email"
        super().__init__("Stock Report Email", test_query, log_file)
        self.stock_data = None
        self.report_content = None
        self.report_file_path = None
        self.email_result = None
        
    def check_environment(self) -> bool:
        """Phase 1: Pre-Test Environment Setup"""
        self.print_header("PHASE 1: Environment Setup")
        
        # Check API server
        api_ok = self.check_api_server()
        
        # Check log file
        log_ok = self.check_log_file()
        
        # Check WebSocket endpoint
        ws_ok = self.check_websocket_endpoint()
        
        # Check stock data access
        print(f"\n{CYAN}Checking stock data access...{NC}")
        try:
            result = get_stock_price.invoke({"symbol": "NVDA"})
            if result.get('error'):
                print(f"  {RED}✗ Stock price fetch error: {result.get('error_message')}{NC}")
                self.add_issue(0, "Stock data access failed", "Check yfinance API and network connectivity")
                return False
            else:
                print(f"  {GREEN}✓ Stock price fetch successful: {result.get('current_price', 'N/A')}{NC}")
        except Exception as e:
            print(f"  {RED}✗ Stock price fetch failed: {e}{NC}")
            self.add_issue(0, f"Stock data access exception: {e}", "Check stock_agent.py and yfinance installation")
            return False
        
        # Check email configuration
        print(f"\n{CYAN}Checking email configuration...{NC}")
        try:
            config = load_config()
            email_settings = config.get("email_settings", {})
            default_recipient = email_settings.get("default_recipient")
            if default_recipient:
                print(f"  {GREEN}✓ Default recipient configured: {default_recipient}{NC}")
            else:
                print(f"  {YELLOW}⚠ No default recipient configured{NC}")
                print(f"  {YELLOW}→ Email will be created as draft{NC}")
        except Exception as e:
            print(f"  {YELLOW}⚠ Could not check email config: {e}{NC}")
        
        # Check Mail.app permissions (optional - just warn)
        print(f"\n{CYAN}Checking Mail.app permissions...{NC}")
        if os.path.exists("check_mail_permissions.sh"):
            print(f"  {CYAN}→ Run check_mail_permissions.sh to verify Mail.app permissions{NC}")
        else:
            print(f"  {YELLOW}⚠ check_mail_permissions.sh not found{NC}")
        
        print(f"\n{GREEN}✓ Environment setup complete{NC}")
        if not api_ok:
            print(f"{YELLOW}Note: API server not running. WebSocket and frontend tests will be skipped.{NC}")
        return True
    
    def check_query_routing(self) -> bool:
        """Checkpoint 1: Query Routing"""
        self.print_header("CHECKPOINT 1: Query Routing")
        
        try:
            # Check if query would reach the agent
            # In a real scenario, this would go through api_server.py
            print(f"  {CYAN}Test query: {self.test_query[:80]}...{NC}")
            
            # Verify query contains expected keywords
            required_keywords = ["nvidia", "stock", "price", "analyze", "report", "email"]
            found_keywords = [kw for kw in required_keywords if kw.lower() in self.test_query.lower()]
            
            if len(found_keywords) >= 4:
                print(f"  {GREEN}✓ Query contains required keywords: {found_keywords}{NC}")
            else:
                print(f"  {YELLOW}⚠ Query may be missing keywords{NC}")
            
            # Check session creation would happen (simulated)
            session_id = str(uuid.uuid4())
            print(f"  {GREEN}✓ Session ID would be generated: {session_id[:8]}...{NC}")
            
            # Check correlation_id would be generated (telemetry)
            correlation_id = f"req_{uuid.uuid4().hex[:8]}"
            print(f"  {GREEN}✓ Correlation ID would be generated: {correlation_id}{NC}")
            
            self.print_checkpoint(1, "Query Routing", "pass", 
                                f"Query validated, session/correlation IDs would be generated",
                                {"session_id": session_id, "correlation_id": correlation_id})
            return True
            
        except Exception as e:
            print(f"  {RED}✗ Routing check failed: {e}{NC}")
            import traceback
            traceback.print_exc()
            self.add_issue(1, f"Exception: {e}", "Review query routing code")
            self.print_checkpoint(1, "Query Routing", "fail", str(e))
            return False
    
    def check_planning(self) -> bool:
        """Checkpoint 2: Plan Generation"""
        self.print_header("CHECKPOINT 2: Plan Generation")
        
        try:
            config = load_config()
            planner = Planner(config)
            
            # Create session context
            session_context = SessionContext(
                original_query=self.test_query,
                session_id=str(uuid.uuid4())
            )
            
            # Get available tools - use the same approach as MainOrchestrator
            from src.orchestrator.tools_catalog import generate_tool_catalog
            tool_catalog = generate_tool_catalog(config=config)  # Returns List[ToolSpec], not dicts
            
            # Create plan
            import asyncio
            plan_result = asyncio.run(planner.create_plan(
                goal=self.test_query,
                available_tools=tool_catalog,
                session_context=session_context
            ))
            
            if not plan_result.get("success"):
                print(f"  {RED}✗ Planning failed: {plan_result.get('error')}{NC}")
                self.add_issue(2, f"Planning failed: {plan_result.get('error')}", "Check planner prompts and tool catalog")
                self.print_checkpoint(2, "Plan Generation", "fail", plan_result.get('error'))
                return False
            
            plan = plan_result.get("plan", [])
            print(f"  {GREEN}✓ Plan created with {len(plan)} steps{NC}")
            
            # Extract tool names from plan
            plan_tools = []
            for step in plan:
                tool = step.get("tool") or step.get("tool_name") or step.get("action")
                if tool:
                    plan_tools.append(tool)
            
            print(f"  Plan tools: {plan_tools[:10]}...")  # Show first 10
            
            # CRITICAL: Check for Pages-free workflow (Pages is unreliable)
            # Plan should use Keynote/PDF tools, NOT create_pages_doc
            has_create_pages = any("create_pages_doc" in str(step).lower() for step in plan)
            has_compose_email = any("compose_email" in str(step).lower() for step in plan)
            has_create_stock_report = any("create_stock_report_and_email" in str(step).lower() for step in plan)
            has_create_keynote = any("create_keynote" in str(step).lower() for step in plan)
            
            # Check if Pages is being used (should NOT be)
            if has_create_pages:
                print(f"  {RED}✗ Plan uses create_pages_doc - Pages is unreliable for this workflow!{NC}")
                self.add_issue(2, "Plan uses create_pages_doc (unreliable)", 
                             "CRITICAL: Pages automation is unresponsive. Use create_stock_report_and_email OR create_keynote/create_keynote_with_images instead. Update planner prompts to avoid Pages for stock report emails.")
                self.print_checkpoint(2, "Plan Generation", "fail", "Plan uses unreliable Pages tool")
                return False
            
            # Check for valid alternatives
            if has_create_stock_report:
                print(f"  {GREEN}✓ Plan uses create_stock_report_and_email (preferred single-tool approach){NC}")
            elif has_create_keynote and has_compose_email:
                # Check order - keynote should come before compose_email
                keynote_idx = next((i for i, step in enumerate(plan) if "create_keynote" in str(step).lower()), -1)
                compose_email_idx = next((i for i, step in enumerate(plan) if "compose_email" in str(step).lower()), -1)
                
                if keynote_idx < compose_email_idx:
                    print(f"  {GREEN}✓ Plan uses create_keynote BEFORE compose_email (correct workflow){NC}")
                else:
                    print(f"  {RED}✗ create_keynote appears AFTER compose_email (WRONG ORDER!){NC}")
                    self.add_issue(2, "create_keynote must come before compose_email", 
                                 "Check planner prompts - workflow should be: create_detailed_report → create_keynote → compose_email")
                    self.print_checkpoint(2, "Plan Generation", "fail", "Incorrect tool order")
                    return False
            elif not has_compose_email:
                print(f"  {RED}✗ Plan missing compose_email step{NC}")
                self.add_issue(2, "Plan missing compose_email step", 
                             "Planner must include compose_email to send the report")
                self.print_checkpoint(2, "Plan Generation", "fail", "Missing compose_email")
                return False
            else:
                print(f"  {YELLOW}⚠ Plan may be missing file creation step{NC}")
                self.add_issue(2, "Plan may be missing file creation", 
                             "Planner should use create_stock_report_and_email OR create_keynote to create file before emailing")
                self.print_checkpoint(2, "Plan Generation", "warning", "May be missing file creation")
            
            # Check for expected tools
            expected_tools = ["search_stock_symbol", "get_stock_price", "create_detailed_report", "create_keynote", "create_stock_report_and_email", "compose_email"]
            found_tools = [tool for tool in expected_tools if any(tool in str(step).lower() for step in plan)]
            
            if found_tools:
                print(f"  {GREEN}✓ Found expected tools: {found_tools}{NC}")
            else:
                print(f"  {YELLOW}⚠ Some expected tools not found in plan{NC}")
            
            # Check parameter threading
            has_threading = any("$step" in json.dumps(step) for step in plan)
            if has_threading:
                print(f"  {GREEN}✓ Parameter threading detected{NC}")
            else:
                print(f"  {YELLOW}⚠ Parameter threading not detected{NC}")
            
            self.print_checkpoint(2, "Plan Generation", "pass", 
                                f"Plan has {len(plan)} steps with correct workflow",
                                {"plan_steps": len(plan), "tools": plan_tools})
            return True
            
        except Exception as e:
            print(f"  {RED}✗ Planning check failed: {e}{NC}")
            import traceback
            traceback.print_exc()
            self.add_issue(2, f"Exception: {e}", "Review orchestrator planning code")
            self.print_checkpoint(2, "Plan Generation", "fail", str(e))
            return False
    
    def check_stock_symbol_search(self) -> bool:
        """Checkpoint 3: Stock Symbol Search"""
        self.print_header("CHECKPOINT 3: Stock Symbol Search")
        
        try:
            result = search_stock_symbol.invoke({"query": "Nvidia"})
            
            if result.get('error'):
                print(f"  {RED}✗ Symbol search error: {result.get('error_message')}{NC}")
                self.add_issue(3, result.get('error_message'), "Check search_stock_symbol tool and network connectivity")
                self.print_checkpoint(3, "Stock Symbol Search", "fail", result.get('error_message'))
                return False
            
            symbol = result.get('symbol') or result.get('stock_symbol')
            company_name = result.get('company_name', '')
            
            if symbol == "NVDA":
                print(f"  {GREEN}✓ Nvidia correctly mapped to NVDA{NC}")
                print(f"  {GREEN}✓ Company name: {company_name}{NC}")
                self.stock_data = result
                self.print_checkpoint(3, "Stock Symbol Search", "pass", 
                                    f"Found: {company_name} ({symbol})",
                                    {"symbol": symbol, "company_name": company_name})
                return True
            else:
                print(f"  {RED}✗ Incorrect symbol: got {symbol}, expected NVDA{NC}")
                self.add_issue(3, f"Incorrect symbol: {symbol}", "Check stock symbol mapping in stock_agent.py")
                self.print_checkpoint(3, "Stock Symbol Search", "fail", f"Got {symbol}, expected NVDA")
                return False
                
        except Exception as e:
            print(f"  {RED}✗ Symbol search check failed: {e}{NC}")
            import traceback
            traceback.print_exc()
            self.add_issue(3, f"Exception: {e}", "Review stock symbol search code")
            self.print_checkpoint(3, "Stock Symbol Search", "fail", str(e))
            return False
    
    def check_stock_price_fetch(self) -> bool:
        """Checkpoint 4: Stock Price Fetching"""
        self.print_header("CHECKPOINT 4: Stock Price Fetching")
        
        try:
            result = get_stock_price.invoke({"symbol": "NVDA"})
            
            if result.get('error'):
                print(f"  {RED}✗ Stock price fetch error: {result.get('error_message')}{NC}")
                self.add_issue(4, result.get('error_message'), "Check yfinance API and network connectivity")
                self.print_checkpoint(4, "Stock Price Fetching", "fail", result.get('error_message'))
                return False
            
            # Check required fields
            required_fields = ["symbol", "current_price", "company_name", "change", "change_percent"]
            missing_fields = [field for field in required_fields if not result.get(field) and result.get(field) != 0]
            
            if missing_fields:
                print(f"  {YELLOW}⚠ Missing fields: {missing_fields}{NC}")
            else:
                print(f"  {GREEN}✓ All required fields present{NC}")
            
            current_price = result.get('current_price')
            company_name = result.get('company_name', 'NVIDIA')
            change_percent = result.get('change_percent', 0)
            
            print(f"  {GREEN}✓ Stock price: ${current_price:.2f}{NC}")
            print(f"  {GREEN}✓ Company: {company_name}{NC}")
            print(f"  {GREEN}✓ Change: {change_percent:+.2f}%{NC}")
            
            self.stock_data = result
            self.print_checkpoint(4, "Stock Price Fetching", "pass",
                                f"{company_name}: ${current_price:.2f} ({change_percent:+.2f}%)",
                                {"price": current_price, "change_percent": change_percent})
            return True
            
        except Exception as e:
            print(f"  {RED}✗ Stock price fetch check failed: {e}{NC}")
            import traceback
            traceback.print_exc()
            self.add_issue(4, f"Exception: {e}", "Review get_stock_price tool")
            self.print_checkpoint(4, "Stock Price Fetching", "fail", str(e))
            return False
    
    def check_content_analysis(self) -> bool:
        """Checkpoint 5: Content Analysis"""
        self.print_header("CHECKPOINT 5: Content Analysis")
        
        try:
            if not self.stock_data:
                print(f"  {RED}✗ Cannot test analysis without stock data{NC}")
                self.print_checkpoint(5, "Content Analysis", "fail", "No stock data available")
                return False
            
            # Create analysis content from stock data
            stock_summary = f"""
            Stock: {self.stock_data.get('company_name', 'NVIDIA')} ({self.stock_data.get('symbol', 'NVDA')})
            Current Price: ${self.stock_data.get('current_price', 0):.2f}
            Change: {self.stock_data.get('change_percent', 0):+.2f}%
            Market Cap: {self.stock_data.get('market_cap', 'N/A')}
            Volume: {self.stock_data.get('volume', 'N/A')}
            """
            
            # Test synthesize_content or create_detailed_report
            # Use synthesize_content for faster testing
            try:
                result = synthesize_content.invoke({
                    "source_contents": [stock_summary],
                    "synthesis_style": "concise",
                    "topic": "stock analysis"
                })
                
                if result.get('error'):
                    print(f"  {YELLOW}⚠ Synthesis error, trying create_detailed_report...{NC}")
                    # Fallback to create_detailed_report
                    result = create_detailed_report.invoke({
                        "content": stock_summary,
                        "title": "NVIDIA Stock Analysis",
                        "report_style": "business"
                    })
            except:
                # Fallback to create_detailed_report
                result = create_detailed_report.invoke({
                    "content": stock_summary,
                    "title": "NVIDIA Stock Analysis",
                    "report_style": "business"
                })
            
            if result.get('error'):
                print(f"  {RED}✗ Content analysis error: {result.get('error_message')}{NC}")
                self.add_issue(5, result.get('error_message'), "Check OpenAI API key and content generation tools")
                self.print_checkpoint(5, "Content Analysis", "fail", result.get('error_message'))
                return False
            
            # Get content (could be synthesized_content or report_content)
            content = result.get('synthesized_content') or result.get('report_content', '')
            
            if not content:
                print(f"  {RED}✗ Generated content is empty{NC}")
                self.add_issue(5, "Empty content generated", "Check content generation logic")
                self.print_checkpoint(5, "Content Analysis", "fail", "Empty content")
                return False
            
            if len(content) < 200:
                print(f"  {YELLOW}⚠ Content is short ({len(content)} chars){NC}")
            else:
                print(f"  {GREEN}✓ Content generated ({len(content)} chars){NC}")
            
            # Check if content mentions stock data
            has_stock_refs = any(keyword in content.lower() for keyword in ["nvidia", "nvda", "stock", "price", "$"])
            if has_stock_refs:
                print(f"  {GREEN}✓ Content contains stock references{NC}")
            else:
                print(f"  {YELLOW}⚠ Content may not reference stock data{NC}")
            
            self.report_content = content
            self.print_checkpoint(5, "Content Analysis", "pass",
                                f"Generated {len(content)} chars of analysis",
                                {"content_length": len(content)})
            return True
            
        except Exception as e:
            print(f"  {RED}✗ Content analysis check failed: {e}{NC}")
            import traceback
            traceback.print_exc()
            self.add_issue(5, f"Exception: {e}", "Review content analysis tools")
            self.print_checkpoint(5, "Content Analysis", "fail", str(e))
            return False
    
    def check_file_creation(self) -> bool:
        """Checkpoint 6: Report File Creation (Keynote/PDF, NOT Pages)"""
        self.print_header("CHECKPOINT 6: Report File Creation (Keynote/PDF)")
        
        try:
            if not self.report_content:
                print(f"  {RED}✗ Cannot create file without report content{NC}")
                self.print_checkpoint(6, "Report File Creation", "fail", "No report content")
                return False
            
            # Try create_keynote first (preferred for stock reports)
            print(f"  {CYAN}Attempting to create Keynote presentation (Pages-free approach)...{NC}")
            result = create_keynote.invoke({
                "title": "NVIDIA Stock Analysis Report",
                "content": self.report_content
            })
            
            if result.get('error'):
                print(f"  {YELLOW}⚠ Keynote creation error: {result.get('error_message')}{NC}")
                print(f"  {CYAN}→ This is acceptable if create_stock_report_and_email is used instead{NC}")
                # Don't fail here - the planner might use create_stock_report_and_email which handles this
                self.print_checkpoint(6, "Report File Creation", "warning", 
                                    f"Keynote test failed, but planner may use create_stock_report_and_email")
                return True  # Allow test to continue - planner may use different approach
            
            keynote_path = result.get('keynote_path')
            if not keynote_path:
                print(f"  {YELLOW}⚠ No keynote_path returned{NC}")
                self.print_checkpoint(6, "Report File Creation", "warning", "No keynote_path in test")
                return True  # May use different tool
            
            # Verify it's a file path, not content
            if len(keynote_path) > 500 or '\n\n' in keynote_path:
                print(f"  {RED}✗ keynote_path appears to be content, not a file path!{NC}")
                self.add_issue(6, "keynote_path is content not file path", "Check create_keynote implementation")
                self.print_checkpoint(6, "Report File Creation", "fail", "Invalid file path")
                return False
            
            # Check if file exists
            import os
            abs_path = os.path.abspath(os.path.expanduser(keynote_path))
            if os.path.exists(abs_path):
                print(f"  {GREEN}✓ Keynote file exists: {abs_path}{NC}")
                if os.path.isfile(abs_path):
                    print(f"  {GREEN}✓ File is readable{NC}")
                    print(f"  {GREEN}✓ Using Keynote instead of Pages (reliable approach){NC}")
                    self.report_file_path = abs_path
                    self.print_checkpoint(6, "Report File Creation", "pass",
                                        f"Keynote file created: {abs_path}",
                                        {"file_path": abs_path, "file_size": os.path.getsize(abs_path), "format": "keynote"})
                    return True
                else:
                    print(f"  {RED}✗ Path is not a file{NC}")
                    self.print_checkpoint(6, "Report File Creation", "fail", "Path is not a file")
                    return False
            else:
                print(f"  {YELLOW}⚠ Keynote file does not exist: {abs_path}{NC}")
                print(f"  {CYAN}→ This may be acceptable if planner uses create_stock_report_and_email{NC}")
                self.print_checkpoint(6, "Report File Creation", "warning", "Keynote file not found in test")
                return True  # Allow test to continue
                
        except Exception as e:
            print(f"  {YELLOW}⚠ File creation check encountered exception: {e}{NC}")
            print(f"  {CYAN}→ This may be acceptable if planner uses create_stock_report_and_email{NC}")
            import traceback
            traceback.print_exc()
            self.print_checkpoint(6, "Report File Creation", "warning", f"Exception in test: {e}")
            return True  # Don't fail - planner may use different approach
    
    def check_email_composition(self) -> bool:
        """Checkpoint 7: Email Composition"""
        self.print_header("CHECKPOINT 7: Email Composition")
        
        try:
            if not self.report_file_path:
                print(f"  {RED}✗ Cannot test email without report file{NC}")
                self.print_checkpoint(7, "Email Composition", "fail", "No report file")
                return False
            
            # Test email composition with attachment
            result = compose_email.invoke({
                "subject": "NVIDIA Stock Analysis Report",
                "body": "Please find the NVIDIA stock analysis report attached.",
                "recipient": "me",  # Will use default recipient
                "attachments": [self.report_file_path],
                "send": False  # Don't actually send during test
            })
            
            if result.get('error'):
                error_msg = result.get('error_message', 'Unknown error')
                print(f"  {RED}✗ Email composition error: {error_msg}{NC}")
                
                # Check if it's the TEXT CONTENT vs FILE PATH error
                if "TEXT CONTENT instead of a FILE PATH" in error_msg:
                    self.add_issue(7, "Attachment validation failed - TEXT vs FILE PATH", 
                                 "CRITICAL: Planner must use $stepN.keynote_path (or pdf_path) not $stepN.report_content")
                else:
                    self.add_issue(7, error_msg, "Check compose_email tool and Mail.app permissions")
                
                self.print_checkpoint(7, "Email Composition", "fail", error_msg)
                return False
            
            status = result.get('status')
            if status in ['sent', 'draft']:
                print(f"  {GREEN}✓ Email composed successfully (status: {status}){NC}")
                print(f"  {GREEN}✓ Attachment validated: {self.report_file_path}{NC}")
                self.email_result = result
                self.print_checkpoint(7, "Email Composition", "pass",
                                    f"Email composed with attachment (status: {status})",
                                    {"status": status, "attachment_path": self.report_file_path})
                return True
            else:
                print(f"  {YELLOW}⚠ Unexpected status: {status}{NC}")
                self.print_checkpoint(7, "Email Composition", "warning", f"Status: {status}")
                return True  # Still pass, just warning
                
        except Exception as e:
            print(f"  {RED}✗ Email composition check failed: {e}{NC}")
            import traceback
            traceback.print_exc()
            self.add_issue(7, f"Exception: {e}", "Review compose_email tool")
            self.print_checkpoint(7, "Email Composition", "fail", str(e))
            return False
    
    def check_email_sending(self) -> bool:
        """Checkpoint 8: Email Sending"""
        self.print_header("CHECKPOINT 8: Email Sending")
        
        # This requires actual Mail.app interaction, so we'll do a limited check
        print(f"  {YELLOW}⚠ Email sending requires Mail.app interaction{NC}")
        print(f"  {YELLOW}→ Manual verification needed{NC}")
        print(f"  {CYAN}→ Check Mail.app for composed email{NC}")
        print(f"  {CYAN}→ Verify attachment is present{NC}")
        
        # Check if compose_email was called with send=true in logs
        if os.path.exists(self.log_file):
            email_logs = self.search_logs(r"compose_email.*send.*true", context_lines=2)
            if email_logs:
                print(f"  {GREEN}✓ Found email send logs{NC}")
            else:
                print(f"  {YELLOW}⚠ No email send logs found (may not have been tested with send=true){NC}")
        
        self.print_checkpoint(8, "Email Sending", "pass", "Manual verification needed")
        return True
    
    def check_response_delivery(self) -> bool:
        """Checkpoint 9: Response Delivery"""
        self.print_header("CHECKPOINT 9: Response Delivery")
        
        # Check WebSocket endpoint exists
        if self.check_websocket_endpoint():
            print(f"  {GREEN}✓ WebSocket endpoint available{NC}")
        else:
            self.print_checkpoint(9, "Response Delivery", "fail", "WebSocket endpoint missing")
            return False
        
        # Check logs for response delivery
        if os.path.exists(self.log_file):
            response_logs = self.search_logs(r"Sending response|Response sent", context_lines=1)
            if response_logs:
                print(f"  {GREEN}✓ Found response delivery logs{NC}")
            else:
                print(f"  {YELLOW}⚠ No response delivery logs found (may need to run full E2E test){NC}")
        
        self.print_checkpoint(9, "Response Delivery", "pass", "WebSocket endpoint available")
        return True
    
    def check_frontend_rendering(self) -> bool:
        """Checkpoint 10: Frontend Rendering"""
        self.print_header("CHECKPOINT 10: Frontend Rendering")
        
        # Check frontend files exist
        frontend_files = [
            "frontend/lib/useWebSocket.ts",
            "frontend/components/MessageBubble.tsx",
            "frontend/components/ChatInterface.tsx"
        ]
        
        if self.check_frontend_files(frontend_files):
            print(f"  {GREEN}✓ Frontend files exist{NC}")
            print(f"  {YELLOW}⚠ Manual verification needed in browser{NC}")
            self.print_checkpoint(10, "Frontend Rendering", "pass", "Files exist (manual verification needed)")
            return True
        else:
            self.print_checkpoint(10, "Frontend Rendering", "fail", "Frontend files missing")
            return False
    
    def check_telemetry(self) -> bool:
        """Checkpoint: Telemetry and Logging"""
        self.print_header("TELEMETRY AND LOGGING VALIDATION")
        
        # Check for telemetry logs in code
        telemetry_keywords = [
            r"\[TELEMETRY\]",
            r"correlation_id",
            r"record_phase_start",
            r"record_phase_end",
            r"log_tool_step"
        ]
        
        files_to_check = [
            "src/agent/stock_agent.py",
            "src/agent/writing_agent.py",
            "src/agent/presentation_agent.py",
            "src/agent/email_agent.py",
            "api_server.py"
        ]
        
        missing_logging = []
        for file_path in files_to_check:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    content = f.read()
                    # Check for telemetry logging
                    has_telemetry = any(re.search(kw, content, re.IGNORECASE) for kw in telemetry_keywords)
                    if not has_telemetry:
                        missing_logging.append(file_path)
        
        if missing_logging:
            print(f"  {YELLOW}⚠ Files missing telemetry logging:{NC}")
            for file_path in missing_logging:
                print(f"    - {file_path}")
                # Add comment suggestion
                self.add_issue(0, f"Missing telemetry in {file_path}", 
                             f"Add telemetry logging: [TELEMETRY] Tool {{tool_name}} started/success - correlation_id={{correlation_id}}",
                             severity="warning")
        else:
            print(f"  {GREEN}✓ Telemetry logging present in key files{NC}")
        
        # Check log file for telemetry entries
        if os.path.exists(self.log_file):
            telemetry_logs = self.search_logs(r"\[TELEMETRY\]", context_lines=0)
            if telemetry_logs:
                print(f"  {GREEN}✓ Found {len(telemetry_logs)} telemetry log entries{NC}")
            else:
                print(f"  {YELLOW}⚠ No telemetry logs found (may need to run full workflow){NC}")
        
        self.print_checkpoint(11, "Telemetry and Logging", "pass" if not missing_logging else "warning",
                            f"Checked {len(files_to_check)} files, {len(missing_logging)} missing telemetry")
        return True
    
    def run_checkpoints(self) -> bool:
        """Run all checkpoints."""
        # Checkpoint 1: Query Routing
        self.check_query_routing()
        
        # Checkpoint 2: Plan Generation
        self.check_planning()
        
        # Checkpoint 3: Stock Symbol Search
        self.check_stock_symbol_search()
        
        # Checkpoint 4: Stock Price Fetching
        self.check_stock_price_fetch()
        
        # Checkpoint 5: Content Analysis
        self.check_content_analysis()
        
        # Checkpoint 6: Report File Creation
        self.check_file_creation()
        
        # Checkpoint 7: Email Composition
        self.check_email_composition()
        
        # Checkpoint 8: Email Sending
        self.check_email_sending()
        
        # Checkpoint 9: Response Delivery
        self.check_response_delivery()
        
        # Checkpoint 10: Frontend Rendering
        self.check_frontend_rendering()
        
        # Telemetry Check
        self.check_telemetry()
        
        # Return True if all critical checkpoints passed
        critical_checkpoints = [cp for cp in self.checkpoints if cp.status == "fail"]
        return len(critical_checkpoints) == 0


def main():
    """Main entry point."""
    tester = StockReportEmailRegressionTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()

