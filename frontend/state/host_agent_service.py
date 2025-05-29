"""Host agent service for frontend-to-backend communication."""

import logging
from typing import Optional
from backend.utils.a2a_utils import send_message_to_agent, check_agent_health

logger = logging.getLogger(__name__)


async def UpdateAppState(app_state, conversation_id: str):
    """Update app state (stub for now)."""
    pass


async def UpdateApiKey(api_key: str) -> bool:
    """Update API key (stub for now)."""
    return True
