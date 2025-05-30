import logging
import uuid
from typing import Any
from collections.abc import AsyncIterable

import httpx
from a2a.client import A2AClient
from a2a.types import (
    AgentCard,
    Message,
    Part,
    Role,
    TextPart,
    SendMessageRequest,
    MessageSendParams,
    MessageSendConfiguration,
    Task,
)
from a2a.utils import get_message_text
from google.adk.agents import Agent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

logger = logging.getLogger(__name__)


class HostAgent:
    """Coordinates between Inventory and Customer Service agents."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    # Agent URLs
    INVENTORY_AGENT_URL = "http://localhost:8001"
    CUSTOMER_SERVICE_AGENT_URL = "http://localhost:8002"

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
        self._agent_cards: dict[str, AgentCard] = {}

    async def _get_agent_card(self, agent_url: str) -> AgentCard | None:
        """Get and cache agent card."""
        if agent_url not in self._agent_cards:
            try:
                logger.info(f"Fetching agent card from {agent_url}")
                async with httpx.AsyncClient() as hc:
                    # Fetch the agent card JSON directly
                    response = await hc.get(f"{agent_url}/.well-known/agent.json")
                    response.raise_for_status()
                    logger.info(f"Direct GET to {agent_url}: {response.status_code}")

                    # Parse the agent card
                    agent_card = AgentCard(**response.json())
                    self._agent_cards[agent_url] = agent_card
                    logger.info(f"Successfully cached agent card for {agent_url}: {agent_card.name}")
                    return agent_card
            except Exception as e:
                logger.error(f"Failed to get agent card from {agent_url}: {e}", exc_info=True)
                return None
        return self._agent_cards.get(agent_url)

    async def _call_agent_with_a2a(self, agent_url: str, query: str, context_id: str) -> str:
        """Call an agent using the A2A protocol."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as hc:
                # Get the A2A client
                client = await A2AClient.get_client_from_agent_card_url(httpx_client=hc, base_url=agent_url)

                # Create message
                message = Message(
                    messageId=str(uuid.uuid4()),
                    contextId=context_id,
                    role=Role.user,
                    parts=[Part(root=TextPart(text=query))],
                )

                # Create request with configuration AND ID
                request = SendMessageRequest(
                    id=str(uuid.uuid4()),  # Add the required id field
                    params=MessageSendParams(
                        message=message,
                        configuration=MessageSendConfiguration(acceptedOutputModes=["text/plain", "text"]),
                    ),
                )

                # Send message
                response = await client.send_message(request)

                # Extract response
                if hasattr(response, "root"):
                    result = response.root.result
                else:
                    result = response.result if hasattr(response, "result") else response

                # Handle different response types
                if isinstance(result, Task):
                    # Task response
                    if result.artifacts:
                        # Extract text from artifacts
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
                    # Direct message response
                    return get_message_text(result)

                else:
                    logger.warning(f"Unexpected response type: {type(result)}")
                    return "Received response but unable to extract text"

        except Exception as e:
            logger.error(f"Error calling agent at {agent_url}: {e}", exc_info=True)
            return f"Error communicating with agent: {str(e)}"

    async def call_customer_service_agent(self, query: str, context_id: str) -> str:
        """Forward query to Customer Service Agent over A2A."""
        return await self._call_agent_with_a2a(self.CUSTOMER_SERVICE_AGENT_URL, query, context_id)

    async def call_inventory_agent(self, query: str, context_id: str) -> str:
        """Forward query to Inventory Agent over A2A."""
        return await self._call_agent_with_a2a(self.INVENTORY_AGENT_URL, query, context_id)

    async def get_agent_status(self) -> str:
        """Return online/offline status for remote agents."""
        lines = ["Agent Status:"]

        for name, url in [
            ("Inventory Agent", self.INVENTORY_AGENT_URL),
            ("Customer Service Agent", self.CUSTOMER_SERVICE_AGENT_URL),
        ]:
            card = await self._get_agent_card(url)
            if card:
                lines.append(f"✅ {name}: Online - {card.description}")
            else:
                lines.append(f"❌ {name}: Offline")

        return "\n".join(lines)

    def _build_agent(self) -> Agent:
        return Agent(
            name="host_agent",
            model="gemini-2.0-flash",
            description="Host agent orchestrating retail queries between specialized agents.",
            instruction=(
                """You are a host agent that coordinates between specialized retail agents.

Your role is to analyze incoming queries and determine which agent should handle them.

Routing rules:
- **Customer Service Agent**: Handle queries about order status, returns, store hours, customer complaints, general inquiries
- **Inventory Agent**: Handle queries about product availability, stock levels, product search, pricing

When you receive a query, respond with ONLY one of these two responses:
1. "ROUTE_TO_INVENTORY" - if the query is about products, stock, availability, or pricing
2. "ROUTE_TO_CUSTOMER_SERVICE" - if the query is about orders, returns, store information, or general help

Do not provide any other information or explanation. Just respond with the routing decision."""
            ),
            tools=[],  # No tools - we'll handle routing in code
        )

    async def stream(self, query: str, session_id: str) -> AsyncIterable[dict[str, Any]]:
        """Stream responses for the given query."""
        try:
            logger.info(f"Host agent received query: {query}")

            # Get or create session
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

            # Use session_id as context_id for consistency
            context_id = session_id

            # Check agent status first
            inventory_card = await self._get_agent_card(self.INVENTORY_AGENT_URL)
            customer_service_card = await self._get_agent_card(self.CUSTOMER_SERVICE_AGENT_URL)

            # Yield initial status
            yield {"type": "status", "message": "Analyzing your request..."}

            # Create user message
            content = types.Content(role="user", parts=[types.Part.from_text(text=query)])

            # Run the agent to determine routing
            routing_decision = None
            async for event in self._runner.run_async(
                user_id=self._user_id,
                session_id=session.id,
                new_message=content,
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    routing_decision = "\n".join(p.text for p in event.content.parts if p.text)
                    break

            if not routing_decision:
                yield {"type": "error", "message": "Unable to determine routing"}
                return

            # Check the routing decision
            if "ROUTE_TO_INVENTORY" in routing_decision:
                if not inventory_card:
                    yield {"type": "error", "message": "Inventory agent is currently offline. Please try again later."}
                    return

                yield {"type": "routing", "agent": "inventory", "message": "Checking our inventory system..."}

                response = await self.call_inventory_agent(query, context_id)

                yield {"type": "agent_response", "agent": "inventory"}

                yield {"type": "result", "content": response}

            elif "ROUTE_TO_CUSTOMER_SERVICE" in routing_decision:
                if not customer_service_card:
                    yield {
                        "type": "error",
                        "message": "Customer service agent is currently offline. Please try again later.",
                    }
                    return

                yield {
                    "type": "routing",
                    "agent": "customer service",
                    "message": "Connecting you with customer service...",
                }

                response = await self.call_customer_service_agent(query, context_id)

                yield {"type": "agent_response", "agent": "customer service"}

                yield {"type": "result", "content": response}

            else:
                # Could not determine routing
                yield {
                    "type": "error",
                    "message": "I couldn't determine which agent should handle your request. Please try rephrasing your question.",
                }

        except Exception as exc:
            logger.error(f"Error in host agent stream: {exc}", exc_info=True)
            yield {"type": "error", "message": f"Error coordinating request: {str(exc)}"}
