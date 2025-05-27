"""Utility helpers + compatibility shim for *a2a-sdk* API changes.

The SDK’s old convenience coroutine was ``await client.send(message)``.  
As of 2025‑04 the library exposes typed helpers like
``await client.send_message(SendMessageRequest(...))`` instead.

This module patches **A2AClient** so existing demo code can keep calling
``client.send(...)`` while you migrate.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Dict, Optional

import httpx
from a2a.client import A2AClient
from a2a.types import (
    AgentCard,
    Message,
    Part,
    Role,
    TextPart,
    SendMessageRequest,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Back‑compat shim
# ---------------------------------------------------------------------------

if not hasattr(A2AClient, "send"):

    async def _shim_send(self: A2AClient, message: Message, *args, **kwargs):  # type: ignore[override]
        """Poly‑fill for the removed ``A2AClient.send`` coroutine.

        Resolution order:
        1. Native *send_message* helper (new API).
        2. Helper on *self.tasks* – ``send``, ``create``, etc. (intermediate API).
        """
        # 1️⃣ new synchronous helper ---------------------------------------
        if hasattr(self, "send_message"):
            try:
                from a2a.types import MessageSendParams  # local import to avoid circularity
                req = SendMessageRequest(params=MessageSendParams(message=message))
                resp = await self.send_message(req, *args, **kwargs)  # type: ignore[arg-type]
                # The response wrapper’s *result* field already contains Message/Task
                                # The RootModel wrapper stores payload in .root
                payload = getattr(resp, "root", resp)
                return getattr(payload, "result", payload)
            except Exception as exc:  # noqa: BLE001
                logger.error("send_message compat path failed – %s", exc)
                raise

        # 2️⃣ older *tasks.xxx* helpers ------------------------------------
        if hasattr(self, "tasks"):
            for cand in ("send", "create", "create_task", "submit", "dispatch"):
                helper = getattr(self.tasks, cand, None)  # type: ignore[attr-defined]
                if helper:
                    return await helper(message, *args, **kwargs)

        raise AttributeError(
            "A2AClient lacks a callable send helper. Update demo code to use "
            "`await client.send_message(SendMessageRequest(...))` or ensure the "
            "library version exposes one of the probed helpers."
        )

    setattr(A2AClient, "send", _shim_send)  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Low‑level helpers
# ---------------------------------------------------------------------------


async def get_agent_card(agent_url: str) -> Optional[AgentCard]:
    """Retrieve the remote *AgentCard* from `/.well‑known/agent.json`."""
    try:
        async with httpx.AsyncClient() as hc:
            return await A2AClient(url=agent_url, httpx_client=hc).get_agent_card()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch agent card from %s – %s", agent_url, exc)
        return None


async def send_message_to_agent(
    agent_url: str,
    message_text: str,
    session_id: str = "default",
) -> Optional[str]:
    """Send a single‑turn query and return the first text reply (if any)."""
    try:
        async with httpx.AsyncClient() as hc:
            client = A2AClient(url=agent_url, httpx_client=hc)

            outbound = Message(
                messageId=str(uuid.uuid4()),
                contextId=session_id,
                role=Role.user,
                parts=[Part(root=TextPart(text=message_text))],
            )

            reply = await client.send(outbound)  # patched shim handles all APIs

            # *reply* may be Message, Task, or wrapper; try to extract first text.
            if hasattr(reply, "artifacts") and reply.artifacts:
                parts = reply.artifacts[0].parts
                if parts:
                    return parts[0].root.text
            elif isinstance(reply, Message):
                for p in reply.parts:
                    if p.root.kind == "text":
                        return p.root.text
            return None
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send message to %s – %s", agent_url, exc)
        return None


async def check_agent_health(agent_url: str) -> bool:
    """Ping the agent card endpoint; return *True* if HTTP 200."""
    try:
        async with httpx.AsyncClient() as hc:
            resp = await hc.get(f"{agent_url}/.well-known/agent.json", timeout=5)
            return resp.status_code == 200
    except Exception:  # noqa: BLE001
        return False


async def _discover_single(url: str, hc: httpx.AsyncClient, out: Dict[str, AgentCard]):
    try:
        card = await A2AClient(url=url, httpx_client=hc).get_agent_card()
        if card:
            out[url] = card
    except Exception as exc:  # noqa: BLE001
        logger.warning("Agent discovery failed for %s – %s", url, exc)


async def discover_agents(urls: list[str]) -> Dict[str, AgentCard]:
    """Return mapping *url → AgentCard* for all reachable URLs."""
    found: Dict[str, AgentCard] = {}
    async with httpx.AsyncClient() as hc:
        await asyncio.gather(*[_discover_single(u, hc, found) for u in urls])
    return found


# ---------------------------------------------------------------------------
# Convenience manager
# ---------------------------------------------------------------------------

class A2AManager:
    """Tiny helper class that caches AgentCards and wraps pings/messages."""

    def __init__(self, agent_urls: Optional[Dict[str, str]] = None):
        self.agent_urls = agent_urls or {
            "host": "http://localhost:8000",
            "inventory": "http://localhost:8001",
            "customer_service": "http://localhost:8002",
        }
        self.agent_cards: Dict[str, AgentCard] = {}
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient()
        await self.initialize()
        return self

    async def __aexit__(self, *exc):
        if self._client:
            await self._client.aclose()

    async def initialize(self):
        self.agent_cards = await discover_agents(list(self.agent_urls.values()))

    async def send_to_agent(self, name: str, text: str) -> Optional[str]:
        if name not in self.agent_urls:
            raise ValueError(f"Unknown agent '{name}'. Expected one of {list(self.agent_urls)}")
        return await send_message_to_agent(self.agent_urls[name], text)

    async def check_all_agents(self) -> Dict[str, bool]:
        return {n: await check_agent_health(u) for n, u in self.agent_urls.items()}

    def get_agent_info(self, name: str) -> Optional[AgentCard]:
        url = self.agent_urls.get(name)
        return self.agent_cards.get(url) if url else None
