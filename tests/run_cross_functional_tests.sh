#!/bin/bash
# Quick test runner for cross-functional queries

echo "=========================================="
echo "Cross-Functional Query Testing"
echo "=========================================="
echo ""

# Check if API server is running
if ! lsof -ti:8000 > /dev/null 2>&1; then
    echo "⚠️  API server is not running on port 8000"
    echo "Please start the API server first:"
    echo "  python3 api_server.py"
    echo ""
    exit 1
fi

echo "✅ API server is running"
echo ""

# Run tests
python3 tests/test_cross_functional_queries_comprehensive.py

echo ""
echo "=========================================="
echo "Testing complete!"
echo "=========================================="
