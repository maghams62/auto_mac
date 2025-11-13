# Spotify Integration Test Plan

## Overview
This document provides a comprehensive test plan with clear success criteria for the Spotify authentication and playback integration.

---

## Prerequisites

### Environment Variables Check
```bash
# Run these commands to verify your environment is set up:
echo "SPOTIFY_CLIENT_ID: $(if [ -n "$SPOTIFY_CLIENT_ID" ]; then echo "✓ Set"; else echo "✗ Missing"; fi)"
echo "SPOTIFY_CLIENT_SECRET: $(if [ -n "$SPOTIFY_CLIENT_SECRET" ]; then echo "✓ Set"; else echo "✗ Missing"; fi)"
echo "SPOTIFY_REDIRECT_URI: $(if [ -n "$SPOTIFY_REDIRECT_URI" ]; then echo "✓ Set"; else echo "✗ Missing"; fi)"
```

**Expected Result:** All three should show "✓ Set"

### Services Running
```bash
# Check backend is running:
curl -s http://localhost:8000/health || echo "Backend NOT running"

# Check frontend is running:
curl -s http://localhost:3000 > /dev/null && echo "Frontend running" || echo "Frontend NOT running"
```

**Expected Result:** Both should be running

---

## Test Phase 1: Authentication Flow

### Step 1.1: Check Initial State
```bash
# Test: Check authentication status before login
curl -s http://localhost:8000/api/spotify/auth-status | jq .
```

**Success Criteria:**
```json
{
  "authenticated": false,
  "has_credentials": true,
  "token_file_exists": false,
  "has_token_object": false
}
```

**✓ PASS:** `has_credentials: true` and `authenticated: false`  
**✗ FAIL:** If `has_credentials: false` → Check environment variables

---

### Step 1.2: Initiate OAuth Login
```bash
# Test: Get the login URL
curl -s http://localhost:8000/api/spotify/login | jq .
```

**Success Criteria:**
```json
{
  "authorization_url": "https://accounts.spotify.com/authorize?..."
}
```

**✓ PASS:** Returns a Spotify authorization URL  
**✗ FAIL:** Returns error → Check logs for credential issues

---

### Step 1.3: Complete OAuth in Browser

**Manual Steps:**
1. Open browser to http://localhost:3000
2. Look for Spotify Player in **bottom-right corner**
3. Click **"Connect Spotify"** button
4. You should be redirected to Spotify login
5. Log in with **Spotify Premium** account
6. Click **"Agree"** to authorize
7. You should be redirected back to http://localhost:3000/redirect
8. Should see: "✓ Authentication successful!"
9. After 2 seconds, redirected to home page

**Success Criteria:**
- ✓ Redirected to Spotify login page
- ✓ Successfully logged in
- ✓ Saw success message
- ✓ Redirected back to home page
- ✓ No error messages

**Check Backend Logs:**
Look for these log messages in the terminal running `api_server.py`:
```
Processing Spotify OAuth callback
Exchanging authorization code for tokens
Spotify authentication successful! Token saved to: data/spotify_tokens.json
Token verified - client is authenticated
```

---

### Step 1.4: Verify Authentication Success
```bash
# Test: Check authentication status after login
curl -s http://localhost:8000/api/spotify/auth-status | jq .
```

**Success Criteria:**
```json
{
  "authenticated": true,
  "has_credentials": true,
  "token_file_exists": true,
  "has_token_object": true
}
```

**✓ PASS:** All values are `true`  
**✗ FAIL:** If `authenticated: false` → Check logs and token file

---

### Step 1.5: Verify Token File Created
```bash
# Test: Check token file exists and has valid structure
ls -lh data/spotify_tokens.json
cat data/spotify_tokens.json | jq .
```

**Success Criteria:**
- ✓ File exists at `data/spotify_tokens.json`
- ✓ File contains JSON with keys: `access_token`, `refresh_token`, `expires_at`
- ✓ `access_token` is a long string (not empty)

---

### Step 1.6: Verify Token Can Be Retrieved
```bash
# Test: Get access token for SDK
curl -s http://localhost:8000/api/spotify/token | jq .
```

**Success Criteria:**
```json
{
  "access_token": "BQD..."
}
```

**✓ PASS:** Returns access_token (long string starting with "BQ" or similar)  
**✗ FAIL:** Returns 401 error → Re-authenticate

---

## Test Phase 2: Web Player Initialization

### Step 2.1: Check Frontend Player Component

**Manual Steps:**
1. Open browser to http://localhost:3000
2. Open Developer Console (F12 or Cmd+Option+I)
3. Look at the **Console** tab

**Success Criteria - Console Logs:**
```
Spotify auth status: {authenticated: true, has_credentials: true, ...}
Spotify Player Ready with Device ID: abc123xyz...
```

**Visual Check - Bottom-Right Corner:**
- ✓ See Spotify player widget (not "Connect Spotify" button)
- ✓ Player shows controls (play/pause buttons)
- ✓ Player is not showing error messages

---

### Step 2.2: Verify Device Registration
```bash
# Test: Check if web player device is registered
curl -s http://localhost:8000/api/spotify/device-id | jq .
```

**Success Criteria:**
```json
{
  "device_id": "abc123xyz..."
}
```

**✓ PASS:** Returns a device_id  
**✗ FAIL:** Returns null → Web player didn't initialize

---

## Test Phase 3: Playback Flow

### Step 3.1: Test Playback Service Availability
```bash
# Test: Check if playback service recognizes API backend
# (This is internal - check the logs when you try to play)
```

**Manual Test:**
1. In the chat interface, type: `status`
2. Check response mentions Spotify

**Success Criteria:**
- ✓ No error about "playback backend not available"

---

### Step 3.2: Request Song Playback

**Manual Steps:**
1. In chat interface at http://localhost:3000
2. Type: `play Breaking the Habit by Linkin Park`
3. Press Enter

**Success Criteria - Backend Logs:**
Look for these in `api_server.py` terminal:
```
[SPOTIFY PLAYBACK SERVICE] Synced web player device ID: abc123...
Selected API backend for play_track
[SPOTIFY API BACKEND] Resolving track query: 'Breaking the Habit'
Started track playback
```

**Success Criteria - Frontend:**
- ✓ No error message about "please connect Spotify"
- ✓ No error about "no playback backend"
- ✓ Agent responds with success message
- ✓ Music starts playing in browser (hear it!)

**Success Criteria - Spotify Player Widget:**
- ✓ Album art appears
- ✓ Track name shows "Breaking the Habit"
- ✓ Artist shows "Linkin Park"
- ✓ Progress bar moving
- ✓ Play button shows pause icon (music is playing)

---

### Step 3.3: Verify Playback Control

**Manual Steps:**
1. Click **pause** button in Spotify widget
2. Music should pause
3. Click **play** button
4. Music should resume

**Success Criteria:**
- ✓ Pause button works
- ✓ Play button works
- ✓ Progress bar reflects current position

---

### Step 3.4: Test Different Song

**Manual Steps:**
1. Type in chat: `play Bohemian Rhapsody by Queen`
2. Press Enter

**Success Criteria:**
- ✓ Previous song stops
- ✓ New song starts playing
- ✓ Widget updates to show new track
- ✓ Album art changes

---

## Test Phase 4: Error Handling

### Step 4.1: Test Invalid Song Request
```
# In chat:
play a song that definitely doesn't exist xyzabc123
```

**Success Criteria:**
- ✓ Agent responds with "Could not find track" or similar
- ✓ No crash or 500 error
- ✓ Previous song continues playing (or stays paused)

---

### Step 4.2: Test Without Authentication (Simulated)

**Manual Steps:**
1. Delete token file: `rm data/spotify_tokens.json`
2. Refresh browser
3. Try to play a song

**Success Criteria:**
- ✓ Shows "Connect to Spotify" button again
- ✓ Agent responds with clear error about authentication needed
- ✓ No crash

**Cleanup:**
- Re-authenticate after this test!

---

## Success Summary Checklist

Use this as your final verification:

### Authentication ✓
- [ ] Environment variables set
- [ ] Can access login URL
- [ ] OAuth flow completes successfully
- [ ] Token file created
- [ ] Auth status returns `authenticated: true`
- [ ] Can retrieve access token

### Web Player ✓
- [ ] Player widget visible in bottom-right
- [ ] No "Connect Spotify" button after auth
- [ ] Device ID registered
- [ ] Console shows "Player Ready"

### Playback ✓
- [ ] Can request song via chat
- [ ] Music plays in browser (audible)
- [ ] Album art displays
- [ ] Track info displays
- [ ] Progress bar moves
- [ ] Play/pause controls work
- [ ] Can play different songs

### Error Handling ✓
- [ ] Invalid song shows appropriate error
- [ ] Unauthenticated state is handled

---

## Troubleshooting Guide

### Issue: `authenticated: false` after OAuth
**Possible Causes:**
1. Token not saved to file
2. Token file path incorrect
3. Token expired immediately

**Debug:**
```bash
# Check if file was created
ls -la data/spotify_tokens.json

# Check API server logs for:
# "Spotify authentication successful! Token saved to: ..."

# Try manual token test
curl -s http://localhost:8000/api/spotify/token
```

---

### Issue: Web Player not initializing
**Possible Causes:**
1. Not using Spotify Premium account
2. SDK script failed to load
3. Token can't be retrieved

**Debug:**
```bash
# Open browser console and look for errors
# Check Network tab for failed requests to sdk.scdn.co

# Verify Premium account in Spotify Developer Dashboard
```

---

### Issue: "No playback backend available"
**Possible Causes:**
1. Web player device not registered
2. API backend not detecting authentication
3. Playback service not syncing device ID

**Debug:**
```bash
# Check device registration
curl -s http://localhost:8000/api/spotify/device-id

# Check playback service logs for:
# "[PLAYBACK SERVICE] Synced web player device ID"
```

---

## Quick Health Check Script

Save this as `check_spotify_health.sh`:

```bash
#!/bin/bash

echo "=== Spotify Integration Health Check ==="
echo ""

echo "1. Environment Variables:"
[ -n "$SPOTIFY_CLIENT_ID" ] && echo "  ✓ CLIENT_ID set" || echo "  ✗ CLIENT_ID missing"
[ -n "$SPOTIFY_CLIENT_SECRET" ] && echo "  ✓ CLIENT_SECRET set" || echo "  ✗ CLIENT_SECRET missing"
[ -n "$SPOTIFY_REDIRECT_URI" ] && echo "  ✓ REDIRECT_URI set" || echo "  ✗ REDIRECT_URI missing"
echo ""

echo "2. Services:"
curl -s http://localhost:8000/health > /dev/null && echo "  ✓ Backend running" || echo "  ✗ Backend down"
curl -s http://localhost:3000 > /dev/null && echo "  ✓ Frontend running" || echo "  ✗ Frontend down"
echo ""

echo "3. Authentication:"
AUTH_STATUS=$(curl -s http://localhost:8000/api/spotify/auth-status | jq -r '.authenticated')
if [ "$AUTH_STATUS" = "true" ]; then
    echo "  ✓ Authenticated"
else
    echo "  ✗ Not authenticated"
fi
echo ""

echo "4. Token File:"
if [ -f "data/spotify_tokens.json" ]; then
    echo "  ✓ Token file exists"
    SIZE=$(wc -c < data/spotify_tokens.json)
    echo "    Size: $SIZE bytes"
else
    echo "  ✗ Token file missing"
fi
echo ""

echo "5. Web Player Device:"
DEVICE_ID=$(curl -s http://localhost:8000/api/spotify/device-id | jq -r '.device_id')
if [ "$DEVICE_ID" != "null" ] && [ -n "$DEVICE_ID" ]; then
    echo "  ✓ Device registered: ${DEVICE_ID:0:20}..."
else
    echo "  ✗ Device not registered"
fi
echo ""

echo "=== End Health Check ==="
```

Run with: `bash check_spotify_health.sh`

---

## Expected Log Output (Full Success)

When everything works, you should see this sequence:

**Backend Terminal:**
```
INFO: Processing Spotify OAuth callback
INFO: Exchanging authorization code for tokens
INFO: Successfully exchanged authorization code for token
INFO: Spotify authentication successful! Token saved to: data/spotify_tokens.json
INFO: Token verified - client is authenticated
INFO: Spotify auth status: authenticated=True, has_token=True, token_file_exists=True
INFO: [PLAYBACK SERVICE] Synced web player device ID: abc123...
INFO: Selected API backend for play_track
INFO: [SPOTIFY API BACKEND] Resolving track query: 'Breaking the Habit'
INFO: Started track playback
```

**Browser Console:**
```
Spotify auth status: {authenticated: true, has_credentials: true, ...}
Spotify Player Ready with Device ID: abc123...
```

**Chat Interface:**
```
User: play Breaking the Habit by Linkin Park
Assistant: ✅ All set! Mission accomplished!
[Music plays in web player]
```

