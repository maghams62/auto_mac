"""
Message Personality Utility - Fun, quirky messages with emojis for static responses.

This module provides fun message generators for different action types.
Only used for static messages (non-LLM generated content).
"""

import random
from typing import Optional


def get_music_playing_message() -> str:
    """Get a fun message for when music starts playing."""
    messages = [
        "🎵 Let's get this party started! Music is now jamming!",
        "🎶 Boom! Your tunes are now serenading the room!",
        "🎵 Music's on! Time to vibe!",
        "🎶 Party mode activated! Music is playing!",
        "🎵 Let the music play! Your soundtrack is live!",
        "🎶 Music's jamming! Ready to rock!",
    ]
    return random.choice(messages)


def get_music_paused_message() -> str:
    """Get a fun message for when music is paused."""
    messages = [
        "⏸️ Music paused! Ready when you are!",
        "⏸️ Hit pause! Music's taking a breather!",
        "⏸️ Music paused! Your soundtrack is on standby!",
        "⏸️ Paused! Ready to resume whenever you are!",
        "⏸️ Music's on hold! Just say the word to continue!",
        "⏸️ Paused! Your tunes are waiting patiently!",
    ]
    return random.choice(messages)


def get_confetti_message() -> str:
    """Get a fun message for confetti celebrations."""
    messages = [
        "🎉🎊 Party time! Confetti explosion activated! 🎊🎉",
        "🎉 Celebration mode: ON! Confetti everywhere! 🎊",
        "🎊 Confetti time! Let's celebrate! 🎉✨",
        "🎉🎊 Confetti activated! Time to party! 🎊🎉",
        "✨ Confetti explosion! Celebration incoming! 🎉🎊",
        "🎊 Party time! Confetti is raining down! 🎉✨",
    ]
    return random.choice(messages)


def get_generic_success_message() -> str:
    """Get a fun generic success message for completed actions."""
    messages = [
        "✨ Done! That was smooth as butter! ✨",
        "✅ All set! Mission accomplished!",
        "🎯 Nailed it! Task completed!",
        "✨ Boom! Done and dusted! ✨",
        "✅ Success! That was a breeze!",
        "🎉 Got it! All wrapped up!",
        "✨ Perfect! That's a wrap! ✨",
        "✅ Done! Smooth sailing!",
        "🎯 Task complete! Easy peasy!",
        "✨ All good! That was quick! ✨",
    ]
    return random.choice(messages)


def get_task_completed_message() -> str:
    """Get a fun message for task completion."""
    messages = [
        "🎉 Task completed successfully! You're awesome!",
        "✨ All done! That was smooth! ✨",
        "✅ Mission accomplished! Well done!",
        "🎯 Task complete! Nailed it!",
        "✨ Finished! That was quick! ✨",
        "✅ Done! Smooth as silk!",
    ]
    return random.choice(messages)


def get_file_saved_message() -> str:
    """Get a fun message for file save operations."""
    messages = [
        "💾 File saved! Safe and sound!",
        "💾 All saved! Your file is secure!",
        "💾 Saved! Locked and loaded!",
        "💾 File stored! Ready when you need it!",
        "💾 Saved successfully! Your data is safe!",
    ]
    return random.choice(messages)


def get_email_sent_message() -> str:
    """Get a fun message for email sent operations."""
    messages = [
        "📧 Email sent! Off it goes!",
        "📧 Message delivered! Your email is on its way!",
        "📧 Email sent! Flying through cyberspace!",
        "📧 Delivered! Your message is out there!",
        "📧 Sent! Email is in the mail!",
    ]
    return random.choice(messages)


def get_bluesky_post_message() -> str:
    """Get a fun message for Bluesky post published."""
    messages = [
        "📱 Posted to Bluesky! Your message is out there!",
        "📱 Bluesky post published! Sharing your thoughts with the world!",
        "📱 Posted! Your Bluesky update is live!",
        "📱 Published to Bluesky! Your post is now public!",
        "📱 Posted successfully! Your Bluesky update is out!",
        "📱 Bluesky post is live! Your message is shared!",
    ]
    return random.choice(messages)


def get_message_for_action(action_type: str, context: Optional[str] = None) -> str:
    """
    Get a fun message based on action type.
    
    Args:
        action_type: Type of action (e.g., 'music_play', 'music_pause', 'confetti', 'success', etc.)
        context: Optional context for more specific messages
    
    Returns:
        Fun message with emojis
    """
    action_map = {
        "music_play": get_music_playing_message,
        "music_pause": get_music_paused_message,
        "confetti": get_confetti_message,
        "success": get_generic_success_message,
        "task_completed": get_task_completed_message,
        "file_saved": get_file_saved_message,
        "email_sent": get_email_sent_message,
        "bluesky_post": get_bluesky_post_message,
    }
    
    generator = action_map.get(action_type.lower())
    if generator:
        return generator()
    
    # Fallback to generic success
    return get_generic_success_message()

