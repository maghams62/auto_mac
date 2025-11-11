"""
Google Finance Agent - Extract stock data and research from Google Finance.

This agent uses Playwright to:
1. Search for company on Google Finance
2. Navigate to the stock page
3. Extract AI-generated research
4. Capture chart screenshot
5. Compile data into reports/presentations
"""

import logging
from typing import Dict, Any, Optional
from langchain_core.tools import tool
import time
import re

logger = logging.getLogger(__name__)


@tool
def search_google_finance_stock(company: str) -> Dict[str, Any]:
    """
    Search for a company on Google Finance and get the stock page URL.

    Args:
        company: Company name or ticker symbol (e.g., "Palantir", "PLTR", "Microsoft")

    Returns:
        Dictionary with stock page URL, ticker, and company name

    Example:
        search_google_finance_stock("Palantir")
        # Returns: {"url": "https://www.google.com/finance/quote/PLTR:NASDAQ", "ticker": "PLTR", ...}
    """
    logger.info(f"[GOOGLE FINANCE AGENT] Searching for: {company}")

    try:
        from automation.web_browser import SyncWebBrowser
        from utils import load_config

        config = load_config()
        # Use non-headless mode with realistic user agent to avoid CAPTCHAs
        browser = SyncWebBrowser(config, headless=False)

        # STRATEGY 1: Try direct Google Finance URL first (avoids Google Search CAPTCHA)
        # Construct likely Google Finance URL
        search_term = company.upper().strip()

        # Try common ticker patterns first
        if len(search_term) <= 5 and search_term.isalpha():
            # Looks like a ticker - try direct access
            for exchange in ["NASDAQ", "NYSE", "NSE", "BSE"]:
                direct_url = f"https://www.google.com/finance/quote/{search_term}:{exchange}"
                logger.info(f"[GOOGLE FINANCE AGENT] Trying direct URL: {direct_url}")

                nav_result = browser.navigate(direct_url, wait_until="networkidle")
                if nav_result.get("success"):
                    time.sleep(2)

                    # Check if page loaded successfully (not 404)
                    page_content = browser.get_page_content()

                    if "404" not in page_content and "not found" not in page_content.lower():
                        # Found it!
                        company_name = company
                        try:
                            # Try to get actual company name from page
                            name_elem = browser.locator('div[class*="zzDege"]').first
                            if name_elem:
                                import asyncio
                                company_name = asyncio.get_event_loop().run_until_complete(name_elem.text_content()).strip()
                        except:
                            pass

                        return {
                            "success": True,
                            "url": direct_url,
                            "ticker": search_term,
                            "ticker_full": f"{search_term}:{exchange}",
                            "exchange": exchange,
                            "company_name": company_name,
                            "method": "direct_url",
                            "message": f"Found {company_name} ({search_term}) via direct URL"
                        }

        # STRATEGY 2: Use Google Finance search directly (not Google Search)
        # This avoids the main Google Search CAPTCHAs
        finance_search_url = f"https://www.google.com/finance/search?q={company.replace(' ', '+')}"
        logger.info(f"[GOOGLE FINANCE AGENT] Using Google Finance search: {finance_search_url}")

        nav_result = browser.navigate(finance_search_url, wait_until="networkidle")

        if not nav_result.get("success"):
            browser.close()
            return {
                "error": True,
                "error_type": "NavigationError",
                "error_message": f"Failed to search for {company}",
                "retry_possible": True
            }

        # Wait for page to load
        time.sleep(2)
        page = browser.page

        # Check for CAPTCHA
        page_content = page.content()
        if "captcha" in page_content.lower() or "unusual traffic" in page_content.lower():
            browser.close()
            return {
                "error": True,
                "error_type": "CAPTCHADetected",
                "error_message": "Google detected unusual traffic and showed a CAPTCHA. Please try again in a few minutes or use a direct ticker symbol.",
                "retry_possible": True,
                "suggestion": "Try using the exact ticker symbol (e.g., PLTR, MSFT) for direct access"
            }

        # STRATEGY 2: Look for search results on Google Finance search page
        try:
            # Google Finance search results appear as clickable items
            search_results = page.locator('div[class*="SxEHyc"], a[href*="/finance/quote"]').all()

            for result in search_results[:3]:  # Check first 3 results
                try:
                    href = result.get_attribute('href')
                    if href and '/finance/quote/' in href:
                        # Extract ticker from URL
                        ticker_match = re.search(r'/quote/([^/\?]+)', href)
                        if ticker_match:
                            ticker_full = ticker_match.group(1)
                            ticker_parts = ticker_full.split(':')
                            ticker = ticker_parts[0]
                            exchange = ticker_parts[1] if len(ticker_parts) > 1 else "UNKNOWN"

                            # Get company name
                            company_name = result.text_content().strip() or company

                            # Make URL absolute
                            if not href.startswith('http'):
                                href = f"https://www.google.com{href}"

                            browser.close()
                            return {
                                "success": True,
                                "url": href,
                                "ticker": ticker,
                                "ticker_full": ticker_full,
                                "exchange": exchange,
                                "company_name": company_name,
                                "method": "finance_search",
                                "message": f"Found {company_name} ({ticker}) via Google Finance search"
                            }
                except Exception as e:
                    continue

        except Exception as e:
            logger.warning(f"[GOOGLE FINANCE AGENT] Error parsing search results: {e}")

        browser.close()

        return {
            "error": True,
            "error_type": "StockNotFound",
            "error_message": f"Could not find Google Finance page for: {company}",
            "retry_possible": True,
            "suggestion": "Try using the exact ticker symbol (e.g., PLTR, MSFT)"
        }

    except Exception as e:
        logger.error(f"[GOOGLE FINANCE AGENT] Error searching: {e}")
        return {
            "error": True,
            "error_type": "SearchError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def extract_google_finance_data(url: str) -> Dict[str, Any]:
    """
    Extract stock data and AI research from a Google Finance page.

    Extracts:
    - Current price and change
    - AI-generated research summary
    - Key statistics
    - About section

    Args:
        url: Google Finance URL (e.g., "https://www.google.com/finance/quote/PLTR:NASDAQ")

    Returns:
        Dictionary with price, research, statistics, and raw content

    Example:
        extract_google_finance_data("https://www.google.com/finance/quote/PLTR:NASDAQ")
    """
    logger.info(f"[GOOGLE FINANCE AGENT] Extracting data from: {url}")

    try:
        from automation.web_browser import SyncWebBrowser
        from utils import load_config

        config = load_config()
        browser = SyncWebBrowser(config, headless=False)

        # Navigate to the stock page
        nav_result = browser.navigate(url, wait_until="networkidle")

        if not nav_result.get("success"):
            return {
                "error": True,
                "error_type": "NavigationError",
                "error_message": f"Failed to load {url}",
                "retry_possible": True
            }

        # Wait for content to load
        time.sleep(3)

        page = browser.page

        # Check for CAPTCHA
        page_content = page.content()
        if "captcha" in page_content.lower() or "unusual traffic" in page_content.lower():
            browser.close()
            return {
                "error": True,
                "error_type": "CAPTCHADetected",
                "error_message": "Google detected unusual traffic. Please wait a few minutes before trying again.",
                "retry_possible": True
            }

        # Extract stock price - try multiple selectors for robustness
        price_data = {}
        try:
            # Try primary price selector
            price_elem = page.locator('div[class*="YMlKec fxKbKc"]').first
            try:
                price_text = price_elem.text_content(timeout=2000)
                if price_text and price_text.strip():
                    price_data["price"] = price_text.strip()
                    logger.info(f"[GOOGLE FINANCE AGENT] Extracted price: {price_data['price']}")
            except:
                pass

            # Try alternative price selectors if primary failed
            if not price_data.get("price"):
                alt_selectors = [
                    'div[data-field="regularMarketPrice"]',
                    'span[data-field="regularMarketPrice"]',
                    'div[jsname="vWLAgc"]',
                    '[data-last-price]'
                ]
                for selector in alt_selectors:
                    try:
                        alt_elem = page.locator(selector).first
                        price_text = alt_elem.text_content(timeout=1000)
                        if price_text and price_text.strip():
                            price_data["price"] = price_text.strip()
                            logger.info(f"[GOOGLE FINANCE AGENT] Extracted price via {selector}: {price_data['price']}")
                            break
                    except:
                        continue

            # Extract change element
            change_elem = page.locator('div[class*="JwB6zf"]').first
            try:
                change_text = change_elem.text_content(timeout=2000)
                if change_text and change_text.strip():
                    price_data["change"] = change_text.strip()
                    logger.info(f"[GOOGLE FINANCE AGENT] Extracted change: {price_data['change']}")
            except:
                pass

            # Try alternative change selectors
            if not price_data.get("change"):
                change_selectors = [
                    'div[data-field="regularMarketChangePercent"]',
                    'span[data-field="regularMarketChangePercent"]',
                    'div[jsname="qRSVye"]'
                ]
                for selector in change_selectors:
                    try:
                        alt_elem = page.locator(selector).first
                        change_text = alt_elem.text_content(timeout=1000)
                        if change_text and change_text.strip():
                            price_data["change"] = change_text.strip()
                            logger.info(f"[GOOGLE FINANCE AGENT] Extracted change via {selector}: {price_data['change']}")
                            break
                    except:
                        continue

            if not price_data:
                logger.warning(f"[GOOGLE FINANCE AGENT] Could not extract price data - selectors may have changed")

        except Exception as e:
            logger.warning(f"[GOOGLE FINANCE AGENT] Error extracting price: {e}")

        # Extract AI Research section
        research_text = None
        try:
            # Look for "Research" or "AI overview" section
            research_section = page.locator('div[data-attrid="Research"], div[aria-label*="research"], div[aria-label*="AI"]').first
            if research_section:
                research_text = research_section.text_content().strip()

            # Alternative: look for any large text blocks that might be research
            if not research_text:
                text_blocks = page.locator('div[class*="bLLb2d"]').all()
                for block in text_blocks:
                    text = block.text_content().strip()
                    if len(text) > 200:  # Substantial text block
                        research_text = text
                        break

        except Exception as e:
            logger.warning(f"[GOOGLE FINANCE AGENT] Could not extract research: {e}")

        # Extract About section
        about_text = None
        try:
            about_section = page.locator('div[data-attrid="About"], div[aria-label*="about"]').first
            if about_section:
                about_text = about_section.text_content().strip()
        except Exception as e:
            logger.warning(f"[GOOGLE FINANCE AGENT] Could not extract about: {e}")

        # Extract key statistics
        stats = {}
        try:
            # Look for stat pairs (label: value)
            stat_elements = page.locator('div[class*="P6K39c"]').all()
            for elem in stat_elements:
                text = elem.text_content().strip()
                if ':' in text:
                    parts = text.split(':', 1)
                    if len(parts) == 2:
                        stats[parts[0].strip()] = parts[1].strip()
        except Exception as e:
            logger.warning(f"[GOOGLE FINANCE AGENT] Could not extract stats: {e}")

        # Get full page content as fallback
        full_content = page.content()

        browser.close()

        # Compile results
        result = {
            "success": True,
            "url": url,
            "price_data": price_data,
            "research": research_text,
            "about": about_text,
            "statistics": stats,
            "raw_html_length": len(full_content),
            "message": f"Extracted data from Google Finance"
        }

        if not price_data and not research_text:
            result["warning"] = "Limited data extracted - page structure may have changed"

        return result

    except Exception as e:
        logger.error(f"[GOOGLE FINANCE AGENT] Error extracting data: {e}")
        return {
            "error": True,
            "error_type": "ExtractionError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def capture_google_finance_chart(url: str, output_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Capture a screenshot of the stock chart from Google Finance.

    Args:
        url: Google Finance URL
        output_name: Optional custom filename

    Returns:
        Dictionary with screenshot path

    Example:
        capture_google_finance_chart("https://www.google.com/finance/quote/PLTR:NASDAQ")
    """
    logger.info(f"[GOOGLE FINANCE AGENT] Capturing chart from: {url}")

    try:
        from automation.web_browser import SyncWebBrowser
        from utils import load_config
        from pathlib import Path

        config = load_config()
        browser = SyncWebBrowser(config, headless=False)

        # Navigate to the page
        nav_result = browser.navigate(url, wait_until="networkidle")

        if not nav_result.get("success"):
            browser.close()
            return {
                "error": True,
                "error_type": "NavigationError",
                "error_message": f"Failed to load {url}",
                "retry_possible": True
            }

        # Wait for chart to load
        time.sleep(3)

        # Take screenshot
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        if output_name:
            filename = f"{output_name}_{timestamp}.png"
        else:
            # Extract ticker from URL for filename
            ticker_match = re.search(r'/quote/([^/\?:]+)', url)
            ticker = ticker_match.group(1) if ticker_match else "stock"
            filename = f"{ticker}_gfinance_{timestamp}.png"

        screenshot_dir = Path("data/screenshots")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshot_dir / filename

        # Capture the full page
        page = browser.page
        page.screenshot(path=str(screenshot_path), full_page=False)

        browser.close()

        return {
            "success": True,
            "screenshot_path": str(screenshot_path),
            "url": url,
            "message": f"Chart captured: {filename}"
        }

    except Exception as e:
        logger.error(f"[GOOGLE FINANCE AGENT] Error capturing chart: {e}")
        return {
            "error": True,
            "error_type": "ScreenshotError",
            "error_message": str(e),
            "retry_possible": True
        }


@tool
def create_stock_report_from_google_finance(company: str, output_format: str = "pdf") -> Dict[str, Any]:
    """
    Create a complete stock report using Google Finance data.

    This HIGH-LEVEL tool orchestrates:
    1. Search Google Finance for the company
    2. Extract price data and AI research
    3. Capture chart screenshot
    4. Compile into PDF report or Keynote presentation

    Args:
        company: Company name or ticker (e.g., "Palantir", "PLTR")
        output_format: "pdf" for report, "presentation" for Keynote (default: "pdf")

    Returns:
        Dictionary with report/presentation path and all extracted data

    Example:
        create_stock_report_from_google_finance("Palantir", "pdf")
        create_stock_report_from_google_finance("MSFT", "presentation")
    """
    logger.info(f"[GOOGLE FINANCE AGENT] Creating {output_format} for: {company}")

    try:
        # Step 1: Search for stock on Google Finance
        search_result = search_google_finance_stock.invoke({"company": company})

        if search_result.get("error"):
            return search_result

        url = search_result["url"]
        ticker = search_result.get("ticker", company)
        company_name = search_result.get("company_name", company)

        # Step 2: Extract data from Google Finance
        data_result = extract_google_finance_data.invoke({"url": url})

        if data_result.get("error"):
            return data_result

        # Step 3: Capture chart
        chart_result = capture_google_finance_chart.invoke({
            "url": url,
            "output_name": f"{ticker.lower()}_report"
        })

        chart_path = chart_result.get("screenshot_path") if not chart_result.get("error") else None

        # Step 4: Compile report or presentation
        if output_format.lower() in ["presentation", "keynote", "slides"]:
            # Create presentation
            from .presentation_agent import create_keynote_with_images
            from .writing_agent import create_slide_deck_content

            # Format content for slides - ensure price data is prominently included
            content_parts = [f"{company_name} ({ticker}) Stock Analysis"]

            # Extract and include price data if available
            price_info = data_result.get("price_data", {})
            if price_info and (price_info.get("price") or price_info.get("change")):
                # Make price information explicit and prominent
                price_str = price_info.get("price", "N/A")
                change_str = price_info.get("change", "N/A")
                content_parts.append(f"\nSTOCK PRICE INFORMATION:")
                content_parts.append(f"Current Price: {price_str}")
                content_parts.append(f"Price Change: {change_str}")

            # Include statistics if available
            stats = data_result.get("statistics", {})
            if stats:
                content_parts.append(f"\nKEY STATISTICS:")
                for key, value in list(stats.items())[:5]:  # Limit to top 5 stats
                    content_parts.append(f"{key}: {value}")

            if data_result.get("research"):
                content_parts.append(f"\nMARKET ANALYSIS:")
                content_parts.append(f"{data_result['research'][:500]}")

            content_text = "\n".join(content_parts)

            # Generate slide content with explicit instruction to preserve price data
            slide_content_result = create_slide_deck_content.invoke({
                "content": content_text,
                "title": f"{company_name} Stock Analysis",
                "num_slides": 4  # Increased to ensure price info gets its own slide
            })

            # Use formatted_content (the correct key) and fallback to original content with price info
            formatted_slide_content = slide_content_result.get("formatted_content", "")
            
            # If formatted content doesn't include price, prepend it explicitly
            if price_info and (price_info.get("price") or price_info.get("change")):
                price_slide = f"\n\nSTOCK PRICE\n• Current Price: {price_info.get('price', 'N/A')}\n• Change: {price_info.get('change', 'N/A')}"
                # Check if price is already in formatted content
                if price_info.get("price") and price_info.get("price") not in formatted_slide_content:
                    formatted_slide_content = price_slide + formatted_slide_content

            # Create presentation
            pres_result = create_keynote_with_images.invoke({
                "title": f"{company_name} Stock Analysis",
                "content": formatted_slide_content if formatted_slide_content else content_text,
                "image_paths": [chart_path] if chart_path else []
            })

            return {
                "success": True,
                "output_format": "presentation",
                "presentation_path": pres_result.get("keynote_path") or pres_result.get("file_path"),
                "chart_path": chart_path,
                "company": company_name,
                "ticker": ticker,
                "google_finance_url": url,
                "data_extracted": data_result,
                "price_data": price_info,  # Include price data in return for verification
                "message": f"Presentation created for {company_name} ({ticker})"
            }

        else:
            # Create PDF report
            from automation.report_generator import ReportGenerator
            from utils import load_config

            config = load_config()
            report_gen = ReportGenerator(config)

            # Build report sections
            sections = []

            # Executive Summary
            summary_parts = [f"{company_name} ({ticker})"]
            if data_result.get("price_data"):
                price_info = data_result["price_data"]
                summary_parts.append(f"\nCurrent Price: {price_info.get('price', 'N/A')}")
                summary_parts.append(f"Change: {price_info.get('change', 'N/A')}")

            sections.append({
                "heading": "Executive Summary",
                "content": "\n".join(summary_parts)
            })

            # AI Research / Analysis
            if data_result.get("research"):
                sections.append({
                    "heading": "Research & Analysis",
                    "content": data_result["research"]
                })

            # About
            if data_result.get("about"):
                sections.append({
                    "heading": "About",
                    "content": data_result["about"]
                })

            # Statistics
            if data_result.get("statistics"):
                stats_text = "\n".join([f"{k}: {v}" for k, v in data_result["statistics"].items()])
                sections.append({
                    "heading": "Key Statistics",
                    "content": stats_text
                })

            # Create report
            report_result = report_gen.create_report(
                title=f"{company_name} ({ticker}) Stock Report",
                content="",
                sections=sections,
                image_paths=[chart_path] if chart_path else None,
                export_pdf=True,
                output_name=f"{ticker.lower()}_gfinance_report"
            )

            if report_result.get("error"):
                return report_result

            return {
                "success": True,
                "output_format": "pdf",
                "report_path": report_result.get("pdf_path") or report_result.get("html_path"),
                "chart_path": chart_path,
                "company": company_name,
                "ticker": ticker,
                "google_finance_url": url,
                "data_extracted": data_result,
                "message": f"Report created for {company_name} ({ticker})"
            }

    except Exception as e:
        logger.error(f"[GOOGLE FINANCE AGENT] Error creating report: {e}")
        return {
            "error": True,
            "error_type": "ReportCreationError",
            "error_message": str(e),
            "retry_possible": False
        }


# Export tools
GOOGLE_FINANCE_AGENT_TOOLS = [
    search_google_finance_stock,
    extract_google_finance_data,
    capture_google_finance_chart,
    create_stock_report_from_google_finance,
]

# Tool hierarchy
GOOGLE_FINANCE_AGENT_HIERARCHY = """
Google Finance Agent Hierarchy:
===============================

LEVEL 1: High-Level Report Creation
└─ create_stock_report_from_google_finance → Complete end-to-end report using Google Finance

LEVEL 2: Individual Operations
├─ search_google_finance_stock → Find stock page URL
├─ extract_google_finance_data → Get price + AI research
└─ capture_google_finance_chart → Screenshot chart

Workflow:
1. Search Google Finance for company
2. Navigate to stock page
3. Extract AI-generated research + price data
4. Capture chart screenshot
5. Compile into PDF or Keynote
"""


class GoogleFinanceAgent:
    """Google Finance Agent - Extract stock data from Google Finance."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in GOOGLE_FINANCE_AGENT_TOOLS}
        logger.info(f"[GOOGLE FINANCE AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self):
        return GOOGLE_FINANCE_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        return GOOGLE_FINANCE_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[GOOGLE FINANCE AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[GOOGLE FINANCE AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
