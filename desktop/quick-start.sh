#!/bin/bash

# Cerebros Desktop Launcher - Quick Start Script
# This script helps you get started with the Electron launcher

set -e  # Exit on error

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Cerebros Desktop Launcher${NC}"
echo -e "${BLUE}Quick Start${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Check Node.js
echo -e "${YELLOW}[1/4] Checking Node.js...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js not found${NC}"
    echo ""
    echo "Please install Node.js first:"
    echo "  brew install node"
    echo "  or download from https://nodejs.org/"
    echo ""
    exit 1
fi

NODE_VERSION=$(node --version)
echo -e "${GREEN}✓ Node.js installed: $NODE_VERSION${NC}"

# Check npm
if ! command -v npm &> /dev/null; then
    echo -e "${RED}✗ npm not found${NC}"
    exit 1
fi

NPM_VERSION=$(npm --version)
echo -e "${GREEN}✓ npm installed: $NPM_VERSION${NC}"
echo ""

# Install dependencies
echo -e "${YELLOW}[2/4] Installing dependencies...${NC}"
if [ ! -d "node_modules" ]; then
    npm install
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}✓ Dependencies already installed${NC}"
fi
echo ""

# Check backend
echo -e "${YELLOW}[3/4] Checking Python backend...${NC}"
if [ ! -d "../venv" ]; then
    echo -e "${RED}✗ Python venv not found${NC}"
    echo ""
    echo "Please create Python virtual environment first:"
    echo "  cd .."
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓ Python venv exists${NC}"
echo ""

# Check frontend
echo -e "${YELLOW}[4/4] Checking Next.js frontend...${NC}"
if [ ! -d "../frontend/node_modules" ]; then
    echo -e "${RED}✗ Frontend dependencies not found${NC}"
    echo ""
    echo "Please install frontend dependencies first:"
    echo "  cd ../frontend"
    echo "  npm install"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
echo ""

# Ready to start
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}✓ All checks passed!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "${BLUE}Starting Cerebros Launcher...${NC}"
echo ""
echo "The launcher will:"
echo "  1. Start Python backend (port 8000)"
echo "  2. Start Next.js frontend (port 3000)"
echo "  3. Open the launcher window"
echo ""
echo -e "${YELLOW}Press Cmd+Option+Space (⌥⌘Space) to show/hide launcher${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Compile TypeScript and start Electron
npm run dev
