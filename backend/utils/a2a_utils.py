"""Utility functions for A2A protocol operations."""

import asyncio
import logging
from typing import Optional, Dict, Any
import httpx

from a2a.client import A2AClient
from a2a.types import AgentCard, Message, Part, Role, TextPart

logger = logging.getLogger(__name__)


async def get_agent_card(agent_url: str) -> Optional[AgentCard]:
    """Get agent card from an A2A server."""
    try:
        client = A2AClient(url=agent_url)
        return await client.get_agent_card()
    except Exception as e:
        logger.error(f"Failed to get agent card from {agent_url}: {e}")
        return None


async def send_message_to_agent(
    agent_url: str,
    message_text: str,
    session_id: str = "default"
) -> Optional[str]:
    """Send a message to an A2A agent and get response."""
    try:
        client = A2AClient(url=agent_url)
        
        message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=message_text))]
        )
        
        response = await client.send(message)
        
        if response.artifacts and response.artifacts[0].parts:
            return response.artifacts[0].parts[0].root.text
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to send message to {agent_url}: {e}")
        return None


async def check_agent_health(agent_url: str) -> bool:
    """Check if an A2A agent is healthy."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{agent_url}/.well-known/agent.json", timeout=5.0)
            return response.status_code == 200
    except Exception:
        return False


async def discover_agents(agent_urls: list[str]) -> Dict[str, AgentCard]:
    """Discover multiple agents and return their cards."""
    agents = {}
    
    for url in agent_urls:
        card = await get_agent_card(url)
        if card:
            agents[url] = card
    
    return agents


class A2AManager:
    """Manager for A2A agent interactions."""
    
    def __init__(self, agent_urls: Optional[Dict[str, str]] = None):
        self.agent_urls = agent_urls or {
            "host": "http://localhost:8000",
            "inventory": "http://localhost:8001", 
            "customer_service": "http://localhost:8002",
        }
        self.agent_cards = {}
    
    async def initialize(self):
        """Initialize the manager by discovering agents."""
        self.agent_cards = await discover_agents(list(self.agent_urls.values()))
        
    async def send_to_agent(self, agent_name: str, message: str) -> Optional[str]:
        """Send message to a specific agent."""
        if agent_name not in self.agent_urls:
            raise ValueError(f"Unknown agent: {agent_name}")
        
        return await send_message_to_agent(
            self.agent_urls[agent_name],
            message
        )
    
    async def check_all_agents(self) -> Dict[str, bool]:
        """Check health of all agents."""
        health_status = {}
        
        for name, url in self.agent_urls.items():
            health_status[name] = await check_agent_health(url)
        
        return health_status
    
    def get_agent_info(self, agent_name: str) -> Optional[AgentCard]:
        """Get agent card for a specific agent."""
        url = self.agent_urls.get(agent_name)
        if url:
            return self.agent_cards.get(url)
        return None