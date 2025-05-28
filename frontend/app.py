"""Simplified Frontend for A2A Retail Demo."""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field
import uuid

import mesop as me
import httpx
from a2a.client import A2AClient
from a2a.types import (
    Message,
    Part,
    Role,
    TextPart,
    SendMessageRequest,
    MessageSendParams,
    MessageSendConfiguration,
    Task,
    TaskState,
)
from a2a.utils import get_message_text

# Add project root to Python path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@me.stateclass
class AppState:
    """Application state."""
    messages: List[dict] = field(default_factory=list)
    current_input: str = ""
    is_loading: bool = False
    error_message: Optional[str] = None
    
    # Agent status
    host_agent_online: bool = False
    inventory_agent_online: bool = False
    customer_service_agent_online: bool = False
    
    # Configuration
    host_agent_url: str = "http://localhost:8000"
    show_debug: bool = False
    
    # Context management
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))


async def check_agent_status_async() -> dict:
    """Check the status of all agents asynchronously."""
    agents = {
        "host": "http://localhost:8000",
        "inventory": "http://localhost:8001",
        "customer_service": "http://localhost:8002",
    }
    
    status = {}
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in agents.items():
            try:
                # Try to get agent card
                a2a_client = await A2AClient.get_client_from_agent_card_url(
                    httpx_client=client,
                    base_url=url
                )
                status[name] = True
            except Exception:
                status[name] = False
    
    return status


def check_agent_status():
    """Check the status of all agents."""
    state = me.state(AppState)
    
    # Run async function synchronously
    try:
        status = asyncio.run(check_agent_status_async())
        state.host_agent_online = status.get("host", False)
        state.inventory_agent_online = status.get("inventory", False)
        state.customer_service_agent_online = status.get("customer_service", False)
    except Exception as e:
        state.error_message = f"Error checking agent status: {str(e)}"


async def send_message_to_host_async(message_text: str, context_id: str) -> str:
    """Send message to host agent via A2A asynchronously."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get A2A client
            a2a_client = await A2AClient.get_client_from_agent_card_url(
                httpx_client=client,
                base_url="http://localhost:8000"
            )
            
            # Create message
            message = Message(
                messageId=str(uuid.uuid4()),
                contextId=context_id,
                role=Role.user,
                parts=[Part(root=TextPart(text=message_text))]
            )
            
            # Create request
            request = SendMessageRequest(
                params=MessageSendParams(
                    message=message,
                    configuration=MessageSendConfiguration(
                        acceptedOutputModes=["text/plain", "text"]
                    )
                )
            )
            
            # Send message
            response = await a2a_client.send_message(request)
            
            # Extract response
            if hasattr(response, 'root'):
                result = response.root.result
            else:
                result = response.result if hasattr(response, 'result') else response
            
            # Handle different response types
            if isinstance(result, Task):
                # Task response
                if result.artifacts:
                    # Extract text from artifacts
                    texts = []
                    for artifact in result.artifacts:
                        for part in artifact.parts:
                            if hasattr(part, 'root') and hasattr(part.root, 'text'):
                                texts.append(part.root.text)
                    return "\n".join(texts) if texts else "Task completed with no text response"
                elif result.status and result.status.message:
                    return get_message_text(result.status.message)
                else:
                    return f"Task {result.id} status: {result.status.state if result.status else 'unknown'}"
            
            elif isinstance(result, Message):
                # Direct message response
                return get_message_text(result)
            
            else:
                return "Received response but unable to extract text"
                
    except Exception as e:
        return f"Error communicating with host agent: {str(e)}"


def on_input_change(e: me.InputEvent):
    """Handle input field changes."""
    me.state(AppState).current_input = e.value


async def on_send_message(e: me.ClickEvent):
    """Handle send message button click."""
    state = me.state(AppState)
    
    if not state.current_input.strip():
        return
    
    # Add user message
    user_message = {
        "role": "user",
        "content": state.current_input,
        "timestamp": datetime.now().isoformat(),
    }
    state.messages.append(user_message)
    
    message_text = state.current_input
    state.current_input = ""
    state.is_loading = True
    state.error_message = None
    
    yield  # Update UI to show user message
    
    try:
        # Send to host agent
        response = await send_message_to_host_async(message_text, state.context_id)
        
        # Add agent response
        agent_message = {
            "role": "agent", 
            "content": response,
            "timestamp": datetime.now().isoformat(),
        }
        state.messages.append(agent_message)
        
    except Exception as e:
        state.error_message = f"Error: {str(e)}"
    finally:
        state.is_loading = False
        yield  # Update UI with response


def on_refresh_status(e: me.ClickEvent):
    """Handle refresh status button click."""
    check_agent_status()


def on_clear_chat(e: me.ClickEvent):
    """Handle clear chat button click."""
    state = me.state(AppState)
    state.messages = []
    state.error_message = None
    # Generate new context ID for new conversation
    state.context_id = str(uuid.uuid4())


def on_toggle_debug(e: me.ClickEvent):
    """Toggle debug information display."""
    state = me.state(AppState)
    state.show_debug = not state.show_debug


def agent_status_card(name: str, online: bool, port: int):
    """Render an agent status card."""
    color = "#4caf50" if online else "#f44336"
    status = "Online" if online else "Offline"
    
    with me.box(
        style=me.Style(
            border=me.Border.all(me.BorderSide(width=2, color=color)),
            border_radius=6,
            padding=me.Padding.all(8),
            margin=me.Margin(right=10),
            min_width="160px",
        )
    ):
        me.text(name, type="subtitle-2")
        me.text(f"{status} • :{port}", style=me.Style(color=color))


def chat_message_bubble(message: dict):
    """Render a chat message bubble."""
    is_user = message["role"] == "user"
    align = "flex-end" if is_user else "flex-start"
    bg = "#1976d2" if is_user else "#e0e0e0"
    fg = "white" if is_user else "black"
    
    timestamp = message.get("timestamp", "")
    try:
        when = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%H:%M:%S")
    except:
        when = ""
    
    with me.box(style=me.Style(display="flex", justify_content=align, margin=me.Margin(bottom=10))):
        with me.box(
            style=me.Style(
                max_width="70%",
                background=bg,
                color=fg,
                padding=me.Padding.all(12),
                border_radius=8,
            )
        ):
            # Support markdown in responses
            if is_user:
                me.text(message["content"])
            else:
                me.markdown(message["content"])
            
            if when:
                me.text(when, type="caption", style=me.Style(opacity=0.7, margin=me.Margin(top=5)))


@me.page(path="/", title="A2A Retail Demo")
def main_page():
    """Main application page."""
    state = me.state(AppState)
    
    # Check agent status on page load
    if not any([state.host_agent_online, state.inventory_agent_online, state.customer_service_agent_online]):
        check_agent_status()
    
    with me.box(style=me.Style(padding=me.Padding.all(20))):
        me.text("🛍️ A2A Retail Demo", type="headline-4", style=me.Style(margin=me.Margin(bottom=10)))
        me.text(
            "Demonstrating Google's Agent-to-Agent protocol with specialized retail agents",
            type="body-1",
            style=me.Style(margin=me.Margin(bottom=30), color="gray"),
        )
        
        # Agent status section
        with me.box(
            style=me.Style(
                background="#f5f5f5",
                padding=me.Padding.all(15),
                border_radius=8,
                margin=me.Margin(bottom=20),
            )
        ):
            me.text("Agent Status", type="subtitle-1")
            with me.box(style=me.Style(display="flex", margin=me.Margin(top=10), flex_wrap="wrap")):
                agent_status_card("Host Agent", state.host_agent_online, 8000)
                agent_status_card("Inventory Agent", state.inventory_agent_online, 8001)
                agent_status_card("Customer Service", state.customer_service_agent_online, 8002)
            
            with me.box(style=me.Style(margin=me.Margin(top=10))):
                me.button("Refresh Status", on_click=on_refresh_status, type="stroked")
                me.button("Clear Chat", on_click=on_clear_chat, type="stroked", style=me.Style(margin=me.Margin(left=10)))
                me.button("Debug Info", on_click=on_toggle_debug, type="stroked", style=me.Style(margin=me.Margin(left=10)))
        
        # Error display
        if state.error_message:
            with me.box(
                style=me.Style(
                    background="#ffebee",
                    border=me.Border.all(me.BorderSide(width=1, color="#f44336")),
                    border_radius=4,
                    padding=me.Padding.all(10),
                    margin=me.Margin(bottom=20),
                )
            ):
                me.text(state.error_message, style=me.Style(color="#d32f2f"))
        
        # Chat area
        with me.box(
            style=me.Style(
                border=me.Border.all(me.BorderSide(width=1, color="#e0e0e0")),
                border_radius=8,
                padding=me.Padding.all(20),
                min_height="400px",
                margin=me.Margin(bottom=20),
            )
        ):
            # Chat history
            with me.box(
                style=me.Style(
                    height="400px",
                    overflow_y="auto",
                    padding=me.Padding.all(10),
                    background="#fafafa",
                    border_radius=4,
                    margin=me.Margin(bottom=20),
                )
            ):
                if not state.messages:
                    me.text(
                        "🤖 Welcome! I'm your retail assistant powered by A2A protocol.",
                        style=me.Style(color="gray", font_style="italic"),
                    )
                    me.text("Try asking:", style=me.Style(margin=me.Margin(top=10), font_weight="bold"))
                    me.text("• 'Do you have Smart TVs in stock?'", style=me.Style(color="gray"))
                    me.text("• 'What's the status of order ORD-12345?'", style=me.Style(color="gray"))
                    me.text("• 'Show me wireless earbuds under $200'", style=me.Style(color="gray"))
                    me.text("• 'What are your store hours?'", style=me.Style(color="gray"))
                
                for message in state.messages:
                    chat_message_bubble(message)
                
                # Loading indicator
                if state.is_loading:
                    with me.box(style=me.Style(display="flex", justify_content="flex-start", margin=me.Margin(top=10))):
                        with me.box(
                            style=me.Style(
                                background="#e0e0e0",
                                padding=me.Padding.all(12),
                                border_radius=8,
                            )
                        ):
                            me.text("🤔 Processing your request via A2A protocol...", style=me.Style(color="gray"))
            
            # Input area
            with me.box(style=me.Style(display="flex", gap=10, align_items="center")):
                me.input(
                    label="Ask about products, orders, or store information...",
                    value=state.current_input,
                    on_input=on_input_change,
                    style=me.Style(flex_grow=1),
                    disabled=state.is_loading,
                )
                me.button(
                    "Send",
                    on_click=on_send_message,
                    type="raised",
                    disabled=state.is_loading or not state.current_input.strip(),
                )
        
        # Debug information
        if state.show_debug:
            with me.box(
                style=me.Style(
                    background="#f0f8ff",
                    border=me.Border.all(me.BorderSide(width=1, color="#2196f3")),
                    border_radius=4,
                    padding=me.Padding.all(15),
                    margin=me.Margin(top=20),
                )
            ):
                me.text("🔧 Debug Information", type="subtitle-1", style=me.Style(margin=me.Margin(bottom=10)))
                me.text(f"Host Agent URL: {state.host_agent_url}")
                me.text(f"Context ID: {state.context_id}")
                me.text(f"Total Messages: {len(state.messages)}")
                me.text(f"Loading: {state.is_loading}")
                
                me.text("A2A Architecture:", style=me.Style(margin=me.Margin(top=10), font_weight="bold"))
                me.text("Frontend → Host Agent (8000) → [Inventory Agent (8001) | Customer Service Agent (8002)]")


if __name__ == "__main__":
    import uvicorn
    from werkzeug.serving import run_simple
    
    HOST = os.environ.get("MESOP_HOST", "127.0.0.1")
    PORT = int(os.environ.get("MESOP_PORT", "8080"))
    
    print(f"🚀 Starting A2A Retail Demo Frontend on http://{HOST}:{PORT}")
    
    try:
        wsgi_app = me.create_wsgi_app()
        run_simple(HOST, PORT, wsgi_app, use_reloader=False, use_debugger=True)
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        import traceback
        traceback.print_exc()