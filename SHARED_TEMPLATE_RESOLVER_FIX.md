# Shared Template Resolver: The Complete Fix

## Problem Statement

**You were absolutely right!** The issue was that **two different executors** had different parameter resolution logic, and one of them (AutomationAgent) was leaving orphaned braces in the output.

### Symptom
```
UI shows: "Found {2} groups of duplicates, wasting {0.38} MB"
Expected: "Found 2 groups of duplicates, wasting 0.38 MB"
```

### Root Cause Analysis (Your Diagnosis)

1. **PlanExecutor** ([src/orchestrator/executor.py:374](src/orchestrator/executor.py#L374))
   - I added `_resolve_template_string()` to this one
   - **Status:** Partially fixed (only this path worked)

2. **AutomationAgent** ([src/agent/agent.py:586](src/agent/agent.py#L586))
   - Used simple regex: `re.sub(r'\$step\d+\.\w+', replace_var, value)`
   - **Problem:** Replaced `$step1.count` with `2`, but **left the braces**: `{2}`
   - **Status:** BROKEN (causing the bug you saw)

### Why This Happened

The regex in AutomationAgent only matched the reference itself, not the surrounding braces:

```python
# Input
"Found {$step1.count} groups"

# Regex matches
$step1.count  # ← Only this part

# Replaces with
"Found {2} groups"  # ← Braces remain! ❌
```

## Solution: Shared Utility Module

Following your recommendations, I created a **shared template resolver** that both executors use.

### 1. Created Shared Utility

**File:** [src/utils/template_resolver.py](src/utils/template_resolver.py)

**Key Functions:**

#### A. `resolve_template_string(template, step_results)`
Handles both syntaxes:
- `{$step1.field}` - Template with braces
- `$step1.field` - Direct reference

**Implementation:**
```python
def resolve_template_string(template: str, step_results: Dict[int, Any]) -> str:
    # Pattern 1: Template syntax with braces {$stepN.field}
    template_pattern = r'\{\$step(\d+)\.([^}]+)\}'

    # Pattern 2: Direct reference without braces $stepN.field
    direct_pattern = r'\$step(\d+)\.(\w+)'

    # Resolve template syntax first (removes braces)
    resolved = re.sub(template_pattern, replace_template, template)

    # Then resolve direct references
    resolved = re.sub(direct_pattern, replace_direct, resolved)

    return resolved
```

**Key difference from AutomationAgent:**
- **Old:** Regex only matched `$step1.field`
- **New:** Regex matches `{$step1.field}` including braces
- **Result:** Entire placeholder (including braces) is replaced

#### B. `resolve_direct_reference(reference, step_results)`
Navigates nested field paths:
```python
# Handles:
"$step1.field"           → Simple field
"$step1.data.count"      → Nested object
"$step1.files.0.name"    → Array access
```

#### C. `resolve_parameters(parameters, step_results)`
Top-level function that resolves entire parameter dictionaries:
```python
# Handles:
- Strings with templates
- Direct references
- Lists of parameters
- Nested dictionaries
```

#### D. `_check_unresolved(text)`
Warns about unresolved placeholders:
```python
# Detects:
- Unresolved templates: {$step1.field}
- Unresolved references: $step1.field
- Orphaned braces: {2} ← THE BUG WE'RE PREVENTING!
```

### 2. Updated Both Executors

#### A. PlanExecutor ([src/orchestrator/executor.py:374-393](src/orchestrator/executor.py#L374-L393))

**Before:**
```python
def _resolve_parameters(self, parameters, state):
    # Custom implementation with _resolve_template_string()
    # and _resolve_reference() methods
    ...
```

**After:**
```python
def _resolve_parameters(self, parameters, state):
    """Uses shared template resolver for consistency."""
    from ..utils.template_resolver import resolve_parameters as resolve_params
    return resolve_params(parameters, state["step_results"])
```

**Benefits:**
- ✅ Removed ~120 lines of duplicate code
- ✅ Consistent behavior across executors
- ✅ Single source of truth for resolution logic

#### B. AutomationAgent ([src/agent/agent.py:586-603](src/agent/agent.py#L586-L603))

**Before:**
```python
def _resolve_parameters(self, params, step_results):
    # Simple regex that left braces in output ❌
    resolved[key] = re.sub(r'\$step\d+\.\w+', replace_var, value)
    ...
```

**After:**
```python
def _resolve_parameters(self, params, step_results):
    """Uses shared template resolver for consistency."""
    from ..utils.template_resolver import resolve_parameters as resolve_params
    return resolve_params(params, step_results)
```

**Benefits:**
- ✅ Now handles `{$step1.field}` correctly (removes braces)
- ✅ Consistent with PlanExecutor
- ✅ Cleaner, simpler code

### 3. Created Regression Tests

**File:** [tests/test_template_resolution.py](tests/test_template_resolution.py)

**11 Tests (All Passing ✅):**

1. **test_template_syntax_with_braces** ✅
   - Input: `"Found {$step1.count} items"`
   - Output: `"Found 5 items"` (NO BRACES!)

2. **test_direct_reference_syntax** ✅
   - Input: `"Price is $step1.price"`
   - Output: `"Price is 225.5"`

3. **test_mixed_syntax** ✅
   - Both syntaxes in same string work correctly

4. **test_nested_field_paths** ✅
   - `$step1.metadata.file_size` works

5. **test_array_access** ✅
   - `$step1.files.0.name` works

6. **test_resolve_parameters_dict** ✅
   - Full parameter dictionary resolution

7. **test_no_orphaned_braces** ✅ ← **CRITICAL TEST**
   - Ensures `{2}` never appears in output
   - This is the exact bug we're preventing!

8. **test_missing_step_graceful_fallback** ✅
   - Keeps placeholder if step doesn't exist

9. **test_missing_field_graceful_fallback** ✅
   - Keeps placeholder if field doesn't exist

10. **test_empty_string_unchanged** ✅
    - Empty strings pass through

11. **test_no_placeholders_unchanged** ✅
    - Strings without placeholders pass through

### Test Results:
```
============================================================
TEMPLATE RESOLUTION REGRESSION TESTS
============================================================

✅ Template syntax with braces resolves correctly
✅ Direct reference syntax resolves correctly
✅ Mixed syntax resolves correctly
✅ Nested field paths resolve correctly
✅ Array access resolves correctly
✅ Full parameter dictionary resolves correctly
✅ CRITICAL: No orphaned braces in output
✅ Missing step handled gracefully
✅ Missing field handled gracefully
✅ Empty strings handled correctly
✅ Strings without placeholders pass through unchanged

============================================================
✅ ALL 11 TESTS PASSED!
============================================================
```

## How It Works Now

### Complete Data Flow (Fixed):

```
1. User Query: "what files are duplicated?"
   ↓
2. LLM Planning (uses prompts with {$step1.field} syntax):
   Step 1: folder_find_duplicates(folder_path=null)
   Step 2: reply_to_user(
     message="Found {$step1.total_duplicate_groups} groups, wasting {$step1.wasted_space_mb} MB"
   )
   ↓
3. Step 1 Execution:
   Returns: {
     "total_duplicate_groups": 2,
     "total_duplicate_files": 4,
     "wasted_space_mb": 0.38,
     "duplicates": [...]
   }
   ↓
4. Step 2 Parameter Resolution (BOTH EXECUTORS NOW USE SHARED RESOLVER):

   A. Input to resolver:
      "Found {$step1.total_duplicate_groups} groups, wasting {$step1.wasted_space_mb} MB"

   B. Template pattern regex finds:
      - {$step1.total_duplicate_groups}
      - {$step1.wasted_space_mb}

   C. For each match:
      - Extract: step_id=1, field="total_duplicate_groups"
      - Look up: step_results[1]["total_duplicate_groups"] → 2
      - Replace ENTIRE match (including braces): {$step1.total_duplicate_groups} → 2

   D. Output:
      "Found 2 groups, wasting 0.38 MB" ✅
   ↓
5. reply_to_user receives:
   {
     "message": "Found 2 groups, wasting 0.38 MB",  # ✅ NO BRACES!
     "details": [array with file names]
   }
   ↓
6. UI Rendering:
   Shows: "Found 2 groups of duplicates, wasting 0.38 MB" ✅
```

## Before vs. After

### Before (Broken - Two Executors):

**PlanExecutor:**
```python
# Had custom _resolve_template_string() - worked correctly ✅
```

**AutomationAgent:**
```python
# Simple regex that left braces - BROKEN ❌
re.sub(r'\$step\d+\.\w+', replace_var, value)
# Input:  "Found {$step1.count} items"
# Output: "Found {2} items"  # ← BRACES REMAIN!
```

**Result:** Inconsistent behavior, orphaned braces in UI ❌

### After (Fixed - Shared Resolver):

**PlanExecutor:**
```python
from ..utils.template_resolver import resolve_parameters
return resolve_parameters(parameters, step_results)
```

**AutomationAgent:**
```python
from ..utils.template_resolver import resolve_parameters
return resolve_parameters(parameters, step_results)
```

**Result:** Consistent behavior, no orphaned braces ✅

## Technical Details

### Regex Patterns Explained

#### Template Pattern (with braces):
```python
pattern = r'\{\$step(\d+)\.([^}]+)\}'
```

**Breakdown:**
- `\{` - Match literal opening brace
- `\$step` - Match literal "$step"
- `(\d+)` - Capture step number (group 1)
- `\.` - Match literal dot
- `([^}]+)` - Capture field path until closing brace (group 2)
- `\}` - Match literal closing brace

**Examples:**
- `{$step1.count}` → Matches, captures ("1", "count")
- `{$step1.metadata.size}` → Matches, captures ("1", "metadata.size")

**Key:** The entire match (including braces) gets replaced!

#### Direct Pattern (no braces):
```python
pattern = r'\$step(\d+)\.(\w+)'
```

**Breakdown:**
- `\$step` - Match literal "$step"
- `(\d+)` - Capture step number (group 1)
- `\.` - Match literal dot
- `(\w+)` - Capture field name (group 2)

**Examples:**
- `$step1.count` → Matches, captures ("1", "count")
- `Price is $step1.total` → Matches within string

### Resolution Order

1. **First:** Resolve template syntax (with braces)
   - This prevents conflicts where both patterns might match

2. **Second:** Resolve direct references (without braces)
   - Handles any remaining `$step1.field` references

3. **Finally:** Check for unresolved placeholders
   - Warns about orphaned braces like `{2}`

## Files Modified

1. **src/utils/template_resolver.py** (NEW)
   - Shared resolver used by all executors
   - 270 lines of well-tested, documented code

2. **src/orchestrator/executor.py** (lines 374-393)
   - Replaced custom logic with shared resolver
   - Removed ~120 lines of duplicate code

3. **src/agent/agent.py** (lines 586-603)
   - Replaced broken regex logic with shared resolver
   - Fixed the orphaned braces bug

4. **tests/test_template_resolution.py** (NEW)
   - 11 comprehensive regression tests
   - All tests passing ✅

## Your Recommendations - Implemented ✅

### ✅ 1. Extract Shared Utility
**Status:** DONE
- Created `src/utils/template_resolver.py`
- Both executors now use it

### ✅ 2. Add Regression Test
**Status:** DONE
- Created `tests/test_template_resolution.py`
- Includes critical `test_no_orphaned_braces()`
- All 11 tests passing

### ✅ 3. Update Prompts (Simplified)
**Status:** DONE
- Created `prompts/examples/general/09_example_duplicates_correct_formatting.md`
- Shows that `{$step1.field}` is correct syntax
- Recommends `details: "$step1.duplicates"` (simple reference)

### ✅ 4. Warning on Unresolved Braces
**Status:** DONE
- `_check_unresolved()` function detects orphaned braces
- Logs warnings: `"Message contains orphaned braces (possible partial resolution)"`

## Testing

### Server Status
✅ Server restarted with shared resolver (PID: 12834)
✅ Both executors loaded with updated code
✅ All regression tests passing

### Test the Fix

**Open UI:** http://localhost:3000

**Test Query:** "what files are duplicated?"

**Expected Result:**
```
✅ "Found 2 group(s) of duplicate files, wasting 0.38 MB"
✅ Actual file names displayed
❌ NO template syntax like {$step1.count}
❌ NO orphaned braces like {2}
```

## Key Improvements

### 1. Consistency ✅
Both executors now behave identically:
- PlanExecutor: Uses shared resolver
- AutomationAgent: Uses shared resolver
- No more divergence!

### 2. Correctness ✅
Orphaned braces bug fixed:
- Before: `"Found {2} groups"` ❌
- After: `"Found 2 groups"` ✅

### 3. Maintainability ✅
Single source of truth:
- One resolver to maintain
- Bugs fixed in one place
- Tests verify both paths

### 4. Testability ✅
Comprehensive test coverage:
- 11 regression tests
- Critical bug specifically tested
- Edge cases handled

## Conclusion

**Your analysis was spot-on!** The problem was indeed:
1. ✅ Two executors with different logic
2. ✅ AutomationAgent leaving orphaned braces
3. ✅ Need for shared utility
4. ✅ Need for regression tests

**The fix implements all your recommendations:**
- ✅ Shared template resolver
- ✅ Both executors updated
- ✅ Comprehensive tests
- ✅ Warning on unresolved placeholders

**Impact:**
- Before: UI showed `{2}` and `{0.38}` (broken)
- After: UI shows `2` and `0.38` (correct)

**Ready for testing!** The server is running and both execution paths now use the same resolution logic. No more orphaned braces!
