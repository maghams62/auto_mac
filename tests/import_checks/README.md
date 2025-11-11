# Import Verification Tests

This directory contains automated tests to prevent import issues in the codebase.

## Tests

### 1. check_all_imports.py
Scans all Python files in the `src/` directory for problematic import patterns.

**Usage:**
```bash
python tests/import_checks/check_all_imports.py
```

**What it checks:**
- Imports missing the `src.` prefix
- Patterns like `from utils import` instead of `from src.utils import`
- Identifies all problematic files and line numbers

**Expected output:**
```
✅ No problematic imports found! All imports are using correct 'src.' prefix.
```

### 2. test_critical_imports.py
Tests that all critical modules can be imported successfully.

**Usage:**
```bash
python tests/import_checks/test_critical_imports.py
```

**What it tests:**
- File Agent
- Email Agent
- Browser Agent
- Google Finance Agent
- Writing Agent
- Agent Registry
- Utils
- Documents
- Automation
- Workflow

**Expected output:**
```
✅ All tests pass
RESULTS: 10 passed, 0 failed out of 10 tests
```

## When to Run

### Before Committing
Always run both tests before committing code changes:
```bash
python tests/import_checks/check_all_imports.py
python tests/import_checks/test_critical_imports.py
```

### After Adding New Modules
When creating new modules or agents, add them to `test_critical_imports.py` to ensure they follow the correct import pattern.

### During CI/CD
These tests should be integrated into your CI/CD pipeline to catch import issues automatically.

## Common Issues

### "No module named 'src'"
If you see this error, make sure you're running the tests from the project root or that the path resolution is correct.

### "No module named '<module>'"
This indicates a missing `src.` prefix. The import should be:
```python
from src.<module> import ...
```
Instead of:
```python
from <module> import ...
```

## Import Convention

✅ **Correct:**
```python
from src.utils import load_config
from src.documents import DocumentIndexer
from src.agent.email_agent import compose_email
```

❌ **Incorrect:**
```python
from utils import load_config
from documents import DocumentIndexer
from agent.email_agent import compose_email
```

## Maintenance

If you add new internal modules to the project, update the `PROBLEMATIC_PATTERNS` list in `check_all_imports.py` to ensure they're checked.
