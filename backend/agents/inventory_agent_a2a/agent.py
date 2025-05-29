"""Inventory Agent using Google ADK and A2A Protocol."""

import logging
from typing import Any
from collections.abc import AsyncIterable

from google.adk.agents import Agent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

logger = logging.getLogger(__name__)

# Sample inventory data
INVENTORY_DATA = [
    {
        "id": "prod_001",
        "name": "Smart TV 55-inch 4K",
        "description": "Ultra HD smart LED TV with built-in streaming apps",
        "category": "electronics",
        "price": 699.99,
        "stock_quantity": 25,
        "stock_status": "In Stock",
        "sku": "TV55-4K-001",
        "brand": "TechVision",
    },
    {
        "id": "prod_002",
        "name": "Wireless Earbuds Pro",
        "description": "Noise cancelling wireless earbuds with 24h battery",
        "category": "electronics",
        "price": 199.99,
        "stock_quantity": 150,
        "stock_status": "In Stock",
        "sku": "WE-PRO-002",
        "brand": "AudioMax",
    },
    {
        "id": "prod_003",
        "name": "Cotton T-Shirt",
        "description": "100% organic cotton T-shirt, multiple colors",
        "category": "clothing",
        "price": 29.99,
        "stock_quantity": 8,
        "stock_status": "Low Stock",
        "sku": "TS-COT-003",
        "brand": "EcoWear",
    },
    {
        "id": "prod_004",
        "name": "Coffee Maker Deluxe",
        "description": "12-cup programmable coffee maker with thermal carafe",
        "category": "home",
        "price": 89.99,
        "stock_quantity": 0,
        "stock_status": "Out of Stock",
        "sku": "CM-DLX-004",
        "brand": "BrewMaster",
    },
    {
        "id": "prod_005",
        "name": "Yoga Mat Premium",
        "description": "Extra thick non-slip yoga mat with carrying strap",
        "category": "sports",
        "price": 49.99,
        "stock_quantity": 45,
        "stock_status": "In Stock",
        "sku": "YM-PRM-005",
        "brand": "FitLife",
    },
]


def check_product_availability(product_id: str) -> dict[str, Any]:
    """Check if a specific product is available in inventory."""
    for product in INVENTORY_DATA:
        if product["id"] == product_id or product["sku"].lower() == product_id.lower():
            return {
                "status": "success",
                "product_id": product["id"],
                "name": product["name"],
                "available": product["stock_quantity"] > 0,
                "stock_quantity": product["stock_quantity"],
                "stock_status": product["stock_status"],
                "price": product["price"],
            }

    return {
        "status": "error",
        "error_message": f"Product {product_id} not found",
    }


def search_products(
    query: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    in_stock_only: bool = True,
) -> dict[str, Any]:
    """Search for products based on various criteria."""
    results = []

    for product in INVENTORY_DATA:
        # Filter by category
        if category and product["category"].lower() != category.lower():
            continue

        # Filter by price range
        if min_price and product["price"] < min_price:
            continue
        if max_price and product["price"] > max_price:
            continue

        # Filter by stock availability
        if in_stock_only and product["stock_quantity"] == 0:
            continue

        # Filter by search query
        if query:
            query_lower = query.lower()
            if not any(
                [
                    query_lower in product["name"].lower(),
                    query_lower in product["description"].lower(),
                    query_lower in product["brand"].lower() if product["brand"] else False,
                    query_lower in product["category"].lower(),
                ]
            ):
                continue

        results.append(product)

    return {
        "status": "success",
        "total_count": len(results),
        "products": results,
    }


def get_low_stock_items(threshold: int = 10) -> dict[str, Any]:
    """Get items that are low in stock."""
    low_stock_items = [
        {
            "id": product["id"],
            "name": product["name"],
            "current_stock": product["stock_quantity"],
            "category": product["category"],
            "sku": product["sku"],
        }
        for product in INVENTORY_DATA
        if 0 < product["stock_quantity"] < threshold
    ]

    return {
        "status": "success",
        "threshold": threshold,
        "count": len(low_stock_items),
        "products": low_stock_items,
    }


class InventoryAgent:
    """Inventory management agent that handles product availability and stock levels."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        self._agent = self._build_agent()
        self._user_id = "inventory_agent_user"
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def _build_agent(self) -> Agent:
        """Build the ADK agent for inventory management."""
        return Agent(
            name="inventory_agent",
            model="gemini-2.0-flash",
            description="Retail inventory management agent that handles product availability, stock levels, and product searches.",
            instruction="""You are an inventory management assistant for a retail organization. Your role is to:

1. Check product availability and stock levels
2. Search for products based on various criteria (name, category, price range)
3. Monitor low stock items
4. Provide accurate inventory information

Always provide clear, accurate information about product availability and stock status. 
When products are out of stock, mention alternative products if available.
Format your responses in a helpful and organized manner.

IMPORTANT SEARCH TIPS:
- When searching for products, start with a broad search using just the query parameter
- Don't assume category names - our categories are: "electronics", "clothing", "home", "sports"
- If the initial search returns no results, try searching without category filters first
- TVs are in the "electronics" category, not "TV" category

Use the available tools to:
- check_product_availability: Check if a specific product is in stock by product ID
- search_products: Search for products by name, category, or other criteria
- get_low_stock_items: Get items that are running low in stock

When responding with product information, format it clearly with details like:
- Product name and ID
- Price
- Stock status and quantity
- Brand and category

If a search returns no results, try a broader search before saying the item is not available.""",
            tools=[
                check_product_availability,
                search_products,
                get_low_stock_items,
            ],
        )

    async def stream(self, query: str, session_id: str) -> AsyncIterable[dict[str, Any]]:
        """Stream responses from the inventory agent."""
        try:
            # Get or create session
            session = await self._runner.session_service.get_session(
                app_name=self._agent.name,
                user_id=self._user_id,
                session_id=session_id,
            )

            if session is None:
                session = await self._runner.session_service.create_session(
                    app_name=self._agent.name,
                    user_id=self._user_id,
                    state={},
                    session_id=session_id,
                )

            # Create user message
            content = types.Content(role="user", parts=[types.Part.from_text(text=query)])

            # Yield initial status
            yield {"type": "status", "message": "Processing inventory request..."}

            # Run agent
            tool_called = False # noqa F401
            final_response = None

            async for event in self._runner.run_async(
                user_id=self._user_id, session_id=session.id, new_message=content
            ):
                # Check for tool calls
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.function_call:
                            tool_called = True # noqa F401
                            yield {
                                "type": "tool_call",
                                "tool_name": part.function_call.name,
                                "message": f"Checking {part.function_call.name.replace('_', ' ')}...",
                            }

                # Check for final response
                if event.is_final_response():
                    final_response = event

            # Process final response
            if final_response and final_response.content:
                response_text = ""
                response_data = None

                if final_response.content.parts:
                    # Extract text parts
                    text_parts = []
                    for part in final_response.content.parts:
                        if part.text:
                            text_parts.append(part.text)
                        elif part.function_response:
                            # Handle function response
                            response_data = part.function_response.response

                    if text_parts:
                        response_text = "\n".join(text_parts)

                # Yield final result
                if response_data:
                    yield {"type": "result", "content": response_data}
                else:
                    yield {"type": "result", "content": response_text or "No response generated"}
            else:
                yield {"type": "error", "message": "No response from inventory agent"}

        except Exception as e:
            logger.error(f"Error in inventory agent stream: {e}", exc_info=True)
            yield {"type": "error", "message": f"Error processing inventory request: {str(e)}"}
