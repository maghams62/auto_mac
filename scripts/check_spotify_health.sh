#!/bin/bash

echo "=== Spotify Integration Health Check ==="
echo ""

echo "1. Environment Variables:"
[ -n "$SPOTIFY_CLIENT_ID" ] && echo "  ✓ CLIENT_ID set" || echo "  ✗ CLIENT_ID missing"
[ -n "$SPOTIFY_CLIENT_SECRET" ] && echo "  ✓ CLIENT_SECRET set" || echo "  ✗ CLIENT_SECRET missing"
[ -n "$SPOTIFY_REDIRECT_URI" ] && echo "  ✓ REDIRECT_URI set" || echo "  ✗ REDIRECT_URI missing"
echo ""

echo "2. Services:"
curl -s http://localhost:8000/health > /dev/null 2>&1 && echo "  ✓ Backend running (port 8000)" || echo "  ✗ Backend down"
curl -s http://localhost:3000 > /dev/null 2>&1 && echo "  ✓ Frontend running (port 3000)" || echo "  ✗ Frontend down"
echo ""

echo "3. Authentication Status:"
AUTH_JSON=$(curl -s http://localhost:8000/api/spotify/auth-status 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "  $AUTH_JSON" | jq .
else
    echo "  ✗ Cannot reach auth endpoint"
fi
echo ""

echo "4. Token File:"
if [ -f "data/spotify_tokens.json" ]; then
    echo "  ✓ Token file exists"
    SIZE=$(wc -c < data/spotify_tokens.json)
    echo "    Size: $SIZE bytes"
    echo "    Contents preview:"
    cat data/spotify_tokens.json | jq 'with_entries(if .key == "access_token" or .key == "refresh_token" then .value = (.value[:20] + "...") else . end)'
else
    echo "  ✗ Token file missing"
    echo "    Expected location: data/spotify_tokens.json"
fi
echo ""

echo "5. Web Player Device:"
DEVICE_JSON=$(curl -s http://localhost:8000/api/spotify/device-id 2>/dev/null)
DEVICE_ID=$(echo "$DEVICE_JSON" | jq -r '.device_id' 2>/dev/null)
if [ "$DEVICE_ID" != "null" ] && [ -n "$DEVICE_ID" ]; then
    echo "  ✓ Device registered: ${DEVICE_ID:0:40}..."
else
    echo "  ✗ Device not registered"
    echo "    (This is normal if you haven't authenticated yet)"
fi
echo ""

echo "6. Token Retrieval Test:"
TOKEN_RESULT=$(curl -s http://localhost:8000/api/spotify/token 2>/dev/null)
TOKEN_STATUS=$?
if [ $TOKEN_STATUS -eq 0 ]; then
    if echo "$TOKEN_RESULT" | jq -e '.access_token' > /dev/null 2>&1; then
        TOKEN_PREVIEW=$(echo "$TOKEN_RESULT" | jq -r '.access_token' | cut -c1-20)
        echo "  ✓ Can retrieve access token: ${TOKEN_PREVIEW}..."
    else
        echo "  ✗ Token endpoint returned error:"
        echo "    $TOKEN_RESULT" | jq .
    fi
else
    echo "  ✗ Cannot reach token endpoint"
fi
echo ""

echo "=== Summary ==="
if echo "$AUTH_JSON" | jq -e '.authenticated == true' > /dev/null 2>&1; then
    echo "✅ READY TO PLAY MUSIC!"
    echo ""
    echo "Try in chat: 'play Breaking the Habit by Linkin Park'"
else
    echo "⚠️  AUTHENTICATION REQUIRED"
    echo ""
    echo "Next steps:"
    echo "  1. Open http://localhost:3000"
    echo "  2. Look for Spotify player in bottom-right"
    echo "  3. Click 'Connect Spotify'"
    echo "  4. Run this script again after authenticating"
fi
echo ""
echo "=== End Health Check ==="

