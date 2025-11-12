# Test Results Format Specification

## Overview

This document specifies the JSON format for test results stored by the test infrastructure.

## Status Board Format

**File**: `data/test_results/status_board.json`

```json
{
  "version": "1.0",
  "last_updated": "2025-01-15T14:30:22.123456",
  "tests": {
    "test_name": {
      "last_run": "2025-01-15T14:30:22.123456",
      "status": "passed" | "failed" | "error" | "unknown",
      "pass_count": 5,
      "fail_count": 0,
      "result_file": "test_name_20250115_143022.json",
      "execution_time": 2.34,
      "error_message": "Optional error message"
    }
  },
  "locks": {},
  "messages": []
}
```

### Fields

- **version**: Format version (currently "1.0")
- **last_updated**: ISO timestamp of last update
- **tests**: Dictionary mapping test names to status
  - **last_run**: ISO timestamp of last execution
  - **status**: Overall test status
  - **pass_count**: Number of passing test cases
  - **fail_count**: Number of failing test cases
  - **result_file**: Filename of detailed result JSON
  - **execution_time**: Execution time in seconds (optional)
  - **error_message**: Error message if failed (optional)
- **locks**: Reserved for future use
- **messages**: Reserved for future use

## Individual Test Result Format

**File**: `data/test_results/results/<test_name>_<timestamp>.json`

```json
{
  "test_name": "email_attachments",
  "test_file": "tests/test_email_attachments.py",
  "status": "passed" | "failed" | "error",
  "pass_count": 5,
  "fail_count": 0,
  "error_count": 0,
  "execution_time": 2.34,
  "timestamp": "2025-01-15T14:30:22.123456",
  "details": {
    "status": "passed",
    "passed": 5,
    "failed": 0,
    "errors": 0,
    "returncode": 0,
    "stdout": "Test output...",
    "stderr": "",
    "output": "Combined output..."
  },
  "error_message": "Optional error message"
}
```

### Fields

- **test_name**: Name of the test (extracted from filename)
- **test_file**: Path to test file
- **status**: Overall status ("passed", "failed", "error")
- **pass_count**: Number of passing assertions/tests
- **fail_count**: Number of failing assertions/tests
- **error_count**: Number of errors (optional)
- **execution_time**: Total execution time in seconds
- **timestamp**: ISO timestamp when test was run
- **details**: Detailed execution information
  - **status**: pytest status
  - **passed**: Count of passed tests
  - **failed**: Count of failed tests
  - **errors**: Count of errors
  - **returncode**: Process return code (0 = success)
  - **stdout**: Standard output from pytest
  - **stderr**: Standard error from pytest
  - **output**: Combined stdout + stderr
- **error_message**: Error message if test failed (optional)

## Agent-Friendly Format

When agents call `check_test_status`, they receive:

```json
{
  "test_name": "email_attachments",
  "status": "passed" | "failed" | "error" | "not_found",
  "last_run": "2025-01-15T14:30:22.123456",
  "pass_count": 5,
  "fail_count": 0,
  "execution_time": 2.34,
  "error_message": "Optional error message",
  "message": "Human-readable status message"
}
```

### Status Values

- **passed**: All tests passed
- **failed**: One or more tests failed
- **error**: Test execution error
- **not_found**: No results found for this test
- **locked**: Test is currently locked by another agent

## Example: Email Attachments Test

### Status Board Entry:
```json
{
  "email_attachments": {
    "last_run": "2025-01-15T14:30:22",
    "status": "passed",
    "pass_count": 5,
    "fail_count": 0,
    "result_file": "email_attachments_20250115_143022.json",
    "execution_time": 2.34
  }
}
```

### Detailed Result:
```json
{
  "test_name": "email_attachments",
  "test_file": "tests/test_email_attachments.py",
  "status": "passed",
  "pass_count": 5,
  "fail_count": 0,
  "execution_time": 2.34,
  "timestamp": "2025-01-15T14:30:22",
  "details": {
    "status": "passed",
    "passed": 5,
    "failed": 0,
    "returncode": 0,
    "stdout": "tests/test_email_attachments.py::test_email_attachment_validation_missing_file PASSED\n...",
    "stderr": "",
    "output": "..."
  }
}
```

## Lock File Format

**File**: `data/.agent_locks/test_infrastructure/<test_name>.lock`

```json
{
  "test_name": "email_attachments",
  "agent_id": "agent_123",
  "timestamp": "2025-01-15T14:30:22.123456",
  "timeout": 3600
}
```

### Fields

- **test_name**: Name of the test being locked
- **agent_id**: ID of agent holding the lock
- **timestamp**: When lock was acquired (ISO format)
- **timeout**: Lock timeout in seconds (default: 3600)

## Querying Results

### Get Latest Status
```python
from src.utils.test_results import get_test_status

status = get_test_status("email_attachments")
# Returns status board entry or None
```

### Get Full Result
```python
from src.utils.test_results import get_test_result

result = get_test_result("email_attachments")
# Returns full result JSON or None
```

### Get Specific Timestamp Result
```python
result = get_test_result("email_attachments", timestamp="2025-01-15T14:30:22")
# Returns result for specific run
```

### List All Tests
```python
from src.utils.test_results import list_available_tests

tests = list_available_tests()
# Returns: ["email_attachments", "tweet_accuracy", ...]
```

## Validation

### Required Fields

Status board entry:
- `last_run` (string, ISO timestamp)
- `status` (string, one of: "passed", "failed", "error", "unknown")
- `pass_count` (integer, >= 0)
- `fail_count` (integer, >= 0)
- `result_file` (string, filename)

Test result:
- `test_name` (string)
- `status` (string)
- `timestamp` (string, ISO timestamp)
- `pass_count` (integer)
- `fail_count` (integer)

### Optional Fields

- `execution_time` (float, seconds)
- `error_message` (string)
- `details` (object, test-specific details)

## Migration

If the format changes in the future:

1. Version field in status board indicates format version
2. Migration scripts can check version and convert
3. Old result files are preserved for historical reference

## Notes

- All timestamps are in ISO 8601 format
- File paths are relative to workspace root or absolute
- JSON files use 2-space indentation
- Test names are derived from filenames (e.g., `test_email_attachments.py` -> `email_attachments`)

