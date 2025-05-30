import asyncio
import logging
import uuid
from typing import Any, List, Dict
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
    """Coordinates between Inventory and Customer Service agents with support for parallel invocation."""

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

    async def call_agents_parallel(self, inventory_query: str, customer_service_query: str, context_id: str) -> Dict[str, str]:
        """Call both agents in parallel and return their responses."""
        logger.info("Executing parallel agent calls")
        
        # Create tasks for parallel execution
        inventory_task = asyncio.create_task(
            self.call_inventory_agent(inventory_query, context_id)
        )
        customer_service_task = asyncio.create_task(
            self.call_customer_service_agent(customer_service_query, context_id)
        )
        
        # Wait for both tasks to complete
        inventory_response, customer_service_response = await asyncio.gather(
            inventory_task, 
            customer_service_task,
            return_exceptions=True
        )
        
        # Handle any exceptions
        if isinstance(inventory_response, Exception):
            inventory_response = f"Error from inventory agent: {str(inventory_response)}"
        if isinstance(customer_service_response, Exception):
            customer_service_response = f"Error from customer service agent: {str(customer_service_response)}"
        
        return {
            "inventory": inventory_response,
            "customer_service": customer_service_response
        }

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
            description="Host agent orchestrating retail queries between specialized agents with parallel execution support.",
            instruction=(
                """You are a host agent that coordinates between specialized retail agents.

Your role is to analyze incoming queries and determine the best routing strategy.

Available agents and their capabilities:

**Customer Service Agent**: Handles order status, returns, refunds, complaints, store hours, policies, shipping issues
**Inventory Agent**: Handles product searches, stock availability, pricing, categories, product recommendations

Analyze the user's query and respond with ONLY one of these routing decisions:

1. "ROUTE_TO_CUSTOMER_SERVICE" - Use when the query is about:
   - Order status or tracking
   - Returns or refunds  
   - Store hours or policies
   - Complaints or issues with orders
   - Any query mentioning an order ID
   - Questions about "my order" or "my purchase"

2. "ROUTE_TO_INVENTORY" - Use when the query is about:
   - Product availability or stock
   - Product searches or recommendations
   - Pricing information
   - Product categories or specifications
   - Finding alternatives or similar products (without order context)

3. "ROUTE_TO_BOTH" - Use ONLY when the query explicitly requires both agents:
   - User asks to check order status AND find alternative products
   - User wants to return something AND needs help finding a replacement
   - Query contains "and also" or similar phrases connecting both domains

Important guidelines:
- If someone wants to return a product from an order, that's CUSTOMER SERVICE only
- Just mentioning a product name in an order/return context doesn't require inventory lookup
- Default to single agent routing unless there's a clear need for both
- When in doubt about order-related queries, choose CUSTOMER SERVICE"""
            ),
            tools=[],  # No tools - the agent uses its understanding to route
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

            # Create content for the agent to analyze
            content = types.Content(role="user", parts=[types.Part.from_text(text=f"Query: {query}")])

            # Run the agent to determine routing
            routing_decision = None
            async for event in self._runner.run_async(
                user_id=self._user_id,
                session_id=session.id,
                new_message=content,
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    routing_decision = "\n".join(p.text for p in event.content.parts if p.text)
                    logger.info(f"Routing decision: {routing_decision}")
                    break

            if not routing_decision:
                yield {"type": "error", "message": "Unable to determine routing"}
                return

            # Execute based on routing decision
            if "ROUTE_TO_BOTH" in routing_decision:
                # Parallel execution
                if not inventory_card or not customer_service_card:
                    yield {"type": "error", "message": "One or more agents are offline. Cannot execute parallel request."}
                    return

                yield {"type": "routing", "agent": "both", "message": "Coordinating with both inventory and customer service..."}
                
                # Execute parallel calls
                responses = await self.call_agents_parallel(query, query, context_id)
                
                yield {"type": "agent_response", "agent": "parallel"}
                
                # Combine responses
                combined_response = f"""I've consulted both our inventory and customer service systems:

**Inventory Information:**
{responses['inventory']}

**Customer Service Information:**
{responses['customer_service']}"""
                
                yield {"type": "result", "content": combined_response}

            elif "ROUTE_TO_INVENTORY" in routing_decision:
                # Single inventory agent
                if not inventory_card:
                    yield {"type": "error", "message": "Inventory agent is currently offline. Please try again later."}
                    return

                yield {"type": "routing", "agent": "inventory", "message": "Checking our inventory system..."}
                response = await self.call_inventory_agent(query, context_id)
                yield {"type": "agent_response", "agent": "inventory"}
                yield {"type": "result", "content": response}

            elif "ROUTE_TO_CUSTOMER_SERVICE" in routing_decision:
                # Single customer service agent
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