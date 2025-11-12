#!/usr/bin/env python3
"""
Permissions Verification Test Script

This script checks if all necessary macOS permissions are granted for:
1. Mail.app access (reading emails)
2. Notes.app access (creating/editing notes)

Following browser automation testing guidelines:
- Clear, isolated test cases
- Explicit success/failure reporting
- Detailed error messages
- Step-by-step verification
"""

import sys
import os
import subprocess
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class Color:
    """Terminal colors for clear output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text):
    """Print a clear section header"""
    print(f"\n{Color.BOLD}{Color.BLUE}{'=' * 80}{Color.END}")
    print(f"{Color.BOLD}{Color.BLUE}  {text}{Color.END}")
    print(f"{Color.BOLD}{Color.BLUE}{'=' * 80}{Color.END}\n")


def print_success(text):
    """Print success message"""
    print(f"{Color.GREEN}✅ {text}{Color.END}")


def print_error(text):
    """Print error message"""
    print(f"{Color.RED}❌ {text}{Color.END}")


def print_warning(text):
    """Print warning message"""
    print(f"{Color.YELLOW}⚠️  {text}{Color.END}")


def print_info(text):
    """Print info message"""
    print(f"   {text}")


def test_mail_app_permissions():
    """
    Test 1: Verify Mail.app automation permissions

    This test attempts to:
    1. Check if Mail.app is running
    2. Try to access Mail.app via AppleScript
    3. Verify we can read basic Mail.app information
    """
    print_header("TEST 1: Mail.app Permissions")

    print("Step 1: Checking if Mail.app is installed...")
    mail_app_path = "/Applications/Mail.app"
    if os.path.exists(mail_app_path):
        print_success(f"Mail.app found at {mail_app_path}")
    else:
        print_error(f"Mail.app not found at {mail_app_path}")
        return False

    print("\nStep 2: Testing Mail.app automation access...")

    # Simple AppleScript to test Mail.app access
    test_script = '''
    tell application "Mail"
        try
            set accountCount to count of accounts
            return "SUCCESS:" & accountCount
        on error errMsg
            return "ERROR:" & errMsg
        end try
    end tell
    '''

    try:
        result = subprocess.run(
            ['osascript', '-e', test_script],
            capture_output=True,
            text=True,
            timeout=10
        )

        output = result.stdout.strip()

        if result.returncode == 0 and output.startswith("SUCCESS:"):
            account_count = output.split(":")[1]
            print_success("Mail.app automation access GRANTED")
            print_info(f"Found {account_count} email account(s) configured")

            if account_count == "0":
                print_warning("No email accounts configured in Mail.app")
                print_info("You need to add an email account to Mail.app first")
                return False

            return True
        else:
            error_msg = output if output.startswith("ERROR:") else result.stderr
            print_error("Mail.app automation access DENIED")
            print_info(f"Error: {error_msg}")
            print_info("")
            print_info("To fix this:")
            print_info("1. Open System Settings")
            print_info("2. Go to Privacy & Security → Automation")
            print_info("3. Find Terminal (or Python) in the list")
            print_info("4. Enable checkbox for 'Mail'")
            print_info("5. Restart this test")
            return False

    except subprocess.TimeoutExpired:
        print_error("Mail.app access test timed out")
        print_info("This usually means Mail.app is prompting for permission")
        print_info("Check if there's a permission dialog on screen")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False


def test_mail_app_read_capability():
    """
    Test 2: Verify we can actually read emails from Mail.app

    This test attempts to:
    1. Get the INBOX mailbox
    2. Count messages in INBOX
    3. Verify we can access message properties
    """
    print_header("TEST 2: Mail.app Read Capability")

    print("Testing ability to read from INBOX...")

    read_test_script = '''
    tell application "Mail"
        try
            set inboxMessages to messages of inbox
            set messageCount to count of inboxMessages

            if messageCount > 0 then
                set firstMessage to item 1 of inboxMessages
                set messageSender to sender of firstMessage
                return "SUCCESS:" & messageCount & " messages found"
            else
                return "SUCCESS:0 messages found (inbox is empty)"
            end if
        on error errMsg
            return "ERROR:" & errMsg
        end try
    end tell
    '''

    try:
        result = subprocess.run(
            ['osascript', '-e', read_test_script],
            capture_output=True,
            text=True,
            timeout=15
        )

        output = result.stdout.strip()

        if result.returncode == 0 and output.startswith("SUCCESS:"):
            message = output.split(":", 1)[1]
            print_success(f"Successfully accessed INBOX: {message}")
            return True
        else:
            error_msg = output if output.startswith("ERROR:") else result.stderr
            print_error("Failed to read from INBOX")
            print_info(f"Error: {error_msg}")
            return False

    except subprocess.TimeoutExpired:
        print_error("Mail reading test timed out")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False


def test_notes_app_permissions():
    """
    Test 3: Verify Notes.app automation permissions

    This test attempts to:
    1. Check if Notes.app is running
    2. Try to access Notes.app via AppleScript
    3. Verify we can read basic Notes.app information
    """
    print_header("TEST 3: Notes.app Permissions")

    print("Step 1: Checking if Notes.app is installed...")
    notes_app_path = "/Applications/Notes.app"
    if os.path.exists(notes_app_path):
        print_success(f"Notes.app found at {notes_app_path}")
    else:
        print_error(f"Notes.app not found at {notes_app_path}")
        return False

    print("\nStep 2: Testing Notes.app automation access...")

    # Simple AppleScript to test Notes.app access
    test_script = '''
    tell application "Notes"
        try
            set folderCount to count of folders
            return "SUCCESS:" & folderCount
        on error errMsg
            return "ERROR:" & errMsg
        end try
    end tell
    '''

    try:
        result = subprocess.run(
            ['osascript', '-e', test_script],
            capture_output=True,
            text=True,
            timeout=10
        )

        output = result.stdout.strip()

        if result.returncode == 0 and output.startswith("SUCCESS:"):
            folder_count = output.split(":")[1]
            print_success("Notes.app automation access GRANTED")
            print_info(f"Found {folder_count} folder(s) in Notes.app")
            return True
        else:
            error_msg = output if output.startswith("ERROR:") else result.stderr
            print_error("Notes.app automation access DENIED")
            print_info(f"Error: {error_msg}")
            print_info("")
            print_info("To fix this:")
            print_info("1. Open System Settings")
            print_info("2. Go to Privacy & Security → Automation")
            print_info("3. Find Terminal (or Python) in the list")
            print_info("4. Enable checkbox for 'Notes'")
            print_info("5. Restart this test")
            return False

    except subprocess.TimeoutExpired:
        print_error("Notes.app access test timed out")
        print_info("This usually means Notes.app is prompting for permission")
        print_info("Check if there's a permission dialog on screen")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False


def test_notes_app_write_capability():
    """
    Test 4: Verify we can create/write notes in Notes.app

    This test attempts to:
    1. Create a test note
    2. Verify the note was created
    3. Clean up the test note
    """
    print_header("TEST 4: Notes.app Write Capability")

    print("Testing ability to create a note...")

    test_note_title = "Permission Test Note"
    test_note_body = "This is a test note created by the permission verification script."

    create_script = f'''
    tell application "Notes"
        try
            set newNote to make new note at folder "Notes" with properties {{name:"{test_note_title}", body:"{test_note_body}"}}
            set noteID to id of newNote
            return "SUCCESS:" & noteID
        on error errMsg
            return "ERROR:" & errMsg
        end try
    end tell
    '''

    try:
        result = subprocess.run(
            ['osascript', '-e', create_script],
            capture_output=True,
            text=True,
            timeout=10
        )

        output = result.stdout.strip()

        if result.returncode == 0 and output.startswith("SUCCESS:"):
            note_id = output.split(":", 1)[1]
            print_success("Successfully created test note")
            print_info(f"Note ID: {note_id}")

            # Try to clean up the test note
            print("\nCleaning up test note...")
            delete_script = f'''
            tell application "Notes"
                try
                    set testNote to note id "{note_id}"
                    delete testNote
                    return "SUCCESS:Deleted"
                on error errMsg
                    return "ERROR:" & errMsg
                end try
            end tell
            '''

            delete_result = subprocess.run(
                ['osascript', '-e', delete_script],
                capture_output=True,
                text=True,
                timeout=10
            )

            if delete_result.returncode == 0:
                print_success("Test note cleaned up successfully")
            else:
                print_warning("Could not delete test note - please remove it manually")
                print_info(f"Note title: '{test_note_title}'")

            return True
        else:
            error_msg = output if output.startswith("ERROR:") else result.stderr
            print_error("Failed to create test note")
            print_info(f"Error: {error_msg}")
            return False

    except subprocess.TimeoutExpired:
        print_error("Note creation test timed out")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False


def test_config_file():
    """
    Test 5: Verify config.yaml is properly configured

    This test checks:
    1. config.yaml exists
    2. Email account is configured
    3. OpenAI API key is set
    """
    print_header("TEST 5: Configuration File")

    print("Checking config.yaml...")

    config_path = Path(__file__).parent.parent / "config.yaml"

    if not config_path.exists():
        print_error(f"config.yaml not found at {config_path}")
        return False

    print_success(f"config.yaml found at {config_path}")

    print("\nValidating configuration...")

    try:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Check email configuration
        email_config = config.get('email', {})
        account_email = email_config.get('account_email')

        if account_email and not account_email.startswith('${'):
            print_success(f"Email account configured: {account_email}")
        else:
            print_warning("Email account not configured in config.yaml")
            print_info("Set 'email.account_email' in config.yaml")

        # Check OpenAI API key
        openai_config = config.get('openai', {})
        api_key = openai_config.get('api_key', '')

        if api_key and not api_key.startswith('${'):
            print_success("OpenAI API key is configured")
        else:
            print_warning("OpenAI API key not configured")
            print_info("Set OPENAI_API_KEY environment variable")

        return True

    except Exception as e:
        print_error(f"Error reading config.yaml: {e}")
        return False


def main():
    """Run all permission verification tests"""
    print(f"\n{Color.BOLD}{'=' * 80}")
    print(f"  EMAIL & NOTES PERMISSIONS VERIFICATION")
    print(f"{'=' * 80}{Color.END}\n")

    print("This script will verify that your system has all necessary permissions")
    print("to read emails from Mail.app and create notes in Notes.app.\n")

    results = {}

    # Test 1: Mail.app permissions
    results['mail_permissions'] = test_mail_app_permissions()

    # Test 2: Mail.app read capability (only if permissions granted)
    if results['mail_permissions']:
        results['mail_read'] = test_mail_app_read_capability()
    else:
        results['mail_read'] = False
        print_header("TEST 2: Mail.app Read Capability")
        print_warning("Skipped - Mail.app permissions not granted")

    # Test 3: Notes.app permissions
    results['notes_permissions'] = test_notes_app_permissions()

    # Test 4: Notes.app write capability (only if permissions granted)
    if results['notes_permissions']:
        results['notes_write'] = test_notes_app_write_capability()
    else:
        results['notes_write'] = False
        print_header("TEST 4: Notes.app Write Capability")
        print_warning("Skipped - Notes.app permissions not granted")

    # Test 5: Config file
    results['config'] = test_config_file()

    # Print summary
    print_header("SUMMARY")

    print("Test Results:")
    print(f"  1. Mail.app Permissions:      {Color.GREEN}✅ PASS{Color.END}" if results['mail_permissions'] else f"  1. Mail.app Permissions:      {Color.RED}❌ FAIL{Color.END}")
    print(f"  2. Mail.app Read Capability:  {Color.GREEN}✅ PASS{Color.END}" if results['mail_read'] else f"  2. Mail.app Read Capability:  {Color.RED}❌ FAIL{Color.END}")
    print(f"  3. Notes.app Permissions:     {Color.GREEN}✅ PASS{Color.END}" if results['notes_permissions'] else f"  3. Notes.app Permissions:     {Color.RED}❌ FAIL{Color.END}")
    print(f"  4. Notes.app Write Capability:{Color.GREEN}✅ PASS{Color.END}" if results['notes_write'] else f"  4. Notes.app Write Capability:{Color.RED}❌ FAIL{Color.END}")
    print(f"  5. Configuration File:        {Color.GREEN}✅ PASS{Color.END}" if results['config'] else f"  5. Configuration File:        {Color.RED}❌ FAIL{Color.END}")

    print(f"\n{Color.BOLD}{'=' * 80}{Color.END}\n")

    all_passed = all(results.values())

    if all_passed:
        print_success("ALL TESTS PASSED!")
        print("\n✅ Your system is ready to:")
        print("   • Read emails from Mail.app")
        print("   • Summarize emails with AI")
        print("   • Create notes in Notes.app")
        print("\nYou can now run:")
        print(f"   {Color.BLUE}python tests/test_email_summarization_browser.py{Color.END}")
        return 0
    else:
        print_error("SOME TESTS FAILED")
        print("\n⚠️  Please fix the issues above before proceeding.")
        print("\nQuick fixes:")

        if not results['mail_permissions']:
            print(f"\n{Color.BOLD}Mail.app Permissions:{Color.END}")
            print("  → System Settings → Privacy & Security → Automation")
            print("  → Enable Terminal/Python → Mail")

        if not results['notes_permissions']:
            print(f"\n{Color.BOLD}Notes.app Permissions:{Color.END}")
            print("  → System Settings → Privacy & Security → Automation")
            print("  → Enable Terminal/Python → Notes")

        if not results['config']:
            print(f"\n{Color.BOLD}Configuration:{Color.END}")
            print("  → Edit config.yaml")
            print("  → Set email.account_email")
            print("  → Set OPENAI_API_KEY environment variable")

        return 1


if __name__ == "__main__":
    sys.exit(main())
