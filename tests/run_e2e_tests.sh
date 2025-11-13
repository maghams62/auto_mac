#!/bin/bash
"""
End-to-End Test Execution Script

This script runs the complete e2e test suite with proper setup and teardown.
It ensures all services are running and configured correctly before executing tests.

Usage:
  ./run_e2e_tests.sh [options]

Options:
  --api-only        Run only backend API tests
  --ui-only         Run only UI tests
  --smoke           Run critical path tests only
  --full            Run complete test suite (default)
  --verbose         Enable verbose output
  --report          Generate detailed HTML report
  --parallel        Run tests in parallel
"""

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
API_URL="${API_URL:-http://localhost:8000}"
UI_URL="${UI_URL:-http://localhost:3000}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_MODE="full"
VERBOSE=false
REPORT=false
PARALLEL=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --api-only)
      TEST_MODE="api"
      shift
      ;;
    --ui-only)
      TEST_MODE="ui"
      shift
      ;;
    --smoke)
      TEST_MODE="smoke"
      shift
      ;;
    --full)
      TEST_MODE="full"
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    --report)
      REPORT=true
      shift
      ;;
    --parallel)
      PARALLEL=true
      shift
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      echo "Usage: $0 [--api-only|--ui-only|--smoke|--full] [--verbose] [--report] [--parallel]"
      exit 1
      ;;
  esac
done

# Logging functions
log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
  echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

# Service health checks
check_service() {
  local url=$1
  local service_name=$2
  local max_attempts=30
  local attempt=1

  log_info "Checking $service_name at $url..."

  while [ $attempt -le $max_attempts ]; do
    if curl -s --max-time 5 "$url" > /dev/null 2>&1; then
      log_success "$service_name is responding"
      return 0
    fi

    log_info "Waiting for $service_name... (attempt $attempt/$max_attempts)"
    sleep 2
    ((attempt++))
  done

  log_error "$service_name failed to respond at $url"
  return 1
}

# Setup test environment
setup_test_environment() {
  log_info "Setting up test environment..."

  # Create test data directories
  mkdir -p "$PROJECT_ROOT/data/test_results"
  mkdir -p "$PROJECT_ROOT/data/test_data"
  mkdir -p "$PROJECT_ROOT/tests/e2e/data/test_data"

  # Set environment variables
  export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"
  export TEST_MODE=true
  export API_BASE_URL="$API_URL"
  export UI_BASE_URL="$UI_URL"

  # Clean up previous test artifacts
  find "$PROJECT_ROOT/data/test_results" -name "*.json" -mtime +7 -delete 2>/dev/null || true

  log_success "Test environment setup complete"
}

# Run API tests
run_api_tests() {
  log_info "Running API end-to-end tests..."

  cd "$PROJECT_ROOT"

  local pytest_args="-v --tb=short"
  local test_paths="tests/e2e/finance/ tests/e2e/emails/ tests/e2e/reminders/ tests/e2e/bluesky/ tests/e2e/explain/ tests/e2e/files/ tests/e2e/calendar/ tests/e2e/spotify/ tests/e2e/images/"

  if [ "$VERBOSE" = true ]; then
    pytest_args="$pytest_args -s"
  fi

  if [ "$PARALLEL" = true ]; then
    pytest_args="$pytest_args -n auto"
  fi

  if [ "$REPORT" = true ]; then
    pytest_args="$pytest_args --html=tests/e2e/reports/api_report.html --self-contained-html"
  fi

  if [ "$TEST_MODE" = "smoke" ]; then
    # Run only critical finance workflow test
    pytest $pytest_args tests/e2e/finance/test_finance_presentation_email.py::TestFinancePresentationEmail::test_finance_presentation_email_workflow
  else
    pytest $pytest_args $test_paths
  fi

  local api_exit_code=$?
  if [ $api_exit_code -eq 0 ]; then
    log_success "API tests completed successfully"
  else
    log_error "API tests failed with exit code $api_exit_code"
  fi

  return $api_exit_code
}

# Run UI tests
run_ui_tests() {
  log_info "Running UI regression tests..."

  cd "$PROJECT_ROOT/frontend"

  # Check if Playwright is installed
  if ! command -v npx &> /dev/null; then
    log_error "npx not found. Please install Node.js and npm."
    return 1
  fi

  local playwright_args=""
  if [ "$VERBOSE" = true ]; then
    playwright_args="$playwright_args --debug"
  fi

  if [ "$REPORT" = true ]; then
    playwright_args="$playwright_args --reporter=html"
  fi

  if [ "$PARALLEL" = true ]; then
    playwright_args="$playwright_args --workers=4"
  fi

  # Run Playwright tests
  npx playwright test tests/ui/ $playwright_args

  local ui_exit_code=$?
  if [ $ui_exit_code -eq 0 ]; then
    log_success "UI tests completed successfully"
  else
    log_error "UI tests failed with exit code $ui_exit_code"
  fi

  return $ui_exit_code
}

# Generate test summary report
generate_test_report() {
  log_info "Generating test summary report..."

  local report_dir="$PROJECT_ROOT/tests/e2e/reports"
  mkdir -p "$report_dir"

  local report_file="$report_dir/e2e_test_summary_$(date +%Y%m%d_%H%M%S).md"

  cat > "$report_file" << EOF
# End-to-End Test Execution Summary

**Execution Date:** $(date)
**Test Mode:** $TEST_MODE
**Environment:**
- API URL: $API_URL
- UI URL: $UI_URL
- Parallel Execution: $PARALLEL

## Test Results

### Configuration
- Python Path: $PYTHONPATH
- Test Data Directory: $PROJECT_ROOT/data/test_data
- Reports Directory: $report_dir

### Service Health
- API Service: $(check_service "$API_URL/api/health" "API" && echo "✅ Healthy" || echo "❌ Unhealthy")
- UI Service: $(check_service "$UI_URL" "UI" && echo "✅ Healthy" || echo "❌ Unhealthy")

## Detailed Results

See individual test reports in the reports directory for detailed results.

## Next Steps

1. Review failed tests and fix issues
2. Check test artifacts in data/test_results/
3. Update test baselines if needed
4. Run again with --verbose for debugging

---
*Generated by E2E Test Runner*
EOF

  log_success "Test summary report generated: $report_file"
}

# Main execution
main() {
  log_info "Starting End-to-End Test Suite"
  log_info "Test Mode: $TEST_MODE"
  log_info "Verbose: $VERBOSE, Report: $REPORT, Parallel: $PARALLEL"

  # Setup environment
  setup_test_environment

  # Check service health
  if ! check_service "$API_URL/api/health" "API Service"; then
    log_error "API service not healthy. Please start the API server first."
    log_info "Run: python api_server.py"
    exit 1
  fi

  if [ "$TEST_MODE" = "ui" ] || [ "$TEST_MODE" = "full" ]; then
    if ! check_service "$UI_URL" "UI Service"; then
      log_error "UI service not healthy. Please start the UI server first."
      log_info "Run: cd frontend && npm run dev"
      exit 1
    fi
  fi

  # Run tests based on mode
  local exit_code=0

  case $TEST_MODE in
    "api")
      run_api_tests
      exit_code=$?
      ;;
    "ui")
      run_ui_tests
      exit_code=$?
      ;;
    "smoke")
      run_api_tests  # Smoke tests are API-only for now
      exit_code=$?
      ;;
    "full")
      # Run API tests first
      if run_api_tests; then
        log_success "API tests passed, proceeding with UI tests..."
        # Run UI tests after API tests pass
        run_ui_tests
        exit_code=$?
      else
        log_error "API tests failed, skipping UI tests"
        exit_code=1
      fi
      ;;
  esac

  # Generate report if requested
  if [ "$REPORT" = true ]; then
    generate_test_report
  fi

  # Final status
  if [ $exit_code -eq 0 ]; then
    log_success "🎉 All tests completed successfully!"
  else
    log_error "❌ Test suite completed with failures"
  fi

  return $exit_code
}

# Run main function
main "$@"
