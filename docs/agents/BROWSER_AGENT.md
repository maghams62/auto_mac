# Browser Tool Hierarchy

## Overview

Browser capabilities are **separated** from core file/document automation tools to maintain clear separation of concerns. All web browsing tools are isolated in their own hierarchy.

## Separation Architecture

```
src/agent/
├── tools.py                 → Core automation tools (documents, email, files)
└── browser_tools.py         → Separate browser tool suite (web automation)

src/orchestrator/
└── tools_catalog.py         → Registers both tool categories
```

## Browser Tool Hierarchy

```
Browser Tools (Separate Agent Capability)
│
├─ LEVEL 1: Primary Search
│  └─ google_search
│     ├─ Input: query (str), num_results (int)
│     ├─ Output: results (list), query, num_results
│     └─ Purpose: Find information on the web, discover URLs
│
├─ LEVEL 2: Navigation & Content Extraction
│  ├─ navigate_to_url
│  │  ├─ Input: url (str), wait_until (str)
│  │  ├─ Output: url, title, status
│  │  └─ Purpose: Visit specific webpages
│  │
│  └─ extract_page_content
│     ├─ Input: url (Optional[str])
│     ├─ Output: content (str), title, word_count, extraction_method
│     ├─ Uses: langextract for intelligent content extraction
│     └─ Purpose: Get clean text for LLM processing/disambiguation
│
├─ LEVEL 3: Visual Capture
│  └─ take_web_screenshot
│     ├─ Input: url (Optional[str]), full_page (bool)
│     ├─ Output: screenshot_path, url
│     └─ Purpose: Capture visual proof of webpage content
│
└─ LEVEL 4: Cleanup
   └─ close_browser
      ├─ Input: None
      ├─ Output: message
      └─ Purpose: Free resources, close browser windows
```

## Typical Workflow

### Example 1: Research Documentation
```
User: "Search for Python's asyncio documentation and extract the tutorial content"

Step 1: google_search(query="Python asyncio documentation")
  → Returns: [
      {title: "asyncio - Python Docs", link: "https://docs.python.org/3/library/asyncio.html", ...},
      ...
    ]

Step 2: extract_page_content(url="https://docs.python.org/3/library/asyncio.html")
  → Returns: {
      content: "asyncio is a library to write concurrent code using async/await...",
      word_count: 5420,
      extraction_method: "langextract"
    }

Step 3: [LLM processes extracted content for disambiguation/analysis]

Step 4: close_browser()
```

### Example 2: Web Research with Screenshots
```
User: "Find the official LangChain website and capture a screenshot"

Step 1: google_search(query="LangChain official website")
  → Returns search results with links

Step 2: navigate_to_url(url=<first result link>)
  → Navigates to the page

Step 3: take_web_screenshot(full_page=True)
  → Saves screenshot to temp file
  → Returns: {screenshot_path: "/tmp/screenshot_xyz.png"}

Step 4: close_browser()
```

## Why Separate Browser Tools?

### 1. **Clear Separation of Concerns**
- Core tools handle local file/document automation
- Browser tools handle web-based operations
- Each has distinct dependencies (Playwright vs PyMuPDF)

### 2. **Independent Lifecycle**
- Browser instance lifecycle managed separately
- Browser can be closed/reopened without affecting other tools
- Resource management is isolated

### 3. **Different Execution Contexts**
- Local file operations are synchronous
- Web operations are async (wrapped for LangChain)
- Error handling differs (network vs file errors)

### 4. **Modular Dependencies**
```python
# Core tools
from src.agent.tools import ALL_TOOLS  # Always available

# Browser tools (optional if Playwright not installed)
try:
    from src.agent.browser_tools import BROWSER_TOOLS
    COMBINED_TOOLS = ALL_TOOLS + BROWSER_TOOLS
except ImportError:
    COMBINED_TOOLS = ALL_TOOLS
    logger.warning("Browser tools not available - Playwright not installed")
```

## Implementation Details

### Browser Instance Management
```python
# Lazy initialization - browser only starts when first tool is used
_browser_instance = None

def get_browser():
    """Get or create browser instance."""
    global _browser_instance
    if _browser_instance is None:
        from ..automation.web_browser import SyncWebBrowser
        config = load_config()
        _browser_instance = SyncWebBrowser(config, headless=False)
    return _browser_instance
```

### Content Extraction with langextract
```python
# Uses langextract for intelligent content extraction
from langextract import LangExtract

html_content = await page.content()
extractor = LangExtract()
extracted = extractor.extract(html_content)

# Returns clean text suitable for LLM processing
return {
    "content": extracted.get("text", ""),
    "word_count": len(extracted.get("text", "").split()),
    "method": "langextract"
}
```

## Tool Catalog Registration

Browser tools are registered with a distinct `kind`:
```python
"google_search": ToolSpec(  # DuckDuckGo-backed search
    name="google_search",
    kind="browser_tool",  # Different from "tool"
    io={...},
    strengths=[...],
    description="..."
)
```

This allows the planner to:
1. Identify browser vs file tools
2. Understand tool hierarchy (LEVEL 1, 2, 3, 4)
3. Plan workflows that combine both tool types

## Error Handling

### Network Errors
```python
try:
    result = browser.google_search(query)  # DuckDuckGo HTML endpoint
except Exception as e:
    return {
        "error": True,
        "error_type": "SearchError",  # Browser-specific error type
        "error_message": str(e),
        "retry_possible": True  # Network errors are retryable
    }
```

### Browser Initialization Errors
```python
try:
    from playwright.async_api import async_playwright
    # Initialize browser...
except ImportError:
    logger.error("Playwright not installed. Run: pip install playwright && playwright install")
    raise
```

## Dependencies

Browser tools require:
```bash
# Install Playwright
pip install playwright

# Install browser binaries
playwright install

# Install langextract for content extraction
pip install langextract
```

## Usage Patterns

### Pattern 1: Search → Extract
Most common pattern for research tasks:
```python
1. google_search("topic") → Find URLs
2. extract_page_content(url) → Get content
3. [LLM analyzes content]
4. close_browser()
```

### Pattern 2: Direct URL → Extract
When URL is known:
```python
1. extract_page_content("https://example.com")  # Navigates + extracts
2. [LLM processes content]
3. close_browser()
```

### Pattern 3: Search → Navigate → Screenshot
When visual capture is needed:
```python
1. google_search("topic")
2. navigate_to_url(result["results"][0]["link"])
3. take_web_screenshot(full_page=True)
4. close_browser()
```

## Integration with Core Tools

Browser tools can be combined with core tools in workflows:

```
Example: "Search for Python docs, extract asyncio tutorial, create a Keynote presentation"

Step 1: google_search("Python asyncio tutorial")          [BROWSER TOOL]
Step 2: extract_page_content(url)                         [BROWSER TOOL]
Step 3: close_browser()                                   [BROWSER TOOL]
Step 4: create_keynote(title="Asyncio", content=<text>)  [CORE TOOL]
```

The orchestrator handles both tool types seamlessly:
```python
COMBINED_TOOLS = ALL_TOOLS + BROWSER_TOOLS

# Executor can call any tool from combined list
tool = next((t for t in COMBINED_TOOLS if t.name == tool_name), None)
```

## Future Enhancements

1. **Form Interaction**: Add tools for clicking elements, filling forms
2. **Advanced Navigation**: Support for clicking, scrolling, waiting for elements
3. **Multiple Pages**: Support opening multiple tabs/pages simultaneously
4. **Session Persistence**: Save/restore browser sessions
5. **Cookie Management**: Handle authentication, session cookies
6. **JavaScript Execution**: Run custom JavaScript on pages
7. **PDF Generation**: Save webpages as PDFs

## Anti-Hallucination Protection

Browser tools are protected by the same 3-layer defense system:

1. **Prompt Engineering**: Tool catalog clearly lists all browser tools with LEVEL indicators
2. **Programmatic Validation**: PlanValidator checks that all tools (including browser tools) exist
3. **Execution-Time Validation**: Executor verifies tool exists before calling

Browser tools are added to the validator's whitelist:
```python
# In PlanValidator
self.tool_names = {tool["name"] for tool in available_tools}
# Includes: google_search, navigate_to_url, extract_page_content, take_web_screenshot, close_browser
```
