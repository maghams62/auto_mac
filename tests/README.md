# Tests Directory

This directory contains all test files for Cerebro OS.

**📚 [Test Index](TEST_INDEX.md)** - **START HERE** - Central repository mapping all test files for easy discovery.

## Structure

- **Unit Tests**: Test individual components and agents
- **Integration Tests**: Test complete workflows and orchestration
- **System Tests**: End-to-end tests of the entire system
- **Test Data**: `data/` - Test data files and documents
- **Test Logs**: `logs/` - Test execution logs

## Running Tests

### Run all tests:
```bash
python -m pytest tests/
```

### Run specific test file:
```bash
python tests/test_direct_agent.py
```

### Run with scripts:
```bash
./tests/run_tests.sh
./tests/quick_tool_tests.sh
```

## Test Organization

### By Agent
- **File Agent**: `test_file_organize.py`, `test_document_search_fix.py`
- **Browser Agent**: `test_google_agent.py`, `test_google_search.py`
- **Maps Agent**: `test_maps_agent.py`, `test_maps_applescript.py`
- **Email Agent**: `test_email_scenarios.py`, `test_email_reply.py`
- **Stock Agent**: `test_new_stock_agent.py`, `test_stock_workflow_final.py`
- **Writing Agent**: `test_writing_agent.py`
- **Folder Agent**: `test_folder_agent.py`, `test_folder_workflows.py`
- **And more...** See [TEST_INDEX.md](TEST_INDEX.md) for complete list

### By Type
- **Unit Tests**: Individual component tests
- **Integration Tests**: Multi-component workflow tests
- **System Tests**: End-to-end system tests
- **Debug Tests**: Fix validation tests

## Test Data

Test data is organized under `tests/data/`:
- `tests/data/test_data/` - General test data files
- `tests/data/test_doc/` - Test document files
- `tests/data/test_docs/` - Additional test documents

## Test Logs

Test execution logs are stored in `tests/logs/`:
- `test_execution.log` - General test execution log
- `api_test.log` - API test logs
- `api_server_test.log` - API server test logs
- `frontend_test.log` - Frontend test logs

## Quick Reference

See [TEST_INDEX.md](TEST_INDEX.md) for:
- Complete list of all test files
- Test organization by agent, feature, and type
- Quick reference tables
- Test data paths

## Notes

- Tests should be run from the project root directory
- Some tests may require API keys or specific environment setup
- Check individual test files for specific requirements
- Test data paths have been updated to `tests/data/` structure

