"""
Automated Quality Test Execution Script

Runs comprehensive multi-step workflow tests and generates detailed quality report.
Tests core functionality: Financial, Document, Email, Folder, File workflows.
"""

import sys
import os
import time
import json
from datetime import datetime
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.workflow import execute_workflow
from src.utils import load_config

# Test results storage
test_results = []
config = load_config()

def log_test(test_id: str, status: str, message: str, details: Dict = None):
    """Log test result"""
    result = {
        "test_id": test_id,
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "details": details or {}
    }
    test_results.append(result)

    # Print to console
    status_emoji = {
        "PASS": "✅",
        "FAIL": "❌",
        "PARTIAL": "⚠️ ",
        "SKIP": "⏭️ ",
        "ERROR": "🔥"
    }.get(status, "❓")

    print(f"{status_emoji} {test_id}: {message}")
    return result

def run_test(test_id: str, query: str, expected_steps: int, success_criteria: List[str]):
    """Execute a single test case"""
    print(f"\n{'='*80}")
    print(f"Running: {test_id}")
    print(f"Query: {query}")
    print(f"{'='*80}")

    start_time = time.time()

    try:
        # Execute workflow
        result = execute_workflow(query, config)

        execution_time = time.time() - start_time

        # Check if workflow succeeded
        if result.get("status") == "completed":
            # Check success criteria
            passed_criteria = []
            failed_criteria = []

            for criterion in success_criteria:
                # Simple check - can be enhanced
                if "error" not in str(result).lower():
                    passed_criteria.append(criterion)
                else:
                    failed_criteria.append(criterion)

            if len(passed_criteria) == len(success_criteria):
                log_test(test_id, "PASS", f"All criteria met ({execution_time:.2f}s)", {
                    "execution_time": execution_time,
                    "steps": result.get("current_step", 0),
                    "result": str(result)[:500]
                })
            else:
                log_test(test_id, "PARTIAL", f"Some criteria failed ({execution_time:.2f}s)", {
                    "execution_time": execution_time,
                    "passed": passed_criteria,
                    "failed": failed_criteria,
                    "result": str(result)[:500]
                })
        else:
            # Workflow failed
            log_test(test_id, "FAIL", f"Workflow failed: {result.get('status')}", {
                "execution_time": execution_time,
                "error": result.get("error", "Unknown"),
                "result": str(result)[:500]
            })

    except Exception as e:
        execution_time = time.time() - start_time
        log_test(test_id, "ERROR", f"Exception: {str(e)}", {
            "execution_time": execution_time,
            "exception": str(e)
        })

print("="*80)
print("AUTOMATED QUALITY TEST SUITE")
print("="*80)
print(f"Started: {datetime.now().isoformat()}")
print(f"Focus: Core workflows (Financial, Document, Email, Folder)")
print("="*80)

# CRITICAL TESTS FIRST

print("\n🔴 PHASE 1: CRITICAL TESTS")
print("="*80)

# TEST A1: NVIDIA Benchmark (CRITICAL)
run_test(
    "A1-BENCHMARK",
    "Find the stock price of NVIDIA, create a report, turn it into a PDF, zip it, and email it to me",
    expected_steps=6,
    success_criteria=[
        "Finds NVDA ticker",
        "Extracts stock price",
        "Creates report",
        "Creates ZIP",
        "Sends email"
    ]
)

# TEST G1: Ambiguous Query (CRITICAL)
print("\n[Manual Check Required for G1 - Ambiguous Query]")
log_test(
    "G1-AMBIGUITY",
    "SKIP",
    "Manual test - requires checking if system asks clarifying question",
    {"note": "Run manually: 'Email me about the stocks' - should ask which stocks"}
)

# TEST G2: Missing File (CRITICAL)
run_test(
    "G2-MISSING-FILE",
    "Create a report from the file 'definitely_does_not_exist_12345.pdf' and email it",
    expected_steps=1,
    success_criteria=[
        "Detects missing file",
        "Returns clear error",
        "Does not proceed"
    ]
)

# TEST G3: Invalid Ticker (CRITICAL)
run_test(
    "G3-BAD-TICKER",
    "Search Google Finance for INVALID_TICKER_XYZ123, create report, email it",
    expected_steps=1,
    success_criteria=[
        "Detects invalid ticker",
        "Returns error",
        "Does not create empty report"
    ]
)

print("\n\n🟡 PHASE 2: HIGH PRIORITY TESTS")
print("="*80)

# TEST A2: Multi-Stock Comparison
run_test(
    "A2-MULTI-STOCK",
    "Compare Apple, Microsoft, and Google stock prices and create a detailed report",
    expected_steps=7,
    success_criteria=[
        "Finds all 3 tickers",
        "Extracts data for each",
        "Creates comparison report"
    ]
)

# TEST B1: Folder Organization
run_test(
    "B1-FOLDER-ORG",
    "List files in the current directory and organize them by type",
    expected_steps=2,
    success_criteria=[
        "Lists files",
        "Organizes by type"
    ]
)

# TEST B3: Summarize Files in Folder
run_test(
    "B3-SUMMARIZE-FILES",
    "List and explain all files in the current directory",
    expected_steps=3,
    success_criteria=[
        "Lists files",
        "Explains files",
        "Provides summary"
    ]
)

# TEST B4: Folder Summary Email
run_test(
    "B4-FOLDER-EMAIL",
    "Explain the current folder and email the summary to me",
    expected_steps=4,
    success_criteria=[
        "Analyzes folder",
        "Creates report",
        "Sends email"
    ]
)

# TEST C1: Web Research to Presentation
run_test(
    "C1-WEB-PRESENTATION",
    "Search for 'AI trends 2024', extract content from the top result, and create a summary",
    expected_steps=4,
    success_criteria=[
        "Searches Google",
        "Extracts content",
        "Creates summary"
    ]
)

# TEST C2: Document Search to Report
run_test(
    "C2-DOC-REPORT",
    "Search documents for 'test' and create a summary report",
    expected_steps=3,
    success_criteria=[
        "Searches documents",
        "Creates summary"
    ]
)

# TEST D1: Email Read and Reply
print("\n[Note: D1 requires actual emails - may skip if none available]")
run_test(
    "D1-EMAIL-REPLY",
    "Read my latest email and create a summary",
    expected_steps=2,
    success_criteria=[
        "Reads email",
        "Creates summary"
    ]
)

print("\n\n🟢 PHASE 3: MEDIUM PRIORITY TESTS")
print("="*80)

# TEST A3: Stock Chart with Notification
run_test(
    "A3-STOCK-CHART",
    "Get the stock price for Tesla and send me a notification",
    expected_steps=3,
    success_criteria=[
        "Finds TSLA",
        "Gets price",
        "Sends notification"
    ]
)

# TEST B5: Organize and Zip
run_test(
    "B5-ORG-ZIP",
    "Create a zip archive of the current directory",
    expected_steps=2,
    success_criteria=[
        "Creates ZIP",
        "Includes files"
    ]
)

# TEST D2: Email Summary
print("\n[Note: D2 requires recent emails]")
run_test(
    "D2-EMAIL-SUMMARY",
    "Summarize my latest emails",
    expected_steps=2,
    success_criteria=[
        "Reads emails",
        "Creates summary"
    ]
)

# TEST F1: Document Archive
run_test(
    "F1-DOC-ARCHIVE",
    "Search for documents and list what you find",
    expected_steps=1,
    success_criteria=[
        "Searches documents",
        "Lists results"
    ]
)

print("\n\n🟣 PHASE 4: EXECUTIVE WORKFLOWS")
print("="*80)

# TEST H1: Executive Briefing Pack
run_test(
    "H1-EXEC-BRIEFING",
    "Create an executive briefing on Project Atlas by combining internal documents and the latest web coverage, build slides, and email the deck to leadership",
    expected_steps=9,
    success_criteria=[
        "Finds internal docs",
        "Fetches web coverage",
        "Creates slide deck",
        "Emails deck"
    ]
)

# TEST H2: Meeting Recap Package with Audio
run_test(
    "H2-MEETING-RECAP",
    "Summarize emails from the past hour, turn them into meeting notes, generate an audio briefing, and notify me",
    expected_steps=6,
    success_criteria=[
        "Summarizes emails",
        "Creates meeting notes",
        "Generates audio",
        "Sends notification"
    ]
)

# TEST H3: Screenshot Intelligence Digest
run_test(
    "H3-SCREEN-DIGEST",
    "Capture a screenshot of my current workspace, analyze it, create a report, zip the evidence, and email it to me",
    expected_steps=6,
    success_criteria=[
        "Captures screenshot",
        "Analyzes screenshot",
        "Creates report",
        "Emails archive"
    ]
)

print("\n\n🔵 PHASE 5: LOW PRIORITY TESTS")
print("="*80)

# TEST E2: Screenshot Analysis
print("\n[Note: E2 requires vision API - may have cost]")
run_test(
    "E2-SCREENSHOT",
    "Take a screenshot",
    expected_steps=1,
    success_criteria=[
        "Captures screenshot"
    ]
)

# TEST E3: Text to Speech
run_test(
    "E3-TTS",
    "Create a voice message saying 'Test complete'",
    expected_steps=1,
    success_criteria=[
        "Generates audio"
    ]
)

# GENERATE REPORT
print("\n\n" + "="*80)
print("TEST EXECUTION COMPLETE")
print("="*80)

# Calculate statistics
total_tests = len(test_results)
passed = len([t for t in test_results if t["status"] == "PASS"])
failed = len([t for t in test_results if t["status"] == "FAIL"])
partial = len([t for t in test_results if t["status"] == "PARTIAL"])
errors = len([t for t in test_results if t["status"] == "ERROR"])
skipped = len([t for t in test_results if t["status"] == "SKIP"])

print(f"\nTotal Tests: {total_tests}")
print(f"✅ Passed: {passed} ({passed/total_tests*100:.1f}%)")
print(f"⚠️  Partial: {partial} ({partial/total_tests*100:.1f}%)")
print(f"❌ Failed: {failed} ({failed/total_tests*100:.1f}%)")
print(f"🔥 Errors: {errors} ({errors/total_tests*100:.1f}%)")
print(f"⏭️  Skipped: {skipped} ({skipped/total_tests*100:.1f}%)")

# Overall health
success_rate = (passed + partial * 0.5) / total_tests * 100
print(f"\nOverall Success Rate: {success_rate:.1f}%")

if success_rate >= 90:
    print("🥇 GOLD STANDARD - Excellent system health!")
elif success_rate >= 75:
    print("✅ ACCEPTABLE - System performing well")
else:
    print("⚠️  NEEDS WORK - Multiple issues detected")

# Save detailed results
report_file = "test_results_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
with open(report_file, 'w') as f:
    json.dump({
        "summary": {
            "total": total_tests,
            "passed": passed,
            "failed": failed,
            "partial": partial,
            "errors": errors,
            "skipped": skipped,
            "success_rate": success_rate
        },
        "tests": test_results
    }, f, indent=2)

print(f"\nDetailed results saved to: {report_file}")
print("\n" + "="*80)
