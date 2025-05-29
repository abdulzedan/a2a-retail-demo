"""Customer Service Agent using LangGraph and A2A Protocol."""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterable
from typing import Any, Literal

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

ORDERS: dict[str, dict[str, Any]] = {
    "ORD-12345": {
        "status": "shipped",
        "tracking_number": "1Z999AA1012345678",
        "items": ["Smart TV 55-inch 4K"],
        "total": 699.99,
    },
    "ORD-67890": {
        "status": "processing",
        "items": ["Wireless Earbuds Pro", "Cotton T-Shirt"],
        "total": 229.98,
    },
}

STORE_HOURS = {
    "monday-friday": "9:00 AM - 9:00 PM",
    "saturday": "9:00 AM - 10:00 PM",
    "sunday": "10:00 AM - 7:00 PM",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_order_id(raw: str) -> str:
    """Return canonical `ORD-xxxxx` (upper-case, no trailing punctuation)."""
    oid = re.sub(r"[!?.,]+$", "", raw.strip()).upper()
    return oid if oid.startswith("ORD-") else f"ORD-{oid.lstrip('ORD-')}"


# ---------------------------------------------------------------------------
# LangChain tools
# ---------------------------------------------------------------------------


@tool
def check_order_status(order_id: str) -> str:
    """Check the status of an order by order ID. Use this when a customer asks about their order."""
    logger.info(f"Checking order status for: {order_id}")
    order_id = _clean_order_id(order_id)
    order = ORDERS.get(order_id)
    if not order:
        return f"I couldn't find order {order_id}. Please verify the order number."

    parts = [f"Order {order_id} is currently {order['status']}."]
    if order["status"] == "shipped":
        parts.append(f"Tracking number: {order['tracking_number']}")
    parts.append(f"Items: {', '.join(order['items'])}")
    parts.append(f"Total: ${order['total']}")

    result = " ".join(parts)
    logger.info(f"Order status result: {result}")
    return result


@tool
def get_store_hours(location: str = "main") -> str:
    """Get the store hours for a specific location. Use this when asked about store hours or opening times."""
    logger.info(f"Getting store hours for location: {location}")
    return (
        f"Store hours for {location} location:\n"
        f"Monday-Friday: {STORE_HOURS['monday-friday']}\n"
        f"Saturday: {STORE_HOURS['saturday']}\n"
        f"Sunday: {STORE_HOURS['sunday']}"
    )


@tool
def process_return_request(order_id: str, product_name: str, reason: str) -> str:
    """Process a return request for a product. Use this when a customer wants to return an item."""
    logger.info(f"Processing return for order {order_id}, product: {product_name}, reason: {reason}")
    rid = f"RET-{_clean_order_id(order_id)[-5:]}"
    return (
        f"Return request {rid} has been created for {product_name} from order {order_id}. "
        f"Reason: {reason}. You will receive a return shipping label via email within 24 hours."
    )


# ---------------------------------------------------------------------------
# LangGraph wiring
# ---------------------------------------------------------------------------

memory = MemorySaver()


class ResponseFormat(BaseModel):
    """Respond to the user in this format."""

    status: Literal["input_required", "completed", "error", "inventory_query"] = "completed"
    message: str


class CustomerServiceAgent:
    """LangGraph customer-service agent."""

    SYSTEM_INSTRUCTION = """You are a helpful customer service agent for an online retail store. 

Your primary responsibilities:
1. Check order status when customers ask about their orders
2. Provide store hours information
3. Process return requests

You have access to the following tools:
- check_order_status: Use this to look up order information
- get_store_hours: Use this to provide store hours
- process_return_request: Use this to initiate returns

If a customer asks about product availability, inventory, or product details:
- Set status to 'inventory_query'
- Set message to explain that you need to check the inventory system

For all other requests within your capabilities:
- Set status to 'completed' when you successfully handle the request
- Set status to 'input_required' if you need more information from the user
- Set status to 'error' if there's an error processing the request

Always be helpful, professional, and concise."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self) -> None:
        self.model = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.3,
        )
        self.tools = [
            check_order_status,
            get_store_hours,
            process_return_request,
        ]

        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=ResponseFormat,
        )

    def invoke(self, query: str, session_id: str) -> dict[str, Any]:
        """Invoke the agent synchronously."""
        config = {"configurable": {"thread_id": session_id}}
        self.graph.invoke({"messages": [("user", query)]}, config)
        return self.get_agent_response(config)

    async def stream(self, query: str, session_id: str) -> AsyncIterable[dict[str, Any]]:
        """Stream responses for the given query."""
        try:
            logger.info(f"Customer service agent processing query: {query}")

            # Yield initial status
            yield {
                "is_task_complete": False,
                "require_user_input": False,
                "content": "Processing your request...",
            }

            inputs = {"messages": [("user", query)]}
            config = {"configurable": {"thread_id": session_id}}

            # Stream through the graph execution
            async for item in self.graph.astream(inputs, config, stream_mode="values"):
                if "messages" not in item:
                    continue

                messages = item["messages"]
                if not messages:
                    continue

                last_message = messages[-1]

                # Handle tool calls
                if (
                    isinstance(last_message, AIMessage)
                    and hasattr(last_message, "tool_calls")
                    and last_message.tool_calls
                    and len(last_message.tool_calls) > 0
                ):
                    for tool_call in last_message.tool_calls:
                        yield {
                            "is_task_complete": False,
                            "require_user_input": False,
                            "content": f"Looking up {tool_call['name'].replace('_', ' ')}...",
                        }

                # Handle tool responses
                elif isinstance(last_message, ToolMessage):
                    yield {
                        "is_task_complete": False,
                        "require_user_input": False,
                        "content": "Processing information...",
                    }

            # Get the final response
            yield self.get_agent_response(config)

        except Exception as exc:
            logger.error(f"Customer service stream error: {exc}", exc_info=True)
            yield {
                "is_task_complete": False,
                "require_user_input": True,
                "content": "I apologize, but I encountered an error processing your request. Please try again.",
            }

    def get_agent_response(self, config: dict[str, Any]) -> dict[str, Any]:
        """Extract the final response from the agent state."""
        current_state = self.graph.get_state(config)
        structured_response = current_state.values.get("structured_response")

        if structured_response and isinstance(structured_response, ResponseFormat):
            if structured_response.status == "input_required":
                return {
                    "is_task_complete": False,
                    "require_user_input": True,
                    "content": structured_response.message,
                }
            elif structured_response.status == "error":
                return {
                    "is_task_complete": False,
                    "require_user_input": True,
                    "content": structured_response.message,
                }
            elif structured_response.status == "inventory_query":
                # This is a special case for inventory queries
                return {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "inventory_query": True,
                    "content": structured_response.message,
                }
            elif structured_response.status == "completed":
                return {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": structured_response.message,
                }

        # Fallback response
        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "I apologize, but I was unable to process your request. Please try again or provide more information.",
        }
