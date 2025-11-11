# API Parameter Validation - Generalized Defensive Programming

## Overview

This document describes the generalized defensive programming system for validating API parameters across all agents that interact with external APIs.

**Core Principle:** Never assume all API endpoints support the same parameters. Always validate against actual API capabilities.

## The Problem

### Example: Twitter API Failure
```json
{
  "error_type": "TwitterAPIError",
  "error_message": "The query parameter [start_time] is not one of [id,max_results,...]"
}
```

**Root Cause:** Different API endpoints support different parameters, but our code assumed all endpoints supported the same parameters.

### Generalized Pattern

This same issue can occur with ANY external API:
- **Twitter:** Lists endpoint vs Search endpoint
- **Google Maps:** Directions API vs Places API
- **Playwright:** Different browser methods
- **Discord:** Different webhook endpoints
- **Reddit:** Old vs new API endpoints

## The Solution: APIValidator

### Architecture

```
┌─────────────────────────────────────────┐
│         Agent Request                   │
│   "Summarize last 1 hour of tweets"     │
└──────────────┬──────────────────────────┘
               │
               v
┌─────────────────────────────────────────┐
│      Twitter Agent                      │
│   Prepares parameters:                  │
│   {start_time, max_results, fields}     │
└──────────────┬──────────────────────────┘
               │
               v
┌─────────────────────────────────────────┐
│      Twitter Client                     │
│   + APIValidator                        │
│   Validates against endpoint:           │
│   - lists_tweets (no start_time)        │
│   - search_recent (has start_time)      │
└──────────────┬──────────────────────────┘
               │
               v
┌─────────────────────────────────────────┐
│      Validated Parameters               │
│   Filters out unsupported params        │
│   Logs warnings for debugging           │
└──────────────┬──────────────────────────┘
               │
               v
┌─────────────────────────────────────────┐
│      External API Call                  │
│   ✅ Only sends supported parameters    │
│   ✅ No more 400 errors                 │
└─────────────────────────────────────────┘
```

### Implementation

#### 1. Define API Capabilities

**File:** `src/utils/api_validator.py`

```python
from src.utils.api_validator import APIValidator, APIEndpoint

validator = APIValidator("Twitter API v2")

# Register each endpoint with its supported parameters
validator.register_endpoint(APIEndpoint(
    name="lists_tweets",
    url_pattern="/2/lists/:id/tweets",
    supported_params={
        "max_results",
        "pagination_token",
        "expansions",
        "tweet.fields",
        # ... other supported params
        # NOTE: start_time is NOT in this list!
    },
    description="Get tweets from a Twitter List"
))

validator.register_endpoint(APIEndpoint(
    name="search_recent",
    url_pattern="/2/tweets/search/recent",
    supported_params={
        "query",
        "start_time",  # ✅ Search DOES support this
        "end_time",
        "max_results",
        # ... etc
    },
    required_params={"query"},
    description="Search recent tweets"
))
```

#### 2. Use Validator in API Client

**File:** `src/integrations/twitter_client.py`

```python
from ..utils.api_validator import create_twitter_validator

class TwitterAPIClient:
    def __init__(self):
        # ... auth setup ...

        # Initialize validator
        self._validator = create_twitter_validator()

    def fetch_list_tweets(self, list_id: str, start_time_iso: Optional[str] = None):
        params = {
            "max_results": 100,
            "tweet.fields": "created_at,author_id",
            "start_time": start_time_iso  # Will be filtered out!
        }

        # DEFENSIVE: Validate parameters
        validated_params = self._validator.validate_params("lists_tweets", params)
        # Result: {'max_results': 100, 'tweet.fields': '...'}
        # 'start_time' removed with warning logged

        response = self.session.get(url, params=validated_params)
```

## Applying to All Agents

### Current Status

| Agent | API Used | Validator Status |
|-------|----------|-----------------|
| **Twitter** | Twitter API v2 | ✅ Implemented |
| **Browser** | Playwright | 🔄 Recommended |
| **Maps** | Google Maps API | 🔄 Recommended |
| **Google** | Google Search | 🔄 Recommended |
| **Discord** | Discord API | 🔄 Recommended |
| **Reddit** | Reddit API | 🔄 Recommended |

### Implementation Guide

For each agent that uses external APIs:

#### Step 1: Document API Capabilities

Create a function in `api_validator.py`:

```python
def create_YOURAPI_validator() -> APIValidator:
    """Create validator for YOUR API."""
    validator = APIValidator("YOUR API Name")

    # Register each endpoint you use
    validator.register_endpoint(APIEndpoint(
        name="endpoint_name",
        url_pattern="/api/path",
        supported_params={"param1", "param2", "param3"},
        required_params={"param1"},
        description="What this endpoint does"
    ))

    return validator
```

#### Step 2: Add Validator to Client

```python
class YourAPIClient:
    def __init__(self):
        self._validator = create_YOURAPI_validator()

    def call_endpoint(self, **kwargs):
        # Build params
        params = {...}

        # DEFENSIVE: Validate
        validated = self._validator.validate_params("endpoint_name", params)

        # Make request with validated params
        response = requests.get(url, params=validated)
```

#### Step 3: Handle Filtered Parameters

If a parameter is filtered out, decide how to handle it:

**Option A: Client-side alternative**
```python
# If server-side filtering not supported, do it client-side
if 'start_time' in params and 'start_time' not in validated:
    logger.info("start_time not supported, filtering client-side")
    # Filter results after fetching
```

**Option B: Fallback to different endpoint**
```python
# Use a different endpoint that supports the parameter
if 'start_time' in params:
    endpoint = "search_recent"  # Supports start_time
else:
    endpoint = "lists_tweets"  # Doesn't support it
```

## Examples for Each Agent

### Browser Agent (Playwright)

```python
def create_playwright_validator() -> APIValidator:
    validator = APIValidator("Playwright")

    validator.register_endpoint(APIEndpoint(
        name="page_goto",
        supported_params={"timeout", "wait_until", "referer"}
    ))

    validator.register_endpoint(APIEndpoint(
        name="page_screenshot",
        supported_params={"path", "type", "quality", "full_page", "clip"}
    ))

    return validator
```

### Maps Agent (Google Maps)

```python
def create_google_maps_validator() -> APIValidator:
    validator = APIValidator("Google Maps API")

    # Directions endpoint
    validator.register_endpoint(APIEndpoint(
        name="directions",
        supported_params={"origin", "destination", "waypoints", "mode", "avoid"},
        required_params={"origin", "destination"}
    ))

    # Places endpoint
    validator.register_endpoint(APIEndpoint(
        name="places_search",
        supported_params={"location", "radius", "type", "keyword"},
        required_params={"location"}
    ))

    return validator
```

### Discord Agent

```python
def create_discord_validator() -> APIValidator:
    validator = APIValidator("Discord API")

    validator.register_endpoint(APIEndpoint(
        name="send_message",
        supported_params={"content", "embeds", "files", "tts"},
        required_params={"content"}
    ))

    validator.register_endpoint(APIEndpoint(
        name="create_webhook",
        supported_params={"name", "avatar", "channel_id"},
        required_params={"name"}
    ))

    return validator
```

## Benefits

### 1. Prevents 400 Errors
- ✅ No more "invalid parameter" errors
- ✅ API calls always use supported parameters
- ✅ Graceful degradation when parameters not supported

### 2. Self-Documenting
- ✅ Code documents what each endpoint supports
- ✅ Easy to see API capabilities at a glance
- ✅ Helps onboarding new developers

### 3. Debuggable
- ✅ Warnings logged when parameters filtered
- ✅ Shows exactly what was filtered and why
- ✅ Points to API documentation

### 4. Maintainable
- ✅ Centralized API capability definitions
- ✅ Easy to update when APIs change
- ✅ Consistent pattern across all agents

## Testing

### Unit Tests

```python
def test_twitter_validator():
    validator = create_twitter_validator()

    # Test lists endpoint filters start_time
    params = {"max_results": 100, "start_time": "2025-01-01"}
    validated = validator.validate_params("lists_tweets", params)

    assert "max_results" in validated
    assert "start_time" not in validated  # Filtered out

def test_search_endpoint_keeps_start_time():
    validator = create_twitter_validator()

    params = {"query": "test", "start_time": "2025-01-01"}
    validated = validator.validate_params("search_recent", params)

    assert "start_time" in validated  # Kept for search endpoint
```

### Integration Tests

```python
def test_twitter_agent_with_validator():
    """Test that Twitter agent works with parameter validation."""
    agent = TwitterAgent(config)

    # This should not raise 400 error even though start_time not supported
    result = agent.execute("summarize_list_activity", {
        "lookback_hours": 1  # Will use start_time internally
    })

    assert result.get("error") is not True
```

## Migration Checklist

For each agent:

- [ ] Identify all external APIs used
- [ ] Document API endpoint capabilities
- [ ] Create validator function in `api_validator.py`
- [ ] Add validator to API client `__init__`
- [ ] Update all API calls to use `validate_params`
- [ ] Handle filtered parameters (client-side or fallback)
- [ ] Add unit tests for validator
- [ ] Add integration tests for agent
- [ ] Update agent documentation

## Summary

**The Pattern:**
1. Define what each API endpoint supports
2. Validate parameters before making requests
3. Filter out unsupported parameters
4. Log warnings for debugging
5. Handle filtered parameters gracefully

**The Result:**
- ✅ No more 400 "invalid parameter" errors
- ✅ Self-documenting API capabilities
- ✅ Consistent pattern across all agents
- ✅ Easy to maintain and update
- ✅ Defensive programming at the API boundary

This generalizes the Twitter fix to a reusable pattern for ALL external API interactions!
