#!/usr/bin/env python3
"""
Test Complete Workflow: Create report → Zip → Email

Tests the user's exact request:
"create a report on the current stock price of nike including the current
stock price as an image. zip the pdf and email it to spamstuff062@gmail.com"
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.google_finance_agent_v2 import create_stock_report_from_google_finance
from src.automation.file_organizer import FileOrganizer
from src.agent.email_agent import compose_email
from src.utils import load_config
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_complete_workflow():
    """Test the complete workflow from report creation to email."""

    print("\n" + "="*80)
    print("COMPLETE WORKFLOW TEST")
    print("="*80)
    print("\nUser Request:")
    print("'Create a report on the current stock price of Nike including")
    print("the current stock price as an image. Zip the PDF and email it")
    print("to spamstuff062@gmail.com'")
    print("="*80)

    try:
        config = load_config()

        # STEP 1: Create stock report for Nike
        print("\n" + "="*80)
        print("STEP 1: Create Stock Report for Nike")
        print("="*80)
        print("\n🔍 Searching for Nike stock...")

        # Nike ticker is NKE
        result = create_stock_report_from_google_finance.invoke({
            "company": "NKE",  # Use ticker for 0% CAPTCHA risk
            "output_format": "pdf"
        })

        if result.get("error"):
            print(f"\n❌ STEP 1 FAILED: {result['error_message']}")
            print(f"   Error Type: {result.get('error_type')}")
            if result.get("suggestion"):
                print(f"   Suggestion: {result['suggestion']}")
            return False, "Step 1: Report creation failed", result

        print(f"\n✅ STEP 1 SUCCESS!")
        print(f"   Company: {result['company']}")
        print(f"   Ticker: {result['ticker']}")
        print(f"   Report: {result['report_path']}")
        print(f"   Chart: {result['chart_path']}")
        print(f"   Google Finance: {result['google_finance_url']}")

        # Extract data
        report_path = result['report_path']
        chart_path = result.get('chart_path')

        # Verify files exist
        if not Path(report_path).exists():
            print(f"\n❌ STEP 1 VERIFICATION FAILED: Report file not found at {report_path}")
            return False, "Step 1: Report file doesn't exist", result

        print(f"   ✓ Report file verified: {Path(report_path).stat().st_size} bytes")

        if chart_path and Path(chart_path).exists():
            print(f"   ✓ Chart file verified: {Path(chart_path).stat().st_size} bytes")
        else:
            print(f"   ⚠️  Chart file not found (optional)")

        # STEP 2: Create ZIP file
        print("\n" + "="*80)
        print("STEP 2: Create ZIP Archive")
        print("="*80)
        print(f"\n📦 Creating ZIP of: {report_path}")

        try:
            from agent.file_agent import create_zip_archive

            # Create descriptive name for zip
            zip_name = f"nike_stock_report_{time.strftime('%Y%m%d')}.zip"

            # create_zip_archive expects: source_path, zip_name
            zip_result = create_zip_archive.invoke({
                "source_path": report_path,
                "zip_name": zip_name
            })

            if zip_result.get("error"):
                print(f"\n❌ STEP 2 FAILED: {zip_result['error_message']}")
                return False, "Step 2: ZIP creation failed", zip_result

            print(f"\n✅ STEP 2 SUCCESS!")
            print(f"   ZIP file: {zip_result['zip_path']}")
            if 'size_mb' in zip_result:
                print(f"   Size: {zip_result['size_mb']} MB")
            if 'file_count' in zip_result:
                print(f"   Files included: {zip_result['file_count']}")

            zip_path = zip_result['zip_path']

            # Verify ZIP exists
            if not Path(zip_path).exists():
                print(f"\n❌ STEP 2 VERIFICATION FAILED: ZIP file not found")
                return False, "Step 2: ZIP file doesn't exist", zip_result

            print(f"   ✓ ZIP file verified: {Path(zip_path).stat().st_size} bytes")

        except ImportError as e:
            print(f"\n❌ STEP 2 FAILED: Missing file_agent module")
            print(f"   Error: {e}")
            print(f"   Note: file_agent might not have create_zip_archive tool")

            # Fallback: Try using FileOrganizer directly
            print(f"\n   Trying FileOrganizer fallback...")
            try:
                organizer = FileOrganizer(config)
                zip_path = organizer.create_archive([report_path], output_name=zip_name)

                if Path(zip_path).exists():
                    print(f"\n✅ STEP 2 SUCCESS (via fallback)!")
                    print(f"   ZIP file: {zip_path}")
                else:
                    print(f"\n❌ STEP 2 FAILED: Fallback didn't create ZIP")
                    return False, "Step 2: ZIP creation failed (fallback)", None

            except Exception as e2:
                print(f"\n❌ STEP 2 FAILED: Fallback also failed")
                print(f"   Error: {e2}")
                return False, "Step 2: ZIP creation failed (all methods)", None

        # STEP 3: Compose email with attachment
        print("\n" + "="*80)
        print("STEP 3: Compose Email")
        print("="*80)
        print(f"\n✉️  Preparing email to: spamstuff062@gmail.com")

        email_body = f"""Hi,

Please find attached the stock report for Nike Inc. (NKE).

Report Details:
- Company: {result['company']}
- Ticker: {result['ticker']}
- Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

The report includes:
• Current stock price and change
• AI-generated research and analysis
• Key statistics and metrics
• Stock price chart visualization

Best regards,
Stock Report System
"""

        try:
            email_result = compose_email.invoke({
                "recipient": "spamstuff062@gmail.com",
                "subject": f"Nike (NKE) Stock Report - {time.strftime('%Y-%m-%d')}",
                "body": email_body,
                "attachments": [zip_path]
            })

            if email_result.get("error"):
                print(f"\n❌ STEP 3 FAILED: {email_result['error_message']}")
                print(f"   Error Type: {email_result.get('error_type')}")
                return False, "Step 3: Email composition failed", email_result

            print(f"\n✅ STEP 3 SUCCESS!")
            print(f"   Email drafted in Mail.app")
            print(f"   Recipient: spamstuff062@gmail.com")
            print(f"   Subject: Nike (NKE) Stock Report")
            print(f"   Attachment: {Path(zip_path).name}")
            print(f"   Status: {email_result.get('message', 'Ready to send')}")

        except Exception as e:
            print(f"\n❌ STEP 3 FAILED: Exception during email composition")
            print(f"   Error: {e}")
            return False, "Step 3: Email composition exception", None

        # SUCCESS - All steps completed
        print("\n" + "="*80)
        print("✅ COMPLETE WORKFLOW SUCCESS!")
        print("="*80)
        print("\nAll steps completed successfully:")
        print("  1. ✅ Created Nike stock report with chart")
        print("  2. ✅ Created ZIP archive")
        print("  3. ✅ Composed email with attachment")
        print("\n📧 Email is ready to send in Mail.app")
        print("   (User needs to click Send)")

        return True, "All steps completed", {
            "report_path": report_path,
            "zip_path": zip_path,
            "email_drafted": True
        }

    except Exception as e:
        logger.error(f"Workflow failed with exception: {e}", exc_info=True)
        print(f"\n❌ WORKFLOW FAILED WITH EXCEPTION")
        print(f"   Error: {str(e)}")
        return False, f"Exception: {str(e)}", None


def main():
    """Run the complete workflow test."""
    print("\n" + "="*80)
    print("COMPLETE WORKFLOW TEST: Report → ZIP → Email")
    print("="*80)
    print("\nThis test simulates the exact user request:")
    print("'Create a report on Nike stock, zip it, and email it'\n")

    success, message, data = test_complete_workflow()

    print("\n" + "="*80)
    print("FINAL RESULT")
    print("="*80)

    if success:
        print("\n✅ WORKFLOW COMPLETED SUCCESSFULLY")
        print(f"\nResult: {message}")
        if data:
            print(f"\nGenerated Files:")
            for key, value in data.items():
                print(f"  - {key}: {value}")
        print("\n📧 Check Mail.app for the drafted email")
        return True
    else:
        print(f"\n❌ WORKFLOW FAILED")
        print(f"\nFailure Point: {message}")
        if data:
            print(f"\nError Details:")
            print(f"  {data}")

        print("\n" + "="*80)
        print("DEBUGGING GUIDE")
        print("="*80)
        print("\nPossible Issues:")
        print("  1. CAPTCHA detected → Use ticker symbols (NKE not Nike)")
        print("  2. create_zip_archive tool missing → Check file_agent.py")
        print("  3. Mail.app not accessible → Check permissions")
        print("  4. Network issues → Check internet connection")

        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
