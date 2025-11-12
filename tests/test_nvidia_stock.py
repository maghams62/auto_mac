#!/usr/bin/env python3
"""
Test NVIDIA stock report generation and email sending.
"""
from src.agent.google_finance_agent import create_stock_report_from_google_finance
from src.agent.email_agent import compose_email
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("=== Testing NVIDIA Stock Report Generation ===")

    # Step 1: Create stock report/presentation
    logger.info("Step 1: Creating NVIDIA stock presentation...")
    result = create_stock_report_from_google_finance.invoke({
        'company': 'NVDA',
        'output_format': 'presentation'
    })

    logger.info("\n=== Stock Report Result ===")
    print(json.dumps(result, indent=2, default=str))

    if result.get("error"):
        logger.error(f"Failed to create stock report: {result.get('error_message')}")
        return

    # Step 2: Send email with the presentation
    presentation_path = result.get("presentation_path")
    company = result.get("company", "NVIDIA")
    ticker = result.get("ticker", "NVDA")
    price_data = result.get("price_data", {})

    # Construct email body with price data
    email_body = f"""Stock Analysis Report for {company} ({ticker})

"""

    if price_data:
        price = price_data.get("price", "N/A")
        change = price_data.get("change", "N/A")
        email_body += f"""Current Price: {price}
Price Change: {change}

"""

    email_body += """Please find the detailed stock analysis presentation attached.

Best regards,
Automation Assistant"""

    logger.info("\nStep 2: Sending email with presentation...")
    email_result = compose_email.invoke({
        "subject": f"{company} ({ticker}) Stock Analysis",
        "body": email_body,
        "recipient": "me",  # Will use default_recipient from config
        "attachments": [presentation_path] if presentation_path else None,
        "send": True
    })

    logger.info("\n=== Email Result ===")
    print(json.dumps(email_result, indent=2, default=str))

    if email_result.get("error"):
        logger.error(f"Failed to send email: {email_result.get('error_message')}")
    else:
        logger.info("✅ Successfully created presentation and sent email!")

if __name__ == "__main__":
    main()
