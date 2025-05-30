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

# Import the VertexSearchStore
import sys
from pathlib import Path
# Add the project root to the path to import from backend.utils
ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
from backend.utils.vector_search_store import VertexSearchStore

logger = logging.getLogger(__name__)


class InventoryAgent:
    """Inventory management agent that handles product availability and stock levels using Vertex AI Search."""
    
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]
    
    def __init__(self):
        # Initialize Vertex AI Search Store
        serving_config = os.getenv("VERTEX_SEARCH_SERVING_CONFIG")
        if not serving_config:
            raise ValueError(
                "VERTEX_SEARCH_SERVING_CONFIG environment variable must be set. "
                "Format: projects/{project}/locations/{location}/collections/{collection}/dataStores/{datastore}/servingConfigs/{config}"
            )
        
        self._search_store = VertexSearchStore(serving_config=serving_config)
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
        # Store reference to search store for use in tools
        search_store = self._search_store
        
        def check_product_availability(product_id: str) -> Dict[str, Any]:
            """Check if a specific product is available in inventory."""
            try:
                # Use exact ID matching
                result = search_store.get_by_id(product_id)
                
                if result:
                    if "metadata" in result:
                        metadata = result["metadata"]
                        return {
                            "status": "success",
                            "product_id": result.get("id", product_id),
                            "name": metadata.get("name", "Unknown"),
                            "available": metadata.get("stock_quantity", 0) > 0,
                            "stock_quantity": metadata.get("stock_quantity", 0),
                            "stock_status": metadata.get("stock_status", "Unknown"),
                            "price": metadata.get("price", 0),
                            "description": metadata.get("description", ""),
                            "category": metadata.get("category", ""),
                            "brand": metadata.get("brand", ""),
                            "sku": metadata.get("sku", ""),
                        }
                    else:
                        return {
                            "status": "success",
                            "product_id": result.get("id", product_id),
                            "name": result.get("name", "Unknown"),
                            "available": result.get("stock_quantity", 0) > 0,
                            "stock_quantity": result.get("stock_quantity", 0),
                            "stock_status": result.get("stock_status", "Unknown"),
                            "price": result.get("price", 0),
                            "description": result.get("description", ""),
                            "category": result.get("category", ""),
                            "brand": result.get("brand", ""),
                            "sku": result.get("sku", ""),
                        }
                
                return {
                    "status": "error",
                    "error_message": f"Product {product_id} not found",
                }
                
            except Exception as e:
                logger.error(f"Error checking product availability: {e}")
                return {
                    "status": "error",
                    "error_message": f"Failed to check product: {str(e)}",
                }
        def search_products_by_query(query: str) -> Dict[str, Any]:
            """Search for products by name or description.
            
            Args:
                query: Search term to look for in product names and descriptions
            """
            try:
                # Use Vertex AI Search's hybrid search capabilities
                results = search_store.search(query=query, top_k=20)
                
                products = []
                for result in results:
                    # Handle both metadata and flattened data structures
                    if "metadata" in result:
                        metadata = result["metadata"]
                        products.append({
                            "id": result.get("id"),
                            "name": metadata.get("name"),
                            "description": metadata.get("description"),
                            "category": metadata.get("category"),
                            "price": metadata.get("price"),
                            "stock_quantity": metadata.get("stock_quantity", 0),
                            "stock_status": metadata.get("stock_status"),
                            "sku": metadata.get("sku"),
                            "brand": metadata.get("brand"),
                            "similarity_score": result.get("similarity_score", 0),
                        })
                    else:
                        # Flattened structure
                        products.append({
                            "id": result.get("id"),
                            "name": result.get("name"),
                            "description": result.get("description"),
                            "category": result.get("category"),
                            "price": result.get("price"),
                            "stock_quantity": result.get("stock_quantity", 0),
                            "stock_status": result.get("stock_status"),
                            "sku": result.get("sku"),
                            "brand": result.get("brand"),
                            "similarity_score": result.get("similarity_score", 0),
                        })
                
                return {
                    "status": "success",
                    "total_count": len(products),
                    "products": products,
                }
                
            except Exception as e:
                logger.error(f"Error searching products: {e}")
                return {
                    "status": "error",
                    "error_message": f"Search failed: {str(e)}",
                    "products": [],
                }

        def search_products_by_category(category: str) -> Dict[str, Any]:
            """Search for products in a specific category.
            
            Args:
                category: Category name (electronics, clothing, home, sports)
            """
            try:
                # Search with category filter
                query = f"category:{category.lower()}"
                results = search_store.search(query=query, top_k=50)
                
                products = []
                for result in results:
                    # Get product data
                    if "metadata" in result:
                        metadata = result["metadata"]
                        # Double-check category match
                        if metadata.get("category", "").lower() == category.lower():
                            products.append({
                                "id": result.get("id"),
                                "name": metadata.get("name"),
                                "description": metadata.get("description"),
                                "category": metadata.get("category"),
                                "price": metadata.get("price"),
                                "stock_quantity": metadata.get("stock_quantity", 0),
                                "stock_status": metadata.get("stock_status"),
                                "sku": metadata.get("sku"),
                                "brand": metadata.get("brand"),
                            })
                    else:
                        # Flattened structure
                        if result.get("category", "").lower() == category.lower():
                            products.append({
                                "id": result.get("id"),
                                "name": result.get("name"),
                                "description": result.get("description"),
                                "category": result.get("category"),
                                "price": result.get("price"),
                                "stock_quantity": result.get("stock_quantity", 0),
                                "stock_status": result.get("stock_status"),
                                "sku": result.get("sku"),
                                "brand": result.get("brand"),
                            })
                
                return {
                    "status": "success",
                    "total_count": len(products),
                    "products": products,
                }
                
            except Exception as e:
                logger.error(f"Error searching by category: {e}")
                return {
                    "status": "error",
                    "error_message": f"Category search failed: {str(e)}",
                    "products": [],
                }

        def search_products_by_price_range(min_price: float, max_price: float) -> Dict[str, Any]:
            """Search for products within a price range.
            
            Args:
                min_price: Minimum price
                max_price: Maximum price
            """
            try:
                # Search for products and filter by price
                # Vertex AI Search doesn't have native numeric range filters in the query syntax,
                # so we'll search broadly and filter results
                query = f"price product"  # Generic query to get products
                results = search_store.search(query=query, top_k=100)
                
                products = []
                for result in results:
                    # Get price from appropriate location
                    if "metadata" in result:
                        price = result["metadata"].get("price", 0)
                        if min_price <= price <= max_price:
                            metadata = result["metadata"]
                            products.append({
                                "id": result.get("id"),
                                "name": metadata.get("name"),
                                "description": metadata.get("description"),
                                "category": metadata.get("category"),
                                "price": price,
                                "stock_quantity": metadata.get("stock_quantity", 0),
                                "stock_status": metadata.get("stock_status"),
                                "sku": metadata.get("sku"),
                                "brand": metadata.get("brand"),
                            })
                    else:
                        price = result.get("price", 0)
                        if min_price <= price <= max_price:
                            products.append({
                                "id": result.get("id"),
                                "name": result.get("name"),
                                "description": result.get("description"),
                                "category": result.get("category"),
                                "price": price,
                                "stock_quantity": result.get("stock_quantity", 0),
                                "stock_status": result.get("stock_status"),
                                "sku": result.get("sku"),
                                "brand": result.get("brand"),
                            })
                
                # Sort by price
                products.sort(key=lambda x: x["price"])
                
                return {
                    "status": "success",
                    "total_count": len(products),
                    "products": products,
                }
                
            except Exception as e:
                logger.error(f"Error searching by price range: {e}")
                return {
                    "status": "error",
                    "error_message": f"Price range search failed: {str(e)}",
                    "products": [],
                }

        def get_low_stock_items(threshold: int) -> Dict[str, Any]:
            """Get items that are low in stock.
            
            Args:
                threshold: Stock quantity threshold (items below this are considered low stock)
            """
            try:
                # Search for products with stock information
                query = "stock_quantity stock inventory"
                results = search_store.search(query=query, top_k=100)
                
                low_stock_items = []
                for result in results:
                    # Get stock quantity from appropriate location
                    if "metadata" in result:
                        stock_quantity = result["metadata"].get("stock_quantity", 0)
                        if 0 < stock_quantity < threshold:
                            metadata = result["metadata"]
                            low_stock_items.append({
                                "id": result.get("id"),
                                "name": metadata.get("name"),
                                "current_stock": stock_quantity,
                                "category": metadata.get("category"),
                                "sku": metadata.get("sku"),
                            })
                    else:
                        stock_quantity = result.get("stock_quantity", 0)
                        if 0 < stock_quantity < threshold:
                            low_stock_items.append({
                                "id": result.get("id"),
                                "name": result.get("name"),
                                "current_stock": stock_quantity,
                                "category": result.get("category"),
                                "sku": result.get("sku"),
                            })
                
                # Sort by stock quantity (lowest first)
                low_stock_items.sort(key=lambda x: x["current_stock"])
                
                return {
                    "status": "success",
                    "threshold": threshold,
                    "count": len(low_stock_items),
                    "products": low_stock_items,
                }
                
            except Exception as e:
                logger.error(f"Error getting low stock items: {e}")
                return {
                    "status": "error",
                    "error_message": f"Low stock search failed: {str(e)}",
                    "products": [],
                }

        def get_all_products() -> Dict[str, Any]:
            """Get all products in inventory."""
            try:
                # Use a broad query to get all products
                query = "*"  # Or use a generic term like "product"
                results = search_store.search(query=query, top_k=100)
                
                products = []
                for result in results:
                    if "metadata" in result:
                        metadata = result["metadata"]
                        products.append({
                            "id": result.get("id"),
                            "name": metadata.get("name"),
                            "description": metadata.get("description"),
                            "category": metadata.get("category"),
                            "price": metadata.get("price"),
                            "stock_quantity": metadata.get("stock_quantity", 0),
                            "stock_status": metadata.get("stock_status"),
                            "sku": metadata.get("sku"),
                            "brand": metadata.get("brand"),
                        })
                    else:
                        products.append({
                            "id": result.get("id"),
                            "name": result.get("name"),
                            "description": result.get("description"),
                            "category": result.get("category"),
                            "price": result.get("price"),
                            "stock_quantity": result.get("stock_quantity", 0),
                            "stock_status": result.get("stock_status"),
                            "sku": result.get("sku"),
                            "brand": result.get("brand"),
                        })
                
                return {
                    "status": "success",
                    "total_count": len(products),
                    "products": products,
                }
                
            except Exception as e:
                logger.error(f"Error getting all products: {e}")
                return {
                    "status": "error",
                    "error_message": f"Failed to retrieve products: {str(e)}",
                    "products": [],
                }
        
        return Agent(
            name="inventory_agent",
            model="gemini-2.0-flash",
            description="Retail inventory management agent that handles product availability, stock levels, and product searches using Vertex AI Search.",
            instruction="""You are an inventory management assistant for a retail organization. Your role is to:

1. Check product availability and stock levels
2. Search for products based on various criteria (name, category, price range)
3. Monitor low stock items
4. Provide accurate inventory information

You have access to a Vertex AI Search datastore that contains the product inventory.

Always provide clear, accurate information about product availability and stock status. 
When products are out of stock, mention alternative products if available.
Format your responses in a helpful and organized manner.

IMPORTANT SEARCH GUIDELINES:
- When a user asks about a product, use search_products_by_query first with the product name
- Our categories are: "electronics", "clothing", "home", "sports"
- If you need to search by category, use search_products_by_category
- If you need to search by price range, use search_products_by_price_range
- Use check_product_availability only when you have a specific product ID or SKU

Use the available tools:
- search_products_by_query: Search for products by name or description (uses Vertex AI Search)
- search_products_by_category: Get all products in a specific category
- search_products_by_price_range: Find products within a price range
- check_product_availability: Check if a specific product ID is in stock
- get_low_stock_items: Get items that are running low in stock
- get_all_products: Get a list of all products

When responding with product information, format it clearly with details like:
- Product name and ID
- Price
- Stock status and quantity
- Brand and category

If a search returns no results, try different search approaches before saying the item is not available.""",
            tools=[
                check_product_availability,
                search_products_by_query,
                search_products_by_category,
                search_products_by_price_range,
                get_low_stock_items,
                get_all_products,
            ],
        )
    
    async def stream(self, query: str, session_id: str) -> AsyncIterable[Dict[str, Any]]:
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
            content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=query)]
            )
            
            # Yield initial status
            yield {
                "type": "status",
                "message": "Searching inventory database..."
            }
            
            # Run agent
            tool_called = False
            final_response = None
            
            async for event in self._runner.run_async(
                user_id=self._user_id,
                session_id=session.id,
                new_message=content
            ):
                # Check for tool calls
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.function_call:
                            tool_called = True
                            yield {
                                "type": "tool_call",
                                "tool_name": part.function_call.name,
                                "message": f"Searching Vertex AI: {part.function_call.name.replace('_', ' ')}..."
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
                    yield {
                        "type": "result",
                        "content": response_data
                    }
                else:
                    yield {
                        "type": "result",
                        "content": response_text or "No response generated"
                    }
            else:
                yield {
                    "type": "error",
                    "message": "No response from inventory agent"
                }
        
        except Exception as e:
            logger.error(f"Error in inventory agent stream: {e}", exc_info=True)
            yield {
                "type": "error",
                "message": f"Error processing inventory request: {str(e)}"
            }