#!/bin/bash
"""
Slash Command Regression Test Runner

Runs the complete slash command regression test suite including:
- Python backend tests
- Playwright UI tests
- Telemetry validation

Usage:
  ./run_slash_regression.sh [options]

Options:
  --python-only    Run only Python backend tests
  --playwright-only Run only Playwright UI tests
  --verbose        Enable verbose output
"""

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

# Default values
PYTHON_ONLY=false
PLAYWRIGHT_ONLY=false
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --python-only)
      PYTHON_ONLY=true
      shift
      ;;
    --playwright-only)
      PLAYWRIGHT_ONLY=true
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

# Run Python tests
run_python_tests() {
  log_info "Running Python slash command regression tests..."
  
  cd "$PROJECT_ROOT"
  
  python_args=""
  if [ "$VERBOSE" = true ]; then
    python_args="-v"
  fi
  
  python tests/test_slash_regression.py $python_args
  
  if [ $? -eq 0 ]; then
    log_success "Python tests passed"
    return 0
  else
    log_error "Python tests failed"
    return 1
  fi
}

# Run Playwright tests
run_playwright_tests() {
  log_info "Running Playwright slash command UI tests..."
  
  cd "$PROJECT_ROOT/tests/ui"
  
  if ! command -v npx &> /dev/null; then
    log_error "npx not found. Please install Node.js and npm."
    return 1
  fi
  
  playwright_args="test_slash_commands_ui.spec.ts"
  if [ "$VERBOSE" = true ]; then
    playwright_args="$playwright_args --debug"
  fi
  
  npx playwright test $playwright_args
  
  if [ $? -eq 0 ]; then
    log_success "Playwright tests passed"
    return 0
  else
    log_error "Playwright tests failed"
    return 1
  fi
}

# Main execution
main() {
  log_info "Starting Slash Command Regression Tests"
  
  exit_code=0
  
  if [ "$PLAYWRIGHT_ONLY" = true ]; then
    run_playwright_tests
    exit_code=$?
  elif [ "$PYTHON_ONLY" = true ]; then
    run_python_tests
    exit_code=$?
  else
    # Run both
    if run_python_tests; then
      log_success "Python tests passed, proceeding with Playwright tests..."
      run_playwright_tests
      exit_code=$?
    else
      log_error "Python tests failed, skipping Playwright tests"
      exit_code=1
    fi
  fi
  
  if [ $exit_code -eq 0 ]; then
    log_success "🎉 All slash command regression tests passed!"
  else
    log_error "❌ Some tests failed"
  fi
  
  return $exit_code
}

main "$@"

