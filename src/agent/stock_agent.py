"""
Stock/Finance Agent - Get stock prices and market data
"""

import logging
import re
import time
from typing import Dict, Any, Optional, List, Tuple
from langchain_core.tools import tool
import yfinance as yf
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _format_period_for_search(period: Optional[str]) -> str:
    """Convert tool period input into a human-friendly phrase for search queries."""
    if not period:
        return "recent"

    period_clean = period.replace("_", " ").replace("-", " ").strip().lower()
    normalized_map = {
        "1d": "past day",
        "1 day": "past day",
        "today": "today",
        "24h": "past day",
        "24 hours": "past day",
        "5d": "past week",
        "5 days": "past week",
        "7d": "past week",
        "one week": "past week",
        "1week": "past week",
        "1 wk": "past week",
        "1 week": "past week",
        "last week": "past week",
        "1mo": "past month",
        "1 month": "past month",
        "30d": "past month",
        "3mo": "past 3 months",
        "3 months": "past 3 months",
        "6mo": "past 6 months",
        "6 months": "past 6 months",
        "1y": "past year",
        "1 yr": "past year",
        "1 year": "past year",
        "2y": "past 2 years",
        "5y": "past 5 years",
        "10y": "past 10 years",
        "ytd": "year to date",
        "year to date": "year to date",
        "max": "historical",
    }
    return normalized_map.get(period_clean, period_clean)


def _normalize_history_period(period: Optional[str]) -> Tuple[str, Optional[str]]:
    """Map natural-language periods to yfinance-supported values."""
    allowed_periods = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}

    if not period:
        return "1mo", None

    raw = period.strip().lower()
    if raw in allowed_periods:
        return raw, None

    # Insert space between digits and letters to handle inputs like "1week"
    spaced = re.sub(r'(?<=\d)(?=[a-zA-Z])', ' ', raw)
    cleaned = spaced.replace("_", " ").replace("-", " ")

    word_to_int = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
    }

    number: Optional[int] = None
    for token in cleaned.split():
        if token.isdigit():
            number = int(token)
            break
        if token in word_to_int:
            number = word_to_int[token]
            break

    def note(mapped: str) -> str:
        return f"Normalized period '{period}' to '{mapped}' for data compatibility."

    if "ytd" in cleaned or "year to date" in cleaned:
        return "ytd", note("ytd")
    if "all time" in cleaned or "max" in cleaned:
        return "max", note("max")

    if "week" in cleaned or cleaned.endswith("wk"):
        if not number or number <= 1:
            return "5d", note("5d")
        if number == 2:
            return "1mo", note("1mo")
        if number == 3:
            return "3mo", note("3mo")
        return "6mo", note("6mo")

    if "day" in cleaned or cleaned.endswith("d"):
        if not number:
            number = 1
        if number <= 1:
            return "1d", note("1d")
        if number <= 5:
            return "5d", note("5d")
        if number <= 10:
            return "1mo", note("1mo")
        if number <= 20:
            return "1mo", note("1mo")
        return "3mo", note("3mo")

    if "month" in cleaned or cleaned.endswith("mo"):
        if not number or number <= 1:
            return "1mo", note("1mo")
        if number == 2:
            return "3mo", note("3mo")
        if number <= 4:
            return "3mo", note("3mo")
        if number <= 6:
            return "6mo", note("6mo")
        if number <= 12:
            return "1y", note("1y")
        return "2y", note("2y")

    if "year" in cleaned or cleaned.endswith("y"):
        if not number or number <= 1:
            return "1y", note("1y")
        if number == 2:
            return "2y", note("2y")
        if number <= 5:
            return "5y", note("5y")
        return "10y", note("10y")

    return raw, None


def _fallback_stock_history_via_search(
    symbol: str,
    period: Optional[str],
    original_error: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fallback path when structured market data is unavailable.

    Uses DuckDuckGo search to gather recent stock commentary so downstream steps still have
    content to synthesize. This avoids hardcoded numbers and leans on web data.
    """
    logger.warning(
        "[STOCK AGENT] Falling back to DuckDuckGo search for %s (%s) due to missing history. Reason: %s",
        symbol,
        period,
        original_error or "unknown"
    )

    try:
        from duckduckgo_search import DDGS
    except ImportError as import_error:
        logger.error(
            "[STOCK AGENT] Failed to import duckduckgo_search.DDGS for fallback: %s",
            import_error
        )
        return {
            "error": True,
            "error_type": "HistoryFallbackImportError",
            "error_message": (
                f"Unable to load web search fallback after history lookup failed: {import_error}"
            ),
            "retry_possible": False
        }

    query_period = _format_period_for_search(period)
    search_query = f"{symbol} stock price {query_period}".strip()

    search_results: List[Dict[str, Any]] = []
    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            with DDGS() as ddgs:
                search_results = list(ddgs.text(search_query, max_results=6, backend="lite"))
            if search_results:
                break
        except Exception as search_error:
            last_error = search_error
            if "ratelimit" in str(search_error).lower() and attempt == 0:
                logger.warning(
                    "[STOCK AGENT] DuckDuckGo rate limited %s query. Retrying after short pause.",
                    symbol
                )
                time.sleep(1.5)
                continue
            logger.error(
                "[STOCK AGENT] DuckDuckGo search fallback threw exception for %s: %s",
                symbol,
                search_error
            )
            return {
                "error": True,
                "error_type": "HistoryFallbackSearchError",
                "error_message": (
                    f"Stock history unavailable and web search fallback failed: {search_error}"
                ),
                "retry_possible": False
            }

    if not search_results and last_error:
        logger.error(
            "[STOCK AGENT] DuckDuckGo search fallback ultimately failed for %s: %s",
            symbol,
            last_error
        )
        return {
            "error": True,
            "error_type": "HistoryFallbackSearchError",
            "error_message": (
                f"Stock history unavailable and web search fallback failed: {last_error}"
            ),
            "retry_possible": False
        }

    if not search_results:
        logger.error(
            "[STOCK AGENT] DuckDuckGo search returned no results for %s (%s)",
            symbol,
            search_query
        )
        return {
            "error": True,
            "error_type": "HistoryFallbackNoResults",
            "error_message": (
                f"Stock history unavailable for {symbol}, and DuckDuckGo search returned no results."
            ),
            "retry_possible": True
        }

    history_entries: List[Dict[str, Any]] = []
    summary_lines: List[str] = []
    for item in search_results:
        entry = {
            "title": item.get("title"),
            "snippet": item.get("body"),
            "link": item.get("href"),
            "source": "duckduckgo_search"
        }
        history_entries.append(entry)

        title = entry.get("title") or "Result"
        snippet = (entry.get("snippet") or "").strip()
        link = entry.get("link") or ""
        details = f"{title}: {snippet}".strip()
        if link:
            details = f"{details} ({link})"
        summary_lines.append(details)

    formatted_summary = (
        f"{symbol} stock roundup ({query_period}):\n"
        + "\n".join(f"- {line}" for line in summary_lines if line)
    )

    return {
        "symbol": symbol,
        "period": period,
        "data_points": None,
        "latest_date": None,
        "latest_price": None,
        "oldest_date": None,
        "oldest_price": None,
        "period_change": None,
        "period_change_percent": None,
        "history": history_entries,
        "formatted_summary": formatted_summary,
        "message": (
            f"Used DuckDuckGo search results for {symbol} ({query_period}) because structured "
            "historical data was unavailable."
        ),
        "search_query": search_query,
        "search_result_count": len(history_entries),
        "source": "duckduckgo_search",
        "fallback_used": True,
        "fallback_reason": original_error,
    }


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

    # TODO: Add telemetry logging for regression testing
    # [TELEMETRY] Tool get_stock_price started - correlation_id={correlation_id}, symbol={symbol}
    # Use telemetry/tool_helpers.py: log_tool_step("get_stock_price", "start", metadata={"symbol": symbol}, correlation_id=correlation_id)

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
        
        # TODO: Add telemetry logging for regression testing
        # [TELEMETRY] Tool get_stock_price success - correlation_id={correlation_id}, price={current_price}
        # Use telemetry/tool_helpers.py: log_tool_step("get_stock_price", "success", metadata={"price": current_price, "symbol": symbol}, correlation_id=correlation_id)

    except Exception as e:
        logger.error(f"Error fetching stock price for {symbol}: {e}")
        
        # TODO: Add telemetry logging for regression testing
        # [TELEMETRY] Tool get_stock_price error - correlation_id={correlation_id}, error={str(e)}
        # Use telemetry/tool_helpers.py: log_tool_step("get_stock_price", "error", metadata={"error": str(e), "symbol": symbol}, correlation_id=correlation_id)
        
        return {
            "error": True,
            "error_type": "StockDataError",
            "error_message": f"Failed to fetch stock data: {str(e)}",
            "retry_possible": False
        }


@tool
def get_stock_history(symbol: str, period: str = "1mo", reasoning_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get historical stock price data for a given ticker symbol.

    Use this when you need to:
    - See stock price trends over time
    - Get historical price data
    - Analyze stock performance over a period

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL')
        period: Time period - "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"
        reasoning_context: Optional memory context for learning from past attempts

    Returns:
        Dictionary with historical price data

    Example:
        get_stock_history("AAPL", "1mo")  # Apple stock for last month
    """
    logger.info(f"[STOCK AGENT] Tool: get_stock_history(symbol='{symbol}', period='{period}')")

    # Check memory context for learning from past attempts
    if reasoning_context:
        past_attempts = reasoning_context.get("past_attempts", 0)
        commitments = reasoning_context.get("commitments", [])
        logger.debug(f"[STOCK AGENT] Memory context: {past_attempts} past attempts, commitments: {commitments}")

        # If we've had issues with stock data before, be more thorough
        if past_attempts > 0:
            logger.info(f"[STOCK AGENT] Learning from {past_attempts} past attempts - using more robust data fetching")

    try:
        symbol = symbol.upper()
        stock = yf.Ticker(symbol)

        # Get historical data
        allowed_periods = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
        normalized_period, normalization_note = _normalize_history_period(period)

        if normalized_period not in allowed_periods:
            logger.info(
                "[STOCK AGENT] Period '%s' not supported by yfinance. Switching to DuckDuckGo fallback.",
                period
            )
            return _fallback_stock_history_via_search(
                symbol,
                period,
                original_error=f"Unsupported period '{period}'"
            )

        hist = stock.history(period=normalized_period)

        if hist.empty:
            logger.warning(
                "[STOCK AGENT] No historical data returned for %s with period %s. Using DuckDuckGo fallback.",
                symbol,
                normalized_period
            )
            return _fallback_stock_history_via_search(
                symbol,
                period,
                original_error="No historical data returned from yfinance"
            )

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

        # Format detailed summary for LLM consumption
        formatted_summary = f"{symbol} Stock History ({period}):\n\n"
        formatted_summary += f"Period: {oldest['date']} to {latest['date']}\n"
        formatted_summary += f"Starting Price: ${oldest['close']:.2f}\n"
        formatted_summary += f"Ending Price: ${latest['close']:.2f}\n"
        formatted_summary += f"Change: ${change:.2f} ({'+' if change_percent > 0 else ''}{change_percent:.2f}%)\n\n"
        formatted_summary += "Daily Prices:\n"
        for day in history_data[-10:]:  # Last 10 days
            formatted_summary += f"  {day['date']}: ${day['close']:.2f} (Vol: {day.get('volume', 0):,})\n"
        
        response = {
            "symbol": symbol,
            "period": period,
            "normalized_period": normalized_period,
            "data_points": len(history_data),
            "latest_date": latest['date'] if latest else None,
            "latest_price": latest['close'] if latest else None,
            "oldest_date": oldest['date'] if oldest else None,
            "oldest_price": oldest['close'] if oldest else None,
            "period_change": round(change, 2) if change else None,
            "period_change_percent": round(change_percent, 2) if change_percent else None,
            "history": history_data[-10:],  # Return last 10 data points
            "formatted_summary": formatted_summary,  # NEW: Formatted text for LLM
            "message": f"{symbol} history for {period or normalized_period}: {len(history_data)} data points"
        }
        if normalization_note:
            response["message"] += f" ({normalization_note})"
            response["normalization_note"] = normalization_note
        return response

    except Exception as e:
        logger.error(f"Error fetching stock history for {symbol}: {e}")
        return {
            "error": True,
            "error_type": "HistoryError",
            "error_message": f"Failed to fetch historical data: {str(e)}",
            "retry_possible": False
        }


@tool
def search_stock_symbol(query: str, use_web_fallback: bool = True, reasoning_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Search for stock ticker symbols by company name with intelligent web fallback.

    This tool provides multi-level ticker resolution:
    1. Checks local cache of common tickers
    2. Falls back to web search if not found
    3. Detects if company is publicly traded or private

    Use this when you need to:
    - Find the ticker symbol for ANY company
    - Determine if a company is publicly traded
    - Search for international stock symbols
    - Handle ambiguous company names

    Args:
        query: Company name or search query (e.g., "Apple", "Bosch", "Microsoft")
        use_web_fallback: Whether to use web search if local lookup fails (default: True)
        reasoning_context: Optional memory context for learning from past attempts

    Returns:
        Dictionary with stock symbol, company info, or indication if private company

    Example:
        search_stock_symbol("Apple")  # Find AAPL
        search_stock_symbol("Bosch")  # Find BOSCHLTD.NS or detect private
        search_stock_symbol("Tesla")  # Find TSLA
    """
    logger.info(f"[STOCK AGENT] Tool: search_stock_symbol(query='{query}', use_web_fallback={use_web_fallback})")
    
    # TODO: Add telemetry logging for regression testing
    # [TELEMETRY] Tool search_stock_symbol started - correlation_id={correlation_id}, query={query}
    # Use telemetry/tool_helpers.py: log_tool_step("search_stock_symbol", "start", metadata={"query": query}, correlation_id=correlation_id)

    # Check memory context for learning from past attempts
    if reasoning_context:
        past_attempts = reasoning_context.get("past_attempts", 0)
        commitments = reasoning_context.get("commitments", [])
        logger.debug(f"[STOCK AGENT] Memory context: {past_attempts} past attempts, commitments: {commitments}")

        # If we've had issues with symbol lookup before, be more thorough
        if past_attempts > 0:
            logger.info(f"[STOCK AGENT] Learning from {past_attempts} past attempts - using more thorough symbol lookup")

    try:
        # Common stock mappings (expanded)
        common_stocks = {
            'adidas': 'ADDYY',
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
        private_companies = {
            "openai": "OpenAI is a private company and does not have a publicly traded stock ticker.",
            "spacex": "SpaceX is privately held and is not listed on public stock exchanges.",
        }

        matched_private = next(
            (name for name in private_companies.keys() if name in query_lower),
            None
        )

        if matched_private:
            message = private_companies[matched_private]
            logger.info(f"[STOCK AGENT] Known private company detected for query '{query}': {message}")
            return {
                "found": False,
                "error": True,
                "error_type": "PrivateCompany",
                "error_message": message,
                "retry_possible": False,
                "query": query,
                "is_private_company": True,
                "message": message,
                "suggestion": "Consider asking about a publicly traded company or provide a different ticker symbol.",
            }

        # Check for exact match
        if query_lower in common_stocks:
            symbol = common_stocks[query_lower]

            # Verify symbol exists and get company name
            try:
                stock = yf.Ticker(symbol)
                info = stock.info
                company_name = info.get('longName', symbol)

                return {
                    "found": True,
                    "symbol": symbol,
                    "stock_symbol": symbol,  # Alias for LLM compatibility
                    "company_name": company_name,
                    "query": query,
                    "source": "local_cache",
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
                        "found": True,
                        "symbol": symbol,
                        "company_name": company_name,
                        "query": query,
                        "source": "direct_symbol",
                        "message": f"Found: {company_name} ({symbol})"
                    }
            except:
                pass

        # Partial matches in local cache
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
                "found": True,
                "query": query,
                "matches": matches,
                "count": len(matches),
                "source": "local_cache",
                "message": f"Found {len(matches)} match(es) for '{query}'"
            }

        # If web fallback is disabled, return not found
        if not use_web_fallback:
            return {
                "found": False,
                "error": True,
                "error_type": "SymbolNotFound",
                "error_message": f"No stock symbol found in local cache for: {query}",
                "retry_possible": True,
                "suggestion": "Enable web_fallback or use Browser Agent to search online"
            }

        # Web fallback: Search for ticker online
        logger.info(f"[STOCK AGENT] Local lookup failed, using web search for: {query}")

        # Import browser agent tools
        from .browser_agent import google_search, extract_page_content

        # Search for the company's stock ticker
        search_query = f"{query} stock ticker symbol"
        search_result = google_search.invoke({"query": search_query, "num_results": 3})

        if search_result.get("error"):
            return {
                "found": False,
                "error": True,
                "error_type": "WebSearchFailed",
                "error_message": f"Web search failed for '{query}'",
                "retry_possible": True
            }

        # Look for ticker in search results
        results = search_result.get("results", [])
        potential_ticker = None
        is_private = False

        # Check snippets for ticker symbols or private company indicators
        for result in results:
            snippet = result.get("snippet", "").upper()
            title = result.get("title", "").upper()

            # Check for private company indicators
            if any(keyword in snippet.lower() or keyword in title.lower()
                   for keyword in ["private company", "privately held", "not publicly traded", "not listed"]):
                is_private = True
                logger.info(f"[STOCK AGENT] Detected '{query}' is likely a private company")

            # Look for ticker patterns (1-5 uppercase letters in parentheses or after colon)
            import re
            ticker_patterns = [
                r'\(([A-Z]{1,5})\)',  # (MSFT)
                r'NYSE:\s*([A-Z]{1,5})',  # NYSE: MSFT
                r'NASDAQ:\s*([A-Z]{1,5})',  # NASDAQ: AAPL
                r'TICKER:\s*([A-Z]{1,5})',  # TICKER: TSLA
                r'\b([A-Z]{2,5})\s*STOCK',  # AAPL STOCK
            ]

            for pattern in ticker_patterns:
                match = re.search(pattern, snippet + " " + title)
                if match:
                    potential_ticker = match.group(1)
                    logger.info(f"[STOCK AGENT] Found potential ticker: {potential_ticker}")
                    break

            if potential_ticker:
                break

        # If we detected it's private, return that information
        if is_private:
            private_message = f"'{query}' appears to be a private company (not publicly traded)."
            logger.info(f"[STOCK AGENT] {private_message}")
            return {
                "found": False,
                "error": True,
                "error_type": "PrivateCompany",
                "error_message": private_message,
                "retry_possible": False,
                "query": query,
                "is_private_company": True,
                "source": "web_search",
                "message": private_message,
                "suggestion": "Try providing a publicly traded company or a specific ticker symbol."
            }

        # If we found a potential ticker, verify it
        if potential_ticker:
            try:
                stock = yf.Ticker(potential_ticker)
                info = stock.info
                company_name = info.get('longName')

                if company_name:
                    return {
                        "found": True,
                        "symbol": potential_ticker,
                        "company_name": company_name,
                        "query": query,
                        "source": "web_search",
                        "message": f"Found via web search: {company_name} ({potential_ticker})"
                    }
            except Exception as e:
                logger.warning(f"[STOCK AGENT] Ticker verification failed for {potential_ticker}: {e}")

        # Last resort: couldn't find ticker
        fallback_message = (
            f"Could not find a public stock ticker for '{query}'. "
            "It may be a private company or listed under a different name."
        )
        logger.warning(f"[STOCK AGENT] Symbol lookup failed for '{query}': {fallback_message}")
        return {
            "found": False,
            "error": True,
            "error_type": "SymbolNotFound",
            "error_message": fallback_message,
            "retry_possible": False,
            "suggestion": "Try providing the exact ticker symbol (e.g., AAPL, MSFT) or verify if the company is publicly traded.",
            "query": query
        }

    except Exception as e:
        logger.error(f"Error searching for stock symbol '{query}': {e}")
        return {
            "found": False,
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


@tool
def capture_stock_chart(symbol: str, output_name: Optional[str] = None, use_web_fallback: bool = True) -> Dict[str, Any]:
    """
    Capture a screenshot of stock chart with automatic fallback options.

    This tool provides multiple chart capture methods:
    1. PRIMARY: Mac Stocks app (fast, native, works for major stocks)
    2. FALLBACK: Yahoo Finance web chart (works for all symbols including international)

    Use this when you need a visual chart/graph of a stock for presentations or reports.

    Args:
        symbol: Stock ticker symbol (e.g., 'NVDA', 'AAPL', 'TSLA', 'BOSCHLTD.NS')
        output_name: Optional custom name for screenshot file
        use_web_fallback: If True, tries web capture if Mac Stocks fails (default: True)

    Returns:
        Dictionary with screenshot path and capture method used

    Examples:
        capture_stock_chart("NVDA")  # Capture Nvidia chart from Stocks app
        capture_stock_chart("BOSCHLTD.NS")  # International stock, uses web fallback
        capture_stock_chart("AAPL", "apple_analysis")  # Custom name
    """
    logger.info(f"[STOCK AGENT] Tool: capture_stock_chart(symbol='{symbol}')")

    # Try Mac Stocks app first
    try:
        from ..automation.stocks_app_automation import StocksAppAutomation
        from ..utils import load_config

        config = load_config()
        automation = StocksAppAutomation(config)

        result = automation.open_and_capture_stock(symbol, output_name)

        if not result.get("error"):
            result["capture_method"] = "mac_stocks_app"
            return result
        else:
            logger.warning(f"[STOCK AGENT] Mac Stocks app failed: {result.get('error_message')}")

            if not use_web_fallback:
                return result

    except Exception as e:
        logger.warning(f"[STOCK AGENT] Mac Stocks app error: {e}")

        if not use_web_fallback:
            return {
                "error": True,
                "error_type": "ChartCaptureError",
                "error_message": f"Failed to capture chart: {str(e)}",
                "retry_possible": True
            }

    # Web fallback: Capture from Yahoo Finance
    if use_web_fallback:
        logger.info(f"[STOCK AGENT] Using web fallback for chart capture: {symbol}")

        try:
            from .browser_agent import take_web_screenshot
            from pathlib import Path
            import time

            # Yahoo Finance chart URL
            yahoo_url = f"https://finance.yahoo.com/quote/{symbol}"

            # Take screenshot
            screenshot_result = take_web_screenshot.invoke({
                "url": yahoo_url,
                "full_page": False
            })

            if screenshot_result.get("error"):
                return {
                    "error": True,
                    "error_type": "WebChartCaptureFailed",
                    "error_message": f"Both Mac Stocks and web fallback failed for {symbol}",
                    "retry_possible": True
                }

            # Rename screenshot to match expected naming
            if output_name:
                final_name = f"{output_name}_20{time.strftime('%y%m%d_%H%M%S')}.png"
            else:
                final_name = f"{symbol}_chart_{time.strftime('%Y%m%d_%H%M%S')}.png"

            from pathlib import Path
            screenshot_path = Path(screenshot_result["screenshot_path"])
            new_path = screenshot_path.parent / final_name

            import shutil
            shutil.move(str(screenshot_path), str(new_path))

            return {
                "success": True,
                "screenshot_path": str(new_path),
                "symbol": symbol,
                "capture_method": "yahoo_finance_web",
                "message": f"Chart captured from Yahoo Finance: {new_path.name}"
            }

        except Exception as e:
            logger.error(f"[STOCK AGENT] Web fallback error: {e}")
            return {
                "error": True,
                "error_type": "ChartCaptureError",
                "error_message": f"All chart capture methods failed: {str(e)}",
                "retry_possible": True
            }

    return {
        "error": True,
        "error_type": "ChartCaptureError",
        "error_message": f"Failed to capture chart for {symbol}",
        "retry_possible": True
    }


# Export tools
STOCK_AGENT_TOOLS = [
    get_stock_price,
    get_stock_history,
    search_stock_symbol,
    compare_stocks,
    capture_stock_chart,  # NEW: Capture chart from Stocks app
]

# Tool hierarchy for planner
STOCK_AGENT_HIERARCHY = """
Stock Agent Hierarchy:
======================

LEVEL 0: Ticker & News Discovery (Browser Agent prerequisite)
- Unless the user explicitly provides a ticker (e.g., MSFT, BOSCHLTD.NS), run Browser Agent tools FIRST:
  google_search → navigate_to_url → extract_page_content on allowlisted finance/news sites to confirm the ticker and gather latest headlines.
- Feed the extracted news text into synthesize_content alongside price/history output so every report reflects both quantitative data and current events.

LEVEL 1: Primary Stock Tools
- get_stock_price -> Fetch current metrics for the confirmed ticker
- capture_stock_chart -> Open Mac Stocks app to the ticker and capture a focused-window screenshot (no desktop leakage)
- search_stock_symbol -> Limited helper for well-known US tickers only

LEVEL 2: Secondary Stock Tools
- get_stock_history -> Fetch historical trends for the ticker
- compare_stocks -> Compare multiple tickers side-by-side
"""
