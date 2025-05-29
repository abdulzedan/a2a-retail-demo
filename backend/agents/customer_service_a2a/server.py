"""Customer Service Agent A2A Server."""

import logging
import os
import click
from dotenv import load_dotenv

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

from .agent import CustomerServiceAgent
from .agent_executor import CustomerServiceAgentExecutor

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""

    pass


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to run the server on")
@click.option("--port", default=8002, help="Port to run the server on")
def main(host: str, port: int):
    """Start the Customer Service Agent A2A server."""
    try:
        # Check for API key
        if not os.getenv("GOOGLE_API_KEY"):
            raise MissingAPIKeyError("GOOGLE_API_KEY environment variable not set.")

        # Define agent capabilities
        capabilities = AgentCapabilities(streaming=True)

        # Define agent skills
        skill = AgentSkill(
            id="customer_service",
            name="Customer Service Support",
            description="Handles customer inquiries, order status, returns, and general support",
            tags=["customer service", "orders", "returns", "support"],
            examples=[
                "What's the status of my order ORD-12345?",
                "I want to return a product",
                "What are your store hours?",
                "Do you have Smart TVs in stock?",
                "I need help with my order",
            ],
        )

        # Create agent card - use localhost for URL to ensure consistent access
        agent_card = AgentCard(
            name="Customer Service Agent",
            description="Handles customer inquiries, order status checks, returns, and product availability questions. Can coordinate with inventory systems to provide real-time product information.",
            url=f"http://localhost:{port}/",
            version="1.0.0",
            defaultInputModes=CustomerServiceAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=CustomerServiceAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

        # Create request handler
        request_handler = DefaultRequestHandler(
            agent_executor=CustomerServiceAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )

        # Create A2A server
        server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )

        # Start server
        import uvicorn

        logger.info(f"Starting Customer Service Agent on http://{host}:{port}")
        uvicorn.run(server.build(), host=host, port=port)

    except MissingAPIKeyError as e:
        logger.error(f"Error: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        exit(1)


if __name__ == "__main__":
    main()
