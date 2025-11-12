#!/usr/bin/env python3
"""
Cerebro OS - Main Application

AI-powered document search and email automation for macOS.
"""

import sys
import logging
import re
from typing import Dict
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
# Explicitly load from project root to ensure we get the API key
project_root = Path(__file__).parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path, override=False)
else:
    # Fallback to find_dotenv() behavior
    load_dotenv(override=False)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.utils import load_config, setup_logging, ensure_directories
from src.utils.message_personality import get_task_completed_message
from src.workflow import WorkflowOrchestrator
from src.agent import AutomationAgent
from src.agent.agent_registry import AgentRegistry
from src.memory import SessionManager
from src.ui import ChatUI
from src.ui.slash_commands import create_slash_command_handler


logger = logging.getLogger(__name__)


def main():
    """Main application entry point."""
    try:
        # Ensure directories exist
        ensure_directories()

        # Load configuration
        config = load_config()

        # Setup logging
        setup_logging(config)

        logger.info("Starting Cerebro OS")

        # Check for OpenAI API key
        if not config['openai']['api_key'] or config['openai']['api_key'].startswith('${'):
            print("Error: OPENAI_API_KEY environment variable not set")
            print("Please set it with: export OPENAI_API_KEY='your-key-here'")
            sys.exit(1)

        # Initialize session manager
        session_manager = SessionManager(storage_dir="data/sessions", config=config)
        session_id = "default"  # Single-user mode
        logger.info(f"Session manager initialized with session ID: {session_id}")

        # Initialize agent registry with session support
        agent_registry = AgentRegistry(config, session_manager=session_manager)

        # Initialize workflow orchestrator (legacy) with session support
        orchestrator = WorkflowOrchestrator(config)

        # Initialize LangGraph agent with session support
        agent = AutomationAgent(config, session_manager=session_manager)

        # Initialize slash command handler with session support and config
        slash_handler = create_slash_command_handler(agent_registry, session_manager, config)

        # Initialize chat UI with session support
        ui = ChatUI(slash_command_handler=slash_handler, session_manager=session_manager)
        ui.set_session_id(session_id)

        # Show welcome message
        ui.show_welcome()

        # Check if index exists
        if len(orchestrator.indexer.documents) == 0:
            ui.show_message(
                "⚠ No documents indexed yet. Run `/index` to index your documents.",
                style="yellow"
            )

        # Main interaction loop
        while True:
            # Get user input
            user_input = ui.get_user_input()

            if user_input is None:
                # User pressed Ctrl+C or Ctrl+D
                ui.show_message("\nGoodbye!", style="cyan")
                break

            if not user_input:
                continue

            # Handle commands (including slash commands)
            if user_input.startswith('/'):
                # Try slash commands first
                is_slash_cmd, result = slash_handler.handle(user_input, session_id)
                if is_slash_cmd:
                    # Display slash command result
                    if result.get("type") == "clear":
                        ui.show_session_status(just_cleared=True)
                    else:
                        ui.show_slash_result(result)
                    continue

                # Fall back to legacy commands
                handle_command(user_input, ui, orchestrator, config)
                continue

            # Check for command-like input without slash
            normalized_input = user_input.lower().strip()
            if normalized_input in ['index', 'reindex', 'help', 'test', 'quit', 'exit']:
                ui.show_message(
                    f"💡 Did you mean '/{normalized_input}'? Commands start with /",
                    style="yellow"
                )
                handle_command(f"/{normalized_input}", ui, orchestrator, config)
                continue

            # Execute with LangGraph agent (task decomposition) with session context
            ui.show_thinking("🤖 Agent analyzing and planning...")

            try:
                result = agent.run(user_input, session_id=session_id)

                # Display results
                if result and not result.get("error"):
                    # Check for Maps URL - prioritize top level, then nested
                    maps_url_found = False
                    maps_url = None
                    service = None
                    origin = None
                    destination = None
                    stops = None
                    
                    # Check top level first (extracted by orchestrator)
                    if "maps_url" in result:
                        maps_url_found = True
                        maps_url = result.get("maps_url", "")
                        service = result.get("maps_service", "Apple Maps")
                        origin = result.get("origin", "N/A")
                        destination = result.get("destination", "N/A")
                        stops = result.get("stops", [])
                        simple_message = result.get("message", f"Here's your trip, enjoy: {maps_url}")
                    # Check results (agent.finalize uses "results" key)
                    elif "results" in result and isinstance(result["results"], dict):
                        for step_id, step_result in result["results"].items():
                            if isinstance(step_result, dict) and "maps_url" in step_result:
                                maps_url_found = True
                                maps_url = step_result.get("maps_url", "")
                                service = step_result.get("maps_service", "Apple Maps")
                                origin = step_result.get("origin", "N/A")
                                destination = step_result.get("destination", "N/A")
                                stops = step_result.get("stops", [])
                                # Get message from the step result, not top level
                                simple_message = step_result.get("message", f"Here's your trip, enjoy: {maps_url}")
                                break
                    # Check step_results (alternative format)
                    elif "step_results" in result and isinstance(result["step_results"], dict):
                        for step_result in result["step_results"].values():
                            if isinstance(step_result, dict) and "maps_url" in step_result:
                                maps_url_found = True
                                maps_url = step_result.get("maps_url", "")
                                service = step_result.get("maps_service", "Apple Maps")
                                origin = step_result.get("origin", "N/A")
                                destination = step_result.get("destination", "N/A")
                                stops = step_result.get("stops", [])
                                simple_message = step_result.get("message", f"Here's your trip, enjoy: {maps_url}")
                                break
                    
                    if maps_url_found:
                        # Convert maps:// URLs to https://maps.apple.com/ for better compatibility
                        # Also fix the URL format if it uses "via" - convert to multiple daddr parameters
                        if maps_url.startswith("maps://"):
                            maps_url = maps_url.replace("maps://", "https://maps.apple.com/", 1)
                        
                        # Fix URL format if it uses "via" in daddr (incorrect format)
                        # Convert: daddr=DEST via STOP1, STOP2 to daddr=STOP1&daddr=STOP2&daddr=DEST
                        from urllib.parse import unquote, quote, urlparse, parse_qs, urlencode, urlunparse
                        import logging
                        logger = logging.getLogger(__name__)
                        
                        try:
                            parsed = urlparse(maps_url)
                            params = parse_qs(parsed.query, keep_blank_values=True)
                            
                            # Check if daddr contains "via" (check both encoded and decoded)
                            if 'daddr' in params:
                                daddr_values = params['daddr']
                                # Check if any daddr value contains "via" (URL-decoded)
                                for daddr_val in daddr_values:
                                    decoded = unquote(daddr_val)
                                    if ' via ' in decoded.lower():
                                        # Parse the via format: "DEST via STOP1, STOP2, STOP3"
                                        # Each stop is typically "City, State, Country" format
                                        parts = decoded.split(' via ', 1)
                                        destination = parts[0].strip()
                                        stops_str = parts[1].strip()
                                        
                                        # Smart splitting: look for patterns like "City, State, Country"
                                        # Try to split by ", " but group locations together
                                        # Pattern: "City1, State1, Country1, City2, State2, Country2"
                                        # We need to group every 3 comma-separated parts as one location
                                        all_parts = [s.strip() for s in stops_str.split(',')]
                                        
                                        # Group into locations (assuming format: City, State, Country)
                                        stops_list = []
                                        i = 0
                                        while i < len(all_parts):
                                            # Try to group 3 parts as one location
                                            if i + 2 < len(all_parts):
                                                location = f"{all_parts[i]}, {all_parts[i+1]}, {all_parts[i+2]}"
                                                stops_list.append(location)
                                                i += 3
                                            else:
                                                # If not enough parts, just add remaining
                                                stops_list.append(all_parts[i])
                                                i += 1
                                        
                                        # Rebuild URL with proper format
                                        new_params = {}
                                        if 'saddr' in params:
                                            new_params['saddr'] = params['saddr'][0]
                                        # Add stops as separate daddr parameters
                                        for stop in stops_list:
                                            if 'daddr' not in new_params:
                                                new_params['daddr'] = []
                                            new_params['daddr'].append(stop)
                                        # Add destination as final daddr
                                        if 'daddr' not in new_params:
                                            new_params['daddr'] = []
                                        new_params['daddr'].append(destination)
                                        if 'dirflg' in params:
                                            new_params['dirflg'] = params['dirflg'][0]
                                        
                                        # Rebuild URL
                                        new_query = urlencode(new_params, doseq=True)
                                        maps_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
                                        logger.info(f"[MAIN] Fixed URL format from via to multiple daddr parameters")
                                        break
                        except Exception as e:
                            logger.warning(f"[MAIN] Could not fix URL format: {e}")
                        
                        # Display simple, clean message with URL (skip all step details)
                        ui.show_message(f"\n{simple_message}", style="cyan")
                        
                        # Display clickable URL using Rich
                        from rich.panel import Panel
                        ui.console.print(Panel(
                            f"[link={maps_url}]{maps_url}[/link]",
                            border_style="bright_cyan",
                            title="📍 Maps URL - Click to Open"
                        ))
                        
                        # Also provide a command to open it programmatically
                        import subprocess
                        import logging
                        logger = logging.getLogger(__name__)
                        try:
                            # Try to open the URL automatically
                            result = subprocess.run(["open", maps_url], check=False, capture_output=True, timeout=2)
                            if result.returncode == 0:
                                ui.show_message("💡 Opening Apple Maps...", style="green")
                            else:
                                ui.show_message(f"💡 Click the URL above or run: open '{maps_url}'", style="yellow")
                        except Exception as e:
                            logger.warning(f"Could not auto-open Maps URL: {e}")
                            ui.show_message(f"💡 Click the URL above or run: open '{maps_url}'", style="yellow")
                    else:
                        # Prefer human-friendly reply payload if present
                        step_results = result.get("results", {}) or {}
                        reply_payload = None

                        reply_step_id = result.get("reply_step_id")
                        if reply_step_id is not None and step_results.get(reply_step_id):
                            reply_payload = step_results.get(reply_step_id)
                        else:
                            for candidate in step_results.values():
                                if isinstance(candidate, dict) and candidate.get("type") == "reply":
                                    reply_payload = candidate
                                    break

                        if reply_payload:
                            status_map = {
                                "success": ("✅", "green"),
                                "partial_success": ("⚠", "yellow"),
                                "info": ("ℹ", "cyan"),
                                "error": ("❌", "red"),
                            }
                            status = reply_payload.get("status", result.get("status", "success"))
                            icon, style = status_map.get(status, ("✅", "green"))
                            message_text = reply_payload.get("message") or get_task_completed_message()
                            ui.show_message(f"{icon} {message_text}", style=style)

                            details_text = (reply_payload.get("details") or "").strip()
                            if details_text:
                                from rich.panel import Panel
                                from rich.markdown import Markdown
                                ui.console.print(Panel(Markdown(details_text), border_style="blue", title="Details"))

                            artifacts = [a for a in reply_payload.get("artifacts", []) if a]
                            if artifacts:
                                from rich.panel import Panel
                                artifact_lines = "\n".join(f"- {artifact}" for artifact in artifacts)
                                ui.console.print(Panel(artifact_lines, border_style="cyan", title="📎 Artifacts"))
                        else:
                            ui.show_message(get_task_completed_message(), style="green")

                        ui.show_message(f"Goal: {result.get('goal', 'N/A')}", style="cyan")
                        ui.show_message(f"Steps executed: {result.get('steps_executed', 0)}", style="cyan")
                        
                        for step_id, step_result in step_results.items():
                            if isinstance(step_result, dict) and step_result.get("type") == "reply":
                                continue
                            if step_result.get("error"):
                                ui.show_message(f"❌ Step {step_id}: {step_result.get('message', 'Error')}", style="red")
                            else:
                                ui.show_message(f"✓ Step {step_id}: Success", style="green")
                else:
                    ui.show_message(f"❌ Error: {result.get('message', 'Unknown error')}", style="red")

            except Exception as e:
                logger.error(f"Agent execution error: {e}", exc_info=True)
                ui.show_message(f"Error: {str(e)}", style="red")

    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        print(f"Fatal error: {e}")
        sys.exit(1)


def handle_command(command: str, ui: ChatUI, orchestrator: WorkflowOrchestrator, config: dict):
    """
    Handle special commands.

    Args:
        command: Command string
        ui: Chat UI instance
        orchestrator: Workflow orchestrator
    """
    raw_command = command.strip()
    lower_command = raw_command.lower()

    if lower_command.startswith('/x'):
        handle_twitter_slash(raw_command, ui, config)
        return

    if lower_command == '/quit' or lower_command == '/exit':
        ui.show_message("Goodbye!", style="cyan")
        sys.exit(0)

    elif lower_command == '/help':
        ui.show_help()

    elif lower_command == '/index':
        ui.show_thinking("Indexing documents... This may take a while.")

        try:
            result = orchestrator.reindex_documents()
            ui.show_indexing_result(result)
        except Exception as e:
            logger.error(f"Indexing error: {e}", exc_info=True)
            ui.show_message(f"Indexing error: {str(e)}", style="red")

    elif lower_command == '/test':
        ui.show_thinking("Testing components...")

        try:
            results = orchestrator.test_components()
            ui.show_test_results(results)
        except Exception as e:
            logger.error(f"Test error: {e}", exc_info=True)
            ui.show_message(f"Test error: {str(e)}", style="red")

    else:
        ui.show_message(f"Unknown command: {raw_command}", style="yellow")
        ui.show_message("Type /help for available commands", style="dim")


def handle_twitter_slash(command: str, ui: ChatUI, config: dict):
    """Handle the /x Twitter summarizer command."""
    body = command[2:].strip()
    if not body:
        ui.show_message('Usage: /x "Summarize tweets over the past 6 hours in list:product_watch"', style="yellow")
        return

    if not config.get("twitter"):
        ui.show_message("Twitter configuration missing in config.yaml.", style="red")
        return

    try:
        params = parse_twitter_command(body, config)
    except ValueError as exc:
        ui.show_message(f"⚠ {exc}", style="yellow")
        return

    registry = AgentRegistry(config)
    ui.show_thinking("🧵 Fetching Twitter threads...")
    result = registry.execute_tool("summarize_list_activity", params)
    if result.get("error"):
        ui.show_message(f"❌ Twitter summarizer failed: {result.get('error_message', 'Unknown error')}", style="red")
    else:
        ui.show_twitter_summary(result)


def parse_twitter_command(body: str, config: dict) -> Dict[str, Any]:
    """Parse list name and lookback window from the /x command body."""
    twitter_cfg = config.get("twitter") or {}
    lists_map = twitter_cfg.get("lists") or {}
    default_list = twitter_cfg.get("default_list")

    match = re.search(r'list:([a-zA-Z0-9_\-]+)', body, re.IGNORECASE)
    list_name = None
    if match:
        candidate = match.group(1).lower()
        if candidate in lists_map:
            list_name = candidate
        else:
            raise ValueError(f"List '{candidate}' is not defined in config.yaml.")
    elif default_list and default_list in lists_map:
        list_name = default_list

    if not list_name:
        raise ValueError("No valid list provided. Use syntax list:<name> matching config.yaml.")

    hours = twitter_cfg.get("default_lookback_hours", 24)
    time_match = re.search(r'(\d+)\s*(hour|hr|h)\b', body, re.IGNORECASE)
    day_match = re.search(r'(\d+)\s*(day|d)\b', body, re.IGNORECASE)
    if time_match:
        hours = int(time_match.group(1))
    elif day_match:
        hours = int(day_match.group(1)) * 24

    hours = max(1, min(hours, 168))

    max_items = twitter_cfg.get("max_summary_items", 5)

    return {
        "list_name": list_name,
        "lookback_hours": hours,
        "max_items": max_items,
    }


if __name__ == "__main__":
    main()
