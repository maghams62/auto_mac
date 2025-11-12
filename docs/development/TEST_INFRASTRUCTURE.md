# Test Infrastructure Documentation

## Overview

The test infrastructure provides a comprehensive system for running tests, storing results, and allowing agents to access test status without re-running tests.

## Architecture

### Components

1. **Test Result Storage** (`src/utils/test_results.py`)
   - Stores test results in JSON format
   - Maintains status board with all test statuses
   - Provides locking mechanism for concurrent test execution

2. **Test Runner** (`src/utils/test_runner.py`)
   - Executes tests using pytest programmatically
   - Integrates with result storage
   - Supports single tests, test suites, and all tests

3. **Test Agent** (`src/agent/test_agent.py`)
   - Provides tools for agents to check test status
   - Allows agents to trigger test execution
   - Returns structured results agents can use

4. **CLI Runner** (`tests/run_tests.py`)
   - Command-line interface for manual test execution
   - Supports running tests, checking status, viewing results

## File Structure

```
data/
  test_results/
    status_board.json          # Overall test status board
    results/                   # Individual test result files
      email_attachments_20250115_143022.json
      tweet_accuracy_20250115_143022.json
      ...
  .agent_locks/
    test_infrastructure/      # Test execution locks
      email_attachments.lock
      ...
```

## Usage

### Manual Test Execution

#### Run a specific test:
```bash
python -m tests.run run email_attachments
```

#### Run all tests:
```bash
python -m tests.run all
```

#### Check test status:
```bash
python -m tests.run status
python -m tests.run status email_attachments
```

#### View detailed results:
```bash
python -m tests.run results email_attachments
```

#### List available tests:
```bash
python -m tests.run list
```

#### JSON output:
```bash
python -m tests.run status --json
```

### Programmatic Usage (for Code)

#### Check test status:
```python
from src.utils.test_results import get_test_status

status = get_test_status("email_attachments")
if status and status.get("status") == "passed":
    print("Test passed!")
```

#### Run a test:
```python
from src.utils.test_runner import TestRunner

runner = TestRunner()
result = runner.run_test("email_attachments")
print(f"Status: {result['status']}")
```

#### Save test result:
```python
from src.utils.test_results import save_test_result

save_test_result("my_test", {
    "status": "passed",
    "pass_count": 5,
    "fail_count": 0,
    "details": {...}
})
```

### Agent Usage

#### Check test status (via tool):
```python
from src.agent.test_agent import check_test_status

result = check_test_status.invoke({"test_name": "email_attachments"})
# Returns: {"status": "passed", "last_run": "...", "pass_count": 5, ...}
```

#### List all test statuses:
```python
from src.agent.test_agent import list_test_statuses

result = list_test_statuses.invoke({})
# Returns: {"test_count": 3, "tests": {...}, "summary": {...}}
```

#### Run a test (via tool):
```python
from src.agent.test_agent import run_test

result = run_test.invoke({"test_name": "email_attachments"})
# Executes test and returns results
```

## Test Result Format

### Status Board (`data/test_results/status_board.json`)

```json
{
  "version": "1.0",
  "last_updated": "2025-01-15T14:30:22",
  "tests": {
    "email_attachments": {
      "last_run": "2025-01-15T14:30:22",
      "status": "passed",
      "pass_count": 5,
      "fail_count": 0,
      "result_file": "email_attachments_20250115_143022.json",
      "execution_time": 2.34
    }
  },
  "locks": {},
  "messages": []
}
```

### Individual Test Result (`data/test_results/results/email_attachments_20250115_143022.json`)

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
    "output": "..."
  }
}
```

## Agent Coordination

The test infrastructure uses locks to prevent concurrent test execution:

- **Lock acquisition**: Before running a test, acquire lock
- **Lock release**: After test completes, release lock
- **Conflict checking**: Check if test is already running before starting

Example:
```python
from src.utils.test_results import acquire_test_lock, release_test_lock

if acquire_test_lock("email_attachments", agent_id="my_agent"):
    try:
        # Run test
        pass
    finally:
        release_test_lock("email_attachments", agent_id="my_agent")
```

## Adding New Tests

### 1. Create test file

Create `tests/test_my_feature.py`:
```python
import pytest

def test_my_feature():
    # Test logic
    assert True
```

### 2. Test will automatically save results

The pytest hook in `conftest.py` automatically saves results when tests run.

### 3. Access results

```python
from src.utils.test_results import get_test_status

status = get_test_status("my_feature")
```

## Best Practices

1. **Test Naming**: Use descriptive test names that match the feature being tested
2. **Result Saving**: Results are saved automatically via pytest hooks
3. **Lock Management**: Always use locks when running tests programmatically
4. **Error Handling**: Test infrastructure handles errors gracefully
5. **Backward Compatibility**: Existing tests work without modification

## Troubleshooting

### Tests not saving results

- Check that `src/utils/test_results.py` is importable
- Verify `data/test_results/` directory exists and is writable
- Check logs for errors in result saving

### Lock conflicts

- Check `data/.agent_locks/test_infrastructure/` for stale locks
- Locks expire after 1 hour automatically
- Manually remove lock files if needed

### Test not found

- Verify test file exists in `tests/` directory
- Check test file naming: `test_<name>.py`
- Use `python -m tests.run list` to see available tests

## Integration with Agents

Agents can use the test infrastructure to:

1. **Check if tests have passed** before proceeding with work
2. **Verify functionality** by checking test status
3. **Avoid redundant testing** by reading existing results
4. **Trigger tests** when needed for validation

Example agent workflow:
```python
# Agent checks if email attachment tests passed
status = check_test_status.invoke({"test_name": "email_attachments"})

if status.get("status") == "passed":
    # Proceed with email-related work
    pass
else:
    # Wait or handle failure
    pass
```

