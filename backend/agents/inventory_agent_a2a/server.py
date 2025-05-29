"""Inventory Agent A2A Server."""

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

from .agent import InventoryAgent
from .agent_executor import InventoryAgentExecutor

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Exception for missing API key."""

    pass


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to run the server on")
@click.option("--port", default=8001, help="Port to run the server on")
def main(host: str, port: int):
    """Start the Inventory Agent A2A server."""
    try:
        # Check for API key
        if not os.getenv("GOOGLE_API_KEY"):
            raise MissingAPIKeyError("GOOGLE_API_KEY environment variable not set.")

        # Define agent capabilities
        capabilities = AgentCapabilities(streaming=True)

        # Define agent skills
        skill = AgentSkill(
            id="inventory_management",
            name="Inventory Management",
            description="Manages retail product inventory, stock levels, and availability checks",
            tags=["inventory", "products", "stock", "retail"],
            examples=[
                "Do you have Smart TVs in stock?",
                "Check availability of product prod_001",
                "Search for wireless earbuds",
                "Show me products under $50",
                "What items are low in stock?",
            ],
        )

        # Create agent card - use localhost for URL to ensure consistent access
        agent_card = AgentCard(
            name="Inventory Management Agent",
            description="Manages retail product inventory, stock levels, and availability. Can check product availability, search products by various criteria, and monitor low stock items.",
            url=f"http://localhost:{port}/",
            version="1.0.0",
            defaultInputModes=InventoryAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=InventoryAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

        # Create request handler
        request_handler = DefaultRequestHandler(
            agent_executor=InventoryAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )

        # Create A2A server
        server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )

        # Start server
        import uvicorn

        logger.info(f"Starting Inventory Agent on http://{host}:{port}")
        uvicorn.run(server.build(), host=host, port=port)

    except MissingAPIKeyError as e:
        logger.error(f"Error: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        exit(1)


if __name__ == "__main__":
    main()
