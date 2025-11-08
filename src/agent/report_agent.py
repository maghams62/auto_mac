"""
Report Agent - Handles stock report generation with embedded charts.

This agent orchestrates:
- Stock ticker resolution
- Stock data fetching
- Chart capture
- Content synthesis
- PDF report generation
"""

from typing import Dict, Any, Optional
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)


@tool
def create_stock_report(
    company: str,
    ticker: Optional[str] = None,
    include_analysis: bool = True,
    output_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a comprehensive stock report with chart and analysis for any company.

    This is a HIGH-LEVEL tool that orchestrates the entire stock report workflow:
    1. Resolves stock ticker (if not provided)
    2. Detects if company is publicly traded
    3. Fetches stock data
    4. Captures stock chart (Mac Stocks app or web fallback)
    5. Generates AI analysis
    6. Creates PDF report with embedded chart

    Use this when the user requests:
    - "Create a report on [company] stock"
    - "Generate stock analysis for [company]"
    - "I need a report about [company] stock price"

    Args:
        company: Company name (e.g., "Microsoft", "Bosch", "Apple")
        ticker: Optional ticker symbol (if known)
        include_analysis: Whether to include AI-generated analysis (default: True)
        output_name: Optional custom filename for report

    Returns:
        Dictionary with report_path (PDF), chart_path, and generation status

    Examples:
        create_stock_report("Microsoft")  # Auto-resolves to MSFT
        create_stock_report("Bosch")  # Detects if public/private
        create_stock_report(company="Apple", ticker="AAPL")  # Explicit ticker
    """
    logger.info(f"[REPORT AGENT] Tool: create_stock_report(company='{company}', ticker={ticker})")

    try:
        from .stock_agent import search_stock_symbol, get_stock_price, get_stock_history, capture_stock_chart
        from .writing_agent import synthesize_content
        from ..automation.report_generator import ReportGenerator
        from ..utils import load_config

        config = load_config()
        results = {}

        # Step 1: Resolve ticker if not provided
        if not ticker:
            logger.info(f"[REPORT AGENT] Resolving ticker for: {company}")
            ticker_result = search_stock_symbol.invoke({"query": company, "use_web_fallback": True})

            if ticker_result.get("is_private_company"):
                return {
                    "error": True,
                    "error_type": "PrivateCompany",
                    "error_message": f"{company} appears to be a private company (not publicly traded)",
                    "company": company,
                    "suggestion": "Cannot create stock report for private companies"
                }

            if not ticker_result.get("found"):
                return {
                    "error": True,
                    "error_type": "TickerNotFound",
                    "error_message": f"Could not find stock ticker for: {company}",
                    "company": company,
                    "suggestion": ticker_result.get("suggestion", "Try providing the exact ticker symbol")
                }

            # Handle multiple matches
            if "matches" in ticker_result:
                # Use first match
                ticker = ticker_result["matches"][0]["symbol"]
                company_name = ticker_result["matches"][0]["company_name"]
                logger.info(f"[REPORT AGENT] Using first match: {company_name} ({ticker})")
            else:
                ticker = ticker_result["symbol"]
                company_name = ticker_result["company_name"]

            results["ticker_resolution"] = {
                "ticker": ticker,
                "company_name": company_name,
                "source": ticker_result.get("source", "local_cache")
            }
        else:
            ticker = ticker.upper()
            company_name = company

        # Step 2: Fetch stock data
        logger.info(f"[REPORT AGENT] Fetching stock data for: {ticker}")
        stock_data = get_stock_price.invoke({"symbol": ticker})

        if stock_data.get("error"):
            return {
                "error": True,
                "error_type": "StockDataError",
                "error_message": f"Failed to fetch stock data for {ticker}: {stock_data.get('error_message')}",
                "ticker": ticker
            }

        # Get historical data for context
        history_data = get_stock_history.invoke({"symbol": ticker, "period": "1mo"})

        # Step 3: Capture stock chart
        logger.info(f"[REPORT AGENT] Capturing chart for: {ticker}")
        chart_result = capture_stock_chart.invoke({
            "symbol": ticker,
            "output_name": output_name or f"{ticker.lower()}_report_chart",
            "use_web_fallback": True
        })

        chart_path = None
        if not chart_result.get("error"):
            chart_path = chart_result.get("screenshot_path")
            results["chart_capture"] = {
                "path": chart_path,
                "method": chart_result.get("capture_method", "unknown")
            }
        else:
            logger.warning(f"[REPORT AGENT] Chart capture failed: {chart_result.get('error_message')}")

        # Step 4: Generate analysis content
        report_sections = []

        # Executive Summary section
        summary_content = f"""
{company_name} ({ticker}) is currently trading at ${stock_data['current_price']},
{'+' if stock_data['change'] >= 0 else ''}{stock_data['change_percent']}% from previous close.

Key Metrics:
• Current Price: ${stock_data['current_price']} {stock_data.get('currency', 'USD')}
• Previous Close: ${stock_data.get('previous_close')} {stock_data.get('currency', 'USD')}
• Day Range: ${stock_data.get('day_low')} - ${stock_data.get('day_high')}
• 52-Week Range: ${stock_data.get('fifty_two_week_low')} - ${stock_data.get('fifty_two_week_high')}
• Volume: {stock_data.get('volume'):,} shares
• Market Cap: ${stock_data.get('market_cap', 0):,}
"""

        report_sections.append({
            "heading": "Executive Summary",
            "content": summary_content.strip()
        })

        # Add historical performance
        if not history_data.get("error"):
            perf_content = f"""
Over the past month, {ticker} has moved from ${history_data.get('oldest_price')} to ${history_data.get('latest_price')},
representing a {'+' if history_data.get('period_change', 0) >= 0 else ''}{history_data.get('period_change_percent')}% change.

Monthly Performance:
• Period: {history_data.get('oldest_date')} to {history_data.get('latest_date')}
• Starting Price: ${history_data.get('oldest_price')}
• Ending Price: ${history_data.get('latest_price')}
• Change: ${history_data.get('period_change')} ({'+' if history_data.get('period_change', 0) >= 0 else ''}{history_data.get('period_change_percent')}%)
• Data Points: {history_data.get('data_points')}
"""
            report_sections.append({
                "heading": "Historical Performance (1 Month)",
                "content": perf_content.strip()
            })

        # AI-generated analysis (if requested)
        if include_analysis:
            logger.info(f"[REPORT AGENT] Generating AI analysis for: {ticker}")
            try:
                analysis_input = f"""
Stock: {company_name} ({ticker})
Current Price: ${stock_data['current_price']}
Daily Change: {stock_data['change_percent']}%
Monthly Change: {history_data.get('period_change_percent', 'N/A')}%
Volume: {stock_data.get('volume', 'N/A')}
Market Cap: ${stock_data.get('market_cap', 0)}

Please provide a brief analysis of this stock's performance and outlook.
"""

                synthesis_result = synthesize_content.invoke({
                    "source_contents": [analysis_input],
                    "topic": f"{company_name} Stock Analysis"
                })

                if not synthesis_result.get("error"):
                    report_sections.append({
                        "heading": "Analysis & Outlook",
                        "content": synthesis_result.get("synthesized_content", "Analysis unavailable")
                    })
            except Exception as e:
                logger.warning(f"[REPORT AGENT] Analysis generation failed: {e}")

        # Step 5: Create PDF report
        logger.info(f"[REPORT AGENT] Generating PDF report for: {ticker}")
        report_gen = ReportGenerator(config)

        report_title = f"{company_name} ({ticker}) Stock Report"

        report_result = report_gen.create_report(
            title=report_title,
            content="",
            sections=report_sections,
            image_paths=[chart_path] if chart_path else None,
            export_pdf=True,
            output_name=output_name or f"{ticker.lower()}_stock_report"
        )

        if report_result.get("error"):
            return {
                "error": True,
                "error_type": "ReportGenerationError",
                "error_message": f"Failed to generate report: {report_result.get('error_message')}",
                "ticker": ticker,
                "partial_results": results
            }

        # Success!
        return {
            "success": True,
            "company": company_name,
            "ticker": ticker,
            "report_path": report_result.get("pdf_path") or report_result.get("html_path"),
            "chart_path": chart_path,
            "report_format": "PDF" if report_result.get("pdf_path") else "HTML",
            "ticker_source": results.get("ticker_resolution", {}).get("source", "provided"),
            "chart_method": results.get("chart_capture", {}).get("method", "none"),
            "message": f"Stock report created for {company_name} ({ticker}): {report_result.get('message')}"
        }

    except Exception as e:
        logger.error(f"[REPORT AGENT] Error in create_stock_report: {e}")
        return {
            "error": True,
            "error_type": "ReportAgentError",
            "error_message": f"Failed to create stock report: {str(e)}",
            "company": company,
            "ticker": ticker
        }


# Export tools
REPORT_AGENT_TOOLS = [
    create_stock_report,
]

# Tool hierarchy
REPORT_AGENT_HIERARCHY = """
Report Agent Hierarchy:
======================

LEVEL 1: High-Level Report Generation
└─ create_stock_report → Complete end-to-end stock report with chart and analysis

This tool orchestrates multiple sub-agents:
1. Stock Agent: Ticker resolution, data fetching, chart capture
2. Writing Agent: Content synthesis and analysis
3. Report Generator: PDF creation with embedded images

Typical Usage:
create_stock_report("Microsoft")  # Auto-resolves ticker, creates full report
create_stock_report("Bosch")  # Detects if public/private
"""


class ReportAgent:
    """
    Report Agent - High-level orchestrator for report generation.

    Responsibilities:
    - Stock report generation with charts
    - Ticker resolution and validation
    - Content synthesis and formatting
    - PDF export with embedded images
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in REPORT_AGENT_TOOLS}
        logger.info(f"[REPORT AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self):
        """Get all report agent tools."""
        return REPORT_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get report agent hierarchy documentation."""
        return REPORT_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a report agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Report agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[REPORT AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[REPORT AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }
