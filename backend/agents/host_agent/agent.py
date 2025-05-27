"""Host Agent that orchestrates between Customer Service and Inventory agents.

This version *only* changes the two tool functions so they use the shared
`send_message_to_agent` helper (which contains the A2AClient shim). No other
logic from your original file has been altered.
"""

import logging
import uuid
from typing import Any, AsyncIterable, Dict

import httpx
from a2a.types import AgentCard, Message, Part, Role, TextPart
from google.adk.agents import Agent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from backend.utils.a2a_utils import send_message_to_agent  # central helper with shim

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper to build outbound Message objects (used by fallback paths)
# ---------------------------------------------------------------------------

def _new_user_message(text: str, *, context_id: str | None = None) -> Message:
    return Message(
        messageId=str(uuid.uuid4()),
        contextId=context_id,
        role=Role.user,
        parts=[Part(root=TextPart(text=text))],
    )

# ---------------------------------------------------------------------------
# Remote agent tool functions (now delegate to utils helper)
# ---------------------------------------------------------------------------


async def call_customer_service_agent(query: str) -> str:  # noqa: D401
    """Forward *query* to Customer Service Agent over A2A."""
    response = await send_message_to_agent("http://localhost:8002", query)
    return response or "Customer service is temporarily unavailable."


async def call_inventory_agent(query: str) -> str:  # noqa: D401
    """Forward *query* to Inventory Agent over A2A."""
    response = await send_message_to_agent("http://localhost:8001", query)
    return response or "Inventory system is temporarily unavailable."


async def get_agent_status() -> str:  # noqa: D401
    """Return online/offline status for remote agents."""
    lines: list[str] = []
    async with httpx.AsyncClient() as hc:
        for name, url in [
            ("Inventory Agent", "http://localhost:8001"),
            ("Customer Service Agent", "http://localhost:8002"),
        ]:
            try:
                card: AgentCard = await A2AClient(url=url, httpx_client=hc).get_agent_card()
                lines.append(f"✅ {name}: {card.name} (Online)")
            except Exception:
                lines.append(f"❌ {name}: Offline")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Host Agent definition (unchanged core logic)
# ---------------------------------------------------------------------------

class HostAgent:
    """Coordinates between Inventory and Customer Service agents."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self) -> None:
        self._agent = self._build_agent()
        self._user_id = "host_agent_user"
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    # --------------------------- LLM agent setup ------------------------

    @staticmethod
    def get_processing_message() -> str:
        return "Coordinating with specialized agents..."

    def _build_agent(self) -> Agent:
        return Agent(
            name="host_agent",
            model="gemini-2.0-flash",
            description="Host agent orchestrating retail queries.",
            instruction=(
                "You are a host agent that coordinates between specialized retail agents.\n\n"
                "Follow the routing guidelines and always leverage the specialised agents."
            ),
            tools=[
                call_customer_service_agent,
                call_inventory_agent,
                get_agent_status,
            ],
        )

    # --------------------------- Streaming interface --------------------

    async def stream(self, query: str, session_id: str) -> AsyncIterable[Dict[str, Any]]:
        try:
            session = await self._runner.session_service.get_session(
                app_name=self._agent.name,
                user_id=self._user_id,
                session_id=session_id,
            )
            if session is None:
                session = await self._runner.session_service.create_session(
                    app_name=self._agent.name,
                    user_id=self._user_id,
                    state={},
                    session_id=session_id,
                )

            content = types.Content(role="user", parts=[types.Part.from_text(text=query)])

            async for event in self._runner.run_async(
                user_id=self._user_id,
                session_id=session.id,
                new_message=content,
            ):
                if event.is_final_response():
                    response_txt = ""
                    if event.content and event.content.parts and event.content.parts[0].text:
                        response_txt = "\n".join(p.text for p in event.content.parts if p.text)
                    elif event.content and any(p.function_response for p in event.content.parts):
                        for p in event.content.parts:
                            if p.function_response:
                                response_txt = str(p.function_response.response)
                                break
                    yield {"is_task_complete": True, "content": response_txt}
                else:
                    yield {"is_task_complete": False, "updates": self.get_processing_message()}
        except Exception as exc:  # noqa: BLE001
            logger.error("Error in host agent stream: %s", exc)
            yield {"is_task_complete": True, "content": f"Error coordinating request: {exc}"}
