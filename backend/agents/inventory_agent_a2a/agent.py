"""Inventory Agent using Google ADK and A2A Protocol."""

import asyncio
import json
import logging
import os
from typing import Any, AsyncIterable, Dict, List, Optional

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


def check_product_availability(product_id: str) -> Dict[str, Any]:
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
    query: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = True,
) -> Dict[str, Any]:
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
            if not any([
                query_lower in product["name"].lower(),
                query_lower in product["description"].lower(),  
                query_lower in product["brand"].lower() if product["brand"] else False,
                query_lower in product["category"].lower(),
            ]):
                continue
        
        results.append(product)
    
    return {
        "status": "success",
        "total_count": len(results),
        "products": results,
    }


def get_low_stock_items(threshold: int = 10) -> Dict[str, Any]:
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
    
    def get_processing_message(self) -> str:
        return "Checking inventory..."
    
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

Use the available tools to:
- check_product_availability: Check if a specific product is in stock
- search_products: Search for products by name, category, or other criteria
- get_low_stock_items: Get items that are running low in stock

When responding with product information, format it clearly with details like:
- Product name and ID
- Price
- Stock status and quantity
- Brand and category
""",
            tools=[
                check_product_availability,
                search_products,
                get_low_stock_items,
            ],
        )
    
    async def stream(self, query: str, session_id: str) -> AsyncIterable[Dict[str, Any]]:
        """Stream responses from the inventory agent."""
        try:
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
            
            content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=query)]
            )
            
            async for event in self._runner.run_async(
                user_id=self._user_id,
                session_id=session.id,
                new_message=content
            ):
                if event.is_final_response():
                    response = ""
                    if (event.content and event.content.parts and 
                        event.content.parts[0].text):
                        response = "\n".join([
                            p.text for p in event.content.parts if p.text
                        ])
                    elif (event.content and event.content.parts and 
                          any([p.function_response for p in event.content.parts])):
                        # Handle function call responses
                        for part in event.content.parts:
                            if part.function_response:
                                response = json.dumps(part.function_response.response, indent=2)
                                break
                    
                    yield {
                        "is_task_complete": True,
                        "content": response,
                    }
                else:
                    yield {
                        "is_task_complete": False,
                        "updates": self.get_processing_message(),
                    }
        
        except Exception as e:
            logger.error(f"Error in inventory agent stream: {e}")
            yield {
                "is_task_complete": True,
                "content": f"Error processing inventory request: {str(e)}",
            }