"""Host Agent A2A Server - Using Official A2A SDK."""

import logging
import os
import click
from dotenv import load_dotenv

# Import the correct A2A components
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

from .agent import HostAgent
from .agent_executor import HostAgentExecutor

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.option("--host", default="localhost", help="Host to run the server on")
@click.option("--port", default=8000, help="Port to run the server on")
def main(host: str, port: int):
    """Start the Host Agent A2A server."""
    try:
        # Check for API key
        if not os.getenv("GOOGLE_API_KEY"):
            raise Exception("GOOGLE_API_KEY environment variable not set.")
        
        # Define agent capabilities
        capabilities = AgentCapabilities(streaming=True)
        
        # Define agent skills
        skill = AgentSkill(
            id="retail_coordination",
            name="Retail Service Coordination",
            description="Coordinates between customer service and inventory management",
            tags=["retail", "coordination", "customer service", "inventory"],
            examples=[
                "Do you have Smart TVs in stock?",
                "What's the status of order ORD-12345?",
                "Help me with a return",
                "Show me products under $50",
                "What are your store hours?",
            ],
        )
        
        # Create agent card
        agent_card = AgentCard(
            name="Retail Host Agent",
            description="Orchestrates between customer service and inventory management agents for a seamless retail experience",
            url=f"http://{host}:{port}/",
            version="1.0.0",
            defaultInputModes=HostAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=HostAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        
        # Create request handler
        request_handler = DefaultRequestHandler(
            agent_executor=HostAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )
        
        # Create A2A server
        server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )
        
        # Start server
        import uvicorn
        logger.info(f"Starting Host Agent on http://{host}:{port}")
        uvicorn.run(server.build(), host=host, port=port)
        
    except Exception as e:
        logger.error(f"Server startup error: {e}")
        exit(1)


if __name__ == "__main__":
    main()