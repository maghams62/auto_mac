# Browser Tools Quick Start Guide

## Installation

```bash
# 1. Install Python dependencies
pip install playwright langextract

# 2. Install Playwright browser binaries (required!)
playwright install

# 3. Verify installation
python -c "from src.agent.browser_tools import BROWSER_TOOLS; print('✅ Browser tools ready!')"
```

## Available Browser Tools

### 1. `google_search` - LEVEL 1 (Primary Search)
Search Google and get structured results.

```python
from src.agent.browser_tools import google_search

result = google_search.invoke({
    "query": "Python documentation",
    "num_results": 5
})

print(result["results"])
# [
#   {
#     "position": 1,
#     "title": "Python.org",
#     "link": "https://www.python.org/doc/",
#     "snippet": "Official Python documentation..."
#   },
#   ...
# ]
```

**When to use**: Finding information on the web, discovering URLs

### 2. `navigate_to_url` - LEVEL 2 (Navigation)
Visit a specific webpage.

```python
from src.agent.browser_tools import navigate_to_url

result = navigate_to_url.invoke({
    "url": "https://docs.python.org/3/",
    "wait_until": "load"  # or "domcontentloaded", "networkidle"
})

print(f"Page title: {result['title']}")
print(f"Status: {result['status']}")
```

**When to use**: Visiting known URLs from search results

### 3. `extract_page_content` - LEVEL 2 (Content Extraction)
Extract clean text from a webpage using langextract.

```python
from src.agent.browser_tools import extract_page_content

# Option 1: Extract from URL (navigates + extracts)
result = extract_page_content.invoke({
    "url": "https://en.wikipedia.org/wiki/Python_(programming_language)"
})

# Option 2: Extract from current page
result = extract_page_content.invoke({})

print(f"Title: {result['title']}")
print(f"Word count: {result['word_count']}")
print(f"Content: {result['content'][:500]}...")
print(f"Method: {result['extraction_method']}")  # "langextract" or "basic"
```

**When to use**:
- Reading webpage content for analysis
- Preparing text for LLM processing
- Getting clean text without ads/navigation

**Key feature**: Uses langextract to automatically remove noise!

### 4. `take_web_screenshot` - LEVEL 3 (Visual Capture)
Capture a screenshot of a webpage.

```python
from src.agent.browser_tools import take_web_screenshot

# Option 1: Screenshot from URL
result = take_web_screenshot.invoke({
    "url": "https://example.com",
    "full_page": True  # Capture entire page
})

# Option 2: Screenshot current page
result = take_web_screenshot.invoke({
    "full_page": False  # Viewport only
})

print(f"Screenshot saved to: {result['screenshot_path']}")
```

**When to use**: Visual proof, documentation, capturing dynamic content

### 5. `close_browser` - LEVEL 4 (Cleanup)
Close browser and free resources.

```python
from src.agent.browser_tools import close_browser

result = close_browser.invoke({})
print(result["message"])
```

**When to use**: At the end of web browsing sessions

## Common Workflows

### Workflow 1: Research & Extract Content
```python
from src.agent.browser_tools import google_search, extract_page_content, close_browser

# 1. Search for information
search_result = google_search.invoke({
    "query": "LangChain documentation",
    "num_results": 3
})

# 2. Extract content from first result
url = search_result["results"][0]["link"]
content_result = extract_page_content.invoke({"url": url})

# 3. Use the extracted content
print(f"Extracted {content_result['word_count']} words")
print(content_result["content"][:1000])

# 4. Clean up
close_browser.invoke({})
```

### Workflow 2: Direct URL Extraction
```python
from src.agent.browser_tools import extract_page_content, close_browser

# One-step: Navigate + Extract
result = extract_page_content.invoke({
    "url": "https://docs.python.org/3/library/asyncio.html"
})

print(result["content"])
close_browser.invoke({})
```

### Workflow 3: Search & Screenshot
```python
from src.agent.browser_tools import google_search, take_web_screenshot, close_browser

# 1. Find page
search_result = google_search.invoke({
    "query": "OpenAI GPT-4",
    "num_results": 1
})

# 2. Screenshot first result
url = search_result["results"][0]["link"]
screenshot_result = take_web_screenshot.invoke({
    "url": url,
    "full_page": True
})

print(f"Screenshot: {screenshot_result['screenshot_path']}")
close_browser.invoke({})
```

### Workflow 4: Combined with Core Tools
```python
from src.agent.browser_tools import google_search, extract_page_content, close_browser
from src.agent.tools import create_keynote

# 1. Research web content
search_result = google_search.invoke({"query": "Python asyncio tutorial", "num_results": 1})
content_result = extract_page_content.invoke({"url": search_result["results"][0]["link"]})
close_browser.invoke({})

# 2. Create presentation with extracted content
keynote_result = create_keynote.invoke({
    "title": "Python Asyncio",
    "content": content_result["content"]
})

print(f"Presentation: {keynote_result['keynote_path']}")
```

## Using with Orchestrator

The orchestrator automatically has access to browser tools:

```python
from main_orchestrator import MainOrchestrator
from src.utils import load_config

config = load_config()
orchestrator = MainOrchestrator(config)

# Ask for web-based tasks
result = orchestrator.run(
    goal="Search for LangChain documentation and create a summary"
)

# The planner will automatically use:
# 1. google_search
# 2. extract_page_content
# 3. close_browser
# 4. [possibly create_pages_doc or create_keynote]
```

## Error Handling

All browser tools return consistent error format:

```python
result = google_search.invoke({"query": "test", "num_results": 5})

if result.get("error"):
    print(f"Error type: {result['error_type']}")
    print(f"Message: {result['error_message']}")
    print(f"Retryable: {result['retry_possible']}")
else:
    print("Success!")
    print(result)
```

Common error types:
- `SearchError` - Google search failed
- `NavigationError` - Failed to navigate to URL
- `ExtractionError` - Content extraction failed
- `ScreenshotError` - Screenshot capture failed
- `BrowserError` - Browser initialization/cleanup failed

## Tips & Best Practices

### 1. Always Close Browser
```python
try:
    # ... browser operations ...
finally:
    close_browser.invoke({})
```

### 2. Use extract_page_content for Text
Don't use `navigate_to_url` + manual extraction. Use `extract_page_content` instead:
```python
# ❌ Don't do this
navigate_to_url.invoke({"url": "..."})
# ... manual text extraction ...

# ✅ Do this
extract_page_content.invoke({"url": "..."})
```

### 3. Adjust num_results for Search
```python
# For focused research: 1-3 results
google_search.invoke({"query": "specific topic", "num_results": 3})

# For broad exploration: 5-10 results
google_search.invoke({"query": "general topic", "num_results": 10})
```

### 4. Use full_page for Documentation
```python
# For articles, blogs: viewport is enough
take_web_screenshot.invoke({"url": "...", "full_page": False})

# For documentation, long pages: capture all
take_web_screenshot.invoke({"url": "...", "full_page": True})
```

### 5. Check extraction_method
```python
result = extract_page_content.invoke({"url": "..."})

if result["extraction_method"] == "langextract":
    print("✅ Clean extraction with langextract")
else:
    print("⚠️ Fallback extraction (langextract not available)")
```

## Troubleshooting

### "Playwright not installed"
```bash
pip install playwright
playwright install
```

### "langextract not found"
```bash
pip install langextract
```

### Browser doesn't open
The browser runs in **non-headless mode** by default so you can see what's happening. To run headless:

```python
# Edit src/agent/browser_tools.py line 30:
_browser_instance = SyncWebBrowser(config, headless=True)  # Set to True
```

### Browser window stays open
Always call `close_browser()` at the end:
```python
try:
    # ... operations ...
finally:
    close_browser.invoke({})
```

### Content extraction returns too little text
JavaScript-heavy sites may not load properly. Try:
1. Use `wait_until="networkidle"` with `navigate_to_url`
2. Check if the site requires authentication
3. Some sites block automated browsing

## Testing

Quick test to verify everything works:

```bash
python -c "
from src.agent.browser_tools import google_search, extract_page_content, close_browser

# Test search
print('Testing google_search...')
result = google_search.invoke({'query': 'Python', 'num_results': 2})
print(f'✅ Found {result[\"num_results\"]} results')

# Test extraction
print('Testing extract_page_content...')
result = extract_page_content.invoke({'url': 'https://www.python.org'})
print(f'✅ Extracted {result[\"word_count\"]} words')

# Test cleanup
print('Testing close_browser...')
result = close_browser.invoke({})
print(f'✅ {result[\"message\"]}')

print('\\n✅ All browser tools working!')
"
```

## Next Steps

1. **Test basic search**: Try `google_search` with a simple query
2. **Test content extraction**: Try `extract_page_content` on a documentation page
3. **Test with orchestrator**: Use `main_orchestrator.py` with a web research task
4. **Explore combinations**: Combine browser tools with core automation tools

For more details, see:
- **[BROWSER_TOOL_HIERARCHY.md](BROWSER_TOOL_HIERARCHY.md)** - Complete hierarchy and architecture
- **[BROWSER_INTEGRATION_SUMMARY.md](BROWSER_INTEGRATION_SUMMARY.md)** - Implementation details
- **[src/agent/browser_tools.py](src/agent/browser_tools.py)** - Source code
