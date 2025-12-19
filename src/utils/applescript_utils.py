"""
AppleScript Utility Functions

Provides standardized error handling and execution for AppleScript across all automation modules.
"""

import subprocess
import logging
import tempfile
import os
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def run_applescript(
    script: str,
    timeout: int = 30,
    use_temp_file: bool = False
) -> Tuple[subprocess.CompletedProcess, Optional[str]]:
    """
    Execute AppleScript with standardized error handling.

    Args:
        script: AppleScript code to execute
        timeout: Timeout in seconds (default: 30)
        use_temp_file: If True, use temp file; if False, use stdin (default: False)

    Returns:
        Tuple of (CompletedProcess, user_friendly_error_message)
        - CompletedProcess has returncode, stdout, stderr
        - user_friendly_error_message is None if successful, otherwise contains user-friendly error
    """
    try:
        if use_temp_file:
            # Write to temporary file for reliable execution
            with tempfile.NamedTemporaryFile(mode='w', suffix='.scpt', delete=False, encoding='utf-8') as f:
                f.write(script)
                script_file = f.name

            try:
                result = subprocess.run(
                    ['osascript', script_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding='utf-8'
                )
            finally:
                # Clean up temp file
                try:
                    os.unlink(script_file)
                except Exception:
                    pass
        else:
            # Use stdin (more efficient, but may have issues with complex scripts)
            result = subprocess.run(
                ['osascript', '-'],
                input=script,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8'
            )

        # Check for common error patterns and provide user-friendly messages
        user_error = None
        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()

            # Parse common error patterns
            if "not allowed assistive access" in stderr.lower() or "not allowed automation" in stderr.lower():
                user_error = (
                    "Automation permission denied. Please grant automation permissions:\n"
                    "1. Open System Settings → Privacy & Security → Automation\n"
                    "2. Grant permission to Terminal/Python for the app you're trying to automate"
                )
            elif "can't get" in stderr.lower() or "can't make" in stderr.lower():
                user_error = (
                    f"Application not accessible: {stderr}\n"
                    "Make sure the app is installed and running, or grant automation permissions."
                )
            elif "syntax error" in stderr.lower():
                user_error = (
                    f"AppleScript syntax error: {stderr}\n"
                    "This is an internal error. Please report this issue."
                )
            elif "timeout" in stderr.lower() or result.returncode == -1:
                user_error = (
                    f"Script execution timed out after {timeout} seconds.\n"
                    "The operation may be taking too long. Please try again."
                )
            else:
                # Generic error message
                error_text = stderr or stdout or "Unknown error"
                user_error = (
                    f"AppleScript execution failed: {error_text}\n"
                    "Check that the app is installed, running, and you have automation permissions."
                )

        return result, user_error

    except subprocess.TimeoutExpired:
        logger.error(f"AppleScript timeout after {timeout}s")
        fake_result = subprocess.CompletedProcess(
            args=['osascript'],
            returncode=-1,
            stdout="",
            stderr=f"Timeout after {timeout} seconds"
        )
        user_error = (
            f"Script execution timed out after {timeout} seconds.\n"
            "The operation may be taking too long. Please try again."
        )
        return fake_result, user_error

    except Exception as e:
        logger.error(f"Error running AppleScript: {e}")
        fake_result = subprocess.CompletedProcess(
            args=['osascript'],
            returncode=-1,
            stdout="",
            stderr=str(e)
        )
        user_error = (
            f"Failed to execute AppleScript: {str(e)}\n"
            "Check that osascript is available and you have proper permissions."
        )
        return fake_result, user_error


def format_applescript_error(
    result: subprocess.CompletedProcess,
    operation: str,
    app_name: str,
    user_friendly_error: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format AppleScript error into a standardized error dictionary.

    Args:
        result: CompletedProcess from run_applescript
        operation: Description of the operation (e.g., "create reminder", "compose email")
        app_name: Name of the app being automated (e.g., "Reminders.app", "Mail.app")
        user_friendly_error: Optional user-friendly error message from run_applescript

    Returns:
        Dictionary with error information:
        {
            "success": False,
            "error": True,
            "error_type": str,
            "error_message": str,
            "user_friendly_message": str,
            "retry_possible": bool,
            "technical_details": str
        }
    """
    if result.returncode == 0:
        return {"success": True}

    error_type = "AppleScriptError"
    retry_possible = True

    stderr = result.stderr.strip()
    stdout = result.stdout.strip()

    # Determine error type and retry possibility
    if "not allowed" in stderr.lower() or "permission" in stderr.lower():
        error_type = "PermissionError"
        retry_possible = False  # User needs to grant permission first
    elif "timeout" in stderr.lower() or result.returncode == -1:
        error_type = "TimeoutError"
        retry_possible = True
    elif "can't get" in stderr.lower() or "can't make" in stderr.lower():
        error_type = "ApplicationError"
        retry_possible = True
    elif "syntax error" in stderr.lower():
        error_type = "SyntaxError"
        retry_possible = False  # Code issue, not user issue

    error_message = stderr or stdout or "Unknown error"
    user_message = user_friendly_error or (
        f"Failed to {operation} using {app_name}.\n"
        f"Error: {error_message}"
    )

    return {
        "success": False,
        "error": True,
        "error_type": error_type,
        "error_message": error_message,
        "user_friendly_message": user_message,
        "retry_possible": retry_possible,
        "technical_details": {
            "returncode": result.returncode,
            "stderr": stderr,
            "stdout": stdout
        }
    }
