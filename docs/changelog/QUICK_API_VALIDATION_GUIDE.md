# Quick Guide: Adding API Parameter Validation to Agents

## TL;DR

When your agent calls an external API, validate parameters to prevent 400 errors from unsupported parameters.

## 3-Step Process

### Step 1: Define API Capabilities (5 minutes)

Add to `src/utils/api_validator.py`:

```python
def create_YOUR_API_validator() -> APIValidator:
    """Create validator for YOUR API."""
    validator = APIValidator("YOUR API Name")

    # For each endpoint your agent uses:
    validator.register_endpoint(APIEndpoint(
        name="endpoint_nickname",
        url_pattern="/api/actual/path",
        supported_params={
            "param1",
            "param2",
            "param3"
        },
        required_params={"param1"},  # Optional
        description="Brief description"
    ))

    return validator
```

### Step 2: Add to API Client (2 minutes)

In your API client file (e.g., `src/integrations/your_client.py`):

```python
from ..utils.api_validator import create_YOUR_API_validator

class YourAPIClient:
    def __init__(self):
        # ... existing init code ...

        # Add validator
        self._validator = create_YOUR_API_validator()

    def make_api_call(self, **kwargs):
        params = {
            # build your params
        }

        # DEFENSIVE: Validate before sending
        validated = self._validator.validate_params("endpoint_nickname", params)

        # Use validated params
        response = requests.get(url, params=validated)
```

### Step 3: Test It (1 minute)

```python
# Try sending an unsupported parameter
client = YourAPIClient()
result = client.make_api_call(unsupported_param="value")
# Check logs - should see warning about filtered parameter
# Should NOT get 400 error from API
```

## Quick Reference: Common APIs

### Twitter API v2

```python
# Lists endpoint
supported_params = {
    "max_results", "pagination_token", "expansions",
    "tweet.fields", "user.fields"
}
# ❌ Does NOT support: start_time, end_time

# Search endpoint
supported_params = {
    "query", "start_time", "end_time", "max_results"
}
# ✅ DOES support: start_time, end_time
```

### Google Maps API

```python
# Directions endpoint
supported_params = {
    "origin", "destination", "mode", "waypoints",
    "alternatives", "avoid", "departure_time"
}

# Places Search
supported_params = {
    "location", "radius", "type", "keyword",
    "minprice", "maxprice", "opennow"
}
```

### Playwright (Browser)

```python
# page.goto()
supported_params = {"timeout", "wait_until", "referer"}

# page.screenshot()
supported_params = {"path", "type", "quality", "full_page", "clip"}
```

## When to Use This

✅ **Use when:**
- Agent calls external REST APIs
- Agent uses libraries with method-specific parameters
- Different endpoints support different parameters
- You've seen 400 "invalid parameter" errors

❌ **Don't need when:**
- Internal function calls
- File system operations
- AppleScript calls (they fail loudly anyway)
- Single-endpoint APIs with consistent parameters

## Real Example: Twitter Fix

**Before:**
```python
def fetch_list_tweets(self, list_id, start_time):
    params = {
        "max_results": 100,
        "start_time": start_time  # ❌ Lists endpoint doesn't support this!
    }
    response = requests.get(url, params=params)
    # Result: 400 error
```

**After:**
```python
def fetch_list_tweets(self, list_id, start_time):
    params = {
        "max_results": 100,
        "start_time": start_time
    }

    # Validate - filters out start_time automatically
    validated = self._validator.validate_params("lists_tweets", params)
    # Result: {"max_results": 100}

    response = requests.get(url, params=validated)
    # Result: ✅ Success!
```

## Validation Modes

### Default Mode (Permissive)
```python
validated = validator.validate_params("endpoint", params)
# Filters out unsupported params
# Logs warnings
# Returns validated dict
```

### Strict Mode (Fail Fast)
```python
validated = validator.validate_params("endpoint", params, strict=True)
# Raises ValueError if unsupported params found
# Use for development/testing
```

## Checklist

For each external API your agent uses:

- [ ] List all endpoints you call
- [ ] Check API docs for supported parameters
- [ ] Create validator in `api_validator.py`
- [ ] Add validator to client `__init__`
- [ ] Use `validate_params` before API calls
- [ ] Test with unsupported parameter
- [ ] Verify warning logged
- [ ] Verify no 400 error

## Where to Find API Parameter Lists

**Twitter:**
- https://developer.twitter.com/en/docs/twitter-api

**Google Maps:**
- https://developers.google.com/maps/documentation/directions/get-directions
- https://developers.google.com/maps/documentation/places/web-service/search

**Playwright:**
- https://playwright.dev/python/docs/api/class-page

**Discord:**
- https://discord.com/developers/docs/resources/channel

**Reddit:**
- https://www.reddit.com/dev/api/

## Common Pitfalls

❌ **Don't:** Assume all endpoints support the same parameters
```python
# Bad - assumes all endpoints work the same
params = {"start_time": "...", "end_time": "..."}
client.any_endpoint(params)
```

✅ **Do:** Validate for each endpoint
```python
# Good - validates per endpoint
validated = validator.validate_params("specific_endpoint", params)
client.specific_endpoint(validated)
```

❌ **Don't:** Silently ignore filtered parameters
```python
# Bad - user doesn't know why parameter was ignored
validated = validator.validate_params("endpoint", params)
```

✅ **Do:** Handle filtered parameters appropriately
```python
# Good - explains alternative approach
validated = validator.validate_params("endpoint", params)
if "start_time" not in validated and "start_time" in params:
    logger.info("start_time not supported, using client-side filtering")
    # Implement client-side time filtering
```

## Files Modified

### Minimal Implementation

Only need to touch 2 files:

1. **`src/utils/api_validator.py`** - Add your validator function
2. **`src/integrations/your_client.py`** - Use the validator

### Full Implementation

For complete coverage:

3. **`tests/test_validators.py`** - Unit tests
4. **`tests/test_YOUR_agent.py`** - Integration tests
5. **`docs/YOUR_API_CAPABILITIES.md`** - Documentation

## Summary

**Problem:** Different API endpoints support different parameters

**Solution:** Validate parameters before sending to API

**Benefit:** No more 400 "invalid parameter" errors

**Time:** 10 minutes per agent

**Result:** Defensive, self-documenting, maintainable code
