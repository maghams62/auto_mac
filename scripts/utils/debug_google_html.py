#!/usr/bin/env python3
"""
Debug script to see what HTML Google is returning.
"""

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

def debug_google_html():
    headers = {"User-Agent": USER_AGENT}
    params = {"q": "Python programming", "num": 5, "hl": "en"}

    response = requests.get(
        "https://www.google.com/search",
        params=params,
        headers=headers,
        timeout=10,
    )

    print("Status code:", response.status_code)
    print("=" * 80)

    soup = BeautifulSoup(response.text, "html.parser")

    # Save full HTML for inspection
    with open("/tmp/google_response.html", "w") as f:
        f.write(response.text)
    print("Full HTML saved to /tmp/google_response.html")
    print("=" * 80)

    # Try different selectors
    print("\nTrying selector: div.g")
    results_g = soup.select("div.g")
    print(f"Found {len(results_g)} results with 'div.g'")

    print("\nTrying selector: div[data-sokoban-container]")
    results_sokoban = soup.select("div[data-sokoban-container]")
    print(f"Found {len(results_sokoban)} results with 'div[data-sokoban-container]'")

    print("\nTrying selector: div.Gx5Zad")
    results_gx = soup.select("div.Gx5Zad")
    print(f"Found {len(results_gx)} results with 'div.Gx5Zad'")

    print("\nTrying selector: a h3")
    h3_results = soup.select("a h3")
    print(f"Found {len(h3_results)} h3 elements")
    if h3_results:
        for idx, h3 in enumerate(h3_results[:3], 1):
            print(f"  {idx}. {h3.get_text(strip=True)}")

    print("\nTrying selector: div#search")
    search_div = soup.select_one("div#search")
    if search_div:
        print("Found div#search")
        # Look for links with h3
        links = search_div.select("a")
        print(f"Found {len(links)} links in search div")

    print("\n" + "=" * 80)
    print("Analyzing first result block...")
    print("=" * 80)

    if results_g:
        first = results_g[0]
        print("First div.g HTML:")
        print(first.prettify()[:500])
    elif results_sokoban:
        first = results_sokoban[0]
        print("First sokoban container HTML:")
        print(first.prettify()[:500])
    else:
        print("No result blocks found!")

if __name__ == "__main__":
    debug_google_html()
