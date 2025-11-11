"""Utilities for constructing agent capability summaries."""

from __future__ import annotations

from typing import Dict, Any, List


def build_agent_capabilities(registry) -> List[Dict[str, Any]]:
    """
    Build structured capability descriptions for all registered agents.

    Works with lazy loading - uses static hierarchy constants, not agent instances.
    """

    # Import hierarchy constants (static, no agent initialization needed)
    from ..agent.file_agent import FILE_AGENT_HIERARCHY
    from ..agent.folder_agent import FOLDER_AGENT_HIERARCHY
    from ..agent.google_agent import GOOGLE_AGENT_HIERARCHY
    from ..agent.browser_agent import BROWSER_AGENT_HIERARCHY
    from ..agent.presentation_agent import PRESENTATION_AGENT_HIERARCHY
    from ..agent.email_agent import EMAIL_AGENT_HIERARCHY
    from ..agent.writing_agent import WRITING_AGENT_HIERARCHY
    from ..agent.critic_agent import CRITIC_AGENT_HIERARCHY
    from ..agent.report_agent import REPORT_AGENT_HIERARCHY
    from ..agent.google_finance_agent import GOOGLE_FINANCE_AGENT_HIERARCHY
    from ..agent.maps_agent import MAPS_AGENT_HIERARCHY
    from ..agent.imessage_agent import IMESSAGE_AGENT_HIERARCHY
    from ..agent.discord_agent import DISCORD_AGENT_HIERARCHY
    from ..agent.reddit_agent import REDDIT_AGENT_HIERARCHY
    from ..agent.twitter_agent import TWITTER_AGENT_HIERARCHY
    from ..agent.notifications_agent import NOTIFICATIONS_AGENT_HIERARCHY
    from ..agent.spotify_agent import SPOTIFY_AGENT_HIERARCHY
    from ..agent.whatsapp_agent import WHATSAPP_AGENT_HIERARCHY
    from ..agent.celebration_agent import CELEBRATION_AGENT_HIERARCHY

    # Map agent names to their static hierarchy documentation
    hierarchy_map = {
        "file": FILE_AGENT_HIERARCHY,
        "folder": FOLDER_AGENT_HIERARCHY,
        "google": GOOGLE_AGENT_HIERARCHY,
        "browser": BROWSER_AGENT_HIERARCHY,
        "presentation": PRESENTATION_AGENT_HIERARCHY,
        "email": EMAIL_AGENT_HIERARCHY,
        "writing": WRITING_AGENT_HIERARCHY,
        "critic": CRITIC_AGENT_HIERARCHY,
        "report": REPORT_AGENT_HIERARCHY,
        "google_finance": GOOGLE_FINANCE_AGENT_HIERARCHY,
        "maps": MAPS_AGENT_HIERARCHY,
        "imessage": IMESSAGE_AGENT_HIERARCHY,
        "discord": DISCORD_AGENT_HIERARCHY,
        "reddit": REDDIT_AGENT_HIERARCHY,
        "twitter": TWITTER_AGENT_HIERARCHY,
        "notifications": NOTIFICATIONS_AGENT_HIERARCHY,
        "spotify": SPOTIFY_AGENT_HIERARCHY,
        "whatsapp": WHATSAPP_AGENT_HIERARCHY,
        "celebration": CELEBRATION_AGENT_HIERARCHY,
    }

    capabilities: List[Dict[str, Any]] = []

    for agent_name in registry._agent_classes.keys():
        hierarchy = hierarchy_map.get(agent_name, "")
        title = f"{agent_name.title()} Agent"
        domain = None

        if hierarchy:
            lines = [line.strip() for line in hierarchy.splitlines() if line.strip()]
            if lines:
                title = lines[0]
            for line in lines:
                lowered = line.lower()
                if lowered.startswith("domain"):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        domain = parts[1].strip()
                    break

        capabilities.append({
            "agent": agent_name,
            "title": title,
            "domain": domain,
            "description": hierarchy.strip() if hierarchy else title,
        })

    return capabilities
