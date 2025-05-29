#!/usr/bin/env python3
"""Simple Mesop frontend to test basic functionality."""

import sys
from pathlib import Path

# Add project root to Python path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mesop as me
from dataclasses import field


@me.stateclass
class SimpleState:
    """Simple application state."""

    messages: list[str] = field(default_factory=list)
    current_input: str = ""
    agent_status: str = "Unknown"


@me.page(path="/", title="A2A Retail Demo - Simple")
def simple_page():
    """Simple test page."""
    state = me.state(SimpleState)

    with me.box(style=me.Style(padding=me.Padding.all(20))):
        me.text("🛍️ A2A Retail Demo", type="headline-4")
        me.text("Simple test interface", type="body-1", style=me.Style(color="gray", margin=me.Margin(bottom=20)))

        # Simple status
        with me.box(
            style=me.Style(
                background="#f5f5f5", padding=me.Padding.all(15), border_radius=8, margin=me.Margin(bottom=20)
            )
        ):
            me.text("Agent Status", type="subtitle-1")
            me.text(f"Status: {state.agent_status}")
            me.button("Check Status", on_click=check_status, type="stroked")

        # Simple chat
        with me.box(
            style=me.Style(
                border=me.Border.all(me.BorderSide(width=1, color="#e0e0e0")),
                padding=me.Padding.all(20),
                margin=me.Margin(bottom=20),
            )
        ):
            me.text("Messages:", type="subtitle-1")

            if state.messages:
                for msg in state.messages:
                    me.text(f"• {msg}")
            else:
                me.text("No messages yet", style=me.Style(color="gray"))

            # Input
            with me.box(style=me.Style(display="flex", gap=10, margin=me.Margin(top=20))):
                me.input(
                    label="Your message",
                    value=state.current_input,
                    on_input=on_input_change,
                    style=me.Style(flex_grow=1),
                )
                me.button("Send", on_click=send_message, type="raised")


def check_status(e: me.ClickEvent):
    """Check agent status."""
    state = me.state(SimpleState)

    try:
        import requests

        # Test inventory agent
        try:
            response = requests.get("http://localhost:8001/health", timeout=5)
            inventory_status = "Online" if response.status_code == 200 else "Offline"
        except:
            inventory_status = "Offline"

        # Test customer service agent
        try:
            response = requests.get("http://localhost:8002/health", timeout=5)
            customer_status = "Online" if response.status_code == 200 else "Offline"
        except:
            customer_status = "Offline"

        state.agent_status = f"Inventory: {inventory_status}, Customer Service: {customer_status}"
    except Exception as ex:
        state.agent_status = f"Error: {ex}"


def on_input_change(e: me.InputEvent):
    """Handle input change."""
    me.state(SimpleState).current_input = e.value


def send_message(e: me.ClickEvent):
    """Send a simple message."""
    state = me.state(SimpleState)

    if not state.current_input.strip():
        return

    # Add user message
    state.messages.append(f"You: {state.current_input}")

    # Simple echo response
    state.messages.append(f"Agent: I received your message: '{state.current_input}'")

    # Clear input
    state.current_input = ""


if __name__ == "__main__":
    import os

    HOST = os.environ.get("MESOP_HOST", "127.0.0.1")
    PORT = int(os.environ.get("MESOP_PORT", "8000"))

    print(f"🚀 Starting Simple Mesop UI on http://{HOST}:{PORT}")

    try:
        from werkzeug.serving import run_simple

        wsgi_app = me.create_wsgi_app()
        run_simple(HOST, PORT, wsgi_app, use_reloader=False, use_debugger=True)
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        import traceback

        traceback.print_exc()
