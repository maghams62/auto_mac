# Spotify Authentication & Playback Fixes

## Issues Fixed

### 1. **Token Endpoint Bug** ✅
- **Problem**: The `/api/spotify/token` endpoint was calling `client._load_token()` which returns `None`, causing token retrieval to fail
- **Fix**: Changed to access `client.token.access_token` directly after verifying authentication
- **File**: `api_server.py` lines 1765-1783

### 2. **Frontend Authentication Polling** ✅
- **Problem**: Frontend only checked authentication status every 5 minutes, causing delays in detecting successful authentication
- **Fix**: Added multiple improvements:
  - Immediate check on component mount
  - Quick polling every 2 seconds for the first 30 seconds (catches newly authenticated users)
  - Re-check when window regains focus
  - Continue slow polling (5 minutes) afterwards
- **File**: `frontend/components/SpotifyPlayer.tsx` lines 73-112

### 3. **Enhanced Logging & Debugging** ✅
- **Problem**: Difficult to diagnose authentication issues
- **Fix**: Added comprehensive logging:
  - OAuth callback now logs token storage path and verification status
  - Auth status endpoint logs token file existence and client state
  - Better error messages with stack traces
- **Files**: `api_server.py` lines 1627-1672, 1725-1761

## Required Actions

### Step 1: Restart the API Server
The API server needs to be restarted to load the updated code.

```bash
# Find and kill the current API server process
pkill -f "api_server.py"

# Start the API server again
cd /Users/siddharthsuresh/Downloads/auto_mac
python api_server.py
```

### Step 2: Re-authenticate with Spotify
Since the token file doesn't exist yet, you need to complete the OAuth flow:

1. Open the frontend: http://localhost:3000
2. Look for the Spotify Player in the bottom-right corner
3. Click "Connect Spotify"
4. Log in with your Spotify Premium account
5. Authorize the application
6. You'll be redirected back to the app

### Step 3: Verify Authentication
After completing the OAuth flow, verify that authentication worked:

```bash
# Check authentication status
curl -s http://localhost:8000/api/spotify/auth-status | jq .

# Should return:
# {
#   "authenticated": true,
#   "has_credentials": true,
#   "token_file_exists": true,
#   "has_token_object": true
# }

# Verify token file was created
ls -la /Users/siddharthsuresh/Downloads/auto_mac/data/spotify_tokens.json
```

### Step 4: Test Playback
Once authenticated, try playing a song:

1. In the chat interface, type: "Play Breaking the Habit by Linkin Park"
2. The song should start playing in the web player (visible in your browser)
3. You should see the album art and track info in the embedded Spotify player

## How It Works Now

```
┌─────────────────────────────────────────────────────────────┐
│                    Authentication Flow                       │
└─────────────────────────────────────────────────────────────┘

1. User clicks "Connect Spotify" button
   ↓
2. Frontend redirects to /api/spotify/login
   ↓
3. Backend generates Spotify OAuth URL
   ↓
4. User logs in and authorizes on Spotify
   ↓
5. Spotify redirects to /redirect with auth code
   ↓
6. Frontend sends code to /api/auth/callback
   ↓
7. Backend exchanges code for access + refresh tokens
   ↓
8. Backend saves tokens to data/spotify_tokens.json
   ↓
9. Frontend redirects back to home page
   ↓
10. Frontend polls /api/spotify/auth-status (every 2 sec for 30 sec)
   ↓
11. Backend confirms authentication
   ↓
12. Frontend loads Spotify Web Playback SDK
   ↓
13. SDK connects and creates web player device
   ↓
14. Device ID registered with backend
   ↓
15. ✅ Ready to play music via Web API!
```

```
┌─────────────────────────────────────────────────────────────┐
│                      Playback Flow                          │
└─────────────────────────────────────────────────────────────┘

User Request: "Play song X"
   ↓
Agent → SpotifyPlaybackService
   ↓
Service checks: Is API backend available?
   ├─ YES (authenticated) → Use Spotify Web API
   │                        ↓
   │                     Send play command to web player device
   │                        ↓
   │                     ✅ Music plays in browser!
   │
   └─ NO (not authenticated) → Error: "No playback backend available.
                                Web API requires authentication.
                                Please connect Spotify first."
```

## Configuration

The system uses these settings from `config.yaml`:

```yaml
playback:
  use_api: true                        # Prefer API over automation
  disable_automation_fallback: true    # Don't fall back to AppleScript
  
spotify_api:
  client_id: "${SPOTIFY_CLIENT_ID}"
  client_secret: "${SPOTIFY_CLIENT_SECRET}"
  redirect_uri: "http://127.0.0.1:3000/redirect"
  # token_storage_path defaults to "data/spotify_tokens.json"
```

## Troubleshooting

### Authentication Still Not Working?

1. **Check the logs** (in terminal running `api_server.py`):
   - Look for "Processing Spotify OAuth callback"
   - Look for "Spotify authentication successful"
   - Look for any error messages

2. **Check browser console** (F12 in browser):
   - Look for "Spotify auth status" logs
   - Check for any fetch errors

3. **Verify environment variables**:
   ```bash
   echo $SPOTIFY_CLIENT_ID
   echo $SPOTIFY_CLIENT_SECRET
   echo $SPOTIFY_REDIRECT_URI
   ```

4. **Verify Spotify Developer Dashboard**:
   - Go to https://developer.spotify.com/dashboard
   - Check that your app has the redirect URI: `http://127.0.0.1:3000/redirect`
   - Make sure you're using a Spotify Premium account

### Still Showing "Connect to Spotify"?

The frontend polls every 2 seconds for 30 seconds after mounting. If you just authenticated:
- Wait 2-30 seconds for the next poll
- Or refresh the page to trigger an immediate check
- Or switch to another tab and back (triggers focus event)

### Playback Not Working?

1. Make sure you're using Spotify Premium (Web Playback SDK requires Premium)
2. Check that the web player device appears in Spotify's available devices
3. Try clicking the play button in the embedded player
4. Check for errors in the browser console

## Files Modified

1. **api_server.py**:
   - Fixed `/api/spotify/token` endpoint (lines 1764-1783)
   - Enhanced `/api/spotify/auth-status` endpoint with debugging info (lines 1725-1761)
   - Improved OAuth callback logging (lines 1627-1672)

2. **frontend/components/SpotifyPlayer.tsx**:
   - Enhanced authentication polling strategy (lines 73-112)
   - Added focus event listener for re-checking auth
   - Added console logging for debugging

## Testing

After completing the steps above, the system should:
1. ✅ Properly detect authentication
2. ✅ Load the Spotify Web Playback SDK
3. ✅ Initialize the web player
4. ✅ Play music through the Web API
5. ✅ Show track info in the embedded player

The error "No playback backend available" should no longer appear after authentication.

