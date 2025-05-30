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


class MissingConfigError(Exception):
    """Exception for missing configuration."""
    pass


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to run the server on")
@click.option("--port", default=8001, help="Port to run the server on")
def main(host: str, port: int):
    """Start the Inventory Agent A2A server with Vertex AI Search integration."""
    try:
        # Check for required configuration
        if not os.getenv("GOOGLE_API_KEY"):
            raise MissingConfigError("GOOGLE_API_KEY environment variable not set.")
        
        if not os.getenv("VERTEX_SEARCH_SERVING_CONFIG"):
            raise MissingConfigError(
                "VERTEX_SEARCH_SERVING_CONFIG environment variable not set.\n"
                "Format: projects/{project}/locations/{location}/collections/{collection}"
                "/dataStores/{datastore}/servingConfigs/{config}"
            )
        
        if not os.getenv("GOOGLE_CLOUD_PROJECT"):
            raise MissingConfigError("GOOGLE_CLOUD_PROJECT environment variable not set.")

        # Define agent capabilities
        capabilities = AgentCapabilities(streaming=True)

        # Define agent skills - updated to reflect Vertex AI Search capabilities
        skill = AgentSkill(
            id="inventory_management",
            name="Inventory Management with AI Search",
            description="Manages retail product inventory using Vertex AI Search for intelligent product discovery, stock levels, and availability checks",
            tags=["inventory", "products", "stock", "retail", "ai-search", "vertex-ai"],
            examples=[
                "Do you have Smart TVs in stock?",
                "Find products similar to wireless earbuds",
                "Search for electronics under $200",
                "Show me all products by TechVision brand",
                "What items are low in stock?",
                "Find yoga equipment",
            ],
        )

        # Create agent card - updated description
        agent_card = AgentCard(
            name="Inventory Management Agent (Vertex AI Powered)",
            description=(
                "Advanced inventory management agent powered by Vertex AI Search. "
                "Provides intelligent product search with semantic understanding, "
                "real-time stock availability, similarity search, and inventory analytics. "
                "Can find products by name, description, category, price range, or similar characteristics."
            ),
            url=f"http://localhost:{port}/",
            version="2.0.0",  # Bumped version for Vertex AI integration
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

        logger.info(f"Starting Inventory Agent (Vertex AI) on http://{host}:{port}")
        logger.info(f"Using Vertex AI Search: {os.getenv('VERTEX_SEARCH_SERVING_CONFIG')}")
        logger.info("Agent capabilities: Semantic search, similarity matching, real-time inventory")
        
        uvicorn.run(server.build(), host=host, port=port)

    except MissingConfigError as e:
        logger.error(f"Configuration Error: {e}")
        logger.error("\nPlease ensure your .env file contains:")
        logger.error("  GOOGLE_API_KEY=your-api-key")
        logger.error("  GOOGLE_CLOUD_PROJECT=your-project-id")
        logger.error("  VERTEX_SEARCH_SERVING_CONFIG=projects/.../servingConfigs/default_config")
        exit(1)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        exit(1)


if __name__ == "__main__":
    main()