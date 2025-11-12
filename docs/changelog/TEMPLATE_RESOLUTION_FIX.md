# Template Resolution Fix: From Literal Syntax to Actual Values

## Problem Statement

**Symptom:**
```
UI shows: "Found {2} groups of duplicates, wasting {0.38} MB"
Expected: "Found 2 groups of duplicates, wasting 0.38 MB"
```

The UI was displaying template syntax literally instead of resolving the values.

## Root Cause

### What Was Happening

1. **LLM Planning Phase:**
   - LLM creates plan with parameters like:
   ```json
   {
     "message": "Found {$step1.total_duplicate_groups} groups, wasting {$step1.wasted_space_mb} MB"
   }
   ```

2. **Executor Parameter Resolution (`executor.py:374-442`):**
   - **Only handled direct references:** `"field": "$step1.value"` ✅
   - **Did NOT handle template strings:** `"Found {$step1.count} items"` ❌

3. **Result:**
   - Template syntax passed through to UI literally
   - User sees `{2}` instead of `2`

### The Missing Piece

The `_resolve_parameters()` method in [executor.py](src/orchestrator/executor.py#L374) had this logic:

```python
if isinstance(value, str) and value.startswith("$step"):
    # Resolve direct reference
    resolved[key] = self._resolve_reference(value, state)
else:
    # Pass through unchanged
    resolved[key] = value
```

**Problem:** Template strings like `"Found {$step1.count} items"` don't start with `$step`, so they were passed through unchanged!

## Solution

### 1. Enhanced Executor with Template String Resolution

**File:** [src/orchestrator/executor.py:374-504](src/orchestrator/executor.py#L374-L504)

**Changes:**

#### A. Updated `_resolve_parameters()` to detect templates:
```python
def _resolve_parameters(self, parameters, state):
    resolved = {}
    for key, value in parameters.items():
        if isinstance(value, str):
            # Check for direct reference: "$step1.field"
            if value.startswith("$step"):
                resolved[key] = self._resolve_reference(value, state)
            # Check for template string: "Found {$step1.count} items"
            elif "{$step" in value:
                resolved[key] = self._resolve_template_string(value, state)
            else:
                resolved[key] = value
        else:
            resolved[key] = value
    return resolved
```

#### B. Added `_resolve_template_string()` method:
```python
def _resolve_template_string(self, template, state):
    """
    Resolve template string with embedded references like "Found {$step1.count} items".

    Uses regex to find all {$step...} patterns and substitutes them with actual values.
    """
    import re

    # Find all {$stepN.field} patterns
    pattern = r'\{\$step(\d+)\.([^}]+)\}'

    def replace_placeholder(match):
        step_id = int(match.group(1))
        field_path = match.group(2)

        # Build full reference
        reference = f"$step{step_id}.{field_path}"
        resolved_value = self._resolve_reference(reference, state)

        # Convert to string for template substitution
        if resolved_value is None:
            logger.warning(f"Template placeholder {match.group(0)} resolved to None")
            return match.group(0)  # Keep original if resolution fails
        else:
            return str(resolved_value)

    # Replace all placeholders
    resolved = re.sub(pattern, replace_placeholder, template)

    # Log if any placeholders remain unresolved
    remaining = re.findall(r'\{\$step\d+\.[^}]+\}', resolved)
    if remaining:
        logger.warning(f"Template has unresolved placeholders: {remaining}")

    return resolved
```

#### C. Refactored `_resolve_reference()`:
Extracted the direct reference resolution logic into a separate method that both `_resolve_parameters()` and `_resolve_template_string()` can use.

### 2. Created Clear Example Documentation

**File:** [prompts/examples/general/09_example_duplicates_correct_formatting.md](prompts/examples/general/09_example_duplicates_correct_formatting.md)

**Key Content:**

#### Shows Wrong vs. Right Approach:
```markdown
### ❌ WRONG:
{
  "message": "Here are the duplicate files found in your folder.",
  "details": "Summary of duplicate groups and their locations"
}

### ✅ RIGHT:
{
  "message": "Found {$step1.total_duplicate_groups} group(s), wasting {$step1.wasted_space_mb} MB.",
  "details": "$step1.duplicates"
}
```

#### Explains Template Syntax Rules:
- **For simple substitutions:** Use `{$stepN.field}` in strings
  - `"Found {$step1.count} items"` → `"Found 2 items"`
- **For structured data:** Use `$stepN.field` directly
  - `"details": "$step1.duplicates"` → Passes full array
- **NO complex constructs:** No loops, no conditionals, keep it simple

#### Provides Complete Working Example:
Shows full plan JSON with expected inputs/outputs at each step.

## How It Works Now

### Data Flow (Complete):

```
1. User Query: "what files are duplicated?"
   ↓
2. LLM Planning:
   Step 1: folder_find_duplicates(folder_path=null)
   Step 2: reply_to_user(
     message="Found {$step1.total_duplicate_groups} groups, wasting {$step1.wasted_space_mb} MB",
     details="$step1.duplicates"
   )
   ↓
3. Step 1 Execution:
   Returns: {
     "duplicates": [...],
     "total_duplicate_groups": 2,
     "total_duplicate_files": 4,
     "wasted_space_mb": 0.38
   }
   ↓
4. Step 2 Parameter Resolution (FIXED!):

   A. Resolve "message" field:
      Input:  "Found {$step1.total_duplicate_groups} groups, wasting {$step1.wasted_space_mb} MB"
      Detect: Contains "{$step" → Use _resolve_template_string()
      Find:   {$step1.total_duplicate_groups} → Resolve to 2
      Find:   {$step1.wasted_space_mb} → Resolve to 0.38
      Output: "Found 2 groups, wasting 0.38 MB"

   B. Resolve "details" field:
      Input:  "$step1.duplicates"
      Detect: Starts with "$step" → Use _resolve_reference()
      Output: [Full duplicates array with file names]
   ↓
5. Step 2 Execution:
   Tool receives resolved parameters:
   {
     "message": "Found 2 groups, wasting 0.38 MB",
     "details": [array with actual file names]
   }
   ↓
6. UI Rendering:
   Shows: "Found 2 groups of duplicates, wasting 0.38 MB"
   With full details including actual file names ✅
```

## Technical Implementation Details

### Regex Pattern for Template Detection

```python
pattern = r'\{\$step(\d+)\.([^}]+)\}'
```

**Breakdown:**
- `\{` - Literal opening brace
- `\$step` - Literal text "$step"
- `(\d+)` - Capture group 1: step number (e.g., "1")
- `\.` - Literal dot
- `([^}]+)` - Capture group 2: field path (e.g., "total_duplicate_groups")
- `\}` - Literal closing brace

**Examples:**
- `{$step1.count}` → Matches, captures ("1", "count")
- `{$step2.duplicates.size}` → Matches, captures ("2", "duplicates.size")
- `{$step1}` → Doesn't match (no field path)
- `$step1.count` → Doesn't match (no braces)

### Field Path Navigation

Once a placeholder is found, the resolver:
1. Extracts step_id and field_path from regex match
2. Builds full reference: `$step{step_id}.{field_path}`
3. Calls `_resolve_reference()` which:
   - Gets step result from `state["step_results"][step_id]`
   - Navigates nested fields by splitting on "."
   - Handles dicts, lists, and nested structures
4. Converts resolved value to string
5. Substitutes back into template

### Example Navigation:

```python
# Template: "Found {$step1.wasted_space_mb} MB"
# Step 1 result: {"wasted_space_mb": 0.38}

1. Regex matches {$step1.wasted_space_mb}
2. Captures: step_id=1, field_path="wasted_space_mb"
3. Builds reference: "$step1.wasted_space_mb"
4. Navigates: step_results[1]["wasted_space_mb"] → 0.38
5. Converts: str(0.38) → "0.38"
6. Substitutes: "Found 0.38 MB"
```

## Before vs. After

### Before (Broken):
```
User: "what files are duplicated?"
↓
LLM plans: message="Found {$step1.total_duplicate_groups} groups..."
↓
Executor: Sees "{$step1..." doesn't start with "$step", passes through
↓
reply_to_user receives: "Found {$step1.total_duplicate_groups} groups..."
↓
UI shows: "Found {$step1.total_duplicate_groups} groups..." ❌
```

### After (Fixed):
```
User: "what files are duplicated?"
↓
LLM plans: message="Found {$step1.total_duplicate_groups} groups..."
↓
Executor: Detects "{$step" → Calls _resolve_template_string()
  → Finds {$step1.total_duplicate_groups}
  → Resolves to 2
  → Substitutes: "Found 2 groups..."
↓
reply_to_user receives: "Found 2 groups..."
↓
UI shows: "Found 2 groups of duplicates, wasting 0.38 MB" ✅
```

## Testing

### Server Status
✅ Server restarted with updated executor (PID: 95974)
✅ Folder Agent loaded with 6 tools (includes folder_find_duplicates)
✅ Template resolution code loaded

### Test Cases

**Test 1: Simple Template**
```
Plan: message="Found {$step1.count} items"
Step 1 result: {"count": 5}
Expected: "Found 5 items"
```

**Test 2: Multiple Placeholders**
```
Plan: message="Found {$step1.count} groups, wasting {$step1.space} MB"
Step 1 result: {"count": 2, "space": 0.38}
Expected: "Found 2 groups, wasting 0.38 MB"
```

**Test 3: Nested Field Path**
```
Plan: message="Size: {$step1.metadata.file_size} bytes"
Step 1 result: {"metadata": {"file_size": 1024}}
Expected: "Size: 1024 bytes"
```

**Test 4: Direct Reference (still works)**
```
Plan: details="$step1.duplicates"
Step 1 result: {"duplicates": [array]}
Expected: Passes full array
```

### How to Verify

1. **Open UI:** http://localhost:3000
2. **Enter query:** "what files are duplicated?"
3. **Verify response:**
   - ✅ Message shows "Found 2 group(s) of duplicate files, wasting 0.38 MB"
   - ✅ Details show actual file names (not generic message)
   - ✅ NO template syntax like `{$step1.count}` visible
   - ✅ Only actual values visible

## Error Handling

### Unresolved Placeholders

If a placeholder can't be resolved:
```python
if resolved_value is None:
    logger.warning(f"Template placeholder {match.group(0)} resolved to None")
    return match.group(0)  # Keep original placeholder
```

Result: `"Found {$step1.missing_field} items"` stays as-is, allowing user to see what failed.

### Final Validation

After all substitutions:
```python
remaining = re.findall(r'\{\$step\d+\.[^}]+\}', resolved)
if remaining:
    logger.warning(f"Template has unresolved placeholders: {remaining}")
```

Logs warnings if any templates remain, helping debug issues.

## Key Improvements

### 1. Executor Enhancement (Technical)
- ✅ Template string detection
- ✅ Regex-based placeholder extraction
- ✅ Recursive field path navigation
- ✅ Type conversion (value → string)
- ✅ Error handling for missing fields

### 2. Clear Documentation (Teaching)
- ✅ Shows wrong vs. right examples
- ✅ Explains template syntax rules
- ✅ Provides complete working example
- ✅ Lists what NOT to do

### 3. Generalizability
Works for ANY tool that uses template strings:
- ✅ reply_to_user (primary use case)
- ✅ compose_email (body parameter)
- ✅ Future tools that need formatting

## Files Modified

1. **src/orchestrator/executor.py** (lines 374-504)
   - Updated `_resolve_parameters()` to detect templates
   - Added `_resolve_template_string()` method
   - Refactored `_resolve_reference()` method

2. **prompts/examples/general/09_example_duplicates_correct_formatting.md** (NEW)
   - Complete example showing template syntax
   - Wrong vs. right comparison
   - Syntax rules and guidelines

## Next Steps

### Immediate
1. ✅ Executor updated with template resolution
2. ✅ Server restarted (PID: 95974)
3. ⏳ User testing in UI (PENDING)

### Future Enhancements

1. **Complex Templates:**
   - Support conditional logic: `{if $step1.count > 0}...{endif}`
   - Support loops: `{for item in $step1.items}...{endfor}`
   - Requires more sophisticated parser (not just regex)

2. **Template Validation:**
   - Check templates at planning time
   - Warn if placeholder references non-existent step
   - Suggest corrections for typos

3. **Template Library:**
   - Pre-defined templates for common patterns
   - "duplicate_summary" → Auto-formats duplicate data
   - "file_list" → Auto-formats file arrays

4. **Type-Safe Templates:**
   - Validate field types before substitution
   - Format numbers/dates/etc. appropriately
   - Handle null values gracefully

## Conclusion

**The Fix:**
- Added template string resolution to executor
- Now handles both `$step1.field` (direct) and `{$step1.field}` (template) syntax
- Provided clear examples showing correct usage

**Impact:**
- Before: UI showed `"Found {2} groups"` (literal syntax)
- After: UI shows `"Found 2 groups"` (resolved values)

**This enables:**
- LLM can create user-friendly messages with dynamic values
- No need to format data outside the executor
- Consistent pattern across all tools

**Ready for testing!** Please test in the UI and confirm actual values (not template syntax) appear in the responses.
