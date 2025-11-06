#!/usr/bin/env python3
"""
Mac Automation Assistant - Main Application

AI-powered document search and email automation for macOS.
"""

import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.utils import load_config, setup_logging, ensure_directories
from src.workflow import WorkflowOrchestrator
from src.agent import AutomationAgent
from src.ui import ChatUI


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

        logger.info("Starting Mac Automation Assistant")

        # Check for OpenAI API key
        if not config['openai']['api_key'] or config['openai']['api_key'].startswith('${'):
            print("Error: OPENAI_API_KEY environment variable not set")
            print("Please set it with: export OPENAI_API_KEY='your-key-here'")
            sys.exit(1)

        # Initialize workflow orchestrator (legacy)
        orchestrator = WorkflowOrchestrator(config)

        # Initialize LangGraph agent (new)
        agent = AutomationAgent(config)

        # Initialize chat UI
        ui = ChatUI()

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

            # Handle commands
            if user_input.startswith('/'):
                handle_command(user_input, ui, orchestrator)
                continue

            # Check for command-like input without slash
            normalized_input = user_input.lower().strip()
            if normalized_input in ['index', 'reindex', 'help', 'test', 'quit', 'exit']:
                ui.show_message(
                    f"💡 Did you mean '/{normalized_input}'? Commands start with /",
                    style="yellow"
                )
                handle_command(f"/{normalized_input}", ui, orchestrator)
                continue

            # Execute with LangGraph agent (task decomposition)
            ui.show_thinking("🤖 Agent analyzing and planning...")

            try:
                result = agent.run(user_input)

                # Display results
                if result and not result.get("error"):
                    ui.show_message("✅ Task completed successfully!", style="green")
                    ui.show_message(f"Goal: {result.get('goal', 'N/A')}", style="cyan")
                    ui.show_message(f"Steps executed: {result.get('steps_executed', 0)}", style="cyan")

                    # Show step results
                    for step_id, step_result in result.get("results", {}).items():
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


def handle_command(command: str, ui: ChatUI, orchestrator: WorkflowOrchestrator):
    """
    Handle special commands.

    Args:
        command: Command string
        ui: Chat UI instance
        orchestrator: Workflow orchestrator
    """
    command = command.lower().strip()

    if command == '/quit' or command == '/exit':
        ui.show_message("Goodbye!", style="cyan")
        sys.exit(0)

    elif command == '/help':
        ui.show_help()

    elif command == '/index':
        ui.show_thinking("Indexing documents... This may take a while.")

        try:
            result = orchestrator.reindex_documents()
            ui.show_indexing_result(result)
        except Exception as e:
            logger.error(f"Indexing error: {e}", exc_info=True)
            ui.show_message(f"Indexing error: {str(e)}", style="red")

    elif command == '/test':
        ui.show_thinking("Testing components...")

        try:
            results = orchestrator.test_components()
            ui.show_test_results(results)
        except Exception as e:
            logger.error(f"Test error: {e}", exc_info=True)
            ui.show_message(f"Test error: {str(e)}", style="red")

    else:
        ui.show_message(f"Unknown command: {command}", style="yellow")
        ui.show_message("Type /help for available commands", style="dim")


if __name__ == "__main__":
    main()
