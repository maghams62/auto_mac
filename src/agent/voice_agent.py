"""
Voice Agent - Speech-to-text and text-to-speech capabilities.

This agent provides voice interaction capabilities:
- Speech-to-text using OpenAI Whisper API
- Text-to-speech using OpenAI TTS API
- Audio file transcription
- Text-to-speech audio generation

Built on OpenAI's Whisper and TTS APIs for high-quality voice processing.
"""

from typing import Dict, Any, Optional
from langchain_core.tools import tool
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


@tool
def transcribe_audio_file(audio_file_path: str, language: Optional[str] = None) -> Dict[str, Any]:
    """
    Transcribe an audio file to text using OpenAI Whisper API.

    Use this tool when you need to:
    - Convert speech from audio files to text
    - Process voice recordings
    - Extract text from audio content

    This is useful for:
    - Transcribing voice memos or recordings
    - Processing audio files for content extraction
    - Converting speech to text for further processing

    Args:
        audio_file_path: Path to the audio file to transcribe (supports: mp3, mp4, mpeg, mpga, m4a, wav, webm)
        language: Optional language code (e.g., "en", "es", "fr"). If None, auto-detects language.

    Returns:
        Dictionary with transcribed text and metadata

    Examples:
        # Transcribe an audio file
        transcribe_audio_file(audio_file_path="/path/to/recording.mp3")

        # Transcribe with specific language
        transcribe_audio_file(audio_file_path="/path/to/recording.wav", language="en")
    """
    logger.info(f"[VOICE AGENT] Tool: transcribe_audio_file(audio_file_path='{audio_file_path}', language='{language}')")

    try:
        # Validate input
        if not audio_file_path or not isinstance(audio_file_path, str):
            return {
                "error": True,
                "error_type": "InvalidInput",
                "error_message": "Audio file path must be a non-empty string",
                "retry_possible": True
            }

        # Check if file exists
        if not os.path.exists(audio_file_path):
            return {
                "error": True,
                "error_type": "FileNotFound",
                "error_message": f"Audio file not found: {audio_file_path}",
                "retry_possible": False
            }

        # Validate file extension
        valid_extensions = {'.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm'}
        file_ext = Path(audio_file_path).suffix.lower()
        if file_ext not in valid_extensions:
            return {
                "error": True,
                "error_type": "InvalidFileType",
                "error_message": f"Unsupported audio format: {file_ext}. Supported: {', '.join(valid_extensions)}",
                "retry_possible": False,
                "supported_formats": list(valid_extensions)
            }

        # Get OpenAI client
        from openai import OpenAI
        from ..config_validator import ConfigAccessor
        
        # Load config to get API key
        from ..utils import load_config
        config = load_config()
        config_accessor = ConfigAccessor(config)
        openai_config = config_accessor.get_openai_config()
        
        client = OpenAI(api_key=openai_config["api_key"])

        # Transcribe using OpenAI Whisper
        with open(audio_file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language  # None = auto-detect
            )

        logger.info(f"Successfully transcribed audio file: {len(transcript.text)} characters")
        
        return {
            "success": True,
            "text": transcript.text,
            "language": language or "auto-detected",
            "file_path": audio_file_path,
            "text_length": len(transcript.text),
            "word_count": len(transcript.text.split())
        }

    except Exception as e:
        logger.error(f"[VOICE AGENT] Error in transcribe_audio_file: {e}", exc_info=True)
        return {
            "error": True,
            "error_type": "TranscriptionError",
            "error_message": str(e),
            "retry_possible": True
        }


@tool
def text_to_speech(
    text: str,
    voice: str = "alloy",
    output_path: Optional[str] = None,
    speed: float = 1.0
) -> Dict[str, Any]:
    """
    Convert text to speech audio using OpenAI TTS API.

    Use this tool when you need to:
    - Generate audio from text
    - Create voice responses
    - Convert text content to speech

    This is useful for:
    - Generating voice responses for user queries
    - Creating audio versions of text content
    - Building voice-enabled interactions

    Args:
        text: Text to convert to speech (required, max ~4000 characters)
        voice: Voice to use - "alloy", "echo", "fable", "onyx", "nova", "shimmer" (default: "alloy")
        output_path: Optional path to save audio file. If None, saves to data/audio/ directory
        speed: Speech speed multiplier (0.25 to 4.0, default: 1.0)

    Returns:
        Dictionary with audio file path and metadata

    Examples:
        # Generate speech from text
        text_to_speech(text="Hello, this is a test message")

        # Use specific voice
        text_to_speech(text="Hello world", voice="nova")

        # Save to specific location
        text_to_speech(text="Hello", output_path="/path/to/output.mp3")
    """
    logger.info(f"[VOICE AGENT] Tool: text_to_speech(text_length={len(text) if text else 0}, voice='{voice}')")

    try:
        # Validate input
        if not text or not isinstance(text, str) or len(text.strip()) == 0:
            return {
                "error": True,
                "error_type": "InvalidInput",
                "error_message": "Text must be a non-empty string",
                "retry_possible": True
            }

        # Validate text length (OpenAI TTS limit is ~4000 characters)
        MAX_TEXT_LENGTH = 4000
        if len(text) > MAX_TEXT_LENGTH:
            return {
                "error": True,
                "error_type": "InvalidInput",
                "error_message": f"Text too long (max {MAX_TEXT_LENGTH} characters). Current: {len(text)}",
                "retry_possible": True,
                "max_length": MAX_TEXT_LENGTH
            }

        # Validate voice
        valid_voices = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
        if voice not in valid_voices:
            return {
                "error": True,
                "error_type": "InvalidInput",
                "error_message": f"Invalid voice '{voice}'. Valid voices: {', '.join(valid_voices)}",
                "retry_possible": True,
                "valid_voices": list(valid_voices)
            }

        # Validate speed
        if speed < 0.25 or speed > 4.0:
            return {
                "error": True,
                "error_type": "InvalidInput",
                "error_message": f"Speed must be between 0.25 and 4.0. Got: {speed}",
                "retry_possible": True
            }

        # Get OpenAI client
        from openai import OpenAI
        from ..config_validator import ConfigAccessor
        
        # Load config to get API key
        from ..utils import load_config
        config = load_config()
        config_accessor = ConfigAccessor(config)
        openai_config = config_accessor.get_openai_config()
        
        client = OpenAI(api_key=openai_config["api_key"])

        # Generate speech
        response = client.audio.speech.create(
            model="tts-1",  # or "tts-1-hd" for higher quality
            voice=voice,
            input=text,
            speed=speed
        )

        # Determine output path
        if output_path:
            audio_path = output_path
            # Ensure directory exists
            os.makedirs(os.path.dirname(audio_path) if os.path.dirname(audio_path) else ".", exist_ok=True)
        else:
            # Default to data/audio/ directory
            audio_dir = Path(__file__).parent.parent.parent / "data" / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            audio_path = str(audio_dir / f"tts_{os.urandom(4).hex()}.mp3")

        # Save audio file
        response.stream_to_file(audio_path)

        logger.info(f"Successfully generated speech: {audio_path}")
        
        return {
            "success": True,
            "audio_path": audio_path,
            "text": text,
            "voice": voice,
            "speed": speed,
            "text_length": len(text),
            "file_size_bytes": os.path.getsize(audio_path) if os.path.exists(audio_path) else 0
        }

    except Exception as e:
        logger.error(f"[VOICE AGENT] Error in text_to_speech: {e}", exc_info=True)
        return {
            "error": True,
            "error_type": "TTSError",
            "error_message": str(e),
            "retry_possible": True
        }


# Voice Agent Tool Registry
VOICE_AGENT_TOOLS = [
    transcribe_audio_file,
    text_to_speech,
]


# Voice Agent Hierarchy
VOICE_AGENT_HIERARCHY = """
Voice Agent Hierarchy:
======================

LEVEL 1: Speech Processing
├─ transcribe_audio_file(audio_file_path: str, language: Optional[str])
│  → Convert audio file to text using OpenAI Whisper API
│  → Supports: mp3, mp4, mpeg, mpga, m4a, wav, webm
│  → Auto-detects language if not specified
│
└─ text_to_speech(text: str, voice: str, output_path: Optional[str], speed: float)
   → Convert text to speech audio using OpenAI TTS API
   → Multiple voice options: alloy, echo, fable, onyx, nova, shimmer
   → Adjustable speech speed (0.25x to 4.0x)

Input Parameters:
  • transcribe_audio_file:
    - audio_file_path (required): Path to audio file
    - language (optional): Language code (e.g., "en", "es", "fr") or None for auto-detect
  
  • text_to_speech:
    - text (required): Text to convert to speech (max ~4000 characters)
    - voice (optional): Voice name - "alloy", "echo", "fable", "onyx", "nova", "shimmer" (default: "alloy")
    - output_path (optional): Path to save audio file (default: data/audio/)
    - speed (optional): Speech speed multiplier 0.25-4.0 (default: 1.0)

Typical Workflows:
1. transcribe_audio_file(audio_file_path="/path/to/recording.mp3")
   → Converts audio to text

2. text_to_speech(text="Hello, how can I help you?", voice="nova")
   → Generates speech audio file

3. transcribe_audio_file(...) → text_to_speech(...)
   → Process audio, then generate response audio

Use Cases:
✓ Voice memo transcription
✓ Audio content extraction
✓ Voice response generation
✓ Text-to-audio conversion
✓ Multilingual transcription
✓ Voice-enabled interactions

Features:
- OpenAI Whisper API for high-quality transcription
- OpenAI TTS API for natural-sounding speech
- Multiple voice options
- Adjustable speech speed
- Auto language detection
- Support for multiple audio formats

Available Voices:
  • alloy - Balanced, neutral voice
  • echo - Clear, articulate voice
  • fable - Expressive, storytelling voice
  • onyx - Deep, authoritative voice
  • nova - Bright, energetic voice
  • shimmer - Soft, gentle voice

Example 1 - Transcribe audio:
transcribe_audio_file(audio_file_path="/Users/me/voice_memo.mp3")
→ Returns transcribed text

Example 2 - Generate speech:
text_to_speech(text="Your report is ready!", voice="nova")
→ Creates audio file with speech

Example 3 - Transcribe with language:
transcribe_audio_file(audio_file_path="/path/to/spanish.mp3", language="es")
→ Transcribes Spanish audio

Example 4 - Custom speed:
text_to_speech(text="Slow speech", speed=0.75)
→ Generates slower speech
"""


class VoiceAgent:
    """
    Voice Agent - Mini-orchestrator for speech processing.

    Responsibilities:
    - Speech-to-text transcription using OpenAI Whisper
    - Text-to-speech generation using OpenAI TTS
    - Audio file processing
    - Voice interaction capabilities

    This agent provides voice capabilities for the automation system.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in VOICE_AGENT_TOOLS}
        logger.info(f"[VOICE AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> list:
        """Get all voice agent tools."""
        return VOICE_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        """Get voice agent hierarchy documentation."""
        return VOICE_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a voice agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Voice agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }

        tool = self.tools[tool_name]
        logger.info(f"[VOICE AGENT] Executing: {tool_name}")

        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[VOICE AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }

