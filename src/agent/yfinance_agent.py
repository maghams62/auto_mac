"""
Yahoo Finance Agent - Fetch stock data using yfinance API.

This is a simpler, more reliable alternative to web scraping Google Finance.
Uses the yfinance library to get real-time stock data and create reports.
"""

import logging
from typing import Dict, Any, Optional
from langchain_core.tools import tool
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@tool
def get_stock_data(ticker: str, period: str = "1mo") -> Dict[str, Any]:
    """
    Get comprehensive stock data for a ticker using Yahoo Finance.

    Args:
        ticker: Stock ticker symbol (e.g., "NVDA", "AAPL", "MSFT")
        period: Time period for historical data (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

    Returns:
        Dictionary with current price, historical data, company info, and analysis

    Example:
        get_stock_data("NVDA", "1mo")
    """
    logger.info(f"[YFINANCE AGENT] Fetching data for: {ticker}")

    try:
        import yfinance as yf
        import pandas as pd

        # Create ticker object
        stock = yf.Ticker(ticker)

        # Get basic info
        info = stock.info

        # Get historical data
        hist = stock.history(period=period)

        if hist.empty:
            return {
                "error": True,
                "error_type": "NoDataFound",
                "error_message": f"No data found for ticker: {ticker}",
                "retry_possible": True,
                "suggestion": "Check if the ticker symbol is correct"
            }

        # Calculate statistics
        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        price_change = current_price - prev_close
        price_change_pct = (price_change / prev_close) * 100 if prev_close != 0 else 0

        # Calculate period statistics
        period_high = hist['High'].max()
        period_low = hist['Low'].min()
        avg_volume = hist['Volume'].mean()

        # Extract key information from info
        company_name = info.get('longName', ticker)
        sector = info.get('sector', 'N/A')
        industry = info.get('industry', 'N/A')
        market_cap = info.get('marketCap', 'N/A')
        pe_ratio = info.get('trailingPE', 'N/A')
        dividend_yield = info.get('dividendYield', 'N/A')
        week_52_high = info.get('fiftyTwoWeekHigh', 'N/A')
        week_52_low = info.get('fiftyTwoWeekLow', 'N/A')

        # Get business summary
        business_summary = info.get('longBusinessSummary', '')

        # Calculate trend
        if len(hist) >= 5:
            recent_avg = hist['Close'].tail(5).mean()
            older_avg = hist['Close'].head(5).mean()
            trend = "Upward" if recent_avg > older_avg else "Downward"
        else:
            trend = "Insufficient data"

        result = {
            "success": True,
            "ticker": ticker.upper(),
            "company_name": company_name,
            "sector": sector,
            "industry": industry,
            "current_price": round(float(current_price), 2),
            "price_change": round(float(price_change), 2),
            "price_change_percent": round(float(price_change_pct), 2),
            "period_high": round(float(period_high), 2),
            "period_low": round(float(period_low), 2),
            "average_volume": int(avg_volume),
            "market_cap": market_cap,
            "pe_ratio": round(float(pe_ratio), 2) if isinstance(pe_ratio, (int, float)) else pe_ratio,
            "dividend_yield": round(float(dividend_yield) * 100, 2) if isinstance(dividend_yield, (int, float)) and dividend_yield else dividend_yield,
            "week_52_high": round(float(week_52_high), 2) if isinstance(week_52_high, (int, float)) else week_52_high,
            "week_52_low": round(float(week_52_low), 2) if isinstance(week_52_low, (int, float)) else week_52_low,
            "business_summary": business_summary[:500] if business_summary else "N/A",
            "trend": trend,
            "period": period,
            "data_points": len(hist),
            "message": f"Retrieved data for {company_name} ({ticker})"
        }

        logger.info(f"[YFINANCE AGENT] Successfully fetched data for {company_name}")
        return result

    except ImportError:
        return {
            "error": True,
            "error_type": "DependencyError",
            "error_message": "yfinance library not installed. Please run: pip install yfinance",
            "retry_possible": False
        }
    except Exception as e:
        logger.error(f"[YFINANCE AGENT] Error fetching stock data: {e}")
        return {
            "error": True,
            "error_type": "FetchError",
            "error_message": str(e),
            "retry_possible": True
        }


@tool
def create_enriched_stock_presentation(ticker: str, period: str = "1mo") -> Dict[str, Any]:
    """
    Create an enriched stock analysis presentation with intelligent insights.

    This tool:
    1. Fetches comprehensive stock data
    2. Generates AI-powered analysis and insights
    3. Creates a professional presentation

    Args:
        ticker: Stock ticker symbol (e.g., "NVDA", "AAPL")
        period: Analysis period (default: "1mo")

    Returns:
        Dictionary with presentation path and analysis

    Example:
        create_enriched_stock_presentation("NVDA")
    """
    logger.info(f"[YFINANCE AGENT] Creating enriched presentation for: {ticker}")

    try:
        # Step 1: Get stock data
        stock_data = get_stock_data.invoke({"ticker": ticker, "period": period})

        if stock_data.get("error"):
            return stock_data

        # Step 2: Generate AI-powered insights
        from src.agent.writing_agent import create_slide_deck_content
        from src.agent.presentation_agent import create_keynote_with_images
        from src.utils import load_config
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        config = load_config()
        openai_config = config.get("openai", {})

        # Use AI to generate intelligent insights
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=0.7,
            api_key=openai_config.get("api_key")
        )

        # Create enrichment prompt
        enrichment_prompt = f"""Analyze the following stock data and provide intelligent insights:

Company: {stock_data['company_name']} ({stock_data['ticker']})
Sector: {stock_data['sector']}
Industry: {stock_data['industry']}
Current Price: ${stock_data['current_price']}
Price Change: ${stock_data['price_change']} ({stock_data['price_change_percent']}%)
{period} High: ${stock_data['period_high']}
{period} Low: ${stock_data['period_low']}
Market Cap: {stock_data['market_cap']}
P/E Ratio: {stock_data['pe_ratio']}
52-Week High: ${stock_data['week_52_high']}
52-Week Low: ${stock_data['week_52_low']}
Trend: {stock_data['trend']}

Business Summary: {stock_data['business_summary']}

Please provide:
1. A brief executive summary (2-3 sentences)
2. Key performance highlights (3-4 bullet points)
3. Investment considerations (2-3 points analyzing the valuation and trend)
4. Risk factors to consider (2-3 points)

Keep the analysis concise, professional, and data-driven."""

        messages = [
            SystemMessage(content="You are a financial analyst providing clear, concise stock analysis for presentations."),
            HumanMessage(content=enrichment_prompt)
        ]

        response = llm.invoke(messages)
        ai_analysis = response.content.strip()

        # Step 3: Format content for slides
        slide_content = f"""SLIDE 1: {stock_data['company_name']} ({stock_data['ticker']})
{stock_data['sector']} | {stock_data['industry']}

SLIDE 2: Stock Price Overview
• Current Price: ${stock_data['current_price']}
• Price Change: ${stock_data['price_change']} ({stock_data['price_change_percent']:+.2f}%)
• {period} Range: ${stock_data['period_low']} - ${stock_data['period_high']}
• 52-Week Range: ${stock_data['week_52_low']} - ${stock_data['week_52_high']}

SLIDE 3: Key Metrics
• Market Capitalization: {stock_data['market_cap']}
• P/E Ratio: {stock_data['pe_ratio']}
• Trend: {stock_data['trend']} ({period})
• Average Volume: {stock_data['average_volume']:,}

SLIDE 4: Analysis & Insights
{ai_analysis}

SLIDE 5: Company Overview
{stock_data['business_summary']}
"""

        # Step 4: Create presentation
        pres_result = create_keynote_with_images.invoke({
            "title": f"{stock_data['company_name']} Stock Analysis",
            "content": slide_content,
            "image_paths": []
        })

        if pres_result.get("error"):
            return pres_result

        return {
            "success": True,
            "presentation_path": pres_result.get("keynote_path") or pres_result.get("file_path"),
            "stock_data": stock_data,
            "ai_analysis": ai_analysis,
            "company": stock_data['company_name'],
            "ticker": stock_data['ticker'],
            "current_price": stock_data['current_price'],
            "price_change": stock_data['price_change'],
            "price_change_percent": stock_data['price_change_percent'],
            "message": f"Created enriched presentation for {stock_data['company_name']} ({ticker})"
        }

    except Exception as e:
        logger.error(f"[YFINANCE AGENT] Error creating presentation: {e}")
        return {
            "error": True,
            "error_type": "PresentationError",
            "error_message": str(e),
            "retry_possible": False
        }


# Export tools
YFINANCE_AGENT_TOOLS = [
    get_stock_data,
    create_enriched_stock_presentation,
]


class YFinanceAgent:
    """Yahoo Finance Agent - Reliable stock data fetching."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in YFINANCE_AGENT_TOOLS}
        logger.info(f"[YFINANCE AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self):
        return YFINANCE_AGENT_TOOLS

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Tool '{tool_name}' not found"
            }

        tool = self.tools[tool_name]
        logger.info(f"[YFINANCE AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[YFINANCE AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e)
            }
