"""
Unit tests for the Inventory Agent A2A.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from backend.agents.inventory_agent_a2a.agent import InventoryAgent


class TestInventoryAgent:
    """Test suite for InventoryAgent."""

    @pytest.fixture
    def inventory_agent(self, mock_vector_store, mock_agent_runner):
        """Create an InventoryAgent instance with mocked dependencies."""
        with patch("backend.agents.inventory_agent_a2a.agent.VertexSearchStore", return_value=mock_vector_store):
            with patch("backend.agents.inventory_agent_a2a.agent.Runner", return_value=mock_agent_runner):
                agent = InventoryAgent()
                agent._search_store = mock_vector_store
                agent._runner = mock_agent_runner
                return agent

    def test_agent_initialization(self, inventory_agent):
        """Test that the agent initializes correctly."""
        assert inventory_agent._agent is not None
        assert inventory_agent._agent.name == "inventory_agent"
        assert inventory_agent._agent.model == "gemini-2.0-flash"
        assert inventory_agent._search_store is not None
        assert inventory_agent._runner is not None

    def test_build_agent_tools(self, inventory_agent):
        """Test that the agent builds with the correct tools."""
        agent = inventory_agent._build_agent()

        # Check that agent has tools
        assert hasattr(agent, "tools")
        assert len(agent.tools) == 6  # Updated to match actual number of tools

        # Check tool names
        tool_names = [tool.__name__ for tool in agent.tools]
        assert "check_product_availability" in tool_names
        assert "search_products_by_query" in tool_names
        assert "search_products_by_category" in tool_names
        assert "search_products_by_price_range" in tool_names
        assert "get_low_stock_items" in tool_names
        assert "get_all_products" in tool_names

    def test_check_product_availability_success(self, inventory_agent):
        """Test checking product availability for existing product."""
        # Get the tool directly
        agent = inventory_agent._build_agent()
        check_tool = next(t for t in agent.tools if t.__name__ == "check_product_availability")

        # Execute the tool
        result = check_tool("PROD-001")

        # Verify the result matches actual implementation
        assert result["status"] == "success"
        assert result["product_id"] == "PROD-001"
        assert result["name"] == "Smart TV 55-inch 4K"
        assert result["stock_quantity"] == 15
        assert result["available"] is True
        assert "price" in result
        assert "stock_status" in result

    def test_check_product_availability_not_found(self, inventory_agent):
        """Test checking availability for non-existent product."""
        agent = inventory_agent._build_agent()
        check_tool = next(t for t in agent.tools if t.__name__ == "check_product_availability")

        result = check_tool("PROD-999")

        assert result["status"] == "error"
        assert "error_message" in result
        assert "not found" in result["error_message"].lower()

    def test_search_products_by_query(self, inventory_agent):
        """Test searching products by query."""
        agent = inventory_agent._build_agent()
        search_tool = next(t for t in agent.tools if t.__name__ == "search_products_by_query")

        result = search_tool("smart tv")

        assert result["status"] == "success"
        assert "products" in result
        assert "total_count" in result
        assert len(result["products"]) == 2
        assert result["total_count"] == 2

    def test_search_products_by_category(self, inventory_agent):
        """Test searching products by category."""
        # Mock the search to return electronics items
        mock_vector_store = inventory_agent._search_store
        mock_vector_store.search.return_value = [
            {
                "id": "PROD-001",
                "metadata": {
                    "name": "Smart TV",
                    "category": "electronics",
                    "price": 699.99,
                    "stock_quantity": 15,
                    "stock_status": "in_stock",
                    "sku": "TV-001",
                    "brand": "TechVision",
                    "description": "4K Smart TV"
                }
            }
        ]
        
        agent = inventory_agent._build_agent()
        category_tool = next(t for t in agent.tools if t.__name__ == "search_products_by_category")

        result = category_tool("electronics")

        assert result["status"] == "success"
        assert len(result["products"]) > 0
        assert result["total_count"] == len(result["products"])

    def test_search_products_by_price_range(self, inventory_agent):
        """Test searching products by price range."""
        agent = inventory_agent._build_agent()
        price_tool = next(t for t in agent.tools if t.__name__ == "search_products_by_price_range")

        result = price_tool(100.0, 1000.0)

        assert result["status"] == "success"
        assert "products" in result
        assert "total_count" in result

    def test_get_low_stock_items(self, inventory_agent):
        """Test getting low stock items."""
        agent = inventory_agent._build_agent()
        low_stock_tool = next(t for t in agent.tools if t.__name__ == "get_low_stock_items")

        result = low_stock_tool(10)

        assert result["status"] == "success"
        assert "products" in result
        assert "threshold" in result
        assert result["threshold"] == 10

    def test_search_products_empty_results(self, inventory_agent, mock_vector_store):
        """Test searching products with no results."""
        # Override the mock to return empty results
        mock_vector_store.search.return_value = []

        agent = inventory_agent._build_agent()
        search_tool = next(t for t in agent.tools if t.__name__ == "search_products_by_query")

        result = search_tool("nonexistent product")

        assert result["status"] == "success"
        assert result["products"] == []
        assert result["total_count"] == 0

    def test_search_error_handling(self, inventory_agent, mock_vector_store):
        """Test error handling in search operations."""
        # Make the search raise an exception
        mock_vector_store.search.side_effect = Exception("Database connection error")

        agent = inventory_agent._build_agent()
        search_tool = next(t for t in agent.tools if t.__name__ == "search_products_by_query")

        result = search_tool("test query")

        assert result["status"] == "error"
        assert "error_message" in result
        assert "Database connection error" in result["error_message"]

    @pytest.mark.asyncio
    async def test_stream_method(self, inventory_agent):
        """Test the stream method yields expected events."""
        # Mock the runner's session service
        mock_session = Mock(id="test-session")
        inventory_agent._runner.session_service.get_session = AsyncMock(return_value=None)
        inventory_agent._runner.session_service.create_session = AsyncMock(return_value=mock_session)
        
        # Mock the runner's run_async to return proper events
        async def mock_run_async(*args, **kwargs):
            mock_event = Mock()
            mock_event.content = Mock(parts=[])
            mock_event.is_final_response = Mock(return_value=True)
            yield mock_event
        
        inventory_agent._runner.run_async = mock_run_async
        
        events = []
        async for event in inventory_agent.stream("Find wireless headphones", "test-session-456"):
            events.append(event)

        assert len(events) >= 1
        # Should have at least a status message
        assert any(event.get("type") == "status" for event in events)

    @pytest.mark.asyncio
    async def test_stream_with_tool_calls(self, inventory_agent):
        """Test streaming with tool call events."""
        # Mock session
        mock_session = Mock(id="test-session")
        inventory_agent._runner.session_service.get_session = AsyncMock(return_value=mock_session)
        
        # Mock run_async to include tool calls
        async def mock_run_async(*args, **kwargs):
            # First event with tool call
            mock_event1 = Mock()
            mock_event1.content = Mock()
            mock_event1.content.parts = [Mock(function_call=Mock(name="search_products_by_query"))]
            mock_event1.is_final_response = Mock(return_value=False)
            yield mock_event1
            
            # Final event with response
            mock_event2 = Mock()
            mock_event2.content = Mock()
            mock_event2.content.parts = [Mock(text="Found 3 products", function_call=None)]
            mock_event2.is_final_response = Mock(return_value=True)
            yield mock_event2
        
        inventory_agent._runner.run_async = mock_run_async
        
        events = []
        async for event in inventory_agent.stream("Search for laptops", "test-session"):
            events.append(event)
        
        # Should have tool call event
        tool_events = [e for e in events if e.get("type") == "tool_call"]
        assert len(tool_events) > 0
        
        # Should have final result
        result_events = [e for e in events if e.get("type") == "result"]
        assert len(result_events) == 1

    def test_supported_content_types(self, inventory_agent):
        """Test that supported content types are defined."""
        assert "text" in inventory_agent.SUPPORTED_CONTENT_TYPES
        assert "text/plain" in inventory_agent.SUPPORTED_CONTENT_TYPES