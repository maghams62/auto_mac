#!/usr/bin/env python3
"""
Email Access Diagnostic Script

Comprehensive testing of Mail.app integration to identify why email reading fails.
Tests each layer systematically to pinpoint the exact failure point.
"""

import subprocess
import sys
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MailDiagnostic:
    """Comprehensive Mail.app diagnostic tool."""

    def __init__(self):
        self.results = []

    def log_test(self, test_name: str, status: str, message: str, details: Optional[Dict[str, Any]] = None):
        """Log a test result."""
        result = {
            "test": test_name,
            "status": status,  # "PASS", "FAIL", "SKIP"
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.results.append(result)
        logger.info(f"[{status}] {test_name}: {message}")

    def test_1_mail_app_running(self) -> bool:
        """Test 1: Is Mail.app running?"""
        try:
            script = '''
            tell application "System Events"
                if application process "Mail" exists then
                    return "RUNNING"
                else
                    return "NOT_RUNNING"
                end if
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                status = result.stdout.strip()
                if status == "RUNNING":
                    self.log_test("Mail.app Running", "PASS", "Mail.app is currently running")
                    return True
                else:
                    self.log_test("Mail.app Running", "FAIL", "Mail.app is not running")
                    return False
            else:
                self.log_test("Mail.app Running", "FAIL", f"Failed to check Mail.app status: {result.stderr}")
                return False

        except Exception as e:
            self.log_test("Mail.app Running", "FAIL", f"Error checking Mail.app status: {str(e)}")
            return False

    def test_2_basic_mail_access(self) -> bool:
        """Test 2: Can we access Mail.app at all?"""
        try:
            script = '''
            tell application "Mail"
                return "Mail.app is accessible"
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                response = result.stdout.strip()
                if "accessible" in response:
                    self.log_test("Basic Mail Access", "PASS", "Successfully accessed Mail.app")
                    return True
                else:
                    self.log_test("Basic Mail Access", "FAIL", f"Unexpected response: {response}")
                    return False
            else:
                error_msg = result.stderr.strip()
                self.log_test("Basic Mail Access", "FAIL", f"Mail.app access failed: {error_msg}")
                return False

        except Exception as e:
            self.log_test("Basic Mail Access", "FAIL", f"Error accessing Mail.app: {str(e)}")
            return False

    def test_3_list_accounts(self) -> Dict[str, Any]:
        """Test 3: List all email accounts."""
        try:
            script = '''
            tell application "Mail"
                set accountList to {}
                repeat with acct in accounts
                    set accountName to name of acct
                    set accountEnabled to enabled of acct
                    set accountList to accountList & {accountName & "|" & accountEnabled}
                end repeat
                return accountList
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0:
                raw_output = result.stdout.strip()
                if raw_output:
                    # Parse the output - it's a comma-separated list of "name|enabled"
                    accounts = []
                    for item in raw_output.split(', '):
                        if '|' in item:
                            name, enabled = item.split('|', 1)
                            accounts.append({"name": name, "enabled": enabled == "true"})

                    self.log_test("List Accounts", "PASS", f"Found {len(accounts)} email accounts", {"accounts": accounts})
                    return {"success": True, "accounts": accounts}
                else:
                    self.log_test("List Accounts", "FAIL", "No accounts found or parsing failed")
                    return {"success": False, "accounts": []}
            else:
                error_msg = result.stderr.strip()
                self.log_test("List Accounts", "FAIL", f"Failed to list accounts: {error_msg}")
                return {"success": False, "accounts": []}

        except Exception as e:
            self.log_test("List Accounts", "FAIL", f"Error listing accounts: {str(e)}")
            return {"success": False, "accounts": []}

    def test_4_list_mailboxes(self, account_name: Optional[str] = None) -> Dict[str, Any]:
        """Test 4: List all mailboxes."""
        try:
            if account_name:
                script = f'''
                tell application "Mail"
                    set mailboxList to {{}}
                    try
                        set targetAccount to account "{account_name}"
                        repeat with mbx in mailboxes of targetAccount
                            set mailboxName to name of mbx
                            set mailboxList to mailboxList & {{mailboxName}}
                        end repeat
                    end try
                    return mailboxList
                end tell
                '''
            else:
                script = '''
                tell application "Mail"
                    set mailboxList to {}
                    try
                        repeat with mbx in mailboxes
                            set mailboxName to name of mbx
                            set mailboxList to mailboxList & {mailboxName}
                        end repeat
                    end try
                    return mailboxList
                end tell
                '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0:
                raw_output = result.stdout.strip()
                if raw_output:
                    # Parse mailbox list
                    mailboxes = [mb.strip() for mb in raw_output.split(', ') if mb.strip()]
                    self.log_test("List Mailboxes", "PASS", f"Found {len(mailboxes)} mailboxes", {"mailboxes": mailboxes})
                    return {"success": True, "mailboxes": mailboxes}
                else:
                    self.log_test("List Mailboxes", "FAIL", "No mailboxes found")
                    return {"success": False, "mailboxes": []}
            else:
                error_msg = result.stderr.strip()
                self.log_test("List Mailboxes", "FAIL", f"Failed to list mailboxes: {error_msg}")
                return {"success": False, "mailboxes": []}

        except Exception as e:
            self.log_test("List Mailboxes", "FAIL", f"Error listing mailboxes: {str(e)}")
            return {"success": False, "mailboxes": []}

    def test_5_check_inbox_exists(self, account_name: Optional[str] = None) -> bool:
        """Test 5: Check if INBOX mailbox exists."""
        try:
            if account_name:
                script = f'''
                tell application "Mail"
                    try
                        set targetAccount to account "{account_name}"
                        set inboxRef to mailbox "INBOX" of targetAccount
                        return "EXISTS"
                    on error
                        return "NOT_FOUND"
                    end try
                end tell
                '''
            else:
                script = '''
                tell application "Mail"
                    try
                        set inboxRef to mailbox "INBOX"
                        return "EXISTS"
                    on error
                        return "NOT_FOUND"
                    end try
                end tell
                '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                status = result.stdout.strip()
                if status == "EXISTS":
                    self.log_test("INBOX Exists", "PASS", f"INBOX mailbox exists{' in account ' + account_name if account_name else ''}")
                    return True
                else:
                    self.log_test("INBOX Exists", "FAIL", f"INBOX mailbox not found{' in account ' + account_name if account_name else ''}")
                    return False
            else:
                error_msg = result.stderr.strip()
                self.log_test("INBOX Exists", "FAIL", f"Failed to check INBOX: {error_msg}")
                return False

        except Exception as e:
            self.log_test("INBOX Exists", "FAIL", f"Error checking INBOX: {str(e)}")
            return False

    def test_6_count_emails_in_inbox(self, account_name: Optional[str] = None) -> Dict[str, Any]:
        """Test 6: Count emails in INBOX."""
        try:
            if account_name:
                script = f'''
                tell application "Mail"
                    try
                        set targetAccount to account "{account_name}"
                        set inboxRef to mailbox "INBOX" of targetAccount
                        set allMessages to messages of inboxRef
                        set messageCount to count of allMessages
                        return messageCount as string
                    on error errMsg
                        return "ERROR: " & errMsg
                    end try
                end tell
                '''
            else:
                script = '''
                tell application "Mail"
                    try
                        set inboxRef to mailbox "INBOX"
                        set allMessages to messages of inboxRef
                        set messageCount to count of allMessages
                        return messageCount as string
                    on error errMsg
                        return "ERROR: " & errMsg
                    end try
                end tell
                '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                if output.startswith("ERROR:"):
                    self.log_test("Count Emails", "FAIL", f"Error counting emails: {output}")
                    return {"success": False, "count": 0, "error": output}
                else:
                    try:
                        count = int(output)
                        self.log_test("Count Emails", "PASS", f"INBOX contains {count} emails", {"count": count})
                        return {"success": True, "count": count}
                    except ValueError:
                        self.log_test("Count Emails", "FAIL", f"Invalid count response: {output}")
                        return {"success": False, "count": 0, "error": f"Invalid response: {output}"}
            else:
                error_msg = result.stderr.strip()
                self.log_test("Count Emails", "FAIL", f"Failed to count emails: {error_msg}")
                return {"success": False, "count": 0, "error": error_msg}

        except Exception as e:
            self.log_test("Count Emails", "FAIL", f"Error counting emails: {str(e)}")
            return {"success": False, "count": 0, "error": str(e)}

    def test_7_read_single_email(self, account_name: Optional[str] = None) -> Dict[str, Any]:
        """Test 7: Try to read a single email."""
        try:
            if account_name:
                script = f'''
                tell application "Mail"
                    try
                        set targetAccount to account "{account_name}"
                        set inboxRef to mailbox "INBOX" of targetAccount
                        set allMessages to messages of inboxRef
                        if (count of allMessages) > 0 then
                            set msg to item 1 of allMessages
                            set msgSender to sender of msg
                            set msgSubject to subject of msg
                            set msgDate to date received of msg
                            set msgContent to content of msg
                            return msgSender & "||" & msgSubject & "||" & (msgDate as string) & "||" & (characters 1 thru 100 of msgContent as string)
                        else
                            return "NO_EMAILS"
                        end if
                    on error errMsg
                        return "ERROR: " & errMsg
                    end try
                end tell
                '''
            else:
                script = '''
                tell application "Mail"
                    try
                        set inboxRef to mailbox "INBOX"
                        set allMessages to messages of inboxRef
                        if (count of allMessages) > 0 then
                            set msg to item 1 of allMessages
                            set msgSender to sender of msg
                            set msgSubject to subject of msg
                            set msgDate to date received of msg
                            set msgContent to content of msg
                            return msgSender & "||" & msgSubject & "||" & (msgDate as string) & "||" & (characters 1 thru 100 of msgContent as string)
                        else
                            return "NO_EMAILS"
                        end if
                    on error errMsg
                        return "ERROR: " & errMsg
                    end try
                end tell
                '''

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=20
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                if output == "NO_EMAILS":
                    self.log_test("Read Single Email", "SKIP", "No emails in INBOX to read")
                    return {"success": False, "reason": "no_emails"}
                elif output.startswith("ERROR:"):
                    self.log_test("Read Single Email", "FAIL", f"Error reading email: {output}")
                    return {"success": False, "error": output}
                elif "||" in output:
                    # Parse the email data
                    parts = output.split("||", 3)
                    if len(parts) == 4:
                        email_data = {
                            "sender": parts[0],
                            "subject": parts[1],
                            "date": parts[2],
                            "content_preview": parts[3]
                        }
                        self.log_test("Read Single Email", "PASS", "Successfully read one email", {"email": email_data})
                        return {"success": True, "email": email_data}
                    else:
                        self.log_test("Read Single Email", "FAIL", f"Unexpected email format: {output}")
                        return {"success": False, "error": f"Unexpected format: {output}"}
                else:
                    self.log_test("Read Single Email", "FAIL", f"Unexpected response: {output}")
                    return {"success": False, "error": f"Unexpected response: {output}"}
            else:
                error_msg = result.stderr.strip()
                self.log_test("Read Single Email", "FAIL", f"Failed to read email: {error_msg}")
                return {"success": False, "error": error_msg}

        except Exception as e:
            self.log_test("Read Single Email", "FAIL", f"Error reading email: {str(e)}")
            return {"success": False, "error": str(e)}

    def test_8_full_read_latest_workflow(self, account_name: Optional[str] = None) -> Dict[str, Any]:
        """Test 8: Full read_latest_emails workflow simulation."""
        try:
            # Build the same script used by the actual MailReader
            count = 3
            mailbox_name = "INBOX"

            if account_name:
                mailbox_ref = f'mailbox "{mailbox_name}" of account "{account_name}"'
            else:
                mailbox_ref = f'mailbox "{mailbox_name}"'

            script = f'''
tell application "Mail"
    set emailString to ""
    set messageCount to 0

    try
        set targetMailbox to {mailbox_ref}
        set allMessages to messages of targetMailbox

        repeat with msg in (items 1 thru (count of allMessages) of allMessages)
            if messageCount ≥ {count} then exit repeat

            try
                set msgSender to sender of msg
                set msgSubject to subject of msg
                set msgDate to date received of msg
                set msgContent to content of msg

                set emailData to msgSender & "||SEP||" & msgSubject & "||SEP||" & (msgDate as string) & "||SEP||" & msgContent
                if messageCount > 0 then
                    set emailString to emailString & "|||EMAIL|||"
                end if
                set emailString to emailString & emailData
                set messageCount to messageCount + 1
            end try
        end repeat

        return emailString
    on error errMsg
        return "ERROR: " & errMsg
    end try
end tell
'''

            logger.info("Executing full read_latest_emails simulation...")
            logger.info(f"AppleScript:\n{script}")

            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=30
            )

            logger.info(f"Return code: {result.returncode}")
            logger.info(f"Stdout: {result.stdout}")
            logger.info(f"Stderr: {result.stderr}")

            if result.returncode == 0:
                output = result.stdout.strip()
                if output.startswith("ERROR:"):
                    self.log_test("Full Workflow", "FAIL", f"Workflow failed: {output}")
                    return {"success": False, "error": output}
                elif output:
                    # Handle AppleScript string output with email delimiters
                    if output.startswith('"') and output.endswith('"'):
                        output = output[1:-1]  # Remove surrounding quotes

                    # Try to parse as email list
                    emails = []
                    items = output.split('|||EMAIL|||')
                    for item in items:
                        item = item.strip()
                        if '||SEP||' in item:
                            parts = item.split('||SEP||', 3)
                            if len(parts) == 4:
                                emails.append({
                                    "sender": parts[0],
                                    "subject": parts[1],
                                    "date": parts[2],
                                    "content": parts[3]
                                })
                    self.log_test("Full Workflow", "PASS", f"Successfully read {len(emails)} emails", {"emails": emails})
                    return {"success": True, "emails": emails}
                else:
                    self.log_test("Full Workflow", "FAIL", "No output from workflow")
                    return {"success": False, "error": "No output"}
            else:
                error_msg = result.stderr.strip()
                self.log_test("Full Workflow", "FAIL", f"Workflow execution failed: {error_msg}")
                return {"success": False, "error": error_msg}

        except Exception as e:
            self.log_test("Full Workflow", "FAIL", f"Workflow error: {str(e)}")
            return {"success": False, "error": str(e)}

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all diagnostic tests in sequence."""
        logger.info("=== Starting Mail Access Diagnostics ===\n")

        # Test 1: Is Mail.app running?
        if not self.test_1_mail_app_running():
            logger.warning("Mail.app is not running - cannot proceed with other tests")
            return self.get_summary()

        # Test 2: Basic Mail.app access
        if not self.test_2_basic_mail_access():
            logger.error("Cannot access Mail.app - check permissions")
            return self.get_summary()

        # Test 3: List accounts
        accounts_result = self.test_3_list_accounts()
        account_names = [acc["name"] for acc in accounts_result.get("accounts", []) if acc["enabled"]]

        # Test 4: List mailboxes (try with first enabled account)
        mailbox_result = self.test_4_list_mailboxes(account_names[0] if account_names else None)

        # Test 5: Check if INBOX exists (scoped to account if available)
        self.test_5_check_inbox_exists(account_names[0] if account_names else None)

        # Test 6: Count emails in INBOX (scoped to account if available)
        count_result = self.test_6_count_emails_in_inbox(account_names[0] if account_names else None)
        email_count = count_result.get("count", 0)

        # Test 7: Try to read a single email (only if there are emails)
        if email_count > 0:
            self.test_7_read_single_email(account_names[0] if account_names else None)
        else:
            self.log_test("Read Single Email", "SKIP", "No emails in INBOX to test reading")

        # Test 8: Full workflow simulation (scoped to account if available)
        self.test_8_full_read_latest_workflow(account_names[0] if account_names else None)

        return self.get_summary()

    def get_summary(self) -> Dict[str, Any]:
        """Get diagnostic summary."""
        passed = len([r for r in self.results if r["status"] == "PASS"])
        failed = len([r for r in self.results if r["status"] == "FAIL"])
        skipped = len([r for r in self.results if r["status"] == "SKIP"])

        summary = {
            "total_tests": len(self.results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "success_rate": f"{passed}/{len(self.results)}" if self.results else "0/0",
            "results": self.results
        }

        logger.info(f"\n=== Diagnostic Summary ===")
        logger.info(f"Tests: {summary['total_tests']} total")
        logger.info(f"Passed: {summary['passed']}")
        logger.info(f"Failed: {summary['failed']}")
        logger.info(f"Skipped: {summary['skipped']}")

        # Print detailed results
        for result in self.results:
            status_icon = "✅" if result["status"] == "PASS" else "❌" if result["status"] == "FAIL" else "⏭️"
            print(f"{status_icon} {result['test']}: {result['message']}")

        return summary


def main():
    """Main diagnostic function."""
    print("Mail Access Diagnostic Tool")
    print("=" * 50)
    print("This tool will test each layer of Mail.app integration to identify")
    print("why email reading is failing.\n")

    diagnostic = MailDiagnostic()
    summary = diagnostic.run_all_tests()

    # Save detailed results to file
    output_file = "mail_diagnostic_results.json"
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\nDetailed results saved to: {output_file}")

    # Provide actionable next steps based on failures
    failed_tests = [r for r in summary["results"] if r["status"] == "FAIL"]

    if failed_tests:
        print("\n🔧 NEXT STEPS TO FIX:")
        for test in failed_tests:
            test_name = test["test"]
            if "Mail.app Running" in test_name:
                print("  • Start Mail.app and ensure it's running")
            elif "Basic Mail Access" in test_name:
                print("  • Grant automation permissions: System Settings > Privacy & Security > Automation")
                print("  • Enable 'Terminal' or your Python app to control 'Mail'")
            elif "List Accounts" in test_name:
                print("  • Check Mail.app account setup")
                print("  • Ensure at least one email account is configured and enabled")
            elif "INBOX Exists" in test_name:
                print("  • Check mailbox names - 'INBOX' may not exist")
                print("  • Run the diagnostic again to see available mailboxes")
            elif "Count Emails" in test_name:
                print("  • INBOX may be empty - check for emails in Mail.app")
                print("  • Check if emails are in different mailboxes (Sent, Archive, etc.)")
            elif "Read Single Email" in test_name:
                print("  • Email parsing may be failing - check AppleScript syntax")
            elif "Full Workflow" in test_name:
                print("  • Complete workflow is broken - review AppleScript and parsing logic")

    return summary


if __name__ == "__main__":
    try:
        results = main()
        # Exit with non-zero code if there were failures
        if results.get("failed", 0) > 0:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nDiagnostic interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Diagnostic failed with error: {e}")
        sys.exit(1)
