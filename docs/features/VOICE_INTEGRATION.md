# Voice Integration - Speech-to-Text

## Overview

The Mac Automation Assistant now includes full voice capabilities with ChatGPT-style UI feedback for recording and transcription.

## Features

### ✅ Speech-to-Text (STT)
- **OpenAI Whisper API** integration for high-quality transcription
- Browser-based audio recording using Web Audio API
- Supports WebM format (Chrome/Edge) and other formats
- Automatic transcription and message sending

### ✅ ChatGPT-Style UI
- **Floating recording indicator** with waveform animation
- **Recording timer** showing duration (MM:SS format)
- **Prominent stop button** for easy access
- **Transcription status** indicator
- **Visual feedback** on microphone button

## Components

### 1. RecordingIndicator Component
**Location:** `frontend/components/RecordingIndicator.tsx`

**Features:**
- Floating indicator above input area
- Animated waveform visualization (20 bars)
- Recording timer with MM:SS format
- Stop button with hover effects
- Transcription status with animated bars
- Smooth fade in/out animations

**States:**
- **Recording**: Shows waveform, timer, and stop button
- **Transcribing**: Shows animated bars and "Transcribing..." text

### 2. Voice Recorder Hook
**Location:** `frontend/lib/useVoiceRecorder.ts`

**Capabilities:**
- Browser MediaRecorder API wrapper
- Audio blob management
- Error handling
- Stream cleanup

### 3. API Endpoint
**Location:** `api_server.py` - `/api/transcribe`

**Functionality:**
- Accepts WebM audio files
- Uses OpenAI Whisper API
- Returns transcribed text
- Handles temporary file cleanup

## Usage

### User Flow

1. **Start Recording:**
   - Click microphone button in input area
   - Floating indicator appears with waveform animation
   - Timer starts counting

2. **During Recording:**
   - Waveform bars animate to show audio levels
   - Timer displays recording duration
   - Microphone button shows pulsing red border
   - Stop button available in floating indicator

3. **Stop Recording:**
   - Click "Stop Recording" button in floating indicator
   - OR click microphone button again
   - Recording stops, transcription begins

4. **Transcription:**
   - Indicator shows "Transcribing..." with animated bars
   - Backend processes audio with Whisper API
   - Transcribed text automatically sent as message

## Technical Details

### Audio Format
- **Recording**: WebM with Opus codec (via MediaRecorder)
- **Transcription**: OpenAI Whisper accepts multiple formats
- **Browser Support**: Chrome, Edge (WebM), Safari (different format)

### API Integration
```python
# Backend transcription endpoint
@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    # Uses OpenAI Whisper API
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language="en"
    )
```

### Frontend Integration
```typescript
// Voice recording hook
const { isRecording, startRecording, stopRecording } = useVoiceRecorder();

// Transcription flow
const audioBlob = await stopRecording();
const formData = new FormData();
formData.append("audio", audioBlob, "recording.webm");
const response = await fetch("/api/transcribe", {
  method: "POST",
  body: formData,
});
```

## UI Features

### Recording Indicator
- **Position**: Fixed, centered above input area
- **Animation**: Smooth fade in/out
- **Waveform**: 20 animated bars with varying heights
- **Timer**: Real-time MM:SS format
- **Stop Button**: Red button with hover effects

### Microphone Button
- **Idle State**: Gray microphone icon
- **Recording State**: Red microphone icon with pulsing border
- **Disabled**: When recording (use stop button instead)

### Visual Feedback
- **Recording**: Red color scheme, pulsing animations
- **Transcribing**: Cyan color scheme, animated bars
- **Error**: Error messages displayed in chat

## Configuration

### OpenAI API Key
Required in `config.yaml` or `.env`:
```yaml
openai:
  api_key: "${OPENAI_API_KEY}"
```

### Voice Configuration (Optional)
```yaml
voice:
  default_voice: "alloy"
  default_speed: 1.0
  tts_model: "tts-1"
  stt_model: "whisper-1"
```

## Error Handling

- **Microphone Permission**: Browser prompts for permission
- **API Errors**: Displayed in chat interface
- **Transcription Failures**: User notified with error message
- **Network Issues**: Handled gracefully with retry suggestions

## Browser Compatibility

- ✅ **Chrome/Edge**: Full support (WebM format)
- ✅ **Safari**: May use different audio format
- ⚠️ **Firefox**: May require different MIME type

## Future Enhancements

- [ ] Real-time transcription (streaming)
- [ ] Multiple language support
- [ ] Voice commands (e.g., "stop", "cancel")
- [ ] Audio playback of responses (TTS)
- [ ] Voice activity detection (auto-stop on silence)

## Testing

To test voice recording:
1. Start the frontend: `cd frontend && npm run dev`
2. Start the API server: `python api_server.py`
3. Click microphone button
4. Speak into microphone
5. Click stop button
6. Verify transcription appears in chat

## Troubleshooting

### Microphone Not Working
- Check browser permissions (Settings > Privacy > Microphone)
- Verify microphone is connected and working
- Check browser console for errors

### Transcription Failing
- Verify OpenAI API key is configured
- Check API server logs for errors
- Ensure audio file is being sent correctly

### UI Not Showing
- Check browser console for React errors
- Verify RecordingIndicator component is imported
- Check that framer-motion is installed

