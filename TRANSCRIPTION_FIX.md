# Transcription Error Fix

## Problem
"Failed to fetch" error when trying to transcribe audio.

## Root Cause
The API server needs to be restarted after CORS configuration changes.

## Solution

### Step 1: Restart the API Server

**Option A: If using start_ui.sh**
```bash
# Stop the script (Ctrl+C)
# Then restart:
./start_ui.sh
```

**Option B: If running servers separately**
```bash
# Stop the API server
kill $(lsof -ti:8000)

# Restart it
cd /Users/siddharthsuresh/Downloads/auto_mac
source venv/bin/activate
python3 api_server.py
```

### Step 2: Verify Server is Running
```bash
curl http://localhost:8000/api/stats
```

Should return: `{"indexed_documents":0,...}`

### Step 3: Test Transcription
1. Open http://localhost:3000
2. Click the microphone button
3. Record audio
4. Stop recording
5. Check if transcription works

## What Was Fixed

1. **CORS Configuration**: Added `http://127.0.0.1:3000` to allowed origins
2. **Better Error Messages**: Now shows specific error details
3. **Health Check**: Verifies server connectivity when fetch fails
4. **Timeout Handling**: 30 second timeout for transcription requests

## Debugging

If it still doesn't work:

1. **Check browser console** (F12) for:
   - CORS errors
   - Network errors
   - `[TRANSCRIBE]` logs

2. **Check server logs** for:
   - `[TRANSCRIBE] Request received` messages
   - Any error messages

3. **Test API directly**:
   ```bash
   curl -X POST http://localhost:8000/api/transcribe \
     -F "audio=@/path/to/audio.webm"
   ```

## Expected Behavior

After restart:
- ✅ Recording works
- ✅ Auto-stop works (after 2 seconds of silence)
- ✅ Transcription sends audio to server
- ✅ Server processes with Whisper API
- ✅ Transcribed text appears in chat

