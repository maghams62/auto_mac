#!/bin/bash

echo "=== Spotify Controls Test ==="
echo ""

echo "Prerequisites:"
echo "  1. Spotify widget should be visible at http://localhost:3000"
echo "  2. A song should be playing"
echo "  3. Watch the widget as the tests run!"
echo ""
read -p "Press Enter to continue..."
echo ""

echo "1. Testing Pause..."
PAUSE_RESULT=$(curl -s -X POST http://localhost:8000/api/spotify/pause)
echo "   API Response: $PAUSE_RESULT"
echo "   ✓ Check: Did music stop? Did UI show pause state?"
sleep 3

echo ""
echo "2. Testing Resume..."
PLAY_RESULT=$(curl -s -X POST http://localhost:8000/api/spotify/play)
echo "   API Response: $PLAY_RESULT"
echo "   ✓ Check: Did music resume? Did UI show play state?"
sleep 3

echo ""
echo "3. Testing Next Track..."
NEXT_RESULT=$(curl -s -X POST http://localhost:8000/api/spotify/next)
echo "   API Response: $NEXT_RESULT"
echo "   ✓ Check: Did track change? Did UI update with new track?"
sleep 3

echo ""
echo "4. Testing Previous Track..."
PREV_RESULT=$(curl -s -X POST http://localhost:8000/api/spotify/previous)
echo "   API Response: $PREV_RESULT"
echo "   ✓ Check: Did track change back? Did UI update?"
sleep 2

echo ""
echo "=== API Tests Complete ==="
echo ""
echo "Now test the UI buttons:"
echo "  ⏸️  Click pause button in widget"
echo "  ▶️  Click play button"
echo "  ⏭️  Click next button"
echo "  ⏮️  Click previous button"
echo ""
echo "All controls should work seamlessly!"

