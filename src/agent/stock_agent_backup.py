"""
Stock/Finance Agent - Get stock prices and market data
"""

import logging
from typing import Dict, Any, Optional
from langchain_core.tools import tool
import yfinance as yf
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@tool
def get_stock_price(symbol: str) -> Dict[str, Any]:
    """
    Get current stock price and basic information for a given ticker symbol.

    Use this when you need to:
    - Find the current price of a stock
    - Get basic stock information (company name, market cap, etc.)
    - Check today's stock performance

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL' for Apple, 'GOOGL' for Google)

    Returns:
        Dictionary with current price, change, volume, and other details

    Example:
        get_stock_price("AAPL")  # Get Apple stock price
        get_stock_price("TSLA")  # Get Tesla stock price
    """
    logger.info(f"[STOCK AGENT] Tool: get_stock_price(symbol='{symbol}')")

    try:
        # Normalize symbol to uppercase
        symbol = symbol.upper()

        # Get stock data
        stock = yf.Ticker(symbol)
        info = stock.info

        # Get current price data
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        previous_close = info.get('previousClose') or info.get('regularMarketPreviousClose')

        if current_price is None:
            return {
                "error": True,
                "error_type": "DataNotAvailable",
                "error_message": f"Unable to fetch price data for symbol: {symbol}",
                "retry_possible": True
            }

        # Calculate change
        if previous_close:
            change = current_price - previous_close
            change_percent = (change / previous_close) * 100
        else:
            change = 0
            change_percent = 0

        return {
            "symbol": symbol,
            "company_name": info.get('longName', symbol),
            "current_price": round(current_price, 2),
            "previous_close": round(previous_close, 2) if previous_close else None,
            "change": round(change, 2),
            "change_percent": round(change_percent, 2),
            "currency": info.get('currency', 'USD'),
            "market_cap": info.get('marketCap'),
            "volume": info.get('volume'),
            "day_high": info.get('dayHigh'),
            "day_low": info.get('dayLow'),
            "fifty_two_week_high": info.get('fiftyTwoWeekHigh'),
            "fifty_two_week_low": info.get('fiftyTwoWeekLow'),
            "message": f"{info.get('longName', symbol)} ({symbol}): ${current_price:.2f} ({'+' if change >= 0 else ''}{change_percent:.2f}%)"
        }

    except Exception as e:
        logger.error(f"Error fetching stock price for {symbol}: {e}")
        return {
            "error": True,
            "error_type": "StockDataError",
            "error_message": f"Failed to fetch stock data: {str(e)}",
            "retry_possible": False
        }


@tool
def get_stock_history(symbol: str, period: str = "1mo") -> Dict[str, Any]:
    """
    Get historical stock price data for a given ticker symbol.

    Use this when you need to:
    - See stock price trends over time
    - Get historical price data
    - Analyze stock performance over a period

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL')
        period: Time period - "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"

    Returns:
        Dictionary with historical price data

    Example:
        get_stock_history("AAPL", "1mo")  # Apple stock for last month
    """
    logger.info(f"[STOCK AGENT] Tool: get_stock_history(symbol='{symbol}', period='{period}')")

    try:
        symbol = symbol.upper()
        stock = yf.Ticker(symbol)

        # Get historical data
        hist = stock.history(period=period)

        if hist.empty:
            return {
                "error": True,
                "error_type": "NoHistoricalData",
                "error_message": f"No historical data available for {symbol}",
                "retry_possible": True
            }

        # Convert to readable format
        history_data = []
        for date, row in hist.iterrows():
            history_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": round(row['Open'], 2),
                "high": round(row['High'], 2),
                "low": round(row['Low'], 2),
                "close": round(row['Close'], 2),
                "volume": int(row['Volume'])
            })

        # Get summary stats
        latest = history_data[-1] if history_data else None
        oldest = history_data[0] if history_data else None

        change = None
        change_percent = None
        if latest and oldest:
            change = latest['close'] - oldest['close']
            change_percent = (change / oldest['close']) * 100

        return {
            "symbol": symbol,
            "period": period,
            "data_points": len(history_data),
            "latest_date": latest['date'] if latest else None,
            "latest_price": latest['close'] if latest else None,
            "oldest_date": oldest['date'] if oldest else None,
            "oldest_price": oldest['close'] if oldest else None,
            "period_change": round(change, 2) if change else None,
            "period_change_percent": round(change_percent, 2) if change_percent else None,
            "history": history_data[-10:],  # Return last 10 data points
            "message": f"{symbol} history for {period}: {len(history_data)} data points"
        }

    except Exception as e:
        logger.error(f"Error fetching stock history for {symbol}: {e}")
        return {
            "error": True,
            "error_type": "HistoryError",
            "error_message": f"Failed to fetch historical data: {str(e)}",
            "retry_possible": False
        }


@tool
def search_stock_symbol(query: str) -> Dict[str, Any]:
    """
    Search for stock ticker symbols by company name.

    Use this when you need to:
    - Find the ticker symbol for a company
    - Search for stocks by company name
    - Look up stock symbols

    Args:
        query: Company name or search query (e.g., "Apple", "Microsoft")

    Returns:
        Dictionary with matching stock symbols

    Example:
        search_stock_symbol("Apple")  # Find AAPL
        search_stock_symbol("Tesla")  # Find TSLA
    """
    logger.info(f"[STOCK AGENT] Tool: search_stock_symbol(query='{query}')")

    try:
        # Common stock mappings
        common_stocks = {
            'apple': 'AAPL',
            'microsoft': 'MSFT',
            'google': 'GOOGL',
            'alphabet': 'GOOGL',
            'amazon': 'AMZN',
            'meta': 'META',
            'facebook': 'META',
            'tesla': 'TSLA',
            'nvidia': 'NVDA',
            'netflix': 'NFLX',
            'adobe': 'ADBE',
            'intel': 'INTC',
            'amd': 'AMD',
            'ibm': 'IBM',
            'oracle': 'ORCL',
            'salesforce': 'CRM',
            'cisco': 'CSCO',
            'paypal': 'PYPL',
            'uber': 'UBER',
            'airbnb': 'ABNB',
            'spotify': 'SPOT',
            'twitter': 'TWTR',
            'snap': 'SNAP',
            'zoom': 'ZM',
            'slack': 'WORK',
            'shopify': 'SHOP',
            'square': 'SQ',
            'coinbase': 'COIN',
            'robinhood': 'HOOD',
        }

        query_lower = query.lower().strip()

        # Check for exact match
        if query_lower in common_stocks:
            symbol = common_stocks[query_lower]

            # Verify symbol exists and get company name
            try:
                stock = yf.Ticker(symbol)
                info = stock.info
                company_name = info.get('longName', symbol)

                return {
                    "symbol": symbol,
                    "company_name": company_name,
                    "query": query,
                    "message": f"Found: {company_name} ({symbol})"
                }
            except:
                pass

        # If query is already a valid symbol
        if len(query_lower) <= 5 and query_lower.isalpha():
            try:
                symbol = query.upper()
                stock = yf.Ticker(symbol)
                info = stock.info
                company_name = info.get('longName')

                if company_name:
                    return {
                        "symbol": symbol,
                        "company_name": company_name,
                        "query": query,
                        "message": f"Found: {company_name} ({symbol})"
                    }
            except:
                pass

        # Partial matches
        matches = []
        for name, symbol in common_stocks.items():
            if query_lower in name or name in query_lower:
                try:
                    stock = yf.Ticker(symbol)
                    info = stock.info
                    matches.append({
                        "symbol": symbol,
                        "company_name": info.get('longName', symbol)
                    })
                except:
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
            "suggestion": "Try searching with the ticker symbol directly (e.g., AAPL, MSFT)"
        }

    except Exception as e:
        logger.error(f"Error searching for stock symbol '{query}': {e}")
        return {
            "error": True,
            "error_type": "SearchError",
            "error_message": f"Failed to search for symbol: {str(e)}",
            "retry_possible": False
        }


@tool
def compare_stocks(symbols: list) -> Dict[str, Any]:
    """
    Compare multiple stocks side by side.

    Use this when you need to:
    - Compare performance of multiple stocks
    - Analyze multiple companies at once
    - Get comparative stock data

    Args:
        symbols: List of stock ticker symbols (e.g., ['AAPL', 'MSFT', 'GOOGL'])

    Returns:
        Dictionary with comparison data

    Example:
        compare_stocks(['AAPL', 'MSFT', 'GOOGL'])
    """
    logger.info(f"[STOCK AGENT] Tool: compare_stocks(symbols={symbols})")

    try:
        comparison = []

        for symbol in symbols:
            symbol = symbol.upper()
            stock = yf.Ticker(symbol)
            info = stock.info

            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            previous_close = info.get('previousClose') or info.get('regularMarketPreviousClose')

            if current_price and previous_close:
                change_percent = ((current_price - previous_close) / previous_close) * 100
            else:
                change_percent = 0

            comparison.append({
                "symbol": symbol,
                "company_name": info.get('longName', symbol),
                "price": round(current_price, 2) if current_price else None,
                "change_percent": round(change_percent, 2),
                "market_cap": info.get('marketCap'),
                "pe_ratio": info.get('trailingPE')
            })

        # Sort by market cap (descending)
        comparison.sort(key=lambda x: x.get('market_cap', 0) or 0, reverse=True)

        return {
            "stocks": comparison,
            "count": len(comparison),
            "message": f"Compared {len(comparison)} stocks"
        }

    except Exception as e:
        logger.error(f"Error comparing stocks: {e}")
        return {
            "error": True,
            "error_type": "ComparisonError",
            "error_message": f"Failed to compare stocks: {str(e)}",
            "retry_possible": False
        }


# Export tools
STOCK_AGENT_TOOLS = [
    get_stock_price,
    get_stock_history,
    search_stock_symbol,
    compare_stocks,
]

# Tool hierarchy for planner
STOCK_AGENT_HIERARCHY = {
    "LEVEL 1 - Primary": [
        "get_stock_price",      # Most common: get current price
        "search_stock_symbol",  # Find ticker symbols
    ],
    "LEVEL 2 - Secondary": [
        "get_stock_history",    # Historical data
        "compare_stocks",       # Compare multiple stocks
    ],
}
