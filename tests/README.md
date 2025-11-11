# Tests Directory

This directory contains all test files for the Mac Automation Assistant.

## Structure

- **Unit Tests**: Test individual components and agents
- **Integration Tests**: Test complete workflows and orchestration
- **System Tests**: End-to-end tests of the entire system

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

## Test Categories

### Agent Tests
- `test_direct_agent.py` - Test agent functionality
- `test_writing_agent.py` - Test writing agent
- `test_maps_agent.py` - Test maps agent
- `test_new_stock_agent.py` - Test stock agent

### Workflow Tests
- `test_complete_workflow.py` - Complete workflow tests
- `test_comprehensive_orchestration.py` - Orchestration tests
- `test_hybrid_stock_workflow.py` - Stock workflow tests

### System Tests
- `test_comprehensive_system.py` - Full system tests
- `test_all_tools.py` - Test all available tools

## Notes

- Tests should be run from the project root directory
- Some tests may require API keys or specific environment setup
- Check individual test files for specific requirements

