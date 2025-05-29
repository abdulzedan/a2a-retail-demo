"""Application state for the frontend."""

import mesop as me
from dataclasses import dataclass, field
from typing import List, Optional


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

    # Additional state
    sidenav_open: bool = False
    current_conversation_id: str = ""
    polling_interval: int = 0
