#!/bin/bash
# Quick Test Runner for Mac Automation System
# Usage: ./run_tests.sh [option]

set -e

echo "================================================"
echo "Mac Automation System - Test Runner"
echo "================================================"
echo ""

case "$1" in
    --dry-run|dry)
        echo "Running DRY RUN (showing test definitions only)..."
        python test_comprehensive_system.py --dry-run
        ;;

    --file|file)
        echo "Running FILE AGENT tests..."
        python test_comprehensive_system.py --category single_agent_file
        ;;

    --browser|browser)
        echo "Running BROWSER AGENT tests..."
        python test_comprehensive_system.py --category single_agent_browser
        ;;

    --presentation|presentation)
        echo "Running PRESENTATION AGENT tests..."
        python test_comprehensive_system.py --category single_agent_presentation
        ;;

    --email|email)
        echo "Running EMAIL AGENT tests..."
        python test_comprehensive_system.py --category single_agent_email
        ;;

    --multi|multi)
        echo "Running MULTI-AGENT tests..."
        echo "Available multi-agent categories:"
        echo "  - multi_agent_file_presentation"
        echo "  - multi_agent_file_email"
        echo "  - multi_agent_browser_presentation"
        echo "  - multi_agent_browser_email"
        echo "  - multi_agent_full"
        echo ""
        read -p "Enter category name (or press Enter for multi_agent_full): " category
        category=${category:-multi_agent_full}
        python test_comprehensive_system.py --category "$category"
        ;;

    --original|original)
        echo "Running ORIGINAL FAILING TEST (now fixed!)..."
        echo "Test: Take screenshot of Google News, add to presentation, email it"
        python test_comprehensive_system.py --category multi_agent_full
        ;;

    --edge|edge)
        echo "Running EDGE CASE tests..."
        python test_comprehensive_system.py --category edge_case
        ;;

    --all|all)
        echo "Running ALL tests..."
        echo "WARNING: This will take a long time and require user confirmations!"
        read -p "Are you sure? (y/N): " confirm
        if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
            python test_comprehensive_system.py
        else
            echo "Cancelled."
        fi
        ;;

    --help|help|-h|"")
        echo "Usage: ./run_tests.sh [option]"
        echo ""
        echo "Options:"
        echo "  dry-run         Show all test definitions without running"
        echo "  file            Run FILE AGENT tests only"
        echo "  browser         Run BROWSER AGENT tests only"
        echo "  presentation    Run PRESENTATION AGENT tests only"
        echo "  email           Run EMAIL AGENT tests only"
        echo "  multi           Run MULTI-AGENT tests (interactive)"
        echo "  original        Run the original failing test (now fixed!)"
        echo "  edge            Run edge case tests"
        echo "  all             Run ALL tests (long!)"
        echo "  help            Show this help message"
        echo ""
        echo "Examples:"
        echo "  ./run_tests.sh dry-run"
        echo "  ./run_tests.sh browser"
        echo "  ./run_tests.sh original"
        echo ""
        ;;

    *)
        echo "Unknown option: $1"
        echo "Use './run_tests.sh help' for usage information"
        exit 1
        ;;
esac

echo ""
echo "================================================"
echo "Test run complete!"
echo "Check test_results.json for detailed results"
echo "================================================"
