# Email Mailbox Scope Fix ✅

## Summary

Fixed critical bug where mailbox existence check in `read_latest_emails` was failing because it didn't scope mailbox lookups to the configured account, causing "mailbox not found" errors even when INBOX existed under Google account.

## Problem

The mailbox existence diagnostic check in `src/agent/email_agent.py` was calling AppleScript `mailbox "{mailbox}"` without account scoping. This caused AppleScript to search across all accounts instead of the specific configured account (Google), resulting in MailboxNotFound errors.

**Error Log Example:**
```
INFO:src.agent.agent:Step 1 result: {'error': True, 'error_type': 'MailboxNotFound', 'error_message': "Mailbox 'INBOX' not found or not accessible. Check if the mailbox exists in Mail.app.", 'retry_possible': True, 'diagnostic_suggestion': "Verify that mailbox 'INBOX' exists in Mail.app. Common alternatives: INBOX, Inbox, Archive, Sent, etc."}
```

## Root Cause

- Mailbox existence check used `mailbox "INBOX"` instead of `mailbox "INBOX" of account "Google"`
- AppleScript searches all accounts by default, but INBOX only exists under the Google account
- The actual `read_latest_emails` call correctly scoped to account, but the diagnostic check didn't

## Solution

Updated `src/agent/email_agent.py` (lines 303-334) to:

1. **Escape strings properly** using same logic as `MailReader._escape_applescript_string`
2. **Add account scoping** when `email_settings.account_email` is configured
3. **Log warning instead of blocking** - continue to actual fetch if diagnostic check fails

**Code Changes:**
```python
# Before: No account scoping
test_script = f'''
tell application "Mail"
    try
        set testMailbox to mailbox "{mailbox}"
        return "EXISTS"
    on error errMsg
        return "ERROR: " & errMsg
    end try
end tell
'''

# After: Account-scoped with escaping
escaped_mailbox = mailbox.replace('"', '\\"')
account_clause = ""
if account_email:
    escaped_account = account_email.replace('"', '\\"')
    account_clause = f' of account "{escaped_account}"'

test_script = f'''
tell application "Mail"
    try
        set targetMailbox to mailbox "{escaped_mailbox}"{account_clause}
        return "EXISTS"
    on error errMsg
        return "ERROR: " & errMsg
    end try
end tell
'''

# Changed error handling from blocking to warning
if result.returncode != 0 or "ERROR:" in result.stdout.strip():
    logger.warning(f"[EMAIL AGENT] Mailbox existence check failed for '{mailbox}'{f' in account {account_email}' if account_email else ''}: {result.stdout.strip()}")
    # Don't block the read - continue and let the actual fetch fail if mailbox truly doesn't exist
```

## Testing

✅ **Diagnostic Test Passes:** `python test_mail_access_diagnostic.py`
- All 8 tests pass including "INBOX Exists" test
- Confirms INBOX exists in Google account

✅ **No Regression:** Mailbox check now works correctly with account scoping

## Impact

- **Before:** Email reading failed at diagnostic step with MailboxNotFound
- **After:** Diagnostic passes, email reading proceeds normally
- **Benefit:** Fixes false negative mailbox existence checks for multi-account setups

## Files Modified

- `src/agent/email_agent.py` (lines 303-334): Updated mailbox existence check logic

## Verification

Run diagnostic to confirm fix:
```bash
python test_mail_access_diagnostic.py
```

Should show:
```
✅ INBOX Exists: INBOX mailbox exists in account Google
```
