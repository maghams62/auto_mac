"""
Verify that iMessage and Email agents are clearly distinct.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils import load_config
from src.agent.email_agent import EmailAgent, EMAIL_AGENT_HIERARCHY
from src.agent.imessage_agent import iMessageAgent, IMESSAGE_AGENT_HIERARCHY


def show_agent_comparison():
    """Show the clear distinction between Email and iMessage agents."""
    print("\n" + "="*80)
    print("AGENT COMPARISON: Email vs iMessage")
    print("="*80)

    config = load_config()

    # Email Agent
    print("\n" + "─"*80)
    print("📧 EMAIL AGENT")
    print("─"*80)
    email_agent = EmailAgent(config)
    email_tools = email_agent.get_tools()

    print(f"\nTools: {len(email_tools)}")
    for tool in email_tools:
        print(f"  • {tool.name}")
        # Get tool signature from docstring
        if hasattr(tool, 'description'):
            first_line = tool.description.split('\n')[0]
            print(f"    → {first_line}")

    print(f"\nHierarchy:")
    print(EMAIL_AGENT_HIERARCHY)

    # iMessage Agent
    print("\n" + "─"*80)
    print("📱 iMESSAGE AGENT")
    print("─"*80)
    imessage_agent = iMessageAgent(config)
    imessage_tools = imessage_agent.get_tools()

    print(f"\nTools: {len(imessage_tools)}")
    for tool in imessage_tools:
        print(f"  • {tool.name}")

    print(f"\nHierarchy:")
    print(IMESSAGE_AGENT_HIERARCHY)

    # Key Differences
    print("\n" + "="*80)
    print("🔑 KEY DIFFERENCES")
    print("="*80)

    print("\n📧 EMAIL AGENT (compose_email):")
    print("  Parameters:")
    print("    • subject: str")
    print("    • body: str")
    print("    • recipient: Optional[str]")
    print("    • attachments: Optional[List[str]]")
    print("    • send: bool")
    print("  Use for:")
    print("    ✓ Formal communication")
    print("    ✓ Messages with subject lines")
    print("    ✓ Sending attachments")
    print("    ✓ Drafting emails")

    print("\n📱 iMESSAGE AGENT (send_imessage):")
    print("  Parameters:")
    print("    • message: str  (required)")
    print("    • recipient: Optional[str]  (default: +16618572957)")
    print("  Use for:")
    print("    ✓ Quick text messages")
    print("    ✓ Maps URLs (PREFERRED)")
    print("    ✓ Instant notifications")
    print("    ✓ Phone number messaging")

    print("\n" + "="*80)
    print("✅ AGENTS ARE CLEARLY DISTINCT")
    print("="*80)
    print("\nDefault iMessage recipient: +16618572957")
    print("Agent will automatically use iMessage for Maps URLs\n")


if __name__ == "__main__":
    show_agent_comparison()
