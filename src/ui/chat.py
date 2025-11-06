"""
Terminal-based chat UI using Rich.
"""

import sys
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.table import Table
from rich import box


console = Console()


class ChatUI:
    """
    Simple terminal-based chat interface.
    """

    def __init__(self):
        """Initialize the chat UI."""
        self.console = console

    def show_welcome(self):
        """Display welcome message."""
        welcome_text = """
# Mac Automation Assistant

AI-powered document search and email automation for macOS.

**Commands:**
- Type your request naturally (e.g., "Send me the Tesla Autopilot doc - just the summary")
- `/index` - Reindex all documents
- `/test` - Test system components
- `/help` - Show help
- `/quit` - Exit

---
"""
        self.console.print(Panel(Markdown(welcome_text), border_style="blue"))

    def get_user_input(self) -> Optional[str]:
        """
        Get user input from terminal.

        Returns:
            User input string or None if quit
        """
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
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
