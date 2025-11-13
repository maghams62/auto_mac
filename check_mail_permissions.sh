#!/bin/bash

# Mail.app Automation Permissions Diagnostic Script
# Checks if the current user has proper automation permissions for Mail.app

echo "🔍 Mail.app Automation Permissions Diagnostic"
echo "=============================================="
echo ""

# Check 1: Is Mail.app running?
echo "1. Checking if Mail.app is running..."
if pgrep -x "Mail" > /dev/null; then
    echo "✅ Mail.app is running"
else
    echo "❌ Mail.app is not running"
    echo "   → Start Mail.app and try again"
fi
echo ""

# Check 2: Test basic AppleScript access
echo "2. Testing basic AppleScript access to Mail.app..."
osascript -e 'tell application "Mail" to return "accessible"' 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ AppleScript can access Mail.app"
else
    echo "❌ AppleScript cannot access Mail.app"
    echo "   → Check automation permissions in System Settings"
fi
echo ""

# Check 3: Test mailbox access
echo "3. Testing mailbox access..."
result=$(osascript -e '
tell application "Mail"
    try
        set inboxRef to mailbox "INBOX"
        return "EXISTS"
    on error errMsg
        return "ERROR: " & errMsg
    end try
end tell
' 2>/dev/null)

if [ $? -eq 0 ] && [[ "$result" == "EXISTS" ]]; then
    echo "✅ INBOX mailbox is accessible"
else
    echo "❌ INBOX mailbox not accessible: $result"
    echo "   → Check if INBOX exists or try different mailbox name"
fi
echo ""

# Check 4: Test email count (if accessible)
echo "4. Testing email count retrieval..."
count=$(osascript -e '
tell application "Mail"
    try
        set inboxRef to mailbox "INBOX"
        set allMessages to messages of inboxRef
        return count of allMessages as string
    on error
        return "0"
    end try
end tell
' 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "✅ Email count retrieval works: $count emails in INBOX"
else
    echo "❌ Email count retrieval failed"
fi
echo ""

# Check 5: Check macOS version and permissions structure
echo "5. System information..."
echo "   macOS version: $(sw_vers -productVersion)"
echo "   User: $(whoami)"
echo ""

# Check 6: Check TCC database for automation permissions
echo "6. Checking TCC database for automation permissions..."
# This is complex and may require sudo, so just provide guidance
echo "   To check automation permissions manually:"
echo "   → Go to System Settings > Privacy & Security > Automation"
echo "   → Find your terminal/Python app in the list"
echo "   → Ensure 'Mail' is checked"
echo ""

# Check 7: Provide actionable recommendations
echo "📋 RECOMMENDATIONS:"
echo ""

if ! pgrep -x "Mail" > /dev/null; then
    echo "• Start Mail.app first"
fi

if ! osascript -e 'tell application "Mail" to return "test"' 2>/dev/null; then
    echo "• Grant automation permissions:"
    echo "  1. Open System Settings"
    echo "  2. Go to Privacy & Security > Automation"
    echo "  3. Find your terminal app (Terminal, iTerm, etc.) or Python app"
    echo "  4. Check the box next to 'Mail'"
    echo "  5. You may need to restart your terminal/Python app"
fi

if [[ "$result" != "EXISTS" ]]; then
    echo "• Check mailbox names:"
    echo "  - Try 'INBOX', 'Inbox', 'Archive', 'Sent', etc."
    echo "  - Look in Mail.app to see available mailbox names"
fi

echo ""
echo "Run this diagnostic again after making changes to verify fixes."
echo ""
echo "If issues persist, try running: python test_mail_access_diagnostic.py"
echo "for more detailed diagnostic information."
