"""Demo server implementation following A2A documentation pattern."""

import asyncio
import logging
import os
from typing import Dict, List, Optional
import httpx
from a2a.types import AgentCard, Message
from backend.hosts.multiagent.host_agent import HostAgent
from backend.hosts.multiagent.remote_agent_connection import RemoteAgentConnection, TaskCallbackArg
from backend.utils.a2a_utils import get_agent_card

logger = logging.getLogger(__name__)

class DemoServer:
    """Demo server that manages the host agent and remote agent connections."""
    
    def __init__(self):
        self.http_client = httpx.AsyncClient()
        self.remote_agents: List[RemoteAgentConnection] = []
        self.host_agent: Optional[HostAgent] = None
        
        # Initialize host agent
        self._initialize_host_agent()
    
    def _initialize_host_agent(self):
        """Initialize the host agent."""
        self.host_agent = HostAgent(
            remote_agents=self.remote_agents,
            http_client=self.http_client,
            task_callback=self._task_callback
        )
    
    def _task_callback(self, task: TaskCallbackArg, agent_card: AgentCard):
        """Handle task callbacks from remote agents."""
        logger.info(f"Task callback from {agent_card.name}: {task}")
    
    async def register_agent(self, agent_url: str) -> bool:
        """Register a remote agent."""
        try:
            agent_card = await get_agent_card(agent_url)
            if agent_card:
                agent_conn = RemoteAgentConnection(agent_card, self._task_callback)
                self.remote_agents.append(agent_conn)
                if self.host_agent:
                    self.host_agent.register_agent_card(agent_card)
                logger.info(f"Registered agent: {agent_card.name} at {agent_url}")
                return True
        except Exception as e:
            logger.error(f"Failed to register agent at {agent_url}: {e}")
        return False
    
    async def send_message(self, message: Message) -> Optional[Message]:
        """Send message through the host agent."""
        if self.host_agent:
            return await self.host_agent.route_message(message)
        return None
    
    async def get_registered_agents(self) -> List[AgentCard]:
        """Get list of registered agent cards."""
        return [agent.agent_card for agent in self.remote_agents]
    
    async def check_agent_health(self) -> Dict[str, bool]:
        """Check health of all registered agents."""
        health_status = {}
        for agent in self.remote_agents:
            try:
                await agent.get_agent_card()
                health_status[agent.agent_card.name] = True
            except Exception:
                health_status[agent.agent_card.name] = False
        return health_status
    
    async def shutdown(self):
        """Cleanup resources."""
        await self.http_client.aclose()

# Global demo server instance
demo_server = DemoServer()