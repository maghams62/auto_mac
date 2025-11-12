"""
Enriched Stock Agent - Create intelligent stock presentations using DuckDuckGo search.

This agent searches for comprehensive stock information and creates enriched presentations
with multiple data points including price, analysis, news, and company information.
"""

import logging
import os
from typing import Dict, Any
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Agent coordination
try:
    from src.utils.agent_coordination import (
        acquire_lock, release_lock, check_conflicts, cleanup_stale_locks
    )
    AGENT_COORDINATION_AVAILABLE = True
except ImportError:
    AGENT_COORDINATION_AVAILABLE = False
    logger.warning("[ENRICHED STOCK AGENT] Agent coordination not available")

# Get agent ID from environment or use default
AGENT_ID = os.environ.get("AGENT_ID", "enriched_stock_agent")


@tool
def create_enriched_stock_presentation(company: str) -> Dict[str, Any]:
    """
    Create an intelligent, well-researched stock presentation using DuckDuckGo search.

    This tool performs multiple searches to gather comprehensive information:
    - Current stock price and performance
    - Company overview and business model
    - Recent news and developments
    - Market analysis and trends
    - Financial metrics

    Then uses AI to synthesize this information into a professional presentation.

    Args:
        company: Company name or ticker symbol (e.g., "NVIDIA", "NVDA", "Apple")

    Returns:
        Dictionary with presentation path and enriched content

    Example:
        create_enriched_stock_presentation("NVIDIA")
    """
    logger.info(f"[ENRICHED STOCK AGENT] Creating presentation for: {company}")

    # Agent coordination: Check for conflicts and acquire lock
    files_to_modify = ["src/agent/enriched_stock_agent.py"]
    lock_acquired = False
    
    if AGENT_COORDINATION_AVAILABLE:
        try:
            # Clean up stale locks first
            cleanup_stale_locks()
            
            # Check for conflicts
            conflicts = check_conflicts(files_to_modify, AGENT_ID)
            if conflicts:
                logger.warning(f"[ENRICHED STOCK AGENT] Conflicts detected: {conflicts}")
                # Continue anyway but log the conflict
            
            # Acquire lock
            lock_acquired = acquire_lock(files_to_modify[0], AGENT_ID, timeout=600)
            if lock_acquired:
                logger.info(f"[ENRICHED STOCK AGENT] Lock acquired for {files_to_modify[0]}")
        except Exception as e:
            logger.warning(f"[ENRICHED STOCK AGENT] Coordination error: {e}, continuing without lock")

    try:
        import yfinance as yf
        from src.agent.google_agent import google_search
        from src.agent.presentation_agent import create_keynote_with_images
        from src.utils import load_config

        # Step 1: Get reliable stock data from yfinance API
        logger.info("[ENRICHED STOCK AGENT] Step 1: Fetching stock data from yfinance...")

        # Try to get ticker - handle both company names and ticker symbols
        ticker = company.upper().strip()

        # Common company name to ticker mappings
        ticker_map = {
            "NVIDIA": "NVDA",
            "APPLE": "AAPL",
            "MICROSOFT": "MSFT",
            "AMAZON": "AMZN",
            "GOOGLE": "GOOGL",
            "META": "META",
            "FACEBOOK": "META",
            "TESLA": "TSLA",
            "AMD": "AMD",
            "INTEL": "INTC"
        }

        # Check if it's a known company name
        if ticker in ticker_map:
            ticker = ticker_map[ticker]
            logger.info(f"[ENRICHED STOCK AGENT] Mapped company name to ticker: {ticker}")

        # Force fresh data by clearing cache
        stock = yf.Ticker(ticker)

        # Get fresh historical data (last 5 days to ensure we have recent data)
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5)

        hist = stock.history(start=start_date, end=end_date)
        info = stock.info

        # If no data, try searching for the ticker
        if hist.empty or not info or not info.get('regularMarketPrice'):
            logger.info(f"[ENRICHED STOCK AGENT] Direct lookup failed, searching for ticker...")
            # Try to search for the ticker using yfinance search
            try:
                # Search for potential tickers
                import requests
                search_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={company}"
                resp = requests.get(search_url)
                if resp.status_code == 200:
                    data = resp.json()
                    quotes = data.get('quotes', [])
                    if quotes:
                        ticker = quotes[0]['symbol']
                        logger.info(f"[ENRICHED STOCK AGENT] Found ticker from search: {ticker}")
                        stock = yf.Ticker(ticker)
                        info = stock.info
                        hist = stock.history(period="1mo")
            except:
                pass

        if hist.empty or not info or not info.get('regularMarketPrice'):
            return {
                "error": True,
                "error_type": "TickerNotFound",
                "error_message": f"Could not find stock data for: {company}. Please use the ticker symbol (e.g., NVDA for NVIDIA).",
                "retry_possible": True,
                "suggestion": "Try using the stock ticker symbol instead of the company name"
            }

        # Validate data freshness
        latest_date = hist.index[-1]

        # Handle timezone-aware vs timezone-naive datetimes
        latest_dt = latest_date.to_pydatetime()
        if latest_dt.tzinfo is not None:
            # Make current time timezone-aware
            from datetime import timezone
            now_dt = datetime.now(timezone.utc)
            # Convert latest_dt to UTC if it has a different timezone
            if latest_dt.tzinfo != timezone.utc:
                latest_dt = latest_dt.astimezone(timezone.utc)
        else:
            now_dt = datetime.now()

        days_old = (now_dt - latest_dt).days

        if days_old > 7:
            logger.warning(f"[ENRICHED STOCK AGENT] Data is {days_old} days old, may not be current")

        # Calculate price metrics
        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        price_change = current_price - prev_close
        price_change_pct = (price_change / prev_close) * 100

        # Format the data date
        data_date = latest_date.strftime("%B %d, %Y")

        # Format stock data with date
        price_info = f"""Current Price: ${current_price:.2f} (as of {data_date})
Price Change: ${price_change:+.2f} ({price_change_pct:+.2f}%)
Previous Close: ${prev_close:.2f}
Data Age: {days_old} days old"""

        company_info = f"""Company: {info.get('longName', company)}
Ticker: {ticker}
Sector: {info.get('sector', 'N/A')}
Industry: {info.get('industry', 'N/A')}
Description: {info.get('longBusinessSummary', 'N/A')[:400]}"""

        metrics_info = f"""Market Cap: ${info.get('marketCap', 0):,}
P/E Ratio: {info.get('trailingPE', 'N/A')}
Dividend Yield: {info.get('dividendYield', 0)*100:.2f}% if info.get('dividendYield') else 'N/A'
52-Week High: ${info.get('fiftyTwoWeekHigh', 0):.2f}
52-Week Low: ${info.get('fiftyTwoWeekLow', 0):.2f}
Average Volume: {info.get('averageVolume', 0):,}"""

        # Step 2: Enhanced search strategy with query rewriting
        logger.info("[ENRICHED STOCK AGENT] Step 2: Performing comprehensive web searches...")
        
        # Initialize LLM for query rewriting
        config = load_config()
        openai_config = config.get("openai", {})
        from src.utils import get_temperature_for_model
        
        llm = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.3),
            api_key=openai_config.get("api_key")
        )
        
        # Query rewriting function with few-shot examples
        def rewrite_search_query(base_query: str, context: str = "") -> str:
            """Rewrite search query for better semantic results using few-shot examples."""
            try:
                prompt = f"""You are a search query optimization expert specializing in financial and stock market queries.

Your task: Convert the base query into an optimized semantic search query that will return relevant, high-quality results.

FEW-SHOT EXAMPLES:

Example 1 (Stock Price Query):
Base query: "NVIDIA NVDA stock price current performance"
Context: Searching for Stock price and current performance about NVIDIA (NVDA)
Good rewrite: "NVIDIA NVDA stock price today current market value trading performance"
Bad rewrite: "NVDA" (too vague)
Bad rewrite: "NVIDIA stock" (missing performance context)

Example 2 (Company Overview Query):
Base query: "Apple AAPL company overview business model"
Context: Searching for Company overview and business model about Apple (AAPL)
Good rewrite: "Apple Inc AAPL company business model products services revenue streams"
Bad rewrite: "Apple company" (too generic, missing ticker)
Bad rewrite: "AAPL overview" (missing business model context)

Example 3 (News Query):
Base query: "Microsoft MSFT recent news developments 2024"
Context: Searching for Recent news and developments about Microsoft (MSFT)
Good rewrite: "Microsoft MSFT news 2024 latest developments earnings announcements product launches"
Bad rewrite: "Microsoft news" (missing year and ticker)
Bad rewrite: "MSFT" (too vague)

Example 4 (Market Analysis Query):
Base query: "TSLA stock market analysis trends forecast"
Context: Searching for Market analysis and trends about TSLA
Good rewrite: "Tesla TSLA stock analysis market trends price forecast analyst predictions 2024"
Bad rewrite: "TSLA analysis" (too short, missing context)
Bad rewrite: "Tesla stock" (missing analysis/trends keywords)

Example 5 (Financial Metrics Query):
Base query: "GOOGL financial metrics valuation analysis"
Context: Searching for Financial metrics and valuation about GOOGL
Good rewrite: "Alphabet GOOGL financial metrics P/E ratio market cap valuation analysis revenue"
Bad rewrite: "GOOGL metrics" (too vague)
Bad rewrite: "Google financials" (missing ticker and specific metrics)

RULES:
1. Always include both company name AND ticker symbol
2. Add relevant financial/stock market keywords (e.g., "stock price", "market cap", "earnings", "analyst")
3. Include temporal context when relevant (e.g., "2024", "recent", "latest")
4. Expand with synonyms and related terms (e.g., "performance" → "trading performance market value")
5. Keep queries focused but comprehensive (3-8 key terms)
6. Avoid overly generic terms that return irrelevant results

NOW REWRITE THIS QUERY:
Base query: "{base_query}"
Context: {context}

Respond with ONLY the refined search query as plain text (no JSON, no explanation, no quotes)."""
                
                response = llm.invoke([
                    SystemMessage(content="You are a search query optimization expert specializing in financial and stock market queries. You excel at converting vague queries into precise, semantic search queries that return high-quality results."),
                    HumanMessage(content=prompt)
                ])
                refined = response.content.strip().strip('"').strip("'")
                
                # Validate the rewritten query
                if not refined or len(refined.strip()) < 5:
                    logger.warning(f"[ENRICHED STOCK AGENT] Rewritten query too short, using original: '{refined}'")
                    return base_query
                
                # Ensure ticker is included if it was in the original
                if ticker in base_query.upper() and ticker not in refined.upper():
                    logger.warning(f"[ENRICHED STOCK AGENT] Rewritten query missing ticker {ticker}, adding it")
                    refined = f"{refined} {ticker}"
                
                logger.info(f"[ENRICHED STOCK AGENT] Rewrote query: '{base_query}' -> '{refined}'")
                return refined
            except Exception as e:
                logger.warning(f"[ENRICHED STOCK AGENT] Query rewriting failed: {e}, using original")
                return base_query
        
        # Perform 5 comprehensive searches with query rewriting
        search_queries = [
            (f"{company} {ticker} stock price current performance", "Stock price and current performance"),
            (f"{company} {ticker} company overview business model", "Company overview and business model"),
            (f"{company} {ticker} recent news developments 2024", "Recent news and developments"),
            (f"{ticker} stock market analysis trends forecast", "Market analysis and trends"),
            (f"{ticker} financial metrics valuation analysis", "Financial metrics and valuation")
        ]
        
        search_results = {}
        for base_query, search_type in search_queries:
            try:
                # Rewrite query for better results
                rewritten_query = rewrite_search_query(base_query, f"Searching for {search_type} about {company} ({ticker})")
                
                logger.info(f"[ENRICHED STOCK AGENT] Searching: {search_type}")
                search_result = google_search.invoke({
                    "query": rewritten_query,
                    "num_results": 5  # Get more results for better parsing
                })
                
                search_results[search_type] = search_result
            except Exception as e:
                logger.error(f"[ENRICHED STOCK AGENT] Search failed for {search_type}: {e}")
                search_results[search_type] = {"error": True, "results": []}
        
        # Intelligent result parsing using LLM
        def parse_search_results(search_results_dict: Dict[str, Any], company: str, ticker: str) -> Dict[str, str]:
            """Intelligently parse and extract key information from search results."""
            try:
                # Prepare search results summary
                results_summary = []
                for search_type, result in search_results_dict.items():
                    if result.get("error") or not result.get("results"):
                        continue
                    
                    snippets = []
                    for res in result.get("results", [])[:5]:
                        snippet = res.get("snippet", "")
                        title = res.get("title", "")
                        if snippet:
                            snippets.append(f"Title: {title}\nSnippet: {snippet}")
                    
                    if snippets:
                        results_summary.append(f"{search_type}:\n" + "\n\n".join(snippets))
                
                if not results_summary:
                    return {
                        "price_info": "Limited information available",
                        "company_info": "Limited information available",
                        "news_info": "Limited information available",
                        "analysis_info": "Limited information available",
                        "metrics_info": "Limited information available"
                    }
                
                # Use LLM to parse and extract key information with few-shot examples
                parse_prompt = f"""You are a financial research analyst. Parse and extract key information from these search results about {company} ({ticker}).

CRITICAL: Extract ONLY factual, verifiable information from the search results. Do NOT make up data or create nonsensical content.

FEW-SHOT EXAMPLES (Good vs Bad):

GOOD PRICE_INFO:
• Current price: $150.25, up 2.3% from previous close
• 52-week range: $120.50 - $165.00
• Trading volume: 15.2M shares, above 30-day average

BAD PRICE_INFO (nonsensical):
• Stock price is good (too vague, no numbers)
• The company's stock (not specific)
• Price went up or down (no actual data)

GOOD COMPANY_INFO:
• Leading semiconductor manufacturer specializing in AI chips
• Key products: Data center GPUs, automotive chips, gaming graphics cards
• Market position: Dominant share in AI training chip market

BAD COMPANY_INFO (nonsensical):
• Company makes things (too vague)
• They are a business (meaningless)
• Products include stuff (not specific)

GOOD NEWS_INFO:
• Announced Q4 earnings beat expectations, revenue up 15% YoY
• Launched new data center GPU product line in January 2024
• Partnership with major cloud provider announced last month

BAD NEWS_INFO (nonsensical):
• Company had news (too vague)
• Something happened recently (meaningless)
• Updates were made (not specific)

GOOD ANALYSIS_INFO:
• Analysts maintain Buy rating with average price target $180
• Market trends favor AI chip demand growth through 2025
• Competitive position strengthened by new product launches

BAD ANALYSIS_INFO (nonsensical):
• Analysis says things (too vague)
• Market is interesting (meaningless)
• Trends exist (not specific)

GOOD METRICS_INFO:
• P/E ratio: 35.2, above industry average of 28.5
• Market cap: $1.2 trillion
• Revenue growth: 25% YoY, profit margin: 18.5%

BAD METRICS_INFO (nonsensical):
• Financial metrics are good (too vague)
• Company has numbers (meaningless)
• Metrics show performance (not specific)

RULES:
1. Extract ONLY information that appears in the search results
2. Include specific numbers, dates, and facts
3. If information is not available, say "Limited information available" instead of making things up
4. Avoid vague statements like "good performance" or "recent news"
5. Use actual data points: prices, percentages, dates, names

Search Results:
{chr(10).join(results_summary)}

Extract and organize the following information:
1. Stock Price Info: Current price, recent changes, performance metrics
2. Company Info: Business overview, key products/services, market position
3. News Info: Recent developments, important news, company updates
4. Market Analysis: Market trends, analyst insights, forecasts
5. Financial Metrics: Key financial data, valuation metrics, ratios

For each category, provide 3-5 key bullet points with specific facts and figures.
Keep it concise and data-driven. If information is not available, write "Limited information available".

Respond in this format:
PRICE_INFO:
• [bullet point 1 with specific data]
• [bullet point 2 with specific data]
...

COMPANY_INFO:
• [bullet point 1 with specific data]
• [bullet point 2 with specific data]
...

NEWS_INFO:
• [bullet point 1 with specific data]
• [bullet point 2 with specific data]
...

ANALYSIS_INFO:
• [bullet point 1 with specific data]
• [bullet point 2 with specific data]
...

METRICS_INFO:
• [bullet point 1 with specific data]
• [bullet point 2 with specific data]
..."""
                
                response = llm.invoke([
                    SystemMessage(content="You are a financial research analyst expert at extracting and organizing information from search results."),
                    HumanMessage(content=parse_prompt)
                ])
                
                parsed_content = response.content.strip()
                
                # Parse the structured response
                parsed_info = {
                    "price_info": "",
                    "company_info": "",
                    "news_info": "",
                    "analysis_info": "",
                    "metrics_info": ""
                }
                
                current_section = None
                for line in parsed_content.split('\n'):
                    line = line.strip()
                    if line.startswith('PRICE_INFO:'):
                        current_section = 'price_info'
                    elif line.startswith('COMPANY_INFO:'):
                        current_section = 'company_info'
                    elif line.startswith('NEWS_INFO:'):
                        current_section = 'news_info'
                    elif line.startswith('ANALYSIS_INFO:'):
                        current_section = 'analysis_info'
                    elif line.startswith('METRICS_INFO:'):
                        current_section = 'metrics_info'
                    elif current_section and line.startswith('•'):
                        if parsed_info[current_section]:
                            parsed_info[current_section] += "\n"
                        parsed_info[current_section] += line
                
                # Fallback if parsing failed
                for key in parsed_info:
                    if not parsed_info[key]:
                        parsed_info[key] = "Limited information available"
                
                logger.info("[ENRICHED STOCK AGENT] Successfully parsed search results")
                return parsed_info
                
            except Exception as e:
                logger.error(f"[ENRICHED STOCK AGENT] Error parsing search results: {e}")
                # Fallback to simple extraction
                return {
                    "price_info": extract_search_content_simple(search_results_dict.get("Stock price and current performance", {})),
                    "company_info": extract_search_content_simple(search_results_dict.get("Company overview and business model", {})),
                    "news_info": extract_search_content_simple(search_results_dict.get("Recent news and developments", {})),
                    "analysis_info": extract_search_content_simple(search_results_dict.get("Market analysis and trends", {})),
                    "metrics_info": extract_search_content_simple(search_results_dict.get("Financial metrics and valuation", {}))
                }
        
        def extract_search_content_simple(search_result):
            """Simple fallback extraction."""
            if search_result.get("error") or not search_result.get("results"):
                return "Limited information available"
            
            content = []
            for result in search_result.get("results", [])[:3]:
                snippet = result.get("snippet", "")
                if snippet:
                    content.append(f"• {snippet}")
            
            return "\n".join(content) if content else "Limited information available"
        
        # Parse all search results
        parsed_info = parse_search_results(search_results, company, ticker)
        
        # Combine with yfinance data
        price_info_combined = f"""{price_info}

Additional Web Research:
{parsed_info['price_info']}"""
        
        company_info_combined = f"""{company_info}

Additional Web Research:
{parsed_info['company_info']}"""
        
        news_info = parsed_info['news_info']
        analysis_info = parsed_info['analysis_info']
        metrics_info_combined = f"""{metrics_info}

Additional Web Research:
{parsed_info['metrics_info']}"""

        # Step 3: Planning stage - Create slide structure plan
        logger.info("[ENRICHED STOCK AGENT] Step 3: Planning slide structure...")
        
        planning_prompt = f"""You are a presentation planning expert. Create a detailed plan for a 5-slide stock analysis presentation about {company} ({ticker}).

Available Information:
- Stock Price: {price_info_combined[:500]}...
- Company Info: {company_info_combined[:500]}...
- Recent News: {news_info[:500]}...
- Market Analysis: {analysis_info[:500]}...
- Financial Metrics: {metrics_info_combined[:500]}...

Create a structured plan that defines:
1. What specific information goes in each slide
2. Key points to highlight
3. How to organize the 5 slides logically

The 5 slides should be:
- Slide 1: Stock Price Overview (current price, change, date)
- Slide 2: Performance Metrics (52-week range, market cap, volume)
- Slide 3: Company Analysis (business overview, products, position)
- Slide 4: Market Analysis (news highlights, trends, insights)
- Slide 5: Conclusion & Outlook (strengths, risks, outlook)

For each slide, specify:
- Title
- 3-4 key bullet points with specific data points
- Which information sources to use

Respond in this format:
SLIDE_PLAN:
Slide 1: [Title]
- Bullet 1: [specific data point from available info]
- Bullet 2: [specific data point]
- Bullet 3: [specific data point]
- Bullet 4: [specific data point]

Slide 2: [Title]
- Bullet 1: [specific data point]
...

[Continue for all 5 slides]"""

        planning_messages = [
            SystemMessage(content="You are a presentation planning expert specializing in financial presentations."),
            HumanMessage(content=planning_prompt)
        ]
        
        planning_response = llm.invoke(planning_messages)
        slide_plan = planning_response.content.strip()
        logger.info("[ENRICHED STOCK AGENT] Slide structure plan created")

        # Step 4: Use AI to synthesize and structure the information based on plan
        logger.info("[ENRICHED STOCK AGENT] Step 4: Synthesizing information with AI...")

        # Update LLM temperature for synthesis
        llm_synthesis = ChatOpenAI(
            model=openai_config.get("model", "gpt-4o"),
            temperature=get_temperature_for_model(config, default_temperature=0.7),
            api_key=openai_config.get("api_key")
        )

        synthesis_prompt = f"""You are a financial analyst creating a professional stock analysis presentation.

CRITICAL: Use ONLY factual data from the information provided. Do NOT create nonsensical or vague content.

FEW-SHOT EXAMPLES (Good vs Bad):

GOOD SLIDE CONTENT (data-driven, specific):
SLIDE 1: Stock Price Overview
• Current Price: $150.25 | Change: +2.3%
• Previous Close: $146.89
• As of January 15, 2024

SLIDE 3: Company Analysis
• Leading AI chip manufacturer
• Products: Data center GPUs, gaming cards
• Market leader in AI training chips

SLIDE 4: Market Analysis
• Q4 earnings beat expectations
• Analyst target: $180 average
• Strong demand through 2025

BAD SLIDE CONTENT (nonsensical, vague):
SLIDE 1: Stock Price Overview
• Stock price is good (too vague, no numbers)
• Price changed recently (no actual data)
• Data from somewhere (not specific)

SLIDE 3: Company Analysis
• Company makes things (too vague)
• They have products (meaningless)
• Market position is strong (not specific)

SLIDE 4: Market Analysis
• Company had news (too vague)
• Analysis says things (meaningless)
• Trends exist (not specific)

RULES:
1. Use ONLY actual numbers, dates, and facts from the information provided
2. If data is not available, write "Data not available" instead of making things up
3. Avoid vague statements - always include specific numbers or facts
4. Each bullet must be MAX 7 words
5. Be concise and professional

SLIDE PLAN (follow this structure):
{slide_plan}

AVAILABLE INFORMATION:

STOCK PRICE INFORMATION:
{price_info_combined}

COMPANY INFORMATION:
{company_info_combined}

RECENT NEWS:
{news_info}

MARKET ANALYSIS:
{analysis_info}

FINANCIAL METRICS:
{metrics_info_combined}

IMPORTANT: Always include the data date ({data_date}) in the presentation. If the data is more than 3 days old, add a disclaimer that prices may have changed.

PRESENTATION REQUIREMENTS:
- Create EXACTLY 5 content slides following the plan above
- Each slide: 3-4 bullets MAXIMUM
- Each bullet: MAX 7 words (shorter is better)
- Use actual numbers and data from the information provided above
- Be specific and data-driven
- If information is not available, write "Data not available" instead of making things up

SLIDE STRUCTURE (follow this exact format):

SLIDE 1: Stock Price Overview
• Current Price: ${current_price:.2f} | Change: {price_change_pct:+.2f}%
• Previous Close: ${prev_close:.2f}
• As of {data_date}

SLIDE 2: Performance Metrics
• 52-Week Range: ${info.get('fiftyTwoWeekLow', 0):.2f} - ${info.get('fiftyTwoWeekHigh', 0):.2f}
• Market Cap: ${info.get('marketCap', 0):,}
• Average Volume: {info.get('averageVolume', 0):,} shares

SLIDE 3: Company Analysis
• [Business overview - concise, from company info, use actual facts]
• [Key product/service - from company info, be specific]
• [Market position/strength - from company info, use data]

SLIDE 4: Market Analysis
• [Recent news highlight - from news info, include specific details]
• [Market trend - from analysis info, use actual data]
• [Analyst insight - from analysis info, be specific]

SLIDE 5: Conclusion & Outlook
• [Key strength - data-driven, use actual numbers]
• [Key consideration/risk - data-driven, be specific]
• [Investment outlook summary - data-driven, use facts]

Keep it DATA-DRIVEN: use actual numbers from the information provided above.
Keep it CONCISE: short bullets, clear insights, professional tone.
Follow the slide plan structure but use actual data from the available information.
Do NOT create vague or nonsensical content - if data is missing, say "Data not available"."""

        messages = [
            SystemMessage(content="You are a professional financial analyst creating clear, data-driven stock presentations."),
            HumanMessage(content=synthesis_prompt)
        ]

        response = llm_synthesis.invoke(messages)
        enriched_content = response.content.strip()

        logger.info("[ENRICHED STOCK AGENT] Step 5: Creating presentation...")

        # Step 5: Create the presentation
        pres_result = create_keynote_with_images.invoke({
            "title": f"{company} Stock Analysis",
            "content": enriched_content,
            "image_paths": []  # No screenshots - text-based only
        })

        if pres_result.get("error"):
            return pres_result

        # Extract key data for response
        result = {
            "success": True,
            "presentation_path": pres_result.get("keynote_path") or pres_result.get("file_path"),
            "company": info.get('longName', company),
            "ticker": ticker,
            "current_price": f"${current_price:.2f}",
            "price_change": f"${price_change:+.2f} ({price_change_pct:+.2f}%)",
            "data_date": data_date,
            "data_age_days": days_old,
            "enriched_content": enriched_content,
            "data_sources": {
                "yfinance": "Stock price and financial data",
                "web_searches": {
                    "price_performance": len(search_results.get("Stock price and current performance", {}).get("results", [])),
                    "company_overview": len(search_results.get("Company overview and business model", {}).get("results", [])),
                    "recent_news": len(search_results.get("Recent news and developments", {}).get("results", [])),
                    "market_analysis": len(search_results.get("Market analysis and trends", {}).get("results", [])),
                    "financial_metrics": len(search_results.get("Financial metrics and valuation", {}).get("results", []))
                }
            },
            "total_searches": 5,
            "slide_plan": slide_plan,
            "message": f"Created enriched presentation for {info.get('longName', company)} ({ticker}) with data as of {data_date}"
        }

        logger.info(f"[ENRICHED STOCK AGENT] ✅ Successfully created presentation with real stock data")
        return result

    except Exception as e:
        logger.error(f"[ENRICHED STOCK AGENT] Error creating presentation: {e}", exc_info=True)
        return {
            "error": True,
            "error_type": "PresentationError",
            "error_message": str(e),
            "retry_possible": False
        }
    finally:
        # Release lock if acquired
        if AGENT_COORDINATION_AVAILABLE and lock_acquired:
            try:
                release_lock(files_to_modify[0], AGENT_ID)
                logger.info(f"[ENRICHED STOCK AGENT] Lock released for {files_to_modify[0]}")
            except Exception as e:
                logger.warning(f"[ENRICHED STOCK AGENT] Error releasing lock: {e}")


@tool
def create_enriched_stock_report(company: str, output_format: str = "pdf") -> Dict[str, Any]:
    """
    Create an intelligent, well-researched stock report (PDF or HTML) using yfinance data.

    This tool performs the same comprehensive analysis as the presentation tool
    but outputs a detailed report format instead of slides.

    Args:
        company: Company name or ticker (e.g., "NVIDIA", "NVDA", "Apple")
        output_format: "pdf" or "html" (default: "pdf")

    Returns:
        Dictionary with report path and enriched content

    Example:
        create_enriched_stock_report("NVIDIA", "pdf")
    """
    logger.info(f"[ENRICHED STOCK AGENT] Creating {output_format} report for: {company}")

    try:
        import yfinance as yf
        from src.utils import load_config

        # Step 1: Get reliable stock data (same as presentation)
        logger.info("[ENRICHED STOCK AGENT] Step 1: Fetching stock data from yfinance...")

        ticker = company.upper().strip()
        ticker_map = {
            "NVIDIA": "NVDA", "APPLE": "AAPL", "MICROSOFT": "MSFT",
            "AMAZON": "AMZN", "GOOGLE": "GOOGL", "META": "META",
            "FACEBOOK": "META", "TESLA": "TSLA", "AMD": "AMD", "INTEL": "INTC"
        }

        if ticker in ticker_map:
            ticker = ticker_map[ticker]
            logger.info(f"[ENRICHED STOCK AGENT] Mapped company name to ticker: {ticker}")

        stock = yf.Ticker(ticker)
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5)
        hist = stock.history(start=start_date, end=end_date)
        info = stock.info

        if hist.empty or not info or not info.get('regularMarketPrice'):
            return {
                "error": True,
                "error_type": "TickerNotFound",
                "error_message": f"Could not find stock data for: {company}",
                "retry_possible": True
            }

        # Calculate metrics
        latest_date = hist.index[-1]
        latest_dt = latest_date.to_pydatetime()
        if latest_dt.tzinfo is not None:
            from datetime import timezone
            now_dt = datetime.now(timezone.utc)
            if latest_dt.tzinfo != timezone.utc:
                latest_dt = latest_dt.astimezone(timezone.utc)
        else:
            now_dt = datetime.now()

        days_old = (now_dt - latest_dt).days
        data_date = latest_date.strftime("%B %d, %Y")

        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        price_change = current_price - prev_close
        price_change_pct = (price_change / prev_close) * 100

        # Step 2: Build comprehensive report sections
        logger.info("[ENRICHED STOCK AGENT] Step 2: Building report sections...")

        company_name = info.get('longName', company)

        sections = [
            {
                "heading": "Executive Summary",
                "content": f"""{company_name} ({ticker})

Current Price: ${current_price:.2f} (as of {data_date})
Price Change: ${price_change:+.2f} ({price_change_pct:+.2f}%)
Sector: {info.get('sector', 'N/A')}
Industry: {info.get('industry', 'N/A')}

This report provides a comprehensive analysis of {company_name}'s stock performance, financial metrics, and investment outlook based on data retrieved from Yahoo Finance."""
            },
            {
                "heading": "Stock Price Performance",
                "content": f"""Current Price: ${current_price:.2f}
Previous Close: ${prev_close:.2f}
Price Change: ${price_change:+.2f} ({price_change_pct:+.2f}%)

52-Week Range: ${info.get('fiftyTwoWeekLow', 0):.2f} - ${info.get('fiftyTwoWeekHigh', 0):.2f}
Average Volume: {info.get('averageVolume', 0):,} shares

Data Date: {data_date} ({days_old} days old)"""
            },
            {
                "heading": "Company Overview",
                "content": f"""{info.get('longBusinessSummary', 'No description available.')}

Sector: {info.get('sector', 'N/A')}
Industry: {info.get('industry', 'N/A')}
Employees: {info.get('fullTimeEmployees', 'N/A'):,} (if available)"""
            },
            {
                "heading": "Financial Metrics & Valuation",
                "content": f"""Market Capitalization: ${info.get('marketCap', 0):,}
P/E Ratio (Trailing): {info.get('trailingPE', 'N/A')}
Price-to-Book: {info.get('priceToBook', 'N/A')}
Dividend Yield: {info.get('dividendYield', 0)*100:.2f}% (if applicable)

Revenue: ${info.get('totalRevenue', 0):,}
Profit Margin: {info.get('profitMargins', 0)*100:.2f}% (if available)"""
            },
            {
                "heading": "Investment Analysis",
                "content": f"""Based on the current metrics:

Valuation: The stock trades at a P/E ratio of {info.get('trailingPE', 'N/A')}, with a market capitalization of ${info.get('marketCap', 0):,}.

Price Performance: Over the past year, the stock has ranged from ${info.get('fiftyTwoWeekLow', 0):.2f} to ${info.get('fiftyTwoWeekHigh', 0):.2f}, currently trading at ${current_price:.2f}.

Risk Considerations: Investors should consider market volatility, sector trends, and company-specific factors when evaluating this investment."""
            }
        ]

        # Step 3: Create report as HTML file (simple and reliable)
        logger.info("[ENRICHED STOCK AGENT] Step 3: Generating HTML report...")

        import os
        from pathlib import Path

        # Build HTML content
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{company_name} ({ticker}) Stock Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; }}
        .header {{ background: #ecf0f1; padding: 20px; border-radius: 5px; margin-bottom: 30px; }}
        .content {{ margin-bottom: 20px; }}
        pre {{ background: #f4f4f4; padding: 15px; border-left: 4px solid #3498db; white-space: pre-wrap; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #bdc3c7; color: #7f8c8d; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{company_name} ({ticker}) Stock Analysis Report</h1>
        <p><strong>Generated:</strong> {datetime.now().strftime("%B %d, %Y at %I:%M %p")}</p>
        <p><strong>Data Date:</strong> {data_date} ({days_old} days old)</p>
    </div>
"""

        # Add sections
        for section in sections:
            html_content += f"""
    <div class="content">
        <h2>{section['heading']}</h2>
        <pre>{section['content']}</pre>
    </div>
"""

        html_content += f"""
    <div class="footer">
        <p>This report was generated using data from Yahoo Finance via the yfinance API.</p>
        <p>Stock prices and financial data are subject to market changes. This report is for informational purposes only and should not be considered financial advice.</p>
    </div>
</body>
</html>
"""

        # Save to file
        reports_dir = Path(os.path.expanduser("~/Documents"))
        reports_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{ticker}_stock_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        actual_path = reports_dir / filename

        with open(actual_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"[ENRICHED STOCK AGENT] Report saved to: {actual_path}")

        return {
            "success": True,
            "report_path": actual_path,
            "output_format": output_format,
            "company": company_name,
            "ticker": ticker,
            "current_price": f"${current_price:.2f}",
            "price_change": f"${price_change:+.2f} ({price_change_pct:+.2f}%)",
            "data_date": data_date,
            "data_age_days": days_old,
            "message": f"Created {output_format.upper()} report for {company_name} ({ticker}) with data as of {data_date}"
        }

    except Exception as e:
        logger.error(f"[ENRICHED STOCK AGENT] Error creating report: {e}", exc_info=True)
        return {
            "error": True,
            "error_type": "ReportError",
            "error_message": str(e),
            "retry_possible": False
        }


@tool
def create_stock_report_and_email(company: str, recipient: str = "me") -> Dict[str, Any]:
    """
    Complete workflow: Create enriched stock presentation and email it.

    This high-level tool:
    1. Creates an enriched stock presentation using comprehensive web research
    2. Emails the presentation to the specified recipient

    Args:
        company: Company name or ticker (e.g., "NVIDIA", "Apple")
        recipient: Email recipient (default: "me" uses config default_recipient)

    Returns:
        Dictionary with presentation path, email status, and summary

    Example:
        create_stock_report_and_email("NVIDIA", "me")
    """
    logger.info(f"[ENRICHED STOCK AGENT] Complete workflow for {company} to {recipient}")

    try:
        # Step 1: Create enriched presentation
        pres_result = create_enriched_stock_presentation.invoke({"company": company})

        if pres_result.get("error"):
            return pres_result

        # Step 2: Email the presentation
        from src.agent.email_agent import compose_email

        presentation_path = pres_result.get("presentation_path")

        # Create email body with comprehensive summary
        company_name = pres_result.get('company', company)
        ticker = pres_result.get('ticker', '')
        current_price = pres_result.get('current_price', 'N/A')
        price_change = pres_result.get('price_change', 'N/A')
        data_date = pres_result.get('data_date', 'N/A')
        total_searches = pres_result.get('total_searches', 5)
        
        email_body = f"""Stock Analysis Report: {company_name} ({ticker})

I've created a comprehensive stock analysis presentation for {company_name} ({ticker}) based on current web research and market data.

PRESENTATION SUMMARY:
• Current Price: {current_price}
• Price Change: {price_change}
• Data Date: {data_date}

The presentation includes 5 slides covering:
1. Stock Price Overview - Current price, change, and date
2. Performance Metrics - 52-week range, market cap, volume
3. Company Analysis - Business overview, products, market position
4. Market Analysis - Recent news, trends, analyst insights
5. Conclusion & Outlook - Key strengths, risks, investment outlook

RESEARCH SOURCES:
• {total_searches} comprehensive web searches covering:
  - Stock price and current performance
  - Company overview and business model
  - Recent news and developments
  - Market analysis and trends
  - Financial metrics and valuation
• Yahoo Finance data via yfinance API

Please find the detailed presentation attached as a Keynote file.

Best regards,
Your Automation Assistant"""

        logger.info("[ENRICHED STOCK AGENT] Sending email with presentation...")
        
        # Verify presentation path exists and convert to absolute path
        import os
        from pathlib import Path
        
        attachments = []
        if presentation_path:
            # Convert to absolute path
            try:
                abs_presentation_path = os.path.abspath(os.path.expanduser(presentation_path))
            except Exception as e:
                logger.error(f"[ENRICHED STOCK AGENT] Failed to convert presentation path to absolute: {e}")
                abs_presentation_path = presentation_path
            
            # Verify file exists
            if not os.path.exists(abs_presentation_path):
                logger.error(f"[ENRICHED STOCK AGENT] ⚠️  Presentation file not found: {abs_presentation_path}")
                return {
                    "success": False,
                    "presentation_created": True,
                    "presentation_path": presentation_path,
                    "email_sent": False,
                    "email_error": f"Presentation file not found: {abs_presentation_path}",
                    "message": "Presentation created successfully but file not found for email attachment"
                }
            
            # Verify it's a file (not a directory)
            if not os.path.isfile(abs_presentation_path):
                logger.error(f"[ENRICHED STOCK AGENT] ⚠️  Presentation path is not a file: {abs_presentation_path}")
                return {
                    "success": False,
                    "presentation_created": True,
                    "presentation_path": presentation_path,
                    "email_sent": False,
                    "email_error": f"Presentation path is not a file: {abs_presentation_path}",
                    "message": "Presentation created successfully but path is not a valid file"
                }
            
            # Verify file is readable
            if not os.access(abs_presentation_path, os.R_OK):
                logger.error(f"[ENRICHED STOCK AGENT] ⚠️  Presentation file is not readable: {abs_presentation_path}")
                return {
                    "success": False,
                    "presentation_created": True,
                    "presentation_path": presentation_path,
                    "email_sent": False,
                    "email_error": f"Presentation file is not readable: {abs_presentation_path}",
                    "message": "Presentation created successfully but file is not readable"
                }
            
            attachments.append(abs_presentation_path)
            logger.info(f"[ENRICHED STOCK AGENT] ✅ Verified and attaching presentation: {abs_presentation_path}")
        
        email_result = compose_email.invoke({
            "subject": f"{company_name} ({ticker}) Stock Analysis Report",
            "body": email_body,
            "recipient": recipient,
            "attachments": attachments,
            "send": True
        })

        if email_result.get("error"):
            return {
                "success": False,
                "presentation_created": True,
                "presentation_path": presentation_path,
                "email_sent": False,
                "email_error": email_result.get("error_message"),
                "message": "Presentation created successfully but email failed"
            }

        return {
            "success": True,
            "presentation_path": presentation_path,
            "email_status": email_result.get("status"),
            "company": company,
            "searches_performed": pres_result.get("total_searches", 5),
            "message": f"Successfully created and emailed {company} stock analysis"
        }

    except Exception as e:
        logger.error(f"[ENRICHED STOCK AGENT] Workflow error: {e}", exc_info=True)
        return {
            "error": True,
            "error_type": "WorkflowError",
            "error_message": str(e),
            "retry_possible": False
        }


# Export tools
ENRICHED_STOCK_AGENT_TOOLS = [
    create_enriched_stock_presentation,
    create_enriched_stock_report,
    create_stock_report_and_email,
]


class EnrichedStockAgent:
    """Enriched Stock Agent - Intelligent stock presentations using web research."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in ENRICHED_STOCK_AGENT_TOOLS}
        logger.info(f"[ENRICHED STOCK AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self):
        return ENRICHED_STOCK_AGENT_TOOLS

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Tool '{tool_name}' not found"
            }

        tool = self.tools[tool_name]
        logger.info(f"[ENRICHED STOCK AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[ENRICHED STOCK AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e)
            }
