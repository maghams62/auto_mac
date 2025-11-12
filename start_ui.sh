#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Cerebro OS - Clean Start${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

###########################################
# STEP 1: Kill Existing Servers
###########################################
echo -e "${YELLOW}[1/6] Stopping any existing servers...${NC}"

# Kill API server
API_PIDS=$(ps aux | grep "api_server.py" | grep -v grep | awk '{print $2}')
if [ ! -z "$API_PIDS" ]; then
    echo "  - Found running API server(s): $API_PIDS"
    echo "$API_PIDS" | xargs kill -9 2>/dev/null
    echo -e "  ${GREEN}✓ Killed API server(s)${NC}"
else
    echo "  - No API server running"
fi

# Kill frontend server
FRONTEND_PIDS=$(ps aux | grep "next dev\|npm run dev" | grep -v grep | awk '{print $2}')
if [ ! -z "$FRONTEND_PIDS" ]; then
    echo "  - Found running frontend server(s): $FRONTEND_PIDS"
    echo "$FRONTEND_PIDS" | xargs kill -9 2>/dev/null
    echo -e "  ${GREEN}✓ Killed frontend server(s)${NC}"
else
    echo "  - No frontend server running"
fi

# Kill any Node processes on port 3000
NODE_PIDS=$(lsof -ti:3000 2>/dev/null)
if [ ! -z "$NODE_PIDS" ]; then
    echo "  - Found processes on port 3000: $NODE_PIDS"
    echo "$NODE_PIDS" | xargs kill -9 2>/dev/null
    echo -e "  ${GREEN}✓ Cleared port 3000${NC}"
fi

# Kill any Python processes on port 8000
PYTHON_PIDS=$(lsof -ti:8000 2>/dev/null)
if [ ! -z "$PYTHON_PIDS" ]; then
    echo "  - Found processes on port 8000: $PYTHON_PIDS"
    echo "$PYTHON_PIDS" | xargs kill -9 2>/dev/null
    echo -e "  ${GREEN}✓ Cleared port 8000${NC}"
fi

echo -e "${GREEN}✓ All existing servers stopped${NC}"
echo ""

###########################################
# STEP 2: Clear Python Cache
###########################################
echo -e "${YELLOW}[2/6] Clearing Python cache...${NC}"

# Remove __pycache__ directories
PYCACHE_COUNT=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PYCACHE_COUNT" -gt 0 ]; then
    echo "  - Removing $PYCACHE_COUNT __pycache__ directories..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    echo -e "  ${GREEN}✓ Removed __pycache__ directories${NC}"
else
    echo "  - No __pycache__ directories found"
fi

# Remove .pyc files
PYC_COUNT=$(find . -type f -name "*.pyc" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PYC_COUNT" -gt 0 ]; then
    echo "  - Removing $PYC_COUNT .pyc files..."
    find . -type f -name "*.pyc" -delete 2>/dev/null
    echo -e "  ${GREEN}✓ Removed .pyc files${NC}"
else
    echo "  - No .pyc files found"
fi

# Remove .pyo files
PYO_COUNT=$(find . -type f -name "*.pyo" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PYO_COUNT" -gt 0 ]; then
    echo "  - Removing $PYO_COUNT .pyo files..."
    find . -type f -name "*.pyo" -delete 2>/dev/null
    echo -e "  ${GREEN}✓ Removed .pyo files${NC}"
else
    echo "  - No .pyo files found"
fi

echo -e "${GREEN}✓ Python cache cleared${NC}"
echo ""

###########################################
# STEP 3: Clear Frontend Cache
###########################################
echo -e "${YELLOW}[3/6] Clearing frontend cache...${NC}"

# Clear Next.js cache
if [ -d "frontend/.next" ]; then
    echo "  - Removing .next build cache..."
    rm -rf frontend/.next
    echo -e "  ${GREEN}✓ Removed .next cache${NC}"
else
    echo "  - No .next cache found"
fi

# Clear node_modules/.cache if it exists
if [ -d "frontend/node_modules/.cache" ]; then
    echo "  - Removing node_modules/.cache..."
    rm -rf frontend/node_modules/.cache
    echo -e "  ${GREEN}✓ Removed node_modules cache${NC}"
fi

echo -e "${GREEN}✓ Frontend cache cleared${NC}"
echo ""

###########################################
# STEP 4: Verify Environment Setup
###########################################
echo -e "${YELLOW}[4/6] Verifying environment setup...${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "  ${YELLOW}Virtual environment not found. Creating one...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    echo -e "  ${GREEN}Installing Python dependencies...${NC}"
    pip install -r requirements.txt
    echo -e "  ${GREEN}✓ Virtual environment created${NC}"
else
    source venv/bin/activate
    echo -e "  ${GREEN}✓ Virtual environment activated${NC}"
fi

# Check if Node modules are installed
if [ ! -d "frontend/node_modules" ]; then
    echo -e "  ${YELLOW}Node modules not found. Installing...${NC}"
    cd frontend
    npm install
    cd ..
    echo -e "  ${GREEN}✓ Node modules installed${NC}"
else
    echo -e "  ${GREEN}✓ Node modules found${NC}"
fi

echo -e "${GREEN}✓ Environment verified${NC}"
echo ""

###########################################
# STEP 5: Run Import Verification
###########################################
echo -e "${YELLOW}[5/6] Running import verification tests...${NC}"

# Run import checker if it exists
if [ -f "tests/import_checks/check_all_imports.py" ]; then
    echo "  - Checking for import issues..."
    IMPORT_CHECK=$(python tests/import_checks/check_all_imports.py 2>&1 | grep "No problematic imports found")
    if [ ! -z "$IMPORT_CHECK" ]; then
        echo -e "  ${GREEN}✓ No import issues found${NC}"
    else
        echo -e "  ${RED}⚠ Import issues detected, but continuing...${NC}"
    fi
else
    echo "  - Import checker not found, skipping..."
fi

echo -e "${GREEN}✓ Verification complete${NC}"
echo ""

###########################################
# STEP 6: Start Servers
###########################################
echo -e "${YELLOW}[6/6] Starting servers with fresh code...${NC}"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down servers...${NC}"
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
        echo -e "  ${GREEN}✓ Backend stopped${NC}"
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
        echo -e "  ${GREEN}✓ Frontend stopped${NC}"
    fi
    echo ""
    echo -e "${GREEN}Clean shutdown complete${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend API server
echo "  - Starting backend API server on port 8000..."
python api_server.py > api_server.log 2>&1 &
BACKEND_PID=$!

# Wait a bit and check if backend started successfully
sleep 2
if ps -p $BACKEND_PID > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC}"
else
    echo -e "  ${RED}✗ Backend failed to start. Check api_server.log${NC}"
    exit 1
fi

# Start frontend Next.js server
echo "  - Starting frontend UI on port 3000..."
cd frontend
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait a bit for frontend to initialize
sleep 2
if ps -p $FRONTEND_PID > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"
else
    echo -e "  ${RED}✗ Frontend failed to start. Check frontend.log${NC}"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ ALL SYSTEMS READY - CLEAN STATE${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}Backend API:${NC}       http://localhost:8000"
echo -e "${GREEN}Frontend UI:${NC}       http://localhost:3000"
echo -e "${GREEN}API Docs:${NC}          http://localhost:8000/docs"
echo ""
echo -e "${BLUE}Logs:${NC}"
echo -e "  Backend:  tail -f api_server.log"
echo -e "  Frontend: tail -f frontend.log"
echo ""
echo -e "${GREEN}Clean State Features:${NC}"
echo -e "  ✓ All old servers killed"
echo -e "  ✓ Python cache cleared (__pycache__, .pyc, .pyo)"
echo -e "  ✓ Frontend cache cleared (.next)"
echo -e "  ✓ Ports 3000 & 8000 freed"
echo -e "  ✓ Fresh code loaded"
echo -e "  ✓ Import issues checked"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}"
echo -e "${YELLOW}All changes you made are now active!${NC}"
echo ""

# Wait for processes
wait
