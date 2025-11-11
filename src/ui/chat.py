"""
Terminal-based chat UI using Rich.
"""

import sys
from typing import Optional, Any
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.table import Table
from rich import box


console = Console()


class ChatUI:
    """
    Simple terminal-based chat interface with slash command support.
    """

    def __init__(self, slash_command_handler=None, session_manager=None):
        """
        Initialize the chat UI.

        Args:
            slash_command_handler: Optional SlashCommandHandler for direct agent access
            session_manager: Optional SessionManager for session state display
        """
        self.console = console
        self.slash_handler = slash_command_handler
        self.session_manager = session_manager
        self.session_id = None  # Will be set by main.py

    def show_welcome(self):
        """Display welcome message."""
        welcome_text = """
# Mac Automation Assistant

AI-powered automation with multi-agent coordination and LLM-driven decisions.

**Talk to Agents Directly:**
- `/files <task>` - File operations (organize, zip, search)
- `/browse <task>` - Web browsing and content extraction
- `/present <task>` - Create presentations and documents
- `/email <task>` - Compose and send emails
- `/maps <task>` - Plan trips with stops
- `/stock <task>` - Get stock prices and charts
- Type `/help` for all commands

**Or use natural language for complex tasks:**
- "Organize my PDFs by topic and email a summary"
- "Create a Keynote about AI trends with 5 slides"

**System Commands:**
- `/index` - Reindex documents
- `/agents` - List all agents
- `/clear` - Clear session memory
- `/quit` - Exit

---
"""
        self.console.print(Panel(Markdown(welcome_text), border_style="blue"))

        # Show initial session status
        self.show_session_status(is_new=True)

    def set_session_id(self, session_id: str):
        """Set the current session ID for UI display."""
        self.session_id = session_id

    def show_session_status(self, is_new: bool = False, just_cleared: bool = False):
        """
        Display session status indicator.

        Args:
            is_new: True if this is a brand new session
            just_cleared: True if session was just cleared
        """
        if not self.session_manager or not self.session_id:
            return

        memory = self.session_manager.get_or_create_session(self.session_id)

        if just_cleared:
            status_text = "🧹 [bold green]Session Cleared[/bold green] - Starting fresh"
            self.console.print(f"\n{status_text}\n", style="green")
        elif is_new or memory.is_new_session():
            status_text = "🆕 [bold cyan]New Session[/bold cyan] - No context loaded"
            self.console.print(f"\n{status_text}", style="cyan")
        else:
            interactions = len(memory.interactions)
            last_active = memory.last_active_at[:10] if memory.last_active_at else "Unknown"
            status_text = f"💬 [bold yellow]Session Active[/bold yellow] - {interactions} interactions | Last: {last_active}"
            self.console.print(f"\n{status_text}", style="yellow")

    def get_user_input(self) -> Optional[str]:
        """
        Get user input from terminal.

        Returns:
            User input string or None if quit
        """
        try:
            # Show session indicator in prompt
            if self.session_manager and self.session_id:
                memory = self.session_manager.get_or_create_session(self.session_id)
                if memory.is_new_session():
                    prompt_text = "[bold cyan]You[/bold cyan] [dim](new)[/dim]"
                else:
                    prompt_text = f"[bold cyan]You[/bold cyan] [dim](#{len(memory.interactions) + 1})[/dim]"
            else:
                prompt_text = "[bold cyan]You[/bold cyan]"

            user_input = Prompt.ask(f"\n{prompt_text}")
            return user_input.strip()
        except (KeyboardInterrupt, EOFError):
            return None

    def show_thinking(self, message: str = "Processing..."):
        """Show processing indicator."""
        self.console.print(f"[yellow]⚙ {message}[/yellow]")

    def show_result(self, result: dict):
        """
        Display workflow execution result.

        Args:
            result: Result dictionary from workflow
        """
        if result.get('success'):
            self._show_success(result)
        else:
            self._show_error(result)

    def _show_success(self, result: dict):
        """Display successful workflow result."""
        # Create steps table
        table = Table(title="Workflow Steps", box=box.ROUNDED, show_header=True)
        table.add_column("Step", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Details", style="white")

        for step in result.get('steps', []):
            status_icon = "✓" if step['status'] == 'success' else "✗"
            step_name = step['step'].replace('_', ' ').title()

            # Extract key details
            details = ""
            if step['step'] == 'search_documents':
                data = step.get('data', {})
                details = f"Found: {data.get('top_match', 'N/A')}"
            elif step['step'] == 'select_document':
                data = step.get('data', {})
                details = f"Similarity: {data.get('similarity', 0):.2f}"
            elif step['step'] == 'extract_content':
                data = step.get('data', {})
                details = f"Length: {data.get('content_length', 0)} chars"

            table.add_row(step_name, status_icon, details)

        self.console.print(table)

        # Show summary
        summary = result.get('summary', 'Workflow completed successfully')
        self.console.print(Panel(
            f"[green]✓ {summary}[/green]\n\nEmail draft opened in Mail.app!",
            border_style="green",
            title="Success"
        ))

    def _show_error(self, result: dict):
        """Display workflow error."""
        error_msg = result.get('error', 'Unknown error occurred')

        # Show completed steps
        if result.get('steps'):
            table = Table(title="Completed Steps", box=box.ROUNDED)
            table.add_column("Step", style="cyan")
            table.add_column("Status")

            for step in result['steps']:
                status = "✓" if step['status'] == 'success' else "✗"
                status_color = "green" if step['status'] == 'success' else "red"
                step_name = step['step'].replace('_', ' ').title()
                table.add_row(step_name, f"[{status_color}]{status}[/{status_color}]")

            self.console.print(table)

        # Show error
        self.console.print(Panel(
            f"[red]✗ {error_msg}[/red]",
            border_style="red",
            title="Error"
        ))

    def show_indexing_result(self, result: dict):
        """Display indexing result."""
        if result.get('success'):
            stats = result.get('stats', {})
            message = f"""
[green]✓ Indexing completed successfully![/green]

**Statistics:**
- Documents indexed: {result.get('indexed_documents', 0)}
- Total chunks: {stats.get('total_chunks', 0)}
- Unique files: {stats.get('unique_files', 0)}
"""
            self.console.print(Panel(Markdown(message), border_style="green"))
        else:
            error = result.get('error', 'Unknown error')
            self.console.print(Panel(
                f"[red]✗ Indexing failed: {error}[/red]",
                border_style="red"
            ))

    def show_test_results(self, results: dict):
        """Display component test results."""
        table = Table(title="Component Tests", box=box.ROUNDED)
        table.add_column("Component", style="cyan")
        table.add_column("Status")

        for component, status in results.items():
            status_icon = "✓" if status else "✗"
            status_color = "green" if status else "red"
            component_name = component.replace('_', ' ').title()
            table.add_row(
                component_name,
                f"[{status_color}]{status_icon}[/{status_color}]"
            )

        self.console.print(table)

    def show_help(self):
        """Display help message."""
        help_text = """
# Help

## Usage Examples

**Find and email a document:**
```
"Send me the Tesla Autopilot doc — just the summary"
"Find the Q3 earnings report and email page 5 to john@example.com"
"Get me the machine learning paper, introduction section"
```

## Commands

- `/index` - Reindex all documents in configured folders
- `/test` - Test system components (Mail.app, OpenAI API, FAISS index)
- `/help` - Show this help message
- `/x "Summarize tweets over the past 6 hours in list:product_watch"` - Summarize configured Twitter lists
- `/quit` - Exit the application

## Tips

- Be specific about what section you want (e.g., "summary", "page 10", "introduction")
- The system will find the most relevant document based on semantic search
- Email drafts are opened in Mail.app for review before sending
"""
        self.console.print(Panel(Markdown(help_text), border_style="blue"))

    def show_message(self, message: str, style: str = ""):
        """
        Show a general message.

        Args:
            message: Message to display
            style: Rich style string
        """
        if style:
            self.console.print(f"[{style}]{message}[/{style}]")
        else:
            self.console.print(message)

    def confirm(self, message: str) -> bool:
        """
        Ask for user confirmation.

        Args:
            message: Confirmation message

        Returns:
            True if user confirms, False otherwise
        """
        response = Prompt.ask(message, choices=["y", "n"], default="n")
        return response.lower() == 'y'

    def handle_slash_command(self, message: str) -> tuple[bool, Any]:
        """
        Check if message is a slash command and handle it.

        Args:
            message: User message

        Returns:
            Tuple of (is_command, result)
        """
        if not self.slash_handler:
            return False, None

        return self.slash_handler.handle(message)

    def show_slash_result(self, result: dict):
        """
        Display slash command result.

        Args:
            result: Result from slash command handler
        """
        result_type = result.get("type")

        if result_type == "help":
            # Show help text
            self.console.print(Panel(
                Markdown(result["content"]),
                border_style="blue",
                title="📘 Help"
            ))

        elif result_type == "palette":
            self.console.print(Panel(
                Markdown(result["content"]),
                border_style="magenta",
                title="⌨️ Slash Commands"
            ))

        elif result_type == "agents":
            # Show agents list
            self.console.print(Panel(
                Markdown(result["content"]),
                border_style="cyan",
                title="🤖 Available Agents"
            ))

        elif result_type == "error":
            # Show error
            self.console.print(Panel(
                result["content"],
                border_style="red",
                title="❌ Error"
            ))

        elif result_type == "result":
            # Show agent execution result
            agent = result.get("agent", "unknown")
            command = result.get("command", "unknown")
            exec_result = result.get("result", {})

            # Format based on result type
            if exec_result.get("error"):
                self.console.print(Panel(
                    f"[red]✗ {exec_result.get('error_message', 'Unknown error')}[/red]",
                    border_style="red",
                    title=f"/{command} - Error"
                ))
            else:
                self._show_agent_success(agent, command, exec_result)

    def _show_agent_success(self, agent: str, command: str, result: dict):
        """Show successful agent execution."""
        lines = [f"[green]✓ {agent.title()} Agent - Success[/green]\n"]

        # Check for Maps URL - prioritize top level (from orchestrator extraction), then nested
        maps_result = None
        if "maps_url" in result:
            # Top-level Maps URL (extracted by orchestrator)
            maps_result = result
        elif "step_results" in result and isinstance(result["step_results"], dict):
            # Check step_results for Maps URLs
            for step_result in result["step_results"].values():
                if isinstance(step_result, dict) and "maps_url" in step_result:
                    maps_result = step_result
                    break
        elif "results" in result and isinstance(result["results"], dict):
            # Check results for Maps URLs (legacy format)
            for step_result in result["results"].values():
                if isinstance(step_result, dict) and "maps_url" in step_result:
                    maps_result = step_result
                    break
        
        # Use Maps result if found
        if maps_result:
            result = maps_result

        # Format based on what's in the result
        if "files_moved" in result:
            # File organization result
            lines.append(f"**Files organized:** {len(result['files_moved'])}")
            lines.append(f"**Files skipped:** {len(result.get('files_skipped', []))}")
            lines.append(f"**Target:** {result.get('target_path', 'N/A')}")

            if result.get('reasoning'):
                lines.append(f"\n**Sample reasoning:**")
                for filename, reason in list(result['reasoning'].items())[:2]:
                    lines.append(f"  • {filename}")
                    lines.append(f"    → {reason[:80]}...")

        elif "zip_path" in result:
            # ZIP creation result
            lines.append(f"**ZIP created:** {result['zip_path']}")
            lines.append(f"**Files:** {result.get('file_count', 0)}")
            lines.append(f"**Size:** {result.get('total_size', 0):,} bytes")
            lines.append(f"**Compressed:** {result.get('compressed_size', 0):,} bytes")
            lines.append(f"**Compression:** {result.get('compression_ratio', 0)}%")

        elif "keynote_path" in result:
            # Keynote creation result
            lines.append(f"**Presentation created:** {result['keynote_path']}")
            lines.append(f"**Slides:** {result.get('slide_count', 0)}")

        elif "pages_path" in result:
            # Pages creation result
            lines.append(f"**Document created:** {result['pages_path']}")

        elif "status" in result:
            # Email result
            lines.append(f"**Status:** {result['status']}")
            lines.append(f"**Message:** {result.get('message', 'N/A')}")

        elif "maps_url" in result:
            # Maps result - show simple, clean message with URL
            maps_url = result['maps_url']
            
            # Convert maps:// URLs to https://maps.apple.com/ for better compatibility
            if maps_url.startswith("maps://"):
                maps_url = maps_url.replace("maps://", "https://maps.apple.com/", 1)
            
            # Use the simple message if provided, otherwise create one
            if "message" in result:
                lines.append(result["message"])
            else:
                lines.append(f"Here's your trip, enjoy: {maps_url}")
            
            # Make URL clickable using Rich link syntax
            lines.append(f"\n[link={maps_url}]{maps_url}[/link]")
            
            # Try to open automatically
            try:
                import subprocess
                subprocess.run(["open", maps_url], check=False)
                lines.append("\n💡 Opening Apple Maps...")
            except:
                lines.append(f"\n💡 Click the URL above or run: open '{maps_url}'")

        elif "summary" in result:
            # Google search with LLM summary
            lines.append(f"**Query:** {result.get('query', 'N/A')}")
            lines.append(f"\n**Summary:**")
            lines.append(result['summary'])
            if result.get('num_results'):
                lines.append(f"\n**Found:** {result.get('num_results')} results")
                if result.get('total_results'):
                    lines.append(f"**Total matches:** {result.get('total_results'):,}")
        
        else:
            # Generic result
            lines.append("**Result:**")
            for key, value in list(result.items())[:5]:
                if key not in ['error', 'error_type', 'retry_possible', 'summary', 'results']:
                    lines.append(f"  • {key}: {str(value)[:80]}")

        self.console.print(Panel(
            "\n".join(lines),
            border_style="green",
            title=f"✓ /{command}"
        ))

    def show_twitter_summary(self, result: dict):
        """
        Display Twitter list summary output.
        """
        if result.get("error"):
            self.show_message(f"Twitter summary error: {result.get('error_message', 'Unknown error')}", style="red")
            return

        list_name = result.get("list_name", "twitter")
        header = f"# Twitter Summary — {list_name}\n\n{result.get('summary', '').strip()}"
        self.console.print(Panel(Markdown(header), border_style="cyan"))

        items = result.get("items") or []
        if not items:
            return

        table = Table(title="Highlighted Tweets", box=box.ROUNDED, show_header=True)
        table.add_column("#", style="cyan", no_wrap=True)
        table.add_column("Author", style="magenta")
        table.add_column("Score", style="green")
        table.add_column("Link", style="blue")

        for idx, item in enumerate(items, start=1):
            table.add_row(
                f"{idx}",
                f"{item.get('author_name', '')} (@{item.get('author_handle', '')})",
                f"{item.get('score', 0):.1f}",
                item.get("url", "")
            )

        self.console.print(table)
