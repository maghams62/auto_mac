"""
macOS Clipboard utilities.

This module provides clipboard operations for text and files,
used by agents that need clipboard access (Discord, etc.).
"""

import logging
import subprocess
from typing import Dict, Any, List, Optional

from ..utils.applescript_utils import run_applescript, format_applescript_error

logger = logging.getLogger(__name__)


def read_clipboard(mode: str = "text") -> Dict[str, Any]:
    """
    Read content from the system clipboard.

    Args:
        mode: "text" for plain text, "files" for file paths

    Returns:
        Dictionary with:
        - success: True if read was successful
        - content: The clipboard text (for mode="text")
        - file_paths: List of POSIX paths (for mode="files")
    """
    logger.info(f"[CLIPBOARD] Reading clipboard in mode: {mode}")

    try:
        if mode == "text":
            return _read_clipboard_text()
        elif mode == "files":
            return _read_clipboard_files()
        else:
            return {
                "success": False,
                "error": True,
                "error_type": "InvalidMode",
                "error_message": f"Unknown clipboard mode: {mode}. Use 'text' or 'files'.",
                "retry_possible": False
            }

    except Exception as e:
        logger.error(f"[CLIPBOARD] Error reading clipboard: {e}")
        return {
            "success": False,
            "error": True,
            "error_type": "ClipboardReadError",
            "error_message": str(e),
            "retry_possible": True
        }


def _read_clipboard_text() -> Dict[str, Any]:
    """Read plain text from clipboard using pbpaste."""
    try:
        result = subprocess.run(
            ["pbpaste"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            content = result.stdout
            logger.info(f"[CLIPBOARD] Read {len(content)} characters from clipboard")
            return {
                "success": True,
                "content": content,
                "length": len(content)
            }
        else:
            logger.error(f"[CLIPBOARD] pbpaste failed: {result.stderr}")
            return {
                "success": False,
                "error": True,
                "error_type": "ClipboardReadError",
                "error_message": result.stderr or "Failed to read clipboard",
                "retry_possible": True
            }

    except subprocess.TimeoutExpired:
        logger.error("[CLIPBOARD] pbpaste timed out")
        return {
            "success": False,
            "error": True,
            "error_type": "TimeoutError",
            "error_message": "Clipboard read timed out after 5 seconds",
            "retry_possible": True
        }


def _read_clipboard_files() -> Dict[str, Any]:
    """Read file paths from clipboard using AppleScript."""
    script = '''
try
    set fileList to {}
    set theClipboard to the clipboard as «class furl»
    if class of theClipboard is list then
        repeat with aFile in theClipboard
            set end of fileList to POSIX path of aFile
        end repeat
    else
        set end of fileList to POSIX path of theClipboard
    end if

    set AppleScript's text item delimiters to "|||"
    return fileList as text
on error errMsg
    return "Error: " & errMsg
end try
'''

    result, user_error = run_applescript(script, timeout=10)

    if result.returncode == 0:
        output = result.stdout.strip()

        if output.startswith("Error:"):
            error_msg = output[6:].strip()
            logger.error(f"[CLIPBOARD] File read error: {error_msg}")
            return {
                "success": False,
                "error": True,
                "error_type": "ClipboardFileError",
                "error_message": error_msg,
                "retry_possible": True
            }

        # Parse file paths
        if output:
            file_paths = [p.strip() for p in output.split("|||") if p.strip()]
            logger.info(f"[CLIPBOARD] Read {len(file_paths)} file paths from clipboard")
            return {
                "success": True,
                "file_paths": file_paths,
                "count": len(file_paths)
            }
        else:
            return {
                "success": True,
                "file_paths": [],
                "count": 0,
                "note": "No file paths on clipboard"
            }
    else:
        error_info = format_applescript_error(
            result,
            "read clipboard files",
            "System",
            user_error
        )
        return {
            "success": False,
            "error": True,
            "error_type": error_info.get("error_type", "ClipboardFileError"),
            "error_message": error_info.get("error_message", "Unknown error"),
            "retry_possible": error_info.get("retry_possible", True)
        }


def write_clipboard_text(text: str) -> Dict[str, Any]:
    """
    Write text to the system clipboard.

    Args:
        text: Text to write to clipboard

    Returns:
        Dictionary with success status
    """
    logger.info(f"[CLIPBOARD] Writing {len(text)} characters to clipboard")

    try:
        result = subprocess.run(
            ["pbcopy"],
            input=text,
            text=True,
            check=True,
            timeout=5
        )

        logger.info("[CLIPBOARD] Successfully wrote to clipboard")
        return {
            "success": True,
            "length": len(text)
        }

    except subprocess.TimeoutExpired:
        logger.error("[CLIPBOARD] pbcopy timed out")
        return {
            "success": False,
            "error": True,
            "error_type": "TimeoutError",
            "error_message": "Clipboard write timed out after 5 seconds",
            "retry_possible": True
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"[CLIPBOARD] pbcopy failed: {e}")
        return {
            "success": False,
            "error": True,
            "error_type": "ClipboardWriteError",
            "error_message": str(e),
            "retry_possible": True
        }
    except Exception as e:
        logger.error(f"[CLIPBOARD] Error writing to clipboard: {e}")
        return {
            "success": False,
            "error": True,
            "error_type": "ClipboardWriteError",
            "error_message": str(e),
            "retry_possible": False
        }


def read_file_paths_from_clipboard() -> Dict[str, Any]:
    """
    Convenience wrapper to read file paths from clipboard.

    Returns:
        Dictionary with file_paths list
    """
    return read_clipboard(mode="files")


def clear_clipboard() -> Dict[str, Any]:
    """
    Clear the system clipboard.

    Returns:
        Dictionary with success status
    """
    logger.info("[CLIPBOARD] Clearing clipboard")
    return write_clipboard_text("")
