from googlesearch import search
from bs4 import BeautifulSoup
import requests

query = "OpenAI GPT-5 updates"
print(f"Searching Google for: {query}\n")

# Step 1: Get top 5 results
results = search(query, num_results=5)

# Step 2: Fetch and show text snippets
for i, url in enumerate(results, start=1):
    print(f"{i}. {url}")

    try:
        response = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract visible text snippet
        text = " ".join(soup.stripped_strings)[:400]  # first ~400 chars for preview
        print(f"Snippet:\n{text}\n")
    except Exception as e:
        print(f"Could not fetch {url}: {e}\n")
