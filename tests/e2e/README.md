# End-to-End Test Suite

## Overview

This comprehensive end-to-end test suite validates the complete auto_mac application workflow from user query to UI rendering. It covers all major functionality areas with strict winning criteria for each test scenario.

## Architecture

The test suite is built with:
- **pytest + pytest-asyncio** for backend API testing
- **Playwright** for UI regression testing
- **Structured fixtures** for test data and service mocking
- **Telemetry capture** for execution tracing
- **Comprehensive success criteria** validation

## Test Categories

### 🎯 **Finance-Presentation-Email** (Highest Priority)
**Location**: `tests/e2e/finance/`
- `test_finance_presentation_email.py` - Complete stock → presentation → email workflow
- **Critical**: Validates the most complex user workflow with attachment safety

### 📧 **Email Workflows**
**Location**: `tests/e2e/emails/`
- `test_email_workflows.py` - Compose, reply, forward, summarize, search
- **Critical**: Attachment validation, threading, error handling

### 📅 **Reminders Automation**
**Location**: `tests/e2e/reminders/`
- `test_reminders_automation.py` - Create, list, edit, complete reminders
- **Critical**: Time parsing, scheduling integration

### 🦋 **Bluesky Integration**
**Location**: `tests/e2e/bluesky/`
- `test_bluesky_integration.py` - Post, feed, notifications, rate limiting
- **Critical**: Social media API integration

### ❓ **Explain Command**
**Location**: `tests/e2e/explain/`
- `test_explain_commands.py` - Code explanation, functionality docs
- **Critical**: LLM reasoning and structured output

### 📁 **File/Folder Operations**
**Location**: `tests/e2e/files/`
- `test_file_operations.py` - Search, organize, move, permissions
- **Critical**: File system operations with safety checks

### 📆 **Calendar Day View**
**Location**: `tests/e2e/calendar/`
- `test_calendar_day_view.py` - Multi-source day overview
- **Critical**: Complex synthesis across calendar, email, reminders

### 🎵 **Spotify Playback**
**Location**: `tests/e2e/spotify/`
- `test_spotify_playback.py` - Play, queue, controls, device handling
- **Critical**: External API integration with device management

### 🖼️ **Image Understanding**
**Location**: `tests/e2e/images/`
- `test_image_understanding.py` - Display, OCR, search, metadata
- **Critical**: Visual content processing

### 🎭 **UI Regression Tests**
**Location**: `tests/ui/`
- `test_conversational_ui.spec.ts` - Complete UI workflow validation
- **Critical**: Frontend rendering and interaction

## Winning Criteria Summary

Each test validates **ALL** criteria for success:

### General Criteria (All Tests)
- ✅ No errors in response
- ✅ Substantive content (minimum length)
- ✅ Expected sources mentioned
- ✅ No parameter validation errors
- ✅ Workflow completion
- ✅ UI rendering success
- ✅ Telemetry capture

### Critical Safety Validations
- **Attachments**: Email never sent without required attachments
- **Error Recovery**: Graceful handling of service failures
- **Permissions**: No unauthorized operations
- **Data Integrity**: No corruption during operations

## Execution

### Quick Start
```bash
# Run complete test suite
./tests/run_e2e_tests.sh --full --report

# Run only API tests
./tests/run_e2e_tests.sh --api-only --verbose

# Run only UI tests
./tests/run_e2e_tests.sh --ui-only

# Run critical path only (smoke test)
./tests/run_e2e_tests.sh --smoke
```

### Prerequisites
1. **API Server**: Running on `http://localhost:8000`
   ```bash
   python api_server.py
   ```

2. **UI Server**: Running on `http://localhost:3000`
   ```bash
   cd frontend && npm run dev
   ```

3. **Test Dependencies**:
   ```bash
   pip install pytest pytest-asyncio pytest-html playwright
   cd frontend && npx playwright install
   ```

### Environment Variables
```bash
export API_BASE_URL=http://localhost:8000
export UI_BASE_URL=http://localhost:3000
export TEST_MODE=true
```

## Test Data and Fixtures

### Test Data Structure
```
tests/e2e/data/
├── test_data/          # Test input files
├── fixtures/           # Mock data fixtures
└── reports/            # Test execution reports
```

### Mock Services
The test suite includes comprehensive mocking for:
- Gmail API responses
- Calendar events
- Spotify API
- Bluesky social media
- File system operations

## Success Criteria Validation

Each test implements structured validation:

```python
# Example validation pattern
def test_example(self, success_criteria_checker):
    response = api_client.chat("test query")
    messages = api_client.wait_for_completion()

    # Validate ALL winning criteria
    assert success_criteria_checker.check_no_errors(response)
    assert success_criteria_checker.check_keywords_present(response_text, expected_keywords)
    assert success_criteria_checker.check_workflow_steps(messages, expected_tools)
    # ... additional validations
```

## Telemetry and Debugging

### Execution Tracing
All tests capture:
- Tool execution sequence
- Parameter values
- Execution times
- Error stack traces
- UI interaction events

### Failure Analysis
When tests fail, check:
1. **Test artifacts**: `data/test_results/`
2. **Execution logs**: `tests/e2e/logs/`
3. **UI screenshots**: `tests/ui/test-results/`
4. **Telemetry data**: Individual test result JSON files

## Continuous Integration

### GitHub Actions Example
```yaml
- name: Run E2E Tests
  run: |
    ./tests/run_e2e_tests.sh --full --report --parallel
  env:
    API_BASE_URL: http://localhost:8000
    UI_BASE_URL: http://localhost:3000
```

## Maintenance

### Adding New Tests
1. Create test file in appropriate category directory
2. Follow naming convention: `test_<feature>.py`
3. Implement all winning criteria validations
4. Add telemetry capture
5. Update success criteria documentation

### Updating Success Criteria
1. Modify `E2E_SUCCESS_CRITERIA.md`
2. Update corresponding test implementations
3. Run regression tests to validate changes

## Performance Benchmarks

### Target Execution Times
- **Individual test**: < 60 seconds
- **API test suite**: < 10 minutes
- **UI test suite**: < 15 minutes
- **Full suite**: < 25 minutes

### Resource Requirements
- **Memory**: 4GB minimum
- **Disk**: 2GB for test artifacts
- **Network**: Stable internet for external APIs

## Troubleshooting

### Common Issues

**API Server Not Responding**
```bash
# Check server logs
tail -f api_server.log

# Restart server
python api_server.py
```

**UI Tests Failing**
```bash
# Check Playwright browsers
npx playwright install

# Run with debug
./tests/run_e2e_tests.sh --ui-only --verbose
```

**Test Timeouts**
```bash
# Increase timeout for slow operations
export TEST_TIMEOUT=120
```

**Permission Errors**
```bash
# Fix file permissions
chmod +x tests/run_e2e_tests.sh
```

## Contributing

When adding new functionality:
1. Add corresponding e2e tests
2. Update success criteria documentation
3. Include negative test cases
4. Add telemetry capture
5. Update this README

---

## Success Rate Targets

- **Current Target**: 90% of criteria passing across all scenarios
- **Stretch Goal**: 100% of criteria passing
- **Critical Path**: Finance-Presentation-Email workflow must achieve 100%

This test suite ensures the auto_mac application delivers reliable, high-quality user experiences across all major workflows.
