#!/bin/bash

# Script to safely restart the API server

echo "=========================================="
echo "API Server Restart Script"
echo "=========================================="
echo ""

# Find the running server
PID=$(ps aux | grep "api_server.py" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "❌ No running api_server.py process found"
    echo ""
    echo "Starting the server..."
    python api_server.py &
    echo "✅ Server started"
else
    echo "Found running server with PID: $PID"
    echo ""
    echo "Stopping the server..."
    kill $PID

    # Wait for it to stop
    sleep 2

    # Check if it's really stopped
    if ps -p $PID > /dev/null 2>&1; then
        echo "⚠️  Server didn't stop gracefully, forcing..."
        kill -9 $PID
        sleep 1
    fi

    echo "✅ Server stopped"
    echo ""
    echo "Starting the server with updated code..."
    python api_server.py &

    NEW_PID=$!
    echo "✅ Server restarted with PID: $NEW_PID"
fi

echo ""
echo "=========================================="
echo "Server restart complete!"
echo "=========================================="
echo ""
echo "You can now test your workflow:"
echo '  "send the doc with the song Photograph to my email"'
echo ""
