"""
Stock/Finance Agent - Hybrid approach using web + Mac Stocks app

Strategy:
1. Use browser navigation to get comprehensive stock data from Yahoo Finance
2. Use Mac Stocks app screenshot for visual charts/graphs
3. Combine both for complete stock analysis with visuals
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async functions in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def _get_stock_data_from_web(symbol: str) -> Dict[str, Any]:
    """
    Get stock data by browsing Yahoo Finance.

    Args:
        symbol: Stock ticker symbol (e.g., 'NVDA', 'AAPL')

    Returns:
        Dictionary with stock data extracted from web
    """
    from ..automation.web_browser import WebBrowser
    from ..utils import load_config

    symbol = symbol.upper()
    url = f"https://finance.yahoo.com/quote/{symbol}"

    config = load_config()
    browser = WebBrowser(config, headless=True)

    try:
        # Initialize and navigate
        await browser.initialize()
        logger.info(f"Navigating to Yahoo Finance for {symbol}...")

        nav_result = await browser.navigate(url, wait_until="networkidle", timeout=30000)

        if not nav_result.get("success"):
            raise Exception(f"Failed to load page: {nav_result.get('error')}")

        # Wait for page to fully load
        await asyncio.sleep(2)

        # Extract page content
        content_result = await browser.extract_content(use_langextract=True)

        if not content_result.get("success"):
            raise Exception("Failed to extract content")

        # Get the text content
        text = content_result.get("content", "")

        # Parse the data from Yahoo Finance page text
        stock_data = _parse_yahoo_finance_text(text, symbol)
        stock_data["source"] = "finance.yahoo.com"
        stock_data["source_url"] = url

        return stock_data

    finally:
        await browser.close()


def _parse_yahoo_finance_text(text: str, symbol: str) -> Dict[str, Any]:
    """
    Parse stock data from Yahoo Finance page text.

    Yahoo Finance pages typically contain text like:
    "NVIDIA Corporation (NVDA) ... 181.50 +2.30 (+1.28%) ... Market Cap: 4.47T"
    """
    import re

    # Extract company name (usually appears near the symbol)
    company_match = re.search(r'([A-Z][A-Za-z\s&.,]+(?:Corporation|Inc|LLC|Ltd|Company|Corp)?)[^\w]*\(' + re.escape(symbol) + r'\)', text)
    company_name = company_match.group(1).strip() if company_match else symbol

    # Find all numbers that could be prices (format: 123.45 or 1,234.56)
    price_pattern = r'[\d,]+\.\d{2}'
    numbers = re.findall(price_pattern, text)

    # First substantial number is usually the current price
    current_price = None
    if numbers:
        for num_str in numbers:
            try:
                num = float(num_str.replace(',', ''))
                if num > 1:  # Stock prices are usually > $1
                    current_price = num
                    break
            except ValueError:
                continue

    # Extract change and percent change
    # Pattern: +2.30 (+1.28%) or -1.50 (-0.82%)
    change_pattern = r'([+\-−])[\s]*(\d+\.\d{2})[\s]*\(([+\-−])(\d+\.\d{2})%\)'
    change_match = re.search(change_pattern, text)

    change = None
    change_percent = None
    if change_match:
        change_sign = -1 if change_match.group(1) in ['-', '−'] else 1
        percent_sign = -1 if change_match.group(3) in ['-', '−'] else 1
        try:
            change = change_sign * float(change_match.group(2))
            change_percent = percent_sign * float(change_match.group(4))
        except ValueError:
            pass

    # Calculate previous close
    previous_close = None
    if current_price is not None and change is not None:
        previous_close = round(current_price - change, 2)

    # Extract market cap if available
    market_cap_match = re.search(r'Market Cap[:\s]+(\d+\.?\d*[KMBT])', text, re.IGNORECASE)
    market_cap = None
    if market_cap_match:
        market_cap = _parse_market_cap(market_cap_match.group(1))

    # Format message
    if current_price and change_percent is not None:
        message = f"{company_name} ({symbol}): ${current_price:.2f} ({change_percent:+.2f}%)"
    else:
        message = f"{company_name} ({symbol}): Price data unavailable"

    return {
        "symbol": symbol,
        "company_name": company_name,
        "current_price": current_price,
        "previous_close": previous_close,
        "change": change,
        "change_percent": change_percent,
        "currency": "USD",
        "market_cap": market_cap,
        "message": message
    }


def _parse_market_cap(text: str) -> Optional[float]:
    """Parse market cap from text like '4.47T' or '500B'."""
    import re

    if not text:
        return None

    try:
        match = re.search(r'([\d.]+)\s*([KMBT])?', text.upper())
        if not match:
            return None

        value = float(match.group(1))
        multiplier = match.group(2)

        multipliers = {
            'K': 1_000,
            'M': 1_000_000,
            'B': 1_000_000_000,
            'T': 1_000_000_000_000
        }

        if multiplier:
            value *= multipliers.get(multiplier, 1)

        return value

    except Exception:
        return None


@tool
def get_stock_price(symbol: str) -> Dict[str, Any]:
    """
    Get current stock price and information by browsing Yahoo Finance.

    This tool provides comprehensive stock data by visiting Yahoo Finance
    and extracting the current price, change, market cap, and company info.

    Use this when you need to:
    - Find the current price of a stock
    - Get today's stock performance
    - Understand company valuation (market cap)
    - Get comprehensive stock data for analysis

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL' for Apple, 'NVDA' for Nvidia)

    Returns:
        Dictionary with current price, change, market cap, and other details

    Examples:
        get_stock_price("NVDA")  # Get Nvidia stock data
        get_stock_price("AAPL")  # Get Apple stock data
    """
    logger.info(f"[STOCK AGENT] Tool: get_stock_price(symbol='{symbol}') - Using web browser")

    try:
        result = _run_async(_get_stock_data_from_web(symbol))
        return result

    except Exception as e:
        logger.error(f"Error getting stock price for {symbol}: {e}")
        return {
            "error": True,
            "error_type": "StockDataError",
            "error_message": f"Failed to get stock data: {str(e)}",
            "retry_possible": True
        }


@tool
def search_stock_symbol(query: str) -> Dict[str, Any]:
    """
    Search for a stock ticker symbol by company name.

    Use this when you have a company name but need the ticker symbol.

    Args:
        query: Company name (e.g., "Nvidia", "Apple", "Microsoft")

    Returns:
        Dictionary with matching symbols

    Examples:
        search_stock_symbol("Nvidia")  # Returns NVDA
        search_stock_symbol("Apple")   # Returns AAPL
    """
    logger.info(f"[STOCK AGENT] Tool: search_stock_symbol(query='{query}')")

    # Comprehensive mapping of companies to ticker symbols
    symbol_map = {
        "nvidia": "NVDA",
        "apple": "AAPL",
        "microsoft": "MSFT",
        "google": "GOOGL",
        "alphabet": "GOOGL",
        "amazon": "AMZN",
        "tesla": "TSLA",
        "meta": "META",
        "facebook": "META",
        "netflix": "NFLX",
        "intel": "INTC",
        "amd": "AMD",
        "ibm": "IBM",
        "oracle": "ORCL",
        "salesforce": "CRM",
        "adobe": "ADBE",
        "cisco": "CSCO",
        "qualcomm": "QCOM",
    }

    query_lower = query.lower()
    matches = []

    for name, symbol in symbol_map.items():
        if query_lower in name or name in query_lower:
            matches.append({
                "symbol": symbol,
                "company_name": name.title()
            })

    if matches:
        return {
            "query": query,
            "matches": matches,
            "count": len(matches),
            "message": f"Found {len(matches)} match(es) for '{query}'"
        }

    return {
        "error": True,
        "error_type": "SymbolNotFound",
        "error_message": f"No stock symbol found for: {query}",
        "retry_possible": True,
        "suggestion": "Try using the ticker symbol directly (e.g., AAPL, MSFT, NVDA)"
    }


# Export tools
STOCK_AGENT_TOOLS = [
    get_stock_price,
    search_stock_symbol,
]

# Tool hierarchy for planner
STOCK_AGENT_HIERARCHY = {
    "LEVEL 1 - Primary": [
        "get_stock_price",      # Get current price via web browsing
        "search_stock_symbol",  # Find ticker symbols
    ],
}
