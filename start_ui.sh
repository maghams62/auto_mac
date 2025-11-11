#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Mac Automation Assistant UI Launcher${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating one...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    echo -e "${GREEN}Installing Python dependencies...${NC}"
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Check if Node modules are installed
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Node modules not found. Installing...${NC}"
    cd frontend
    npm install
    cd ..
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend API server
echo -e "${GREEN}Starting backend API server on port 8000...${NC}"
python api_server.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend Next.js server
echo -e "${GREEN}Starting frontend UI on port 3000...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Backend API running at: http://localhost:8000${NC}"
echo -e "${GREEN}✓ Frontend UI running at: http://localhost:3000${NC}"
echo -e "${GREEN}✓ API Documentation at: http://localhost:8000/docs${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}"
echo ""

# Wait for processes
wait
