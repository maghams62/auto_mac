#!/usr/bin/env python3
"""
Web-based Chat UI for Cerebro OS
"""

import gradio as gr
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.utils import load_config, setup_logging
from src.utils.message_personality import get_task_completed_message
from src.workflow import WorkflowOrchestrator
from src.agent import AutomationAgent


# Initialize components
config = load_config()
setup_logging(config)
orchestrator = WorkflowOrchestrator(config)  # For indexing and stats
agent = AutomationAgent(config)  # For task execution


def process_message(message, history):
    """
    Process user message and return response.

    Args:
        message: User input message
        history: Chat history (list of [user_msg, assistant_msg] pairs)

    Returns:
        Updated history with new response
    """
    if not message or not message.strip():
        return history

    # Execute with LangGraph agent
    try:
        result = agent.run(message)

        status = (result or {}).get("status", "").lower() if result else ""

        if result and status in {"cancelled", "noop"} and not result.get("error"):
            ack_message = result.get("message") or ("Request cancelled." if status == "cancelled" else "Okay, I'll wait for your next request.")
            response = f"**Status:** {status.capitalize()}\n\n{ack_message}"
        elif result and not result.get('error'):
            # Build success response
            response = f"**{get_task_completed_message()}**\n\n"
            response += f"**Goal:** {result.get('goal', 'N/A')}\n\n"

            # Add step summary
            step_results = result.get('results', {})
            response += f"**Steps executed:** {result.get('steps_executed', 0)}\n\n"

            for step_id, step_result in step_results.items():
                if step_result.get("error"):
                    response += f"❌ Step {step_id}: {step_result.get('message', 'Error')}\n"
                else:
                    # Show relevant info from step
                    if 'doc_title' in step_result:
                        response += f"✓ Step {step_id}: Found document: {step_result['doc_title']}\n"
                    elif 'status' in step_result:
                        response += f"✓ Step {step_id}: Email {step_result['status']}\n"
                    elif 'keynote_path' in step_result:
                        response += f"✓ Step {step_id}: Created Keynote presentation\n"
                    elif 'pages_path' in step_result:
                        response += f"✓ Step {step_id}: Created Pages document\n"
                    elif 'screenshot_paths' in step_result:
                        count = len(step_result.get('screenshot_paths', []))
                        response += f"✓ Step {step_id}: Captured {count} screenshot(s)\n"
                    else:
                        response += f"✓ Step {step_id}: Completed\n"

            response += f"\n**Status:** {result.get('status', 'unknown')}"

        else:
            # Build error response
            error_msg = result.get('message', 'Unknown error occurred')
            response = f"❌ **Error:** {error_msg}"

    except Exception as e:
        response = f"❌ **Error:** {str(e)}"

    # Add to history
    history.append([message, response])
    return history


def get_system_stats():
    """Get system statistics."""
    stats = orchestrator.indexer.get_stats()
    return f"""
### System Status

- **Indexed Documents:** {stats['unique_files']}
- **Total Chunks:** {stats['total_chunks']}
- **Index Size:** {stats['index_size']}
- **Search Threshold:** {config['search']['similarity_threshold']}

### Commands

Type your request naturally, like:
- "Send me the Tesla Autopilot doc - just the summary"
- "Find the Q3 earnings report and email page 5 to john@example.com"
- "Take a screenshot of page 3 from the AI agents document"
"""


# Create Gradio interface
with gr.Blocks(title="Cerebro OS", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # 🤖 Cerebro OS

    AI-powered document search and email automation for macOS.
    """)

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(
                label="Chat",
                height=500,
                bubble_full_width=False,
                avatar_images=(None, "🤖")
            )

            with gr.Row():
                msg = gr.Textbox(
                    label="Message",
                    placeholder="Type your request here... (e.g., 'Find the AI agents document and email page 3 to me')",
                    scale=9,
                    lines=2
                )
                submit = gr.Button("Send", variant="primary", scale=1)

            gr.Examples(
                examples=[
                    "Find the document about AI agents and email it to spamstuff062@gmail.com",
                    "Send me a screenshot of page 3 from the Night We Met document",
                    "Find the Tesla document and send just the summary",
                ],
                inputs=msg,
                label="Example Queries"
            )

        with gr.Column(scale=1):
            stats_box = gr.Markdown(get_system_stats())
            refresh_btn = gr.Button("🔄 Refresh Stats")

            gr.Markdown("""
            ### Tips

            - Be specific about sections (e.g., "page 3", "summary")
            - Include email address if you want to send
            - Request screenshots for visual content
            - The system uses semantic search to find documents
            """)

    # Event handlers
    submit.click(
        process_message,
        inputs=[msg, chatbot],
        outputs=[chatbot]
    ).then(
        lambda: "",
        outputs=[msg]
    )

    msg.submit(
        process_message,
        inputs=[msg, chatbot],
        outputs=[chatbot]
    ).then(
        lambda: "",
        outputs=[msg]
    )

    refresh_btn.click(
        get_system_stats,
        outputs=[stats_box]
    )


if __name__ == "__main__":
    print("🚀 Starting Cerebro OS...")
    print("📊 Indexed documents:", orchestrator.indexer.get_stats()['unique_files'])
    print("🌐 Opening web interface...")

    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
