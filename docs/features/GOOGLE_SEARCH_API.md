# Google Search API Integration

## Overview

The `/google` command provides fast, reliable web searches using the official Google Custom Search JSON API. This is different from browser-based automation - it uses Google's official API for structured, CAPTCHA-free results.

## Key Features

✅ **Official API**: Google Custom Search JSON API (not browser scraping)
✅ **Fast & Reliable**: Sub-second response times
✅ **Structured Results**: JSON format with rich metadata
✅ **No CAPTCHA**: Avoids browser automation issues
✅ **Multiple Search Types**: Web search, image search, site-specific search
✅ **LLM-Driven**: Automatic tool selection based on user intent

## Setup Instructions

### Step 1: Get Google API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **Custom Search API**:
   - Navigate to "APIs & Services" → "Library"
   - Search for "Custom Search API"
   - Click "Enable"
4. Create API credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "API key"
   - Copy the API key

### Step 2: Create Custom Search Engine

1. Go to [Programmable Search Engine](https://programmablesearchengine.google.com/)
2. Click "Add" to create a new search engine
3. Configure your search engine:
   - **Sites to search**: Enter `*.com` or specific sites
   - **Name**: Any name (e.g., "My Search Engine")
   - **Search the entire web**: Enable this option
4. Click "Create"
5. Copy the **Search engine ID** (CSE ID)

### Step 3: Set Environment Variables

Add to your shell profile (`~/.zshrc`, `~/.bashrc`, or `~/.bash_profile`):

```bash
export GOOGLE_API_KEY="your-api-key-here"
export GOOGLE_CSE_ID="your-cse-id-here"
```

Then reload:
```bash
source ~/.zshrc  # or ~/.bashrc
```

Alternatively, create a `.env` file in the project root:
```
GOOGLE_API_KEY=your-api-key-here
GOOGLE_CSE_ID=your-cse-id-here
```

### Step 4: Verify Setup

```bash
# Test the Google agent
python -c "import os; print('✅ Setup complete' if os.getenv('GOOGLE_API_KEY') and os.getenv('GOOGLE_CSE_ID') else '❌ Environment variables not set')"
```

## Usage Examples

### Example 1: Basic Web Search

```
User: /google Python async programming tutorials

Response:
Found 5 results in 0.23s

1. **Python Async IO Guide** (realpython.com)
   Complete guide to asynchronous programming in Python with asyncio...
   https://realpython.com/async-io-python/

2. **Async Python Tutorial** (docs.python.org)
   Official Python documentation on asyncio library and coroutines...
   https://docs.python.org/3/library/asyncio.html

3. **Asyncio Best Practices** (medium.com)
   Learn best practices for async programming in Python...
   https://medium.com/python-asyncio-best-practices

[Results 4-5...]
```

### Example 2: Image Search

```
User: /google images sunset over mountains

Response:
Found 5 images

1. Mountain Sunset (unsplash.com)
   [Thumbnail]
   https://unsplash.com/photos/sunset-mountains-abc123

2. Alpine Sunset (pexels.com)
   [Thumbnail]
   https://pexels.com/photo/alpine-sunset-xyz789

[Images 3-5...]
```

### Example 3: Site-Specific Search

```
User: /google machine learning site:github.com

Response:
Searching github.com for "machine learning"

Found 10 results in 0.19s

1. **tensorflow/tensorflow** (github.com)
   An Open Source Machine Learning Framework for Everyone
   https://github.com/tensorflow/tensorflow

2. **scikit-learn/scikit-learn** (github.com)
   Machine learning in Python
   https://github.com/scikit-learn/scikit-learn

[Results 3-10...]
```

### Example 4: Quick Search (Alias)

```
User: /search latest AI news

Response:
[Same as /google latest AI news]
```

## Available Tools

The Google Agent provides 3 LangChain tools that the orchestrator can use:

### 1. `google_search(query, num_results, search_type)`

**Purpose**: General web search via Google Custom Search API

**Parameters**:
- `query` (str): Search query
- `num_results` (int): Number of results (1-10, default: 5)
- `search_type` (str): "web" or "image" (default: "web")

**Returns**:
```python
{
    "results": [
        {
            "title": "Page title",
            "link": "https://example.com",
            "snippet": "Description text...",
            "display_link": "example.com"
        },
        # ... more results
    ],
    "total_results": 1500000,  # Estimated total matches
    "search_time": 0.23,       # Seconds
    "query": "original query",
    "num_results": 5
}
```

### 2. `google_search_images(query, num_results)`

**Purpose**: Specialized image search

**Parameters**:
- `query` (str): Image search query
- `num_results` (int): Number of images (1-10, default: 5)

**Returns**:
```python
{
    "results": [
        {
            "title": "Image title",
            "image_url": "https://example.com/image.jpg",
            "thumbnail": "https://example.com/thumb.jpg",
            "context_link": "https://example.com/page",
            "snippet": "Image description"
        },
        # ... more images
    ],
    "total_results": 50000,
    "search_time": 0.18
}
```

### 3. `google_search_site(query, site, num_results)`

**Purpose**: Search within a specific website/domain

**Parameters**:
- `query` (str): Search query
- `site` (str): Domain to search (e.g., "stackoverflow.com")
- `num_results` (int): Number of results (1-10, default: 5)

**Returns**: Same as `google_search`

**Implementation**: Automatically adds `site:domain.com` to the query

## Architecture

### Integration with Existing System

```
User: /google Python tutorials
       ↓
SlashCommandHandler (slash_commands.py)
  - Parses "/google" command
  - Routes to "google" agent
       ↓
GoogleAgent (google_agent.py)
  - LLM selects tool: google_search
  - Extracts parameters: query="Python tutorials"
       ↓
google_search tool
  - Calls Google Custom Search API
  - Returns structured results
       ↓
UI displays formatted results
```

### Orchestrator Integration

The orchestrator has automatic access to all Google tools via `ALL_AGENT_TOOLS`:

```python
# In agent_registry.py
ALL_AGENT_TOOLS = (
    FILE_AGENT_TOOLS +
    FOLDER_AGENT_TOOLS +
    GOOGLE_AGENT_TOOLS +  # ← Automatically included
    BROWSER_AGENT_TOOLS +
    # ... other agents
)
```

When the orchestrator plans a task that requires web search, it can select:
- `google_search` for fast API-based search
- `google_search` (browser) for full page content extraction

The LLM chooses based on requirements:
- Need structured results? → Use `google_search` (API)
- Need full page content? → Use browser automation

## API Limits & Pricing

### Free Tier
- **100 queries/day** free
- No credit card required
- Sufficient for development and testing

### Paid Tier
- **$5 per 1000 queries** after free tier
- Maximum 10,000 queries/day
- Billing via Google Cloud

### Monitoring Usage

Check your usage in [Google Cloud Console](https://console.cloud.google.com/apis/dashboard)

## Error Handling

### Configuration Errors

```
❌ ConfigurationError: Google API credentials not configured

Setup:
1. Get API key: https://console.cloud.google.com/apis/credentials
2. Create CSE: https://programmablesearchengine.google.com/
3. Export variables: GOOGLE_API_KEY and GOOGLE_CSE_ID
```

### Missing Dependencies

```
❌ DependencyError: Google API client not installed

Fix: pip install google-api-python-client
```

### API Errors

```
❌ SearchError: Quota exceeded (API limit reached)

Your free tier quota (100/day) has been reached.
Options:
1. Wait until quota resets (midnight Pacific Time)
2. Enable billing in Google Cloud Console
3. Use browser-based search (/browse) instead
```

## Comparison: API vs Browser

| Feature | `/google` (API) | `/browse` (Browser) |
|---------|----------------|---------------------|
| Speed | ⚡ Very fast (<1s) | 🐢 Slower (3-5s) |
| Reliability | ✅ Always works | ⚠️ CAPTCHA issues |
| Results Format | 📊 Structured JSON | 📝 HTML parsing |
| Full Page Content | ❌ Snippets only | ✅ Complete content |
| Cost | 💰 API quota | 🆓 Free |
| Setup | 🔧 Requires credentials | ✅ No setup |

**When to use `/google`**:
- Quick information lookups
- Multiple search queries
- Need structured, parseable results
- Avoiding CAPTCHA issues

**When to use `/browse`**:
- Need full page content
- Filling out forms
- Interactive browsing
- No API quota available

## Troubleshooting

### "Invalid API key" error

1. Verify API key is correct in environment variables:
   ```bash
   echo $GOOGLE_API_KEY
   ```
2. Check API is enabled in [Google Cloud Console](https://console.cloud.google.com/apis/library)
3. Verify there are no restrictions on the API key (IP, referrer, etc.)

### "CSE ID not found" error

1. Verify CSE ID is correct:
   ```bash
   echo $GOOGLE_CSE_ID
   ```
2. Ensure "Search the entire web" is enabled in [Programmable Search Engine](https://programmablesearchengine.google.com/)
3. Check CSE is active (not deleted)

### No results returned

- Check if search query is too specific
- Try broader search terms
- Verify CSE is configured to search the entire web
- Check API quota hasn't been exceeded

## Testing

### Manual Test

```bash
# Test Google agent directly
python -c "
from src.agent.google_agent import GoogleAgent
from src.utils import load_config

config = load_config()
agent = GoogleAgent(config)
result = agent.execute('google_search', {'query': 'Python tutorials', 'num_results': 3})
print(result)
"
```

### Test via UI

```
/google test query
```

## References

- Implementation: [src/agent/google_agent.py](../../src/agent/google_agent.py)
- Slash Command: [src/ui/slash_commands.py](../../src/ui/slash_commands.py)
- Agent Registry: [src/agent/agent_registry.py](../../src/agent/agent_registry.py)
- Google Custom Search API: https://developers.google.com/custom-search/v1/introduction
- API Console: https://console.cloud.google.com/
- Create CSE: https://programmablesearchengine.google.com/
