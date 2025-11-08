"""Debug script to see what's on the Apple Stocks page."""

from playwright.sync_api import sync_playwright

url = "https://stocks.apple.com/symbol/NVDA"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # Non-headless to see what's happening
    page = browser.new_page()

    print(f"Loading {url}...")
    page.goto(url, wait_until='networkidle', timeout=30000)

    print("\nWaiting 3 seconds for content...")
    page.wait_for_timeout(3000)

    # Save screenshot
    page.screenshot(path="debug_stock_page.png")
    print("Screenshot saved to debug_stock_page.png")

    # Get page HTML
    html = page.content()
    with open("debug_stock_page.html", "w") as f:
        f.write(html)
    print("HTML saved to debug_stock_page.html")

    # Try to find price elements
    print("\nLooking for price-related elements...")

    # Try various selectors
    selectors_to_try = [
        '.quote-header__price',
        '[data-test="current-price"]',
        '.price-value',
        'div[class*="price"]',
        'span[class*="price"]',
        'div:has-text("$")',
    ]

    for selector in selectors_to_try:
        try:
            elements = page.query_selector_all(selector)
            if elements:
                print(f"\n✓ Found {len(elements)} element(s) with selector: {selector}")
                for i, el in enumerate(elements[:3]):  # Show first 3
                    print(f"  [{i}] {el.inner_text()[:100]}")
        except Exception as e:
            print(f"✗ Error with selector {selector}: {e}")

    input("\nPress Enter to close browser...")
    browser.close()
