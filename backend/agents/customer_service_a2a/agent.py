"""Customer Service Agent using LangGraph and A2A Protocol.

Patch 2025‑05‑26
-----------------
* Added `_clean_order_id` helper.
* Added docstrings for each `@tool`.
* Robust filtering of non‑text tool messages before Gemini call while
  preserving function‑call context.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterable
from typing import Any, Dict, List, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel

from a2a.client import A2AClient
from a2a.types import Message, Part, Role, TextPart

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
    """Return shipping status, items and total for *order_id*."""
    order_id = _clean_order_id(order_id)
    order = ORDERS.get(order_id)
    if not order:
        return f"I couldn't find order {order_id}. Please verify the number."
    parts = [f"Order {order_id} is {order['status']}."]
    if order["status"] == "shipped":
        parts.append(f"Tracking #: {order['tracking_number']}.")
    parts.append(f"Items: {', '.join(order['items'])}. Total: ${order['total']}")
    return " ".join(parts)


@tool
def get_store_hours(location: str = "main") -> str:
    """Return formatted opening hours for *location*."""
    return (
        f"Store hours ({location}):\n"
        f"Monday-Friday: {STORE_HOURS['monday-friday']}\n"
        f"Saturday: {STORE_HOURS['saturday']}\n"
        f"Sunday: {STORE_HOURS['sunday']}"
    )


@tool
def process_return_request(order_id: str, product_name: str, reason: str) -> str:
    """Create a mock RMA and confirmation."""
    rid = f"RET-{_clean_order_id(order_id)[-5:]}"
    return (
        f"Return request {rid} created for {product_name} (order {order_id}). "
        f"Reason: {reason}. You will receive a shipping label in 24 h."
    )


async def _query_inventory(query: str) -> str:
    try:
        client = A2AClient(url="http://localhost:8001")
        msg = Message(role=Role.user, parts=[Part(root=TextPart(text=query))])
        resp = await client.send(msg)
        if resp.artifacts and resp.artifacts[0].parts:
            return resp.artifacts[0].parts[0].root.text
        return "Unable to get inventory information."    
    except Exception as exc:  # noqa: BLE001
        logger.error("Inventory agent error: %s", exc)
        return "Inventory system unavailable."


@tool
async def check_inventory(query: str) -> str:
    """Delegate to inventory agent for availability/details."""
    return await _query_inventory(query)

# ---------------------------------------------------------------------------
# LangGraph wiring
# ---------------------------------------------------------------------------

memory = MemorySaver()


class ConversationState(BaseModel):
    messages: List[Any]


class CustomerServiceAgent:
    """LangGraph customer-service agent."""

    SYSTEM_INSTRUCTION = (
        "You are a helpful customer‑service agent. Use the provided tools "
        "(e.g., `check_inventory`, `check_order_status`) to answer queries."
    )

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self) -> None:
        self.model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)
        self.tools = [
            check_order_status,
            get_store_hours,
            process_return_request,
            check_inventory,
        ]
        self.graph = self._build_graph()

    # ---------- build graph ----------

    def _build_graph(self):
        tool_node = ToolNode(self.tools)
        wf = StateGraph(ConversationState)
        wf.add_node("agent", self._call_model)
        wf.add_node("tools", tool_node)
        wf.set_entry_point("agent")
        wf.add_conditional_edges("agent", self._needs_tools, {"continue": "tools", "end": END})
        wf.add_edge("tools", "agent")
        return wf.compile(checkpointer=memory)

    # ---------- core LLM call ----------

    def _call_model(self, state: ConversationState):
        msgs = state.messages
        if not msgs or not isinstance(msgs[0], SystemMessage):
            msgs = [SystemMessage(content=self.SYSTEM_INSTRUCTION)] + msgs

        # Remove ToolMessage (they lack textual content) but keep AI/Human + tool_calls.
        curated = [m for m in msgs if not isinstance(m, ToolMessage)]

        # Ensure at least one HumanMessage.
        if not any(isinstance(m, HumanMessage) for m in curated):
            curated.append(HumanMessage(content="Hi"))

        resp = self.model.bind_tools(self.tools).invoke(curated)
        return {"messages": msgs + [resp]}

    @staticmethod
    def _needs_tools(state: ConversationState):
        last = state.messages[-1]
        return "continue" if getattr(last, "tool_calls", None) else "end"

    # ---------- streaming ----------

    async def stream(self, query: str, session_id: str) -> AsyncIterable[Dict[str, Any]]:
        try:
            cfg = {"configurable": {"thread_id": session_id}}
            init = ConversationState(messages=[HumanMessage(content=query)])
            async for ev in self.graph.astream(init.dict(), config=cfg, stream_mode="values"):
                if "messages" not in ev:
                    continue
                last = ev["messages"][-1]
                if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
                    yield {"is_task_complete": False, "require_user_input": False, "content": "Checking…"}
                elif isinstance(last, AIMessage):
                    yield {"is_task_complete": True, "require_user_input": False, "content": last.content}
                    break
        except Exception as exc:  # noqa: BLE001
            logger.error("Customer‑service stream error: %s", exc)
            yield {"is_task_complete": True, "require_user_input": False, "content": f"Error: {exc}"}

    # ---------- non‑stream helper ----------

    def invoke(self, query: str, session_id: str) -> str:
        cfg = {"configurable": {"thread_id": session_id}}
        init = ConversationState(messages=[HumanMessage(content=query)])
        res = self.graph.invoke(init.dict(), cfg)
        for msg in reversed(res["messages"]):
            if isinstance(msg, AIMessage):
                return msg.content
        return "Unable to process your request."
