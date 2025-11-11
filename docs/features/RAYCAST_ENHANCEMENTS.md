# Raycast-like Enhancements for Mac Automation Assistant

## Overview
This document outlines the enhancements made to transform the Mac Automation Assistant into a Raycast-like experience with voice capabilities.

## Features Implemented

### 1. Keyboard Shortcuts (Raycast-style)
- **⌘K (Cmd+K)**: Focus the input field
- **⌘L (Cmd+L)**: Clear the input field
- **Enter**: Send message (Shift+Enter for new line)
- Shortcuts are displayed in the header for discoverability

### 2. Command History Sidebar
- **Collapsible sidebar** on the left side of the interface
- **History tab**: Shows last 10 user commands for quick re-execution
- **Quick Actions tab**: Pre-configured quick actions for common tasks:
  - Search Documents
  - Create Presentation
  - Stock Analysis
  - Plan Trip
  - Organize Files
  - Send Email
- Clicking a command populates the input field (allows editing before sending)
- Sidebar can be collapsed/expanded with toggle button
- Responsive: Hidden on mobile, visible on desktop

### 3. Voice Recording & Speech-to-Text
- **Microphone button** in the input area
- **Visual feedback**: Button turns red and pulses when recording
- **Browser-based recording**: Uses Web Audio API (MediaRecorder)
- **Backend integration**: Sends audio to `/api/transcribe` endpoint
- **OpenAI Whisper**: Uses OpenAI's Whisper API for transcription
- **Seamless flow**: Transcribed text is automatically sent as a message
- **Status indicators**: Shows "Recording..." and "Transcribing..." states

### 4. Enhanced Status Indicators
- **Connection status**: Real-time online/offline indicator in header
- **System stats**: Shows number of available agents
- **Keyboard shortcuts**: Displayed in header for quick reference
- **Voice status**: Visual feedback during recording/transcription

### 5. UI Improvements
- **Modern glassmorphism design**: Consistent with Raycast aesthetic
- **Smooth animations**: Framer Motion for transitions
- **Responsive layout**: Adapts to different screen sizes
- **Better visual hierarchy**: Clear separation between sidebar and main content

## Technical Implementation

### Frontend Components

#### `InputArea.tsx`
- Enhanced with keyboard shortcuts
- Voice recording button integration
- External value control for sidebar integration
- Auto-resizing textarea

#### `ChatInterface.tsx`
- Voice recording state management
- Integration with transcription API
- Sidebar integration
- Input value synchronization

#### `Sidebar.tsx` (New)
- Command history display
- Quick actions panel
- Collapsible interface
- Status footer

#### `Header.tsx`
- System stats display
- Connection status
- Keyboard shortcuts display

#### `useVoiceRecorder.ts` (New Hook)
- Browser MediaRecorder API wrapper
- Audio blob management
- Error handling

### Backend API

#### `/api/transcribe` (New Endpoint)
- Accepts audio files (WebM format)
- Uses OpenAI Whisper API for transcription
- Returns transcribed text
- Handles temporary file cleanup

## API Endpoints

### POST `/api/transcribe`
Transcribes audio using OpenAI Whisper API.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `audio` file (WebM format)

**Response:**
```json
{
  "text": "Transcribed text here",
  "status": "success"
}
```

## Usage Examples

### Voice Recording
1. Click the microphone button in the input area
2. Speak your command
3. Click the microphone button again to stop
4. Wait for transcription (usually 1-2 seconds)
5. Transcribed text is automatically sent

### Command History
1. Open sidebar (if collapsed)
2. Click "History" tab
3. Click any previous command to reuse it
4. Edit if needed, then press Enter

### Quick Actions
1. Open sidebar
2. Click "Quick" tab
3. Click any quick action
4. Command template is populated in input
5. Fill in details and send

### Keyboard Shortcuts
- Press `⌘K` to quickly focus the input
- Press `⌘L` to clear the input
- Press `Enter` to send (Shift+Enter for new line)

## Configuration

### OpenAI API Key
Ensure your OpenAI API key is set in environment variables:
```bash
export OPENAI_API_KEY='your-key-here'
```

Or in `config.yaml`:
```yaml
openai:
  api_key: "${OPENAI_API_KEY}"
```

### CORS Settings
The API server is configured to accept requests from:
- `http://localhost:3000`
- `http://localhost:3001`

Update `api_server.py` if using different ports.

## Future Enhancements

### Potential Additions
1. **Command Autocomplete**: Suggest commands as user types
2. **Command Aliases**: Create shortcuts for common commands
3. **Voice Commands**: Pre-defined voice commands for quick actions
4. **Command Templates**: Save and reuse command templates
5. **Multi-language Support**: Transcribe in multiple languages
6. **Voice Output**: Text-to-speech for responses
7. **Command Search**: Search through command history
8. **Favorites**: Mark frequently used commands as favorites

### UI Improvements
1. **Dark/Light Theme Toggle**
2. **Customizable Quick Actions**
3. **Command Categories/Tags**
4. **Export/Import Command History**
5. **Keyboard Shortcut Customization**

## Testing

### Voice Recording
1. Grant microphone permissions when prompted
2. Click microphone button
3. Speak clearly
4. Verify transcription accuracy
5. Check that transcribed text is sent correctly

### Keyboard Shortcuts
1. Test `⌘K` to focus input
2. Test `⌘L` to clear input
3. Verify shortcuts work from anywhere in the app

### Sidebar
1. Test collapse/expand functionality
2. Verify command history updates
3. Test quick actions populate input correctly
4. Check responsive behavior on mobile

## Known Limitations

1. **Audio Format**: Currently supports WebM format (Chrome/Edge). Safari uses different format.
2. **Transcription Language**: Currently hardcoded to English. Can be made configurable.
3. **File Size**: Large audio files may take longer to transcribe.
4. **Network Dependency**: Requires internet connection for transcription.

## Troubleshooting

### Voice Recording Not Working
- Check browser permissions for microphone
- Verify browser supports MediaRecorder API
- Check browser console for errors

### Transcription Failing
- Verify OpenAI API key is set correctly
- Check network connection
- Review API server logs for errors

### Sidebar Not Showing
- Check if screen width is below 768px (mobile)
- Verify sidebar is not collapsed
- Check browser console for errors

## Architecture Notes

The implementation follows a clean separation of concerns:
- **Frontend**: React components with hooks for state management
- **Backend**: FastAPI endpoints for API and WebSocket communication
- **Integration**: OpenAI Whisper API for speech-to-text
- **State Management**: React hooks (useState, useEffect, useRef)

All components are designed to be:
- **Modular**: Easy to add/remove features
- **Responsive**: Works on different screen sizes
- **Accessible**: Keyboard shortcuts and clear visual feedback
- **Performant**: Minimal re-renders and efficient state updates

