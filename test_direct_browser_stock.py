"""
Test direct browser access to stocks.apple.com to see what data is available.
"""

import asyncio
from playwright.async_api import async_playwright


async def test_stock_page():
    """Test accessing stocks.apple.com page."""
    symbol = "NVDA"
    url = f"https://stocks.apple.com/symbol/{symbol}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        print(f"Loading {url}...")
        await page.goto(url, wait_until='networkidle')

        print("Waiting 3 seconds for content to load...")
        await asyncio.sleep(3)

        # Get all text content
        text = await page.inner_text('body')
        print("\n" + "=" * 80)
        print("PAGE TEXT CONTENT:")
        print("=" * 80)
        print(text[:1000])  # First 1000 chars

        # Try to find specific elements
        print("\n" + "=" * 80)
        print("SEARCHING FOR PRICE ELEMENTS:")
        print("=" * 80)

        # Look for anything with numbers that might be the price
        all_text_els = await page.query_selector_all('*')
        for el in all_text_els[:50]:  # Check first 50 elements
            try:
                text = await el.inner_text()
                if '$' in text and any(c.isdigit() for c in text):
                    tag = await el.evaluate('el => el.tagName')
                    class_name = await el.get_attribute('class') or ''
                    print(f"{tag}.{class_name[:30]}: {text[:50]}")
            except:
                pass

        input("\nPress Enter to close...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_stock_page())
