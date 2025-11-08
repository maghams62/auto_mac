"""
Stock/Finance Agent - Get stock prices using web scraping from stocks.apple.com

This provides REAL-TIME, ACCURATE stock data by browsing the actual Apple Stocks website.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from langchain_core.tools import tool
import re

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async functions in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def _scrape_stock_data(symbol: str) -> Dict[str, Any]:
    """
    Scrape stock data from stocks.apple.com using browser automation.

    Args:
        symbol: Stock ticker symbol (e.g., 'NVDA', 'AAPL')

    Returns:
        Dictionary with stock data
    """
    from ..automation.web_browser import WebBrowser
    from ..utils import load_config

    symbol = symbol.upper()
    url = f"https://stocks.apple.com/symbol/{symbol}"

    config = load_config()
    browser = WebBrowser(config, headless=True)

    try:
        # Initialize and navigate
        await browser.initialize()
        nav_result = await browser.navigate(url, wait_until="networkidle", timeout=30000)

        if not nav_result.get("success"):
            raise Exception(f"Failed to load page: {nav_result.get('error')}")

        # Wait a bit for dynamic content
        await asyncio.sleep(2)

        # Extract page content
        content_result = await browser.extract_content(use_langextract=True)

        if not content_result.get("success"):
            raise Exception("Failed to extract content")

        # Get the full text content
        text = content_result.get("content", "")

        # Parse stock data from the text
        stock_data = _parse_stock_data_from_text(text, symbol)
        stock_data["source"] = "stocks.apple.com"

        return stock_data

    finally:
        await browser.close()


def _parse_stock_data_from_text(text: str, symbol: str) -> Dict[str, Any]:
    """
    Parse stock data from extracted page text.

    The stocks.apple.com page contains text like:
    "NVIDIA Corporation (NVDA) $181.50 +$2.30 (+1.28%)"
    """
    # Extract company name (usually first line or contains the symbol)
    company_match = re.search(r'([^(]+)\s*\(' + re.escape(symbol) + r'\)', text)
    company_name = company_match.group(1).strip() if company_match else symbol

    # Extract current price (look for $XXX.XX pattern)
    price_matches = re.findall(r'\$?([\d,]+\.?\d*)', text)
    current_price = None
    if price_matches:
        try:
            # First substantial number is usually the price
            for match in price_matches:
                num = float(match.replace(',', ''))
                if num > 1:  # Stock price usually > $1
                    current_price = num
                    break
        except ValueError:
            pass

    # Extract change (+ or - amount)
    change_match = re.search(r'([+\-−])\s*\$?([\d,]+\.?\d+)', text)
    change = None
    if change_match:
        sign = -1 if change_match.group(1) in ['-', '−'] else 1
        try:
            change = sign * float(change_match.group(2).replace(',', ''))
        except ValueError:
            pass

    # Extract percent change
    percent_match = re.search(r'([+\-−])\s*([\d.]+)%', text)
    change_percent = None
    if percent_match:
        sign = -1 if percent_match.group(1) in ['-', '−'] else 1
        try:
            change_percent = sign * float(percent_match.group(2))
        except ValueError:
            pass

    # Calculate previous close
    previous_close = None
    if current_price is not None and change is not None:
        previous_close = current_price - change

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
        "message": message
    }


@tool
def get_stock_price(symbol: str) -> Dict[str, Any]:
    """
    Get current stock price and information by browsing stocks.apple.com

    This tool provides REAL-TIME, ACCURATE stock data by actually visiting
    the Apple Stocks website and extracting the current price.

    Use this when you need to:
    - Find the current price of a stock
    - Get today's stock performance
    - Check real-time stock information

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL' for Apple, 'NVDA' for Nvidia)

    Returns:
        Dictionary with current price, change, and other details

    Examples:
        get_stock_price("NVDA")  # Get Nvidia stock price
        get_stock_price("AAPL")  # Get Apple stock price
    """
    logger.info(f"[STOCK AGENT] Tool: get_stock_price(symbol='{symbol}') - Using web scraping")

    try:
        result = _run_async(_scrape_stock_data(symbol))
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

    # Simple mapping of common companies
    # In production, this could query a stock symbol API
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
        "get_stock_price",      # Get current price (now uses web scraping!)
        "search_stock_symbol",  # Find ticker symbols
    ],
}
