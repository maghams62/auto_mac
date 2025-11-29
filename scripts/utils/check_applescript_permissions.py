#!/usr/bin/env python3
"""
AppleScript Permission Validation Script

Tests macOS automation permissions for all apps used by Cerebro OS:
- Mail.app (email composition and sending)
- Reminders.app (reminder creation)
- Calendar.app (calendar event creation)
- Finder (file operations and reveal)

Run this script to verify that all AppleScript integrations are properly configured.
"""

import subprocess
import sys
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class AppleScriptPermissionChecker:
    """Tests AppleScript permissions for macOS automation apps."""

    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}

    def test_applescript(self, app_name: str, script: str, description: str) -> Dict[str, Any]:
        """Test a single AppleScript execution."""
        logger.info(f"Testing {app_name}: {description}")

        try:
            result = subprocess.run(
                ['osascript', '-'],
                input=script,
                capture_output=True,
                text=True,
                timeout=10
            )

            success = result.returncode == 0
            output = result.stdout.strip()
            error = result.stderr.strip()

            self.results[app_name] = {
                'success': success,
                'description': description,
                'output': output,
                'error': error,
                'returncode': result.returncode
            }

            if success:
                logger.info(f"✅ {app_name}: SUCCESS - {output}")
            else:
                logger.error(f"❌ {app_name}: FAILED - {error}")

            return self.results[app_name]

        except subprocess.TimeoutExpired:
            logger.error(f"⏰ {app_name}: TIMEOUT - Script took too long (>10s)")
            self.results[app_name] = {
                'success': False,
                'description': description,
                'output': '',
                'error': 'Script timeout after 10 seconds',
                'returncode': -1
            }
            return self.results[app_name]

        except Exception as e:
            logger.error(f"💥 {app_name}: EXCEPTION - {str(e)}")
            self.results[app_name] = {
                'success': False,
                'description': description,
                'output': '',
                'error': str(e),
                'returncode': -1
            }
            return self.results[app_name]

    def test_mail_permissions(self) -> Dict[str, Any]:
        """Test Mail.app automation permissions."""
        script = '''
        tell application "Mail"
            set accountList to every mail account
            set accountCount to count of accountList
            if accountCount > 0 then
                return "Mail.app accessible - " & accountCount & " account(s) configured"
            else
                return "Mail.app accessible but no accounts configured"
            end if
        end tell
        '''
        return self.test_applescript('Mail.app', script, 'Check Mail.app automation access and account configuration')

    def test_reminders_permissions(self) -> Dict[str, Any]:
        """Test Reminders.app automation permissions."""
        script = '''
        tell application "Reminders"
            set listList to every list
            set listCount to count of listList
            if listCount > 0 then
                set listNames to name of every list
                return "Reminders.app accessible - " & listCount & " list(s): " & (listNames as string)
            else
                return "Reminders.app accessible but no lists found"
            end if
        end tell
        '''
        return self.test_applescript('Reminders.app', script, 'Check Reminders.app automation access and list configuration')

    def test_calendar_permissions(self) -> Dict[str, Any]:
        """Test Calendar.app automation permissions."""
        script = '''
        tell application "Calendar"
            set calendarList to every calendar
            set calendarCount to count of calendarList
            if calendarCount > 0 then
                set calendarNames to name of every calendar
                return "Calendar.app accessible - " & calendarCount & " calendar(s): " & (calendarNames as string)
            else
                return "Calendar.app accessible but no calendars found"
            end if
        end tell
        '''
        return self.test_applescript('Calendar.app', script, 'Check Calendar.app automation access and calendar configuration')

    def test_finder_permissions(self) -> Dict[str, Any]:
        """Test Finder automation permissions."""
        script = '''
        tell application "Finder"
            set homePath to path to home folder as string
            set desktopPath to path to desktop folder as string
            return "Finder accessible - Home: " & homePath & ", Desktop: " & desktopPath
        end tell
        '''
        return self.test_applescript('Finder', script, 'Check Finder automation access and basic file operations')

    def test_mail_composition(self) -> Dict[str, Any]:
        """Test Mail.app composition capabilities (opens draft but doesn't send)."""
        script = '''
        tell application "Mail"
            -- Create a draft email (don't send it)
            set newMessage to make new outgoing message with properties {subject:"Permission Test", content:"This is a test email from Cerebro OS permission checker."}
            set visible of newMessage to true
            return "Mail composition test successful - draft created"
        end tell
        '''
        return self.test_applescript('Mail Composition', script, 'Test Mail.app draft creation capabilities')

    def test_reminder_creation(self) -> Dict[str, Any]:
        """Test Reminders.app creation capabilities."""
        script = '''
        tell application "Reminders"
            -- Create a test reminder (we'll clean it up)
            set testReminder to make new reminder with properties {name:"Cerebro OS Permission Test", body:"Testing reminder creation permissions"}
            set reminderId to id of testReminder

            -- Delete the test reminder immediately
            delete testReminder

            return "Reminder creation test successful - created and cleaned up reminder: " & reminderId
        end tell
        '''
        return self.test_applescript('Reminder Creation', script, 'Test Reminders.app reminder creation and deletion capabilities')

    def test_finder_reveal(self) -> Dict[str, Any]:
        """Test Finder file reveal capabilities."""
        script = '''
        tell application "Finder"
            -- Try to reveal the home directory
            set homeFolder to home
            select homeFolder
            return "Finder reveal test successful - selected home folder"
        end tell
        '''
        return self.test_applescript('Finder Reveal', script, 'Test Finder file selection/reveal capabilities')

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all AppleScript permission tests."""
        logger.info("🔍 Starting AppleScript permission validation...")
        logger.info("=" * 60)

        # Basic permission tests
        self.test_mail_permissions()
        self.test_reminders_permissions()
        self.test_calendar_permissions()
        self.test_finder_permissions()

        logger.info("-" * 40)
        logger.info("Testing advanced capabilities...")

        # Advanced functionality tests
        self.test_mail_composition()
        self.test_reminder_creation()
        self.test_finder_reveal()

        logger.info("=" * 60)

        return self.results

    def print_summary(self):
        """Print a summary of test results."""
        successful = sum(1 for result in self.results.values() if result['success'])
        total = len(self.results)

        print(f"\n📊 SUMMARY: {successful}/{total} AppleScript permissions working")
        print("=" * 60)

        if successful == total:
            print("🎉 ALL TESTS PASSED!")
            print("✅ Cerebro OS should be able to use all AppleScript integrations.")
        else:
            print("⚠️  SOME TESTS FAILED!")
            print("❌ Cerebro OS may have issues with the following integrations:")

            for app, result in self.results.items():
                if not result['success']:
                    print(f"   • {app}: {result['error']}")

            print("\n🔧 TROUBLESHOOTING:")
            print("1. Open System Settings → Privacy & Security → Automation")
            print("2. Grant automation permissions to the Python/Terminal app")
            print("3. For Mail.app: Ensure at least one email account is configured")
            print("4. Restart your computer and run this script again")

        print("\n" + "=" * 60)

def main():
    """Main entry point."""
    print("🤖 Cerebro OS - AppleScript Permission Validator")
    print("This script tests macOS automation permissions for all apps used by Cerebro OS.")
    print()

    checker = AppleScriptPermissionChecker()
    results = checker.run_all_tests()
    checker.print_summary()

    # Return exit code based on success
    successful = sum(1 for result in results.values() if result['success'])
    total = len(results)

    if successful == total:
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Some failures

if __name__ == "__main__":
    main()
