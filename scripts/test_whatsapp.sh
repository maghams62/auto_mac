#!/bin/bash
# Quick WhatsApp integration test script

echo "WhatsApp Integration Test"
echo "========================"
echo ""
echo "This will test WhatsApp Desktop integration."
echo "Make sure WhatsApp Desktop is running and logged in."
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

cd "$(dirname "$0")/.."

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

python3 tests/test_whatsapp_simple.py

