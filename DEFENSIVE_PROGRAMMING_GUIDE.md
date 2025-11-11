# Defensive Programming Guide - Preventing Agent Failures

## Overview
This document outlines the defensive programming patterns applied across all agents to prevent failures from invalid LLM-generated data or missing resources.

## Core Failure Pattern (The Bug That Was Fixed)

### What Went Wrong
In `file_organizer.py`, the LLM returned filenames that didn't match actual scanned files. The code tried to access `file_decision['path']` which never existed, causing:
```
KeyError: 'path'
OrganizationError: 'path'
```

### Root Cause
**Missing validation when LLM-generated data doesn't match reality**

Three failure modes:
1. **Missing Input Validation** - Not checking if files/paths exist before using them
2. **Assuming LLM Data is Valid** - Trusting LLM-generated data (filenames, paths, URLs) without verification
3. **No Defensive Programming** - Accessing external resources without try-except or existence checks

## Fixes Applied

### 1. File Organizer (`src/automation/file_organizer.py`) ✅

**Before:**
```python
for file_decision in result['files']:
    matching_file = next(
        (f for f in files if f['filename'] == file_decision['filename']),
        None
    )
    if matching_file:
        file_decision['path'] = matching_file['path']

# Later: file_info['path'] causes KeyError if no match found!
```

**After:**
```python
valid_files = []
for file_decision in result['files']:
    matching_file = next(
        (f for f in files if f['filename'] == file_decision['filename']),
        None
    )
    if matching_file:
        file_decision['path'] = matching_file['path']
        valid_files.append(file_decision)  # Only include if valid!
    else:
        logger.warning(f"LLM returned filename '{file_decision['filename']}' that doesn't match any scanned file. Skipping.")

result['files'] = valid_files  # Only process validated files
```

**Key Pattern:** Filter out invalid entries before processing, log warnings for debugging

### 2. Mail Composer (`src/automation/mail_composer.py`) ✅

**Before:**
```python
all_attachments = []
if attachment_path:
    all_attachments.append(attachment_path)
if attachment_paths:
    all_attachments.extend(attachment_paths)
# No validation - passes invalid paths to AppleScript!
```

**After:**
```python
all_attachments = []
invalid_attachments = []

if attachment_path:
    all_attachments.append(attachment_path)
if attachment_paths:
    all_attachments.extend(attachment_paths)

# Validate all attachment paths exist
import os
validated_attachments = []
for att_path in all_attachments:
    if os.path.exists(att_path) and os.path.isfile(att_path):
        validated_attachments.append(att_path)
    else:
        logger.warning(f"[MAIL COMPOSER] Attachment file not found, skipping: {att_path}")
        invalid_attachments.append(att_path)

# Log warning if some attachments were invalid
if invalid_attachments:
    logger.warning(f"[MAIL COMPOSER] {len(invalid_attachments)} attachment(s) not found: {invalid_attachments}")

all_attachments = validated_attachments
```

**Key Pattern:** Validate file existence before passing to system tools (AppleScript, etc.)

### 3. Keynote Composer (`src/automation/keynote_composer.py`) ✅

**Before:**
```python
script = self._build_applescript(
    title=title,
    slides=slides,  # No validation of image paths!
    output_path=output_path,
)
```

**After:**
```python
# Validate slide image paths exist (defensive programming)
import os
validated_slides = []
for i, slide in enumerate(slides):
    validated_slide = slide.copy()
    if 'image_path' in slide and slide['image_path']:
        image_path = slide['image_path']
        if os.path.exists(image_path) and os.path.isfile(image_path):
            validated_slide['image_path'] = image_path
        else:
            logger.warning(f"[KEYNOTE] Slide {i+1} image not found, removing: {image_path}")
            validated_slide.pop('image_path', None)  # Remove invalid path
    validated_slides.append(validated_slide)

script = self._build_applescript(
    title=title,
    slides=validated_slides,  # Only validated slides
    output_path=output_path,
)
```

**Key Pattern:** Validate and sanitize data structures before passing to external systems

## Validation Patterns to Apply

### Pattern 1: File Path Validation
**Use when:** Agent receives file paths from LLM or user
```python
import os

def validate_file_path(path: str, context: str = "") -> Optional[str]:
    """Validate file exists and is a file."""
    if not path:
        return None
    if os.path.exists(path) and os.path.isfile(path):
        return path
    else:
        logger.warning(f"[{context}] File not found: {path}")
        return None

# Usage
validated_path = validate_file_path(llm_generated_path, "EMAIL_AGENT")
if validated_path:
    # proceed with file
else:
    # skip or error
```

### Pattern 2: List Filtering
**Use when:** LLM returns list of items that need matching to real data
```python
# Filter out invalid items, keep only validated ones
validated_items = []
for item in llm_generated_items:
    if validate_item(item):
        validated_items.append(item)
    else:
        logger.warning(f"Invalid item skipped: {item}")

# Only process validated items
process(validated_items)
```

### Pattern 3: Dictionary Key Validation
**Use when:** Accessing dictionary keys that might not exist
```python
# Instead of:
value = data['key']  # KeyError if key missing!

# Use:
value = data.get('key')  # Returns None if missing
if value is not None:
    # process value
```

### Pattern 4: Try-Except with Specific Error Types
**Use when:** External operations that might fail
```python
try:
    result = external_operation(params)
except FileNotFoundError as e:
    logger.error(f"File not found: {e}")
    return {"error": True, "error_type": "FileNotFound", "error_message": str(e)}
except PermissionError as e:
    logger.error(f"Permission denied: {e}")
    return {"error": True, "error_type": "PermissionDenied", "error_message": str(e)}
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return {"error": True, "error_type": "UnexpectedError", "error_message": str(e)}
```

## Pattern 5: API Parameter Validation

**Use when:** Making requests to external APIs

**NEW - Added for generalized API safety**

### The Problem
Different API endpoints support different parameters. Sending unsupported parameters causes 400 errors.

### The Solution
Use `APIValidator` to validate parameters before sending to external APIs.

**Example:**
```python
from src.utils.api_validator import create_twitter_validator

class TwitterAPIClient:
    def __init__(self):
        self._validator = create_twitter_validator()

    def fetch_list_tweets(self, list_id, start_time):
        params = {
            "max_results": 100,
            "start_time": start_time  # May not be supported by this endpoint
        }

        # Validate parameters against endpoint capabilities
        validated = self._validator.validate_params("lists_tweets", params)
        # Result: Filters out unsupported params, logs warning

        response = requests.get(url, params=validated)
```

### Implementation
See [API_PARAMETER_VALIDATION.md](API_PARAMETER_VALIDATION.md) and [QUICK_API_VALIDATION_GUIDE.md](QUICK_API_VALIDATION_GUIDE.md) for full details.

## Checklist for New Agents

When creating or modifying agents, ensure:

- [ ] **File paths are validated** before use (check `os.path.exists()` and `os.path.isfile()`)
- [ ] **LLM-generated data is matched** against real system state before accessing fields
- [ ] **Dictionary keys are accessed safely** using `.get()` or existence checks
- [ ] **Invalid items are filtered out** with logging, not passed to downstream code
- [ ] **External operations are wrapped** in try-except blocks with specific error handling
- [ ] **API parameters are validated** using `APIValidator` before external API calls
- [ ] **User feedback is provided** via logging when invalid data is encountered
- [ ] **Graceful degradation** - continue with valid items even if some are invalid

## Testing Strategy

For each agent, test:

1. **Happy Path** - Valid inputs work correctly
2. **Missing Files** - Non-existent file paths are handled gracefully
3. **LLM Hallucination** - LLM returns data that doesn't match reality
4. **Partial Failures** - Some items valid, some invalid (should process valid ones)
5. **Complete Failures** - All items invalid (should return clear error message)

## Examples from Real Bugs

### Bug: Zip files starting with 'A' and email
- **Request:** "zip all files starting with 'A' and email it to me"
- **Failure:** Looked in wrong directory (test_data instead of test_docs)
- **First Fix:** Intent planner + file system context in planner prompt
- **Second Fix:** Defensive validation ensures graceful handling

### Bug: Organize files by category
- **Request:** "organize music files into Music folder"
- **Failure:** LLM returned filenames slightly different from actual filenames, causing KeyError: 'path'
- **Fix:** Filter out non-matching filenames before processing

## Impact

These patterns prevent:
- ❌ **KeyError** crashes when accessing missing dictionary keys
- ❌ **FileNotFoundError** crashes when files don't exist
- ❌ **System failures** from passing invalid data to AppleScript/external tools
- ❌ **Silent failures** where invalid data is processed without errors

They enable:
- ✅ **Graceful degradation** - process valid items even when some fail
- ✅ **Clear error messages** - users know exactly what went wrong
- ✅ **Debugging support** - logs show which items failed and why
- ✅ **Reliability** - system continues working even with partial failures

## Summary

**The Core Rule:** Never trust that LLM-generated or user-provided data matches system reality. Always validate before use.

**The Fix Pattern:**
1. Validate input data against system state
2. Filter out invalid items
3. Log warnings for debugging
4. Process only validated items
5. Provide clear error messages if nothing is valid

This defensive programming approach makes the system robust against LLM hallucinations, user errors, and system state changes.
