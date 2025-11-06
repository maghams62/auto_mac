#!/bin/bash

# Mac Automation Assistant Startup Script

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Mac Automation Assistant${NC}"
echo "========================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import openai" 2>/dev/null; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
fi

# Check for OpenAI API key
if [ -z "$OPENAI_API_KEY" ]; then
    if [ -f ".env" ]; then
        echo "Loading environment from .env..."
        export $(cat .env | grep -v '^#' | xargs)
    else
        echo -e "${RED}Error: OPENAI_API_KEY not set${NC}"
        echo "Please create .env file with your API key:"
        echo "  cp .env.example .env"
        echo "  # Edit .env and add your key"
        exit 1
    fi
fi

# Create data directories if needed
mkdir -p data/embeddings

# Run the application
echo -e "${GREEN}Starting application...${NC}"
echo ""
python main.py

# Deactivate on exit
deactivate
