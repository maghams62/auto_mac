# Utility Scripts

This folder contains utility scripts for development, debugging, and maintenance tasks.

## Scripts

### `audit_imports.py`
Audits import statements across the codebase to identify missing or circular dependencies.

```bash
python scripts/utils/audit_imports.py
```

### `check_applescript_permissions.py`
Verifies macOS automation permissions required for AppleScript operations.

```bash
python scripts/utils/check_applescript_permissions.py
```

### `check_tool_completeness.py`
Validates that all tools have proper definitions, schemas, and documentation.

```bash
python scripts/utils/check_tool_completeness.py
```

### `debug_google_html.py`
Debug utility for Google search HTML parsing issues.

```bash
python scripts/utils/debug_google_html.py
```

### `diagnose_whatsapp_ui.py`
Diagnostic tool for WhatsApp UI automation issues.

```bash
python scripts/utils/diagnose_whatsapp_ui.py
```

### `regenerate_tool_catalog.py`
Regenerates the tool catalog from agent definitions.

```bash
python scripts/utils/regenerate_tool_catalog.py
```

### `run_quality_tests.py`
Runs quality assurance tests across the codebase.

```bash
python scripts/utils/run_quality_tests.py
```

### `validate_environment.py`
Validates the development environment setup (dependencies, config, etc.).

```bash
python scripts/utils/validate_environment.py
```

## Usage

All scripts should be run from the project root directory:

```bash
cd /path/to/auto_mac
python scripts/utils/<script_name>.py
```

