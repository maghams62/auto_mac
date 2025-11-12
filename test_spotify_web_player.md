# Spotify Web Player Setup - Testing Instructions

## ✅ Fixed Issues

1. **Environment Variable Expansion** - Fixed the config loader to handle `${VAR:-default}` syntax
2. **API Credentials** - Spotify API credentials are now properly loaded
3. **Web Player Integration** - SpotifyPlayer component is embedded in the frontend

## 🎯 What You Need to Do

### Step 1: Start the Frontend (if not running)
```bash
cd frontend
npm run dev
```

### Step 2: Open Your Browser
Navigate to: `http://localhost:3000`

### Step 3: Authenticate with Spotify
1. Look for the **Spotify Player** component in the bottom-right corner
2. Click the **"Connect Spotify"** button
3. You'll be redirected to Spotify's login page
4. **Log in with your Spotify Premium account** (Web Playback SDK requires Premium)
5. Authorize the application
6. You'll be redirected back to the app

### Step 4: Verify the Web Player is Active
Once authenticated, you should see:
- Album art placeholder (or current track if something is playing)
- Play/pause controls
- Progress bar
- The player should show "Ready" or "Connected" status

### Step 5: Test Playback
In the chat interface, type:
```
Play Breaking the Habit by Linkin Park
```

**Expected behavior:**
- The song should start playing **in the web player** (visible in your browser)
- The Mac Spotify app should **NOT** open
- You should see the album art and track info in the embedded player

## 🔧 Why It Was Opening Mac Spotify Before

The backend was defaulting to the **automation backend** (AppleScript) instead of the **API backend** because:

1. The web player device ID wasn't registered yet (requires user to authenticate first)
2. The automation backend was being selected as fallback

## 🎵 How It Works Now

```
User Request → Agent → SpotifyPlaybackService → SpotifyAPIBackend → Web Player Device
```

The flow:
1. User authenticates via web UI → Web player device is created
2. Frontend registers device ID with backend (`POST /api/spotify/register-device`)
3. When user requests playback → Backend targets the web player device
4. Music plays in browser (embedded player), NOT Mac app

## 🐛 Troubleshooting

### If the Mac app still opens:
1. Make sure you've authenticated through the web UI first
2. Check that the device is registered:
   ```bash
   curl http://localhost:8000/api/spotify/device-id
   ```
   Should return: `{"device_id": "some-long-id"}`

### If you get "No active device" errors:
1. Refresh the browser page
2. Wait 5-10 seconds for the player to initialize
3. Check browser console for any errors (F12 → Console)

### If authentication fails:
1. Make sure you're using a **Spotify Premium** account
2. Check that credentials in `.env` are correct
3. Verify redirect URI matches in Spotify Developer Dashboard: `http://127.0.0.1:3000/redirect`

## 📝 Files Modified

- `src/utils/__init__.py` - Fixed `_expand_env_vars()` to handle `${VAR:-default}` syntax
- `frontend/components/SpotifyPlayer.tsx` - Embedded Spotify Web Playback SDK
- `api_server.py` - Added Spotify authentication endpoints
- `src/integrations/spotify_playback_service.py` - Added device ID targeting
- `.env` - Spotify credentials (already configured)

## ✨ Next Steps

1. Follow steps 1-5 above to authenticate
2. Test playback with various requests
3. Enjoy music playing directly in your browser!

The embedded player gives you:
- ✅ Visual feedback (album art, progress)
- ✅ Full playback controls
- ✅ No dependency on Mac Spotify app
- ✅ Works cross-platform (any OS with a browser)
