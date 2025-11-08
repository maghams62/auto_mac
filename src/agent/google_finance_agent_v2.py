"""
Google Finance Agent V2 - Using Google Search API + Playwright for screenshots.

Simplified approach:
1. Use Google Search API to find Google Finance URL
2. Use Playwright to navigate and take screenshot
3. Extract basic data from the page
"""

import logging
from typing import Dict, Any, Optional
from langchain_core.tools import tool
import time
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@tool
def search_google_finance_stock(company: str) -> Dict[str, Any]:
    """
    Search for a company on Google Finance.

    For ticker symbols (short uppercase strings), tries direct URL construction.
    For company names, uses browser search.

    Args:
        company: Company name or ticker symbol (e.g., "Nike", "NKE", "Microsoft")

    Returns:
        Dictionary with stock page URL, ticker, and company name
    """
    logger.info(f"[GOOGLE FINANCE V2] Searching for: {company}")

    try:
        from automation.web_browser import SyncWebBrowser
        from utils import load_config

        config = load_config()

        # STRATEGY 1: If it looks like a ticker, try direct URLs first
        company_upper = company.upper().strip()
        if len(company_upper) <= 5 and company_upper.isalpha():
            logger.info(f"[GOOGLE FINANCE V2] Looks like ticker symbol, trying direct URLs")

            # Try common exchanges
            exchanges = ["NYSE", "NASDAQ", "NYSEAMERICAN"]

            for exchange in exchanges:
                direct_url = f"https://www.google.com/finance/quote/{company_upper}:{exchange}"
                logger.info(f"[GOOGLE FINANCE V2] Trying: {direct_url}")

                browser = SyncWebBrowser(config, headless=False)
                nav_result = browser.navigate(direct_url, wait_until="domcontentloaded")

                if nav_result.get("success"):
                    time.sleep(2)

                    # Check if page has valid stock data (check title instead of content)
                    page_url = nav_result.get("url", "")
                    page_title = nav_result.get("title", "")

                    # Valid Google Finance pages have the stock ticker in the title
                    if company_upper in page_title and "Stock Price" in page_title:
                        logger.info(f"[GOOGLE FINANCE V2] Found via direct URL: {direct_url}")
                        logger.info(f"[GOOGLE FINANCE V2] Page title: {page_title}")
                        browser.close()

                        return {
                            "success": True,
                            "url": direct_url,
                            "ticker": company_upper,
                            "ticker_full": f"{company_upper}:{exchange}",
                            "exchange": exchange,
                            "company_name": company,
                            "method": "direct_url",
                            "message": f"Found {company} ({company_upper}) on {exchange}"
                        }

                browser.close()

        # STRATEGY 2: Search using Google (for company names or if direct URL failed)
        logger.info(f"[GOOGLE FINANCE V2] Trying Google search")
        browser = SyncWebBrowser(config, headless=False)

        search_query = f"{company} stock google finance"
        logger.info(f"[GOOGLE FINANCE V2] Google search query: {search_query}")

        search_result = browser.google_search(search_query, num_results=10)

        if search_result.get("success"):
            results = search_result.get("results", [])

            # Find Google Finance URL
            for result in results:
                url = result.get("link", result.get("url", ""))
                if "google.com/finance/quote/" in url:
                    logger.info(f"[GOOGLE FINANCE V2] Found Google Finance URL: {url}")

                    # Extract ticker from URL
                    ticker_match = re.search(r'/quote/([^/\?]+)', url)
                    if ticker_match:
                        ticker_full = ticker_match.group(1)
                        ticker_parts = ticker_full.split(':')
                        ticker = ticker_parts[0]
                        exchange = ticker_parts[1] if len(ticker_parts) > 1 else "UNKNOWN"

                        browser.close()

                        return {
                            "success": True,
                            "url": url,
                            "ticker": ticker,
                            "ticker_full": ticker_full,
                            "exchange": exchange,
                            "company_name": company,
                            "method": "browser_google_search",
                            "message": f"Found {company} ({ticker}) via Browser Google Search"
                        }

        browser.close()

        # No Google Finance URL found
        return {
            "error": True,
            "error_type": "StockNotFound",
            "error_message": f"Could not find Google Finance page for: {company}",
            "suggestion": "Try using the exact ticker symbol (e.g., NKE for Nike)",
            "retry_possible": True
        }

    except Exception as e:
        logger.error(f"[GOOGLE FINANCE V2] Error searching: {e}", exc_info=True)
        return {
            "error": True,
            "error_type": "SearchError",
            "error_message": str(e),
            "retry_possible": True
        }


@tool
def extract_google_finance_research(url: str) -> Dict[str, Any]:
    """
    Extract Google's AI research and price data from a Google Finance page.

    Args:
        url: Google Finance URL

    Returns:
        Dictionary with price data and research text
    """
    logger.info(f"[GOOGLE FINANCE V2] Extracting research from: {url}")

    try:
        from automation.web_browser import SyncWebBrowser
        from utils import load_config

        config = load_config()
        browser = SyncWebBrowser(config, headless=False)

        # Navigate to page
        nav_result = browser.navigate(url, wait_until="networkidle")
        if not nav_result.get("success"):
            return {
                "error": True,
                "error_message": f"Failed to navigate to {url}",
                "retry_possible": True
            }

        # Wait for content to load and scroll to trigger lazy loading
        time.sleep(3)

        # Scroll down to load dynamic content
        try:
            browser.evaluate("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(2)
        except:
            pass

        page_content = browser.get_page_content()

        # Extract research data from the specific div you mentioned
        # <div jsname="Ldp1ib" class="pzbfwb">
        data = {
            "price": None,
            "change": None,
            "research": None,
            "raw_html": page_content
        }

        # Try to extract price using browser's evaluation
        try:
            price_text = browser.evaluate("""
                () => {
                    const priceElem = document.querySelector('div.YMlKec.fxKbKc');
                    return priceElem ? priceElem.textContent : null;
                }
            """)
            if price_text:
                data["price"] = price_text.strip()
        except Exception as e:
            logger.warning(f"Could not extract price: {e}")

        # Extract research from the div you specified - try multiple selectors
        try:
            research_text = browser.evaluate("""
                () => {
                    // Try the specific jsname first
                    let researchDiv = document.querySelector('div[jsname="Ldp1ib"]');
                    if (researchDiv) {
                        const paragraphs = researchDiv.querySelectorAll('p.ZVghMd, p');
                        if (paragraphs.length > 0) {
                            return Array.from(paragraphs).map(p => p.textContent).join('\\n\\n');
                        }
                    }

                    // Try alternative selectors for research/about section
                    researchDiv = document.querySelector('div.pzbfwb, div[data-id]');
                    if (researchDiv) {
                        const paragraphs = researchDiv.querySelectorAll('p');
                        if (paragraphs.length > 0) {
                            return Array.from(paragraphs).map(p => p.textContent).join('\\n\\n');
                        }
                    }

                    return null;
                }
            """)
            if research_text:
                data["research"] = research_text.strip()
                logger.info(f"Research extracted: {len(research_text)} chars")
        except Exception as e:
            logger.warning(f"Could not extract research: {e}")

        browser.close()

        if data["research"] or data["price"]:
            return {
                "success": True,
                "data": data,
                "message": "Research data extracted"
            }
        else:
            return {
                "error": True,
                "error_message": "Could not extract research data from page",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"[GOOGLE FINANCE V2] Error extracting research: {e}", exc_info=True)
        return {
            "error": True,
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def capture_google_finance_chart(url: str, output_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Capture screenshot of Google Finance chart.

    Args:
        url: Google Finance URL
        output_name: Optional output filename (without extension)

    Returns:
        Dictionary with screenshot path
    """
    logger.info(f"[GOOGLE FINANCE V2] Capturing chart from: {url}")

    try:
        from automation.web_browser import SyncWebBrowser
        from utils import load_config

        config = load_config()
        browser = SyncWebBrowser(config, headless=False)

        # Navigate to page
        nav_result = browser.navigate(url, wait_until="networkidle")
        if not nav_result.get("success"):
            return {
                "error": True,
                "error_message": f"Failed to navigate to {url}",
                "retry_possible": True
            }

        # Wait for chart to load
        time.sleep(3)

        # Take screenshot
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not output_name:
            # Extract ticker from URL
            ticker_match = re.search(r'/quote/([^/:]+)', url)
            ticker = ticker_match.group(1) if ticker_match else "stock"
            output_name = f"{ticker.lower()}_gfinance_{timestamp}"

        screenshots_dir = Path(config.get("data_dir", "data")) / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshots_dir / f"{output_name}.png"

        screenshot_result = browser.take_screenshot(str(screenshot_path), full_page=True)

        browser.close()

        if screenshot_result.get("success"):
            return {
                "success": True,
                "screenshot_path": str(screenshot_path),
                "url": url,
                "message": f"Chart screenshot saved to {screenshot_path}"
            }
        else:
            return {
                "error": True,
                "error_message": "Failed to capture screenshot",
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"[GOOGLE FINANCE V2] Error capturing chart: {e}")
        return {
            "error": True,
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def create_stock_report_from_google_finance(company: str, output_format: str = "pdf") -> Dict[str, Any]:
    """
    Create complete stock report from Google Finance.

    HIGH-LEVEL TOOL - Does everything in one command:
    1. Search for company on Google Finance
    2. Capture chart screenshot
    3. Create report (PDF or presentation)

    Args:
        company: Company name or ticker (e.g., "Nike", "NKE")
        output_format: "pdf" or "presentation"

    Returns:
        Dictionary with report path, chart path, and data
    """
    logger.info(f"[GOOGLE FINANCE V2] Creating {output_format} for: {company}")

    try:
        # Step 1: Search for stock
        logger.info(f"[GOOGLE FINANCE V2] Searching for: {company}")
        search_result = search_google_finance_stock.invoke({"company": company})

        if search_result.get("error"):
            return search_result

        url = search_result["url"]
        ticker = search_result["ticker"]
        company_name = search_result.get("company_name", company)

        # Step 2: Extract research data
        logger.info(f"[GOOGLE FINANCE V2] Extracting research data")
        research_result = extract_google_finance_research.invoke({"url": url})

        research_data = {}
        if not research_result.get("error"):
            research_data = research_result.get("data", {})
            research_text = research_data.get('research') or ''
            logger.info(f"[GOOGLE FINANCE V2] Research extracted: {len(research_text)} chars")
        else:
            logger.warning(f"[GOOGLE FINANCE V2] Research extraction failed: {research_result.get('error_message')}")

        # Step 3: Capture chart
        logger.info(f"[GOOGLE FINANCE V2] Capturing chart")
        chart_result = capture_google_finance_chart.invoke({
            "url": url,
            "output_name": f"{ticker.lower()}_gfinance"
        })

        if chart_result.get("error"):
            logger.warning(f"[GOOGLE FINANCE V2] Chart capture failed: {chart_result.get('error_message')}")
            chart_path = None
        else:
            chart_path = chart_result["screenshot_path"]

        # Step 4: Create report
        logger.info(f"[GOOGLE FINANCE V2] Creating {output_format}")

        from automation.report_generator import ReportGenerator
        from utils import load_config

        config = load_config()
        report_gen = ReportGenerator(config)

        # Build report content with research
        title = f"{company_name} ({ticker}) Stock Report"

        # Include price if available
        price_info = ""
        if research_data.get("price"):
            price_info = f"\nCurrent Price: {research_data['price']}"

        content = f"""
Stock Information for {company_name} ({ticker}){price_info}

Source: Google Finance
URL: {url}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

This report includes the current stock chart and AI-generated research from Google Finance.
"""

        sections = []

        # Add price summary if available
        if research_data.get("price"):
            sections.append({
                "title": "Current Price",
                "content": f"**{research_data['price']}**"
            })

        # Add AI research if available
        if research_data.get("research"):
            sections.append({
                "title": "Market Analysis (AI-Generated)",
                "content": research_data['research']
            })

        # Add data source
        sections.append({
            "title": "Data Source",
            "content": f"Google Finance: {url}"
        })

        # Create report with image
        image_paths = [chart_path] if chart_path else None

        timestamp = datetime.now().strftime("%Y%m%d")
        output_name = f"{ticker.lower()}_gfinance_report_{timestamp}"

        report_result = report_gen.create_report(
            title=title,
            content=content,
            sections=sections,
            image_paths=image_paths,
            export_pdf=(output_format == "pdf"),
            output_name=output_name
        )

        if report_result.get("success"):
            # Get report path - prefer PDF, fallback to HTML if PDF failed
            if output_format == "pdf":
                report_path = report_result.get("pdf_path") or report_result.get("html_path")
            else:
                report_path = report_result.get("html_path")

            return {
                "success": True,
                "company": company_name,
                "ticker": ticker,
                "google_finance_url": url,
                "chart_path": chart_path,
                "report_path": report_path,
                "presentation_path": report_result.get("html_path"),
                "message": f"Stock report created for {company_name} ({ticker})"
            }
        else:
            return {
                "error": True,
                "error_message": "Failed to create report",
                "chart_path": chart_path,  # Still return chart path
                "retry_possible": True
            }

    except Exception as e:
        logger.error(f"[GOOGLE FINANCE V2] Error creating report: {e}", exc_info=True)
        return {
            "error": True,
            "error_message": str(e),
            "retry_possible": False
        }


# Tool registry
GOOGLE_FINANCE_V2_AGENT_TOOLS = [
    search_google_finance_stock,
    extract_google_finance_research,
    capture_google_finance_chart,
    create_stock_report_from_google_finance,
]
