#!/bin/bash
# Quick Tool Tests - Run each test individually

echo "=========================================="
echo "QUICK TOOL TESTS"
echo "=========================================="

# Test 1: File Screenshot
echo -e "\n[1/10] Testing PDF Screenshot..."
python -c "
from src.utils import load_config
from src.agent.agent import AutomationAgent
agent = AutomationAgent(load_config())
result = agent.run('Find a guitar tab and capture page 1 as an image')
print('✅ PASS' if result.get('status') == 'success' else '❌ FAIL')
" 2>/dev/null | tail -1

# Test 2: Organize Files
echo -e "\n[2/10] Testing File Organization..."
python -c "
from src.utils import load_config
from src.agent.agent import AutomationAgent
agent = AutomationAgent(load_config())
result = agent.run('Create a folder called test_folder and organize PDF files into it')
print('✅ PASS' if result.get('status') == 'success' else '❌ FAIL')
" 2>/dev/null | tail -1

# Test 3: Google Search
echo -e "\n[3/10] Testing Google Search..."
python -c "
from src.utils import load_config
from src.agent.agent import AutomationAgent
agent = AutomationAgent(load_config())
result = agent.run('Search Google for Python documentation')
print('✅ PASS' if result.get('status') == 'success' else '❌ FAIL')
" 2>/dev/null | tail -1

# Test 4: Extract Web Content
echo -e "\n[4/10] Testing Web Content Extraction..."
python -c "
from src.utils import load_config
from src.agent.agent import AutomationAgent
agent = AutomationAgent(load_config())
result = agent.run('Navigate to python.org and extract the main content')
print('✅ PASS' if result.get('status') == 'success' else '❌ FAIL')
" 2>/dev/null | tail -1

# Test 5: Create Keynote (Text)
echo -e "\n[5/10] Testing Keynote Creation (Text)..."
python -c "
from src.utils import load_config
from src.agent.agent import AutomationAgent
agent = AutomationAgent(load_config())
result = agent.run('Create a Keynote presentation about Python programming with 2 slides')
print('✅ PASS' if result.get('status') == 'success' else '❌ FAIL')
" 2>/dev/null | tail -1

echo -e "\n=========================================="
echo "QUICK TESTS COMPLETE"
echo "=========================================="
