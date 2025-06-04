"""Frontend for A2A Retail Demo with Dark Mode and Streaming."""
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
    """Application state with theme and streaming support."""
    messages: List[dict] = field(default_factory=list)
    current_input: str = ""
    is_loading: bool = False
    error_message: Optional[str] = None
    
    # Agent status
    host_agent_online: bool = False
    inventory_agent_online: bool = False
    customer_service_agent_online: bool = False
    _status_checked: bool = False
    
    # Configuration
    host_agent_url: str = "http://localhost:8000"
    show_debug: bool = False
    
    # Context management
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Theme and UI
    dark_mode: bool = False
    show_agent_thoughts: bool = True  # Show routing decisions for A2A demo
    
    # Streaming state
    current_stream_message: str = ""
    streaming_active: bool = False
    agent_thinking: bool = False
    current_agent: str = ""
    last_activity: str = "Ready"
    last_response_time: float = 0.0
    current_streaming_response: str = ""
    streaming_speed: float = 0.03  # Seconds between words (faster for better UX)
    
    # Logging and analytics
    show_logs: bool = False
    current_logs: List[dict] = field(default_factory=list)
    session_stats: dict = field(default_factory=lambda: {
        "total_messages": 0,
        "total_tokens": 0,
        "avg_response_time": 0,
        "functions_used": [],
        "agents_used": []
    })

def get_theme_colors(dark_mode: bool) -> dict:
    """Get theme colors based on current mode."""
    if dark_mode:
        return {
            "bg_primary": "#0f0f23",
            "bg_secondary": "#1a1a2e",
            "bg_tertiary": "#16213e",
            "text_primary": "#e4e4e7",
            "text_secondary": "#a1a1aa",
            "text_muted": "#71717a",
            "accent": "#3b82f6",
            "accent_hover": "#2563eb",
            "success": "#10b981",
            "error": "#ef4444",
            "warning": "#f59e0b",
            "border": "#374151",
            "chat_user": "#3b82f6",
            "chat_agent": "#374151",
            "status_online": "#10b981",
            "status_offline": "#ef4444",
        }
    else:
        return {
            "bg_primary": "#ffffff",
            "bg_secondary": "#f8fafc",
            "bg_tertiary": "#f1f5f9",
            "text_primary": "#1e293b",
            "text_secondary": "#475569",
            "text_muted": "#64748b",
            "accent": "#3b82f6",
            "accent_hover": "#2563eb",
            "success": "#10b981",
            "error": "#ef4444",
            "warning": "#f59e0b",
            "border": "#e2e8f0",
            "chat_user": "#3b82f6",
            "chat_agent": "#e2e8f0",
            "status_online": "#10b981",
            "status_offline": "#ef4444",
        }

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
                a2a_client = await A2AClient.get_client_from_agent_card_url(httpx_client=client, base_url=url)
                status[name] = True
            except Exception:
                status[name] = False
    return status

def check_agent_status():
    """Check the status of all agents."""
    state = me.state(AppState)
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
            a2a_client = await A2AClient.get_client_from_agent_card_url(
                httpx_client=client, base_url="http://localhost:8000"
            )
            
            message = Message(
                messageId=str(uuid.uuid4()),
                contextId=context_id,
                role=Role.user,
                parts=[Part(root=TextPart(text=message_text))],
            )
            
            request = SendMessageRequest(
                id=str(uuid.uuid4()),
                params=MessageSendParams(
                    message=message, 
                    configuration=MessageSendConfiguration(acceptedOutputModes=["text/plain", "text"])
                ),
            )
            
            response = await a2a_client.send_message(request)
            
            if hasattr(response, "root"):
                result = response.root.result
            else:
                result = response.result if hasattr(response, "result") else response
            
            if isinstance(result, Task):
                if result.artifacts:
                    texts = []
                    for artifact in result.artifacts:
                        for part in artifact.parts:
                            if hasattr(part, "root") and hasattr(part.root, "text"):
                                texts.append(part.root.text)
                    return "\n".join(texts) if texts else "Task completed with no text response"
                elif result.status and result.status.message:
                    return get_message_text(result.status.message)
                else:
                    return f"Task {result.id} status: {result.status.state if result.status else 'unknown'}"
            elif isinstance(result, Message):
                return get_message_text(result)
            else:
                return "Received response but unable to extract text"
    except Exception as e:
        return f"Error communicating with host agent: {str(e)}"

def on_input_change(e: me.InputEvent):
    """Handle input field changes with debouncing."""
    state = me.state(AppState)
    state.current_input = e.value

def add_log_entry(log_type: str, message: str, metadata: dict = None):
    """Add a new log entry with optimized performance."""
    state = me.state(AppState)
    
    # Only add logs if logging is enabled
    if not state.show_logs:
        return
        
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "type": log_type,
        "message": message,
        "metadata": metadata or {}
    }
    state.current_logs.append(log_entry)
    
    # Keep only last 25 log entries for better performance
    if len(state.current_logs) > 25:
        state.current_logs = state.current_logs[-25:]

def update_session_stats(response_time: float = None, tokens_used: int = None, 
                        functions_used: List[str] = None, agent_used: str = None):
    """Update session statistics."""
    state = me.state(AppState)
    
    state.session_stats["total_messages"] += 1
    
    if tokens_used:
        state.session_stats["total_tokens"] += tokens_used
    
    if response_time:
        current_avg = state.session_stats["avg_response_time"]
        total_messages = state.session_stats["total_messages"]
        state.session_stats["avg_response_time"] = (
            (current_avg * (total_messages - 1) + response_time) / total_messages
        )
    
    if functions_used:
        state.session_stats["functions_used"].extend(functions_used)
        # Keep unique functions
        state.session_stats["functions_used"] = list(set(state.session_stats["functions_used"]))
    
    if agent_used and agent_used not in state.session_stats["agents_used"]:
        state.session_stats["agents_used"].append(agent_used)

async def on_send_message(e: me.ClickEvent):
    """Handle send message button click with streaming and logging."""
    state = me.state(AppState)
    if not state.current_input.strip():
        return

    start_time = datetime.now()
    
    # Add user message
    user_message = {
        "role": "user",
        "content": state.current_input,
        "timestamp": start_time.isoformat(),
    }
    state.messages.append(user_message)
    
    # Log user message
    add_log_entry("user_message", f"User query: {state.current_input}")
    
    message_text = state.current_input
    state.current_input = ""
    state.is_loading = True
    state.streaming_active = True
    state.agent_thinking = True
    state.current_agent = "host"
    state.last_activity = "Starting analysis..."
    yield  # Update UI to show user message

    try:
        # Log analysis phase
        add_log_entry("analysis", "Starting query analysis", {
            "query_length": len(message_text),
            "word_count": len(message_text.split())
        })
        
        # Simulate agent thinking with detailed logging
        if state.show_agent_thoughts:
            thinking_steps = [
                ("🤔 Analyzing your request...", "analysis"),
                ("🔄 Routing to appropriate agent...", "routing"),
                ("📡 Establishing A2A connection...", "connection"),
                ("⚙️ Processing through specialized agent...", "processing")
            ]
            
            for step_message, step_type in thinking_steps:
                thinking_message = {
                    "role": "agent",
                    "content": step_message,
                    "timestamp": datetime.now().isoformat(),
                    "is_thinking": True,
                }
                state.messages.append(thinking_message)
                
                # Log thinking step
                add_log_entry("thinking", step_message, {"step_type": step_type})
                yield
                await asyncio.sleep(0.8)  # Pause for effect
                
                # Remove previous thinking message
                if state.messages and state.messages[-1].get("is_thinking"):
                    state.messages.pop()

        # Log routing decision
        predicted_agent = "inventory" if any(word in message_text.lower() 
                                           for word in ["stock", "product", "price", "available"]) else "customer_service"
        add_log_entry("routing", f"Routing to {predicted_agent} agent", {
            "predicted_agent": predicted_agent,
            "confidence": "high" if predicted_agent == "inventory" else "medium"
        })
        
        # Send to host agent
        add_log_entry("api_call", "Sending request to host agent", {
            "endpoint": state.host_agent_url,
            "protocol": "A2A"
        })
        
        response = await send_message_to_host_async(message_text, state.context_id)
        
        # Calculate response time
        response_time = (datetime.now() - start_time).total_seconds()
        state.last_response_time = response_time
        state.last_activity = f"Completed in {response_time:.2f}s"
        
        # Log response received
        add_log_entry("response", "Response received from agent", {
            "response_time": response_time,
            "response_length": len(response),
            "agent": state.current_agent,
            "word_count": len(response.split()),
            "streaming_speed": f"{state.streaming_speed}s/word"
        })
        
        # Simulate function calls based on response content
        simulated_functions = []
        if "stock" in response.lower() or "inventory" in response.lower():
            simulated_functions.extend(["search_products_by_query", "check_product_availability"])
        if "order" in response.lower():
            simulated_functions.extend(["check_order_status", "get_order_details"])
        if "price" in response.lower():
            simulated_functions.append("search_products_by_price_range")
            
        if simulated_functions:
            add_log_entry("function_calls", f"Functions used: {', '.join(simulated_functions)}", {
                "functions": simulated_functions,
                "count": len(simulated_functions)
            })
        
        # Stream the response word by word
        words = response.split()
        streaming_response = ""
        
        # Set streaming as active
        state.streaming_active = True
        state.agent_thinking = False  # Done thinking, now streaming
        
        # Log streaming start
        add_log_entry("streaming", f"Starting word-by-word streaming ({len(words)} words)", {
            "word_count": len(words),
            "streaming_speed": f"{state.streaming_speed}s/word",
            "estimated_duration": f"{len(words) * state.streaming_speed:.1f}s"
        })
        
        # Create the streaming agent message
        agent_message = {
            "role": "agent",
            "content": "",
            "timestamp": datetime.now().isoformat(),
            "agent": state.current_agent,
            "response_time": response_time,
            "is_streaming": True,
        }
        state.messages.append(agent_message)
        yield  # Show empty message bubble
        
        # Stream words one by one
        for i, word in enumerate(words):
            streaming_response += word + " "
            # Update the last message content
            state.messages[-1]["content"] = streaming_response.strip()
            yield  # Update UI with new word
            await asyncio.sleep(state.streaming_speed)  # Use configurable speed
        
        # Mark streaming as complete
        state.messages[-1]["is_streaming"] = False
        state.messages[-1]["content"] = response  # Ensure complete response
        
        # Log streaming completion
        add_log_entry("streaming", f"Streaming completed ({len(words)} words)", {
            "total_words": len(words),
            "total_time": f"{len(words) * state.streaming_speed:.1f}s"
        })
        
        # Update session statistics
        estimated_tokens = len(message_text.split()) + len(response.split())
        update_session_stats(
            response_time=response_time,
            tokens_used=estimated_tokens,
            functions_used=simulated_functions,
            agent_used=predicted_agent
        )
        
        # Log session update
        add_log_entry("session_stats", "Session statistics updated", {
            "total_messages": state.session_stats["total_messages"],
            "total_tokens": state.session_stats["total_tokens"],
            "avg_response_time": round(state.session_stats["avg_response_time"], 2)
        })
        
    except Exception as e:
        # Log error
        add_log_entry("error", f"Error processing request: {str(e)}", {
            "error_type": type(e).__name__,
            "traceback": str(e)
        })
        state.error_message = f"Error: {str(e)}"
        state.last_activity = f"Error: {str(e)[:50]}..."
    finally:
        state.is_loading = False
        state.streaming_active = False
        state.agent_thinking = False
        state.current_agent = ""
        yield  # Update UI with response

def on_refresh_status(e: me.ClickEvent):
    """Handle refresh status button click."""
    state = me.state(AppState)
    state._status_checked = False  # Reset flag to allow re-checking
    check_agent_status()

def on_clear_chat(e: me.ClickEvent):
    """Handle clear chat button click."""
    state = me.state(AppState)
    state.messages = []
    state.error_message = None
    state.context_id = str(uuid.uuid4())
    state.last_activity = "Ready"
    state.last_response_time = 0.0
    state.streaming_active = False
    state.current_streaming_response = ""

def on_toggle_debug(e: me.ClickEvent):
    """Toggle debug information display."""
    state = me.state(AppState)
    state.show_debug = not state.show_debug

def on_toggle_theme(e: me.ClickEvent):
    """Toggle between dark and light mode."""
    state = me.state(AppState)
    state.dark_mode = not state.dark_mode

def on_toggle_thoughts(e: me.ClickEvent):
    """Toggle agent thoughts display."""
    state = me.state(AppState)
    state.show_agent_thoughts = not state.show_agent_thoughts

def on_toggle_logs(e: me.ClickEvent):
    """Toggle logs panel display."""
    state = me.state(AppState)
    state.show_logs = not state.show_logs

def agent_status_card(name: str, online: bool, port: int, colors: dict):
    """Render an agent status card."""
    status = "Online" if online else "Offline"
    color = colors["status_online"] if online else colors["status_offline"]
    
    with me.box(
        style=me.Style(
            border=me.Border.all(me.BorderSide(width=2, color=color)),
            border_radius=12,
            padding=me.Padding.all(16),
            margin=me.Margin(right=12, bottom=8),
            min_width="180px",
            background=colors["bg_tertiary"],
            box_shadow="0 4px 6px -1px rgba(0, 0, 0, 0.1)",
        )
    ):
        with me.box(style=me.Style(display="flex", align_items="center", margin=me.Margin(bottom=8))):
            # Status indicator
            with me.box(
                style=me.Style(
                    width="12px",
                    height="12px",
                    background=color,
                    border_radius="50%",
                    margin=me.Margin(right=8),
                )
            ):
                pass
            me.text(name, type="subtitle-2", style=me.Style(color=colors["text_primary"], font_weight="600"))
        
        me.text(f"{status} • :{port}", style=me.Style(color=color, font_size="14px"))

def chat_message_bubble(message: dict, colors: dict):
    """Render a chat message bubble with streaming support."""
    is_user = message["role"] == "user"
    is_thinking = message.get("is_thinking", False)
    is_streaming = message.get("is_streaming", False)
    align = "flex-end" if is_user else "flex-start"
    bg = colors["chat_user"] if is_user else colors["chat_agent"]
    text_color = "#ffffff" if is_user else colors["text_primary"]
    timestamp = message.get("timestamp", "")
    agent = message.get("agent", "")
    
    try:
        when = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%H:%M:%S")
    except:
        when = ""

    with me.box(style=me.Style(display="flex", justify_content=align, margin=me.Margin(bottom=16))):
        with me.box(
            style=me.Style(
                max_width="75%",
                background=bg,
                color=text_color,
                padding=me.Padding.all(16),
                border_radius=16 if is_user else 16,
                box_shadow="0 2px 8px rgba(0, 0, 0, 0.1)" if not is_thinking else "0 2px 8px rgba(59, 130, 246, 0.2)",
                border=me.Border.all(me.BorderSide(width=1, color=colors["accent"])) if is_thinking or is_streaming else None,
            )
        ):
            # Agent indicator for non-user messages
            if not is_user and agent:
                status_text = f"🤖 {agent.title()} Agent"
                if is_streaming:
                    status_text += " • ✍️ Typing..."
                me.text(status_text, 
                       type="caption", 
                       style=me.Style(color=colors["accent"], margin=me.Margin(bottom=4), font_weight="600"))
            
            # Message content
            if is_user:
                me.text(message["content"], style=me.Style(line_height="1.5"))
            else:
                me.markdown(message["content"])
                # Add streaming cursor
                if is_streaming and message["content"]:
                    me.text("▋", style=me.Style(color=colors["accent"], margin=me.Margin(left=4), display="inline"))
            
            # Timestamp
            if when:
                me.text(when, 
                       type="caption", 
                       style=me.Style(opacity=0.7, margin=me.Margin(top=8), font_size="12px"))

def floating_action_buttons(colors: dict):
    """Render floating action buttons with proper spacing."""
    state = me.state(AppState)
    
    with me.box(
        style=me.Style(
            position="fixed",
            bottom="100px",  # Higher position to avoid overlap with input
            right="20px",
            display="flex",
            flex_direction="column",
            gap=12,
            z_index=1000,
        )
    ):
        # Logs toggle
        logs_icon = "📊" if not state.show_logs else "📈"
        me.button(
            logs_icon,
            on_click=on_toggle_logs,
            type="raised",
            style=me.Style(
                border_radius="50%",
                width="56px",
                height="56px",
                background=colors["success"],
                color="#ffffff",
                box_shadow="0 4px 12px rgba(0, 0, 0, 0.2)",
            )
        )
        
        # Theme toggle
        theme_icon = "🌙" if not state.dark_mode else "☀️"
        me.button(
            theme_icon,
            on_click=on_toggle_theme,
            type="raised",
            style=me.Style(
                border_radius="50%",
                width="56px",
                height="56px",
                background=colors["accent"],
                color="#ffffff",
                box_shadow="0 4px 12px rgba(0, 0, 0, 0.2)",
            )
        )
        
        # Thoughts toggle
        thoughts_icon = "💭" if state.show_agent_thoughts else "🤐"
        me.button(
            thoughts_icon,
            on_click=on_toggle_thoughts,
            type="raised",
            style=me.Style(
                border_radius="50%",
                width="56px",
                height="56px",
                background=colors["warning"],
                color="#ffffff",
                box_shadow="0 4px 12px rgba(0, 0, 0, 0.2)",
            )
        )

@me.page(path="/", title="A2A Retail Demo")
def main_page():
    """Main application page with dark mode and streaming."""
    state = me.state(AppState)
    colors = get_theme_colors(state.dark_mode)
    
    # Check agent status only once per session (not on every render)
    if not hasattr(state, '_status_checked') or not state._status_checked:
        if not any([state.host_agent_online, state.inventory_agent_online, state.customer_service_agent_online]):
            check_agent_status()
            state._status_checked = True
    
    # Main container with theme-aware styling
    with me.box(
        style=me.Style(
            background=colors["bg_primary"],
            color=colors["text_primary"],
            min_height="100vh",
            padding=me.Padding.all(24),
            display="flex",
            flex_direction="column",
            align_items="center",  # Center all content horizontally
        )
    ):
        # Content wrapper with max width
        with me.box(
            style=me.Style(
                width="100%",
                max_width="1400px",
            )
        ):
            # Header section
            with me.box(
                style=me.Style(
                    margin=me.Margin(bottom=32),
                    width="100%",
                )
            ):
                with me.box(style=me.Style(display="flex", justify_content="space-between", align_items="center")):
                    with me.box():
                        me.text(
                            "🛍️ A2A Retail Demo", 
                            type="headline-4", 
                            style=me.Style(
                                margin=me.Margin(bottom=8),
                                color=colors["text_primary"],
                                font_weight="700"
                            )
                        )
                        me.text(
                            "AI-powered retail assistant with Agent-to-Agent protocol",
                            type="body-1",
                            style=me.Style(color=colors["text_secondary"]),
                        )
                    
                    # Theme indicator
                    with me.box(
                        style=me.Style(
                            background=colors["bg_tertiary"],
                            padding=me.Padding.all(12),
                            border_radius=8,
                            border=me.Border.all(me.BorderSide(width=1, color=colors["border"])),
                        )
                    ):
                        mode_text = "🌙 Dark Mode" if state.dark_mode else "☀️ Light Mode"
                        me.text(mode_text, style=me.Style(color=colors["text_primary"], font_size="14px"))

            # Agent status section
            with me.box(
                style=me.Style(
                    width="100%",
                    display="flex",
                    justify_content="center",
                )
            ):
                with me.box(
                    style=me.Style(
                        background=colors["bg_secondary"],
                        padding=me.Padding.all(20),
                        border_radius=16,
                        margin=me.Margin(bottom=24),
                        border=me.Border.all(me.BorderSide(width=1, color=colors["border"])),
                        box_shadow="0 2px 8px rgba(0, 0, 0, 0.1)",
                        max_width="1200px",
                        width="100%",
                    )
                ):
                    me.text(
                        "🤖 Agent Network Status", 
                        type="subtitle-1", 
                        style=me.Style(color=colors["text_primary"], margin=me.Margin(bottom=16), font_weight="600")
                    )
                    
                    with me.box(style=me.Style(display="flex", flex_wrap="wrap", margin=me.Margin(bottom=16))):
                        agent_status_card("Host Agent", state.host_agent_online, 8000, colors)
                        agent_status_card("Inventory Agent", state.inventory_agent_online, 8001, colors)
                        agent_status_card("Customer Service", state.customer_service_agent_online, 8002, colors)
                    
                    with me.box(style=me.Style(display="flex", gap=12, flex_wrap="wrap")):
                        me.button("🔄 Refresh Status", on_click=on_refresh_status, type="stroked")
                        me.button("🧹 Clear Chat", on_click=on_clear_chat, type="stroked")
                        me.button("🔧 Debug Info", on_click=on_toggle_debug, type="stroked")

            # Error display
            if state.error_message:
                with me.box(
                    style=me.Style(
                        width="100%",
                        display="flex",
                        justify_content="center",
                    )
                ):
                    with me.box(
                        style=me.Style(
                            background="#fef2f2",
                            border=me.Border.all(me.BorderSide(width=1, color=colors["error"])),
                            border_radius=12,
                            padding=me.Padding.all(16),
                            margin=me.Margin(bottom=24),
                            max_width="1200px",
                            width="100%",
                        )
                    ):
                        me.text("⚠️ " + state.error_message, style=me.Style(color=colors["error"]))

            # Logs panel
            if state.show_logs:
                with me.box(
                    style=me.Style(
                        width="100%",
                        display="flex",
                        justify_content="center",
                    )
                ):
                    with me.box(
                        style=me.Style(
                            background=colors["bg_secondary"],
                            border=me.Border.all(me.BorderSide(width=1, color=colors["success"])),
                            border_radius=12,
                            padding=me.Padding.all(20),
                            margin=me.Margin(bottom=24),
                            box_shadow="0 4px 16px rgba(0, 0, 0, 0.1)",
                            max_width="1200px",
                            width="100%",
                        )
                    ):
                        me.text("📊 System Logs & Analytics", type="subtitle-1", 
                               style=me.Style(margin=me.Margin(bottom=16), color=colors["text_primary"], font_weight="600"))
                        
                        # Session Statistics
                        with me.box(style=me.Style(margin=me.Margin(bottom=20))):
                            me.text("📈 Session Statistics", type="subtitle-2", 
                                   style=me.Style(margin=me.Margin(bottom=12), color=colors["success"], font_weight="600"))
                            
                            stats_grid = [
                                ("💬 Total Messages", str(state.session_stats["total_messages"])),
                                ("🪙 Total Tokens", str(state.session_stats["total_tokens"])),
                                ("⏱️ Avg Response Time", f"{state.session_stats['avg_response_time']:.2f}s"),
                                ("🔧 Functions Used", str(len(state.session_stats["functions_used"]))),
                                ("🤖 Agents Used", str(len(state.session_stats["agents_used"]))),
                            ]
                            
                            with me.box(style=me.Style(display="flex", flex_wrap="wrap", gap=16)):
                                for label, value in stats_grid:
                                    with me.box(
                                        style=me.Style(
                                            background=colors["bg_tertiary"],
                                            padding=me.Padding.all(12),
                                            border_radius=8,
                                            min_width="150px",
                                            border=me.Border.all(me.BorderSide(width=1, color=colors["border"])),
                                        )
                                    ):
                                        me.text(label, type="caption", style=me.Style(color=colors["text_secondary"]))
                                        me.text(value, type="body-1", style=me.Style(color=colors["text_primary"], font_weight="600"))
                        
                        # Function Usage
                        if state.session_stats["functions_used"]:
                            with me.box(style=me.Style(margin=me.Margin(bottom=20))):
                                me.text("🔧 Functions Used This Session", type="subtitle-2", 
                                       style=me.Style(margin=me.Margin(bottom=12), color=colors["accent"], font_weight="600"))
                                with me.box(style=me.Style(display="flex", flex_wrap="wrap", gap=8)):
                                    for func in state.session_stats["functions_used"]:
                                        with me.box(
                                            style=me.Style(
                                                background=colors["accent"],
                                                color="#ffffff",
                                                padding=me.Padding(left=8, right=8, top=4, bottom=4),
                                                border_radius=16,
                                                font_size="12px",
                                            )
                                        ):
                                            me.text(func)
                        
                        # Agents Used
                        if state.session_stats["agents_used"]:
                            with me.box(style=me.Style(margin=me.Margin(bottom=20))):
                                me.text("🤖 Agents Utilized", type="subtitle-2", 
                                       style=me.Style(margin=me.Margin(bottom=12), color=colors["warning"], font_weight="600"))
                                with me.box(style=me.Style(display="flex", flex_wrap="wrap", gap=8)):
                                    agent_icons = {"inventory": "📦", "customer_service": "🎧", "host": "🏠"}
                                    for agent in state.session_stats["agents_used"]:
                                        icon = agent_icons.get(agent, "🤖")
                                        with me.box(
                                            style=me.Style(
                                                background=colors["warning"],
                                                color="#ffffff",
                                                padding=me.Padding(left=12, right=12, top=6, bottom=6),
                                                border_radius=20,
                                                font_size="14px",
                                            )
                                        ):
                                            me.text(f"{icon} {agent.replace('_', ' ').title()}")
                        
                        # Real-time Logs
                        me.text("📝 Real-time Logs", type="subtitle-2", 
                               style=me.Style(margin=me.Margin(bottom=12), color=colors["error"], font_weight="600"))
                        
                        with me.box(
                            style=me.Style(
                                height="300px",
                                overflow_y="auto",
                                background=colors["bg_tertiary"],
                                border=me.Border.all(me.BorderSide(width=1, color=colors["border"])),
                                border_radius=8,
                                padding=me.Padding.all(12),
                            )
                        ):
                            if state.current_logs:
                                # Show logs in reverse chronological order
                                for log_entry in reversed(state.current_logs[-10:]):  # Last 10 logs for better performance
                                    log_icons = {
                                        "user_message": "👤",
                                        "analysis": "🔍",
                                        "thinking": "🤔",
                                        "routing": "🔄",
                                        "api_call": "📡",
                                        "function_calls": "🔧",
                                        "response": "✅",
                                        "streaming": "💬",
                                        "session_stats": "📊",
                                        "error": "❌"
                                    }
                                    
                                    icon = log_icons.get(log_entry["type"], "📝")
                                    timestamp = datetime.fromisoformat(log_entry["timestamp"]).strftime("%H:%M:%S")
                                    
                                    with me.box(
                                        style=me.Style(
                                            margin=me.Margin(bottom=8),
                                            padding=me.Padding.all(8),
                                            background=colors["bg_secondary"],
                                            border_radius=6,
                                            border=me.Border(left=me.BorderSide(width=3, color=colors["accent"])),
                                        )
                                    ):
                                        # Log header
                                        with me.box(style=me.Style(display="flex", justify_content="space-between", align_items="center")):
                                            me.text(f"{icon} {log_entry['type'].replace('_', ' ').title()}", 
                                                   style=me.Style(font_weight="600", color=colors["text_primary"]))
                                            me.text(timestamp, type="caption", 
                                                   style=me.Style(color=colors["text_secondary"]))
                                        
                                        # Log message
                                        me.text(log_entry["message"], 
                                               style=me.Style(color=colors["text_secondary"], margin=me.Margin(top=4)))
                                        
                                        # Log metadata (if any)
                                        if log_entry["metadata"]:
                                            metadata_text = " | ".join([f"{k}: {v}" for k, v in log_entry["metadata"].items() if k not in ["traceback"]])
                                            if metadata_text:
                                                me.text(f"📋 {metadata_text}", type="caption", 
                                                       style=me.Style(color=colors["text_muted"], margin=me.Margin(top=2)))
                            else:
                                with me.box(style=me.Style(text_align="center", padding=me.Padding.all(32))):
                                    me.text("📝 No logs yet", style=me.Style(color=colors["text_secondary"]))
                                    me.text("Start a conversation to see real-time system logs", 
                                           type="caption", style=me.Style(color=colors["text_muted"]))

            # Chat area
            with me.box(
                style=me.Style(
                    width="100%",
                    display="flex",
                    justify_content="center",
                )
            ):
                with me.box(
                    style=me.Style(
                        background=colors["bg_secondary"],
                        border=me.Border.all(me.BorderSide(width=1, color=colors["border"])),
                        border_radius=16,
                        padding=me.Padding.all(24),
                        min_height="500px",
                        margin=me.Margin(bottom=24),
                        box_shadow="0 4px 16px rgba(0, 0, 0, 0.1)",
                        max_width="1200px",
                        width="100%",
                    )
                ):
                    # Chat header
                    with me.box(style=me.Style(margin=me.Margin(bottom=20))):
                        me.text(
                            "💬 Conversation", 
                            type="subtitle-1", 
                            style=me.Style(color=colors["text_primary"], font_weight="600")
                        )
                        if state.streaming_active:
                            me.text(
                                "🔄 Agent is processing...", 
                                type="caption", 
                                style=me.Style(color=colors["accent"], margin=me.Margin(top=4))
                            )
                    
                    # Chat history
                    with me.box(
                        style=me.Style(
                            height="400px",
                            overflow_y="auto",
                            padding=me.Padding.all(16),
                            background=colors["bg_tertiary"],
                            border_radius=12,
                            margin=me.Margin(bottom=24),
                            border=me.Border.all(me.BorderSide(width=1, color=colors["border"])),
                        )
                    ):
                        if not state.messages:
                            with me.box(style=me.Style(text_align="center", padding=me.Padding.all(32))):
                                me.text(
                                    "🤖 Welcome to the A2A Retail Demo!",
                                    type="headline-6",
                                    style=me.Style(color=colors["text_primary"], margin=me.Margin(bottom=16))
                                )
                                me.text(
                                    "I'm your AI-powered retail assistant using the Agent-to-Agent protocol.",
                                    style=me.Style(color=colors["text_secondary"], margin=me.Margin(bottom=20))
                                )
                                
                                with me.box(style=me.Style(background=colors["bg_secondary"], padding=me.Padding.all(16), border_radius=8)):
                                    me.text("💡 Try asking:", style=me.Style(margin=me.Margin(bottom=8), font_weight="600", color=colors["text_primary"]))
                                    suggestions = [
                                        "🔍 'Do you have Smart TVs in stock?'",
                                        "📦 'What's the status of order ORD-12345?'",
                                        "💰 'Show me wireless earbuds under $200'",
                                        "🕐 'What are your store hours?'",
                                        "🏃 'Find me some yoga equipment'"
                                    ]
                                    for suggestion in suggestions:
                                        me.text(suggestion, style=me.Style(color=colors["text_secondary"], margin=me.Margin(bottom=4)))
                        
                        for message in state.messages:
                            chat_message_bubble(message, colors)
                        
                        # Typing indicator
                        if state.streaming_active and state.agent_thinking:
                            with me.box(style=me.Style(display="flex", justify_content="flex-start", margin=me.Margin(top=12))):
                                with me.box(
                                    style=me.Style(
                                        background=colors["chat_agent"],
                                        padding=me.Padding.all(16),
                                        border_radius=16,
                                        border=me.Border.all(me.BorderSide(width=2, color=colors["accent"])),
                                    )
                                ):
                                    me.text("🤔 Agent is thinking...", style=me.Style(color=colors["text_primary"]))

                    # Input area with proper alignment and centering
                    with me.box(
                        style=me.Style(
                            width="100%",
                            display="flex",
                            justify_content="center",  # Center the input container
                        )
                    ):
                        with me.box(
                            style=me.Style(
                                width="100%",  # Take full width instead of limiting to 1200px
                                max_width="1400px",  # Much wider max width
                            )
                        ):
                            with me.box(
                                style=me.Style(
                                    display="flex", 
                                    gap=16,  # Larger gap
                                    align_items="stretch",  # Make items stretch to same height
                                    background=colors["bg_primary"],
                                    padding=me.Padding.all(20),  # More padding
                                    border_radius=12,
                                    border=me.Border.all(me.BorderSide(width=1, color=colors["border"])),
                                    box_shadow="0 2px 8px rgba(0, 0, 0, 0.1)",
                                )
                            ):
                                # Input field container - much wider
                                with me.box(
                                    style=me.Style(
                                        flex_grow=1,
                                        display="flex",
                                        align_items="center",
                                        min_width="800px",  # Force minimum width
                                    )
                                ):
                                    me.input(
                                        label="Ask about products, orders, or store information...",
                                        value=state.current_input,
                                        on_input=on_input_change,
                                        style=me.Style(
                                            width="100%",
                                            background=colors["bg_secondary"],
                                            border_radius=8,
                                            font_size="16px",
                                            padding=me.Padding.all(16),  # More padding for larger appearance
                                            min_width="800px",  # Force input field minimum width
                                        ),
                                        disabled=state.is_loading,
                                    )
                                
                                # Send button container
                                with me.box(
                                    style=me.Style(
                                        display="flex",
                                        align_items="center",
                                        flex_shrink=0,  # Don't shrink the button
                                    )
                                ):
                                    me.button(
                                        "🚀 Send" if not state.is_loading else "⏳ Processing...",
                                        on_click=on_send_message,
                                        type="raised",
                                        disabled=state.is_loading or not state.current_input.strip(),
                                        style=me.Style(
                                            background=colors["accent"],
                                            color="#ffffff",
                                            padding=me.Padding(left=32, right=32, top=16, bottom=16),
                                            border_radius=8,
                                            min_width="160px",  # Even wider button
                                            font_weight="600",
                                            font_size="16px",
                                            box_shadow="0 2px 8px rgba(0, 0, 0, 0.1)",
                                        )
                                    )

            # Debug information
            if state.show_debug:
                with me.box(
                    style=me.Style(
                        width="100%",
                        display="flex",
                        justify_content="center",
                    )
                ):
                    with me.box(
                        style=me.Style(
                            background=colors["bg_secondary"],
                            border=me.Border.all(me.BorderSide(width=1, color=colors["accent"])),
                            border_radius=12,
                            padding=me.Padding.all(20),
                            margin=me.Margin(top=24),
                            max_width="1200px",
                            width="100%",
                        )
                    ):
                        me.text("🔧 Debug Information", type="subtitle-1", style=me.Style(margin=me.Margin(bottom=16), color=colors["text_primary"]))
                        debug_info = [
                            f"🌐 Host Agent URL: {state.host_agent_url}",
                            f"🆔 Context ID: {state.context_id}",
                            f"💬 Total Messages: {len(state.messages)}",
                            f"⚡ Loading: {state.is_loading}",
                            f"🌊 Streaming: {'Active' if state.streaming_active else 'Inactive'}",
                            f"🌊 Last Activity: {state.last_activity}",
                            f"⏱️ Last Response Time: {state.last_response_time:.2f}s" if state.last_response_time > 0 else "⏱️ Last Response Time: N/A",
                            f"🎨 Theme: {'Dark' if state.dark_mode else 'Light'}",
                            f"💭 Show Thoughts: {state.show_agent_thoughts}",
                            f"📊 Show Logs: {state.show_logs}",
                        ]
                        for info in debug_info:
                            me.text(info, style=me.Style(color=colors["text_secondary"], margin=me.Margin(bottom=4)))
                        
                        me.text("🏗️ A2A Architecture:", style=me.Style(margin=me.Margin(top=16, bottom=8), font_weight="600", color=colors["text_primary"]))
                        me.text("Frontend → Host Agent (8000) → [Inventory Agent (8001) | Customer Service Agent (8002)]", 
                               style=me.Style(color=colors["text_secondary"]))

    # Floating action buttons (outside main container)
    floating_action_buttons(colors)

if __name__ == "__main__":
    import uvicorn
    from werkzeug.serving import run_simple
    
    HOST = os.environ.get("MESOP_HOST", "127.0.0.1")
    PORT = int(os.environ.get("MESOP_PORT", "8080"))
    
    print(f"🚀 Starting A2A Retail Demo Frontend on http://{HOST}:{PORT}")
    print("✨ Features: Dark Mode, Streaming UI, Agent Thoughts, Modern Design")
    
    try:
        wsgi_app = me.create_wsgi_app()
        run_simple(HOST, PORT, wsgi_app, use_reloader=False, use_debugger=True)
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        import traceback
        traceback.print_exc()