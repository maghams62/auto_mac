# Variable Resolution Fix - Generic String Interpolation

## Problem

The original context variable resolution in `src/agent/agent.py` only supported standalone variables:

```json
{
  "content": "$step1.message"  ✅ Works
}
```

But did NOT support inline interpolation:

```json
{
  "content": "Price: $step1.current_price, Change: $step1.change_percent%"  ❌ Didn't work
}
```

This caused the Writing Agent to receive literal variable names like `$step1.current_price` instead of actual values, which then appeared in the final output.

## Solution

Enhanced `_resolve_parameters()` and `_resolve_single_value()` in [src/agent/agent.py](src/agent/agent.py) to handle both:

1. **Standalone variables**: Entire parameter value is a variable
2. **Inline interpolation**: Variables embedded within text
3. **Multiple variables**: Multiple variables in one string
4. **Lists**: Any combination of the above in list parameters

### Implementation

Uses regex pattern matching (`r'\$step\d+\.\w+'`) to find and replace ALL variable references in strings, regardless of position.

```python
# Before (only worked for standalone):
if value.startswith("$step"):
    # Replace entire value

# After (works for any pattern):
re.sub(r'\$step\d+\.\w+', replace_var, value)
```

## Test Results

All test cases pass (see [test_variable_resolution.py](test_variable_resolution.py)):

- ✅ Standalone: `"$step1.message"` → `"Apple Inc. (AAPL): $225.50 (+2.5%)"`
- ✅ Single inline: `"Price: $step1.current_price"` → `"Price: 225.5"`
- ✅ Multiple inline: `"Price: $step1.current_price, Change: $step1.change_percent%"` → `"Price: 225.5, Change: 2.5%"`
- ✅ Lists: Mixed standalone and inline variables in arrays

## Example 10 Fix

Updated [prompts/few_shot_examples.md](prompts/few_shot_examples.md) Example 10 to use cleaner pattern:

```json
{
  "action": "synthesize_content",
  "parameters": {
    "source_contents": [
      "$step1.message",
      "$step2.message"
    ]
  }
}
```

This works because:
1. Stock tools provide pre-formatted `message` fields
2. Variables are standalone (easier to read)
3. Writing Agent does the synthesis (its job)

But now, if needed, this would ALSO work:

```json
{
  "source_contents": [
    "Current: $step1.message (volume: $step1.volume)",
    "Historical: $step2.message ($step2.period_change_percent% change)"
  ]
}
```

## Benefits

1. **Generic**: No hardcoded logic, works for all cases
2. **Flexible**: Authors can choose best pattern for their use case
3. **Robust**: Handles edge cases like None values, missing fields, etc.
4. **Backward compatible**: Existing standalone usage still works

## Best Practices

While inline interpolation now works, **prefer using pre-formatted fields** when available:

✅ **Recommended**:
```json
{"content": "$step1.message"}
```

⚠️ **Works but less clean**:
```json
{"content": "Price is $step1.current_price and change is $step1.change_percent%"}
```

**Why?** Tools provide formatted `message` fields that are:
- Human-readable
- Consistently formatted
- Include units and context
- Let each tool control its output format

## Files Modified

1. [src/agent/agent.py](src/agent/agent.py) - Enhanced `_resolve_parameters()` and `_resolve_single_value()`
2. [prompts/few_shot_examples.md](prompts/few_shot_examples.md) - Simplified Example 10
3. [test_variable_resolution.py](test_variable_resolution.py) - Test suite (NEW)
4. [VARIABLE_RESOLUTION_FIX.md](VARIABLE_RESOLUTION_FIX.md) - This document (NEW)

## Usage

No changes needed for users. The system now automatically handles both patterns:

```python
# Both work:
params1 = {"content": "$step1.message"}
params2 = {"content": "Today's price: $step1.current_price"}

# Lists work too:
params3 = {"items": ["$step1.field", "Text with $step2.field embedded"]}
```

Variables are resolved before tool execution, so tools always receive actual values.
