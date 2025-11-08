"""
Stock data scraper using Playwright to fetch real-time data from stocks.apple.com
"""

import logging
from typing import Dict, Any, Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import re

logger = logging.getLogger(__name__)


class StockScraper:
    """Scrapes stock data from stocks.apple.com using Playwright."""

    def __init__(self):
        self.base_url = "https://stocks.apple.com/symbol"

    def get_stock_data(self, symbol: str) -> Dict[str, Any]:
        """
        Scrape stock data from Apple Stocks website.

        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL', 'NVDA')

        Returns:
            Dictionary with stock data including price, change, etc.
        """
        symbol = symbol.upper()
        url = f"{self.base_url}/{symbol}"

        logger.info(f"Scraping stock data for {symbol} from {url}")

        try:
            with sync_playwright() as p:
                # Launch browser in headless mode
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )
                page = context.new_page()

                # Navigate to stock page
                try:
                    page.goto(url, wait_until='networkidle', timeout=30000)
                except PlaywrightTimeout:
                    logger.warning(f"Timeout loading {url}, continuing anyway")

                # Wait a bit for dynamic content to load
                page.wait_for_timeout(2000)

                # Extract stock data from the page
                result = self._extract_stock_data(page, symbol)

                browser.close()
                return result

        except Exception as e:
            logger.error(f"Error scraping stock data for {symbol}: {e}")
            return {
                "error": True,
                "error_type": "ScrapingError",
                "error_message": f"Failed to scrape stock data: {str(e)}",
                "retry_possible": True
            }

    def _extract_stock_data(self, page, symbol: str) -> Dict[str, Any]:
        """Extract stock data from the loaded page."""
        try:
            # Get company name
            company_name = self._safe_extract(
                page,
                'h1.quote-header__company-name, [data-test="company-name"]',
                default=symbol
            )

            # Get current price
            price_text = self._safe_extract(
                page,
                '.quote-header__price, [data-test="current-price"], .price-value',
                default="0"
            )
            current_price = self._parse_number(price_text)

            # Get price change
            change_text = self._safe_extract(
                page,
                '.quote-header__change, [data-test="price-change"], .change-value',
                default="0"
            )
            change = self._parse_number(change_text)

            # Get percent change
            change_percent_text = self._safe_extract(
                page,
                '.quote-header__change-percent, [data-test="percent-change"], .percent-change',
                default="0%"
            )
            change_percent = self._parse_number(change_percent_text.replace('%', ''))

            # Calculate previous close
            previous_close = current_price - change if current_price and change else None

            # Get market cap if available
            market_cap_text = self._safe_extract(
                page,
                '[data-test="market-cap"], .market-cap-value',
                default=None
            )
            market_cap = self._parse_market_cap(market_cap_text) if market_cap_text else None

            # Get 52-week high/low if available
            high_52w = self._safe_extract(page, '[data-test="52w-high"]', default=None)
            low_52w = self._safe_extract(page, '[data-test="52w-low"]', default=None)

            # Format message safely
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
                "fifty_two_week_high": self._parse_number(high_52w) if high_52w else None,
                "fifty_two_week_low": self._parse_number(low_52w) if low_52w else None,
                "message": message,
                "source": "stocks.apple.com"
            }

        except Exception as e:
            logger.error(f"Error extracting stock data: {e}")
            raise

    def _safe_extract(self, page, selector: str, default=None) -> Optional[str]:
        """Safely extract text from a selector."""
        try:
            element = page.query_selector(selector)
            if element:
                text = element.inner_text().strip()
                return text if text else default
            return default
        except Exception as e:
            logger.debug(f"Could not extract from selector {selector}: {e}")
            return default

    def _parse_number(self, text: str) -> Optional[float]:
        """Parse a number from text, handling various formats."""
        if not text:
            return None

        try:
            # Remove currency symbols, commas, spaces, and + signs
            cleaned = re.sub(r'[$,\s+]', '', text)
            # Handle negative numbers
            cleaned = cleaned.replace('−', '-')  # Replace minus sign with hyphen
            return float(cleaned)
        except (ValueError, AttributeError):
            logger.debug(f"Could not parse number from: {text}")
            return None

    def _parse_market_cap(self, text: str) -> Optional[float]:
        """Parse market cap from text like '2.5T' or '500B'."""
        if not text:
            return None

        try:
            # Extract number and multiplier
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

        except Exception as e:
            logger.debug(f"Could not parse market cap from: {text}")
            return None


def test_scraper():
    """Test the stock scraper."""
    scraper = StockScraper()

    print("Testing Stock Scraper")
    print("=" * 80)

    # Test NVDA (Nvidia)
    print("\nTesting NVDA (Nvidia)...")
    result = scraper.get_stock_data("NVDA")

    if result.get("error"):
        print(f"❌ Error: {result.get('error_message')}")
    else:
        print(f"✅ {result['message']}")
        print(f"   Current Price: ${result['current_price']}")
        print(f"   Change: ${result['change']} ({result['change_percent']:+.2f}%)")
        print(f"   Company: {result['company_name']}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_scraper()
