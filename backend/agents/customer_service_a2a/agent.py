"""Customer Service Agent using LangGraph and A2A Protocol."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncIterable
from typing import Any, Dict, List, Literal

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

ORDERS: Dict[str, Dict[str, Any]] = {
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


# Note: We don't include check_inventory tool here as that should be handled
# by the host agent routing to the inventory agent

# ---------------------------------------------------------------------------
# LangGraph wiring
# ---------------------------------------------------------------------------

memory = MemorySaver()


class ConversationState(BaseModel):
    """State for the conversation."""
    messages: List[Any]
    
    class Config:
        arbitrary_types_allowed = True


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

If a customer asks about product availability or inventory, you should indicate that you need to check the inventory system (but don't have direct access to it).

Always use the appropriate tool when handling customer requests. Be helpful, professional, and concise."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self) -> None:
        self.model = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", 
            temperature=0.3,
            convert_system_message_to_human=True
        )
        self.tools = [
            check_order_status,
            get_store_hours,
            process_return_request,
        ]
        self.graph = self._build_graph()

    def _build_graph(self):
        """Build the LangGraph state machine."""
        workflow = StateGraph(ConversationState)
        
        # Create tool node
        tool_node = ToolNode(self.tools)
        
        # Add nodes
        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", tool_node)
        
        # Set entry point
        workflow.set_entry_point("agent")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "agent",
            self._should_use_tools,
            {
                "tools": "tools",
                "end": END,
            }
        )
        
        # Add edge from tools back to agent
        workflow.add_edge("tools", "agent")
        
        # Compile with memory
        return workflow.compile(checkpointer=memory)

    def _call_model(self, state: ConversationState) -> Dict[str, Any]:
        """Call the LLM with the current conversation state."""
        messages = state.messages
        
        # Ensure we have system message
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=self.SYSTEM_INSTRUCTION)] + messages
        
        logger.debug(f"Calling model with {len(messages)} messages")
        
        # Bind tools and invoke
        try:
            response = self.model.bind_tools(self.tools).invoke(messages)
            logger.debug(f"Model response: {response}")
            return {"messages": messages + [response]}
        except Exception as e:
            logger.error(f"Error calling model: {e}", exc_info=True)
            error_msg = AIMessage(content="I apologize, but I encountered an error processing your request. Please try again.")
            return {"messages": messages + [error_msg]}

    def _should_use_tools(self, state: ConversationState) -> Literal["tools", "end"]:
        """Determine if we should use tools or end the conversation."""
        messages = state.messages
        last_message = messages[-1]
        
        # Check if the last message has tool calls
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            logger.debug(f"Using tools: {[tc.get('name') for tc in last_message.tool_calls]}")
            return "tools"
        
        logger.debug("No tool calls, ending conversation")
        return "end"

    async def stream(self, query: str, session_id: str) -> AsyncIterable[Dict[str, Any]]:
        """Stream responses for the given query."""
        try:
            logger.info(f"Customer service agent processing query: {query}")
            
            # Yield initial status
            yield {
                "type": "status",
                "message": "Processing your request..."
            }
            
            # Initialize conversation
            config = {"configurable": {"thread_id": session_id}}
            messages = [
                SystemMessage(content=self.SYSTEM_INSTRUCTION),
                HumanMessage(content=query)
            ]
            initial_state = ConversationState(messages=messages)
            
            # Track tool calls
            has_called_tools = False
            
            # Stream the graph execution
            async for event in self.graph.astream(
                initial_state.dict(), 
                config=config,
                stream_mode="values"
            ):
                if "messages" not in event:
                    continue
                    
                messages = event["messages"]
                if not messages:
                    continue
                
                last_message = messages[-1]
                logger.debug(f"Stream event - message type: {type(last_message).__name__}")
                
                # Handle tool calls
                if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls") and last_message.tool_calls:
                    has_called_tools = True
                    for tool_call in last_message.tool_calls:
                        yield {
                            "type": "tool_call",
                            "tool_name": tool_call["name"],
                            "message": f"Looking up {tool_call['name'].replace('_', ' ')}..."
                        }
                
                # Handle tool responses
                elif isinstance(last_message, ToolMessage):
                    yield {
                        "type": "status",
                        "message": "Processing information..."
                    }
                
                # Check if this is about inventory
                elif isinstance(last_message, AIMessage) and last_message.content:
                    content_lower = last_message.content.lower()
                    inventory_keywords = ["stock", "inventory", "available", "in stock", "product", "item"]
                    
                    if any(keyword in content_lower for keyword in inventory_keywords) and not has_called_tools:
                        # This looks like an inventory query
                        yield {
                            "type": "inventory_query",
                            "message": "This appears to be an inventory question. I'll need to check our inventory system."
                        }
                        yield {
                            "type": "result",
                            "content": "I'll need to check our inventory system for product availability. Please hold on while I transfer your query to our inventory specialist."
                        }
                        break
                    else:
                        # Normal response
                        logger.info(f"Final response: {last_message.content}")
                        yield {
                            "type": "result",
                            "content": last_message.content
                        }
                        break
            
        except Exception as exc:
            logger.error(f"Customer service stream error: {exc}", exc_info=True)
            yield {
                "type": "error",
                "message": f"Error processing request: {str(exc)}"
            }