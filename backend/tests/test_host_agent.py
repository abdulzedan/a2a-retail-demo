"""
Unit tests for the Host Agent.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import json
import httpx

from backend.agents.host_agent.agent import HostAgent


class TestHostAgent:
    """Test suite for HostAgent."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx client."""
        client = Mock()

        # Mock inventory agent response
        inventory_response = Mock()
        inventory_response.status_code = 200
        inventory_response.json.return_value = {
            "messages": [{"role": "assistant", "content": "I found 3 smart TVs in stock."}]
        }

        # Mock customer service response
        cs_response = Mock()
        cs_response.status_code = 200
        cs_response.json.return_value = {
            "messages": [{"role": "assistant", "content": "Our store hours are 9 AM to 9 PM daily."}]
        }

        # Route responses based on URL
        def mock_post(url, *args, **kwargs):
            if "inventory" in url:
                return inventory_response
            elif "customer" in url:
                return cs_response
            else:
                raise ValueError(f"Unexpected URL: {url}")

        client.post = AsyncMock(side_effect=mock_post)
        return client

    @pytest.fixture
    def host_agent(self, mock_httpx_client):
        """Create a HostAgent instance with mocked dependencies."""
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            agent = HostAgent()
            agent._client = mock_httpx_client
            return agent

    def test_agent_initialization(self, host_agent):
        """Test that the host agent initializes correctly."""
        assert host_agent.INVENTORY_AGENT_URL is not None
        assert host_agent.CUSTOMER_SERVICE_AGENT_URL is not None
        assert "inventory" in host_agent.INVENTORY_AGENT_URL
        assert "customer" in host_agent.CUSTOMER_SERVICE_AGENT_URL

    def test_analyze_query_inventory(self, host_agent):
        """Test query analysis for inventory-related queries."""
        inventory_queries = [
            "What smart TVs do you have?",
            "Show me products in stock",
            "Find wireless headphones",
            "What's the price of the laptop?",
            "Do you have any coffee makers available?",
        ]

        for query in inventory_queries:
            result = host_agent._analyze_query(query)
            assert result == "inventory", f"Query '{query}' should route to inventory"

    def test_analyze_query_customer_service(self, host_agent):
        """Test query analysis for customer service queries."""
        cs_queries = [
            "What are your store hours?",
            "How do I return an item?",
            "Where is my order ORD-12345?",
            "Can I get a refund?",
            "What's your shipping policy?",
        ]

        for query in cs_queries:
            result = host_agent._analyze_query(query)
            assert result == "customer_service", f"Query '{query}' should route to customer service"

    def test_analyze_query_both_agents(self, host_agent):
        """Test query analysis for queries needing both agents."""
        both_queries = [
            "What TVs do you have and what are your store hours?",
            "I want to buy a laptop and return my old one",
            "Show me products and tell me about shipping",
        ]

        for query in both_queries:
            result = host_agent._analyze_query(query)
            assert result == "both", f"Query '{query}' should route to both agents"

    @pytest.mark.asyncio
    async def test_call_inventory_agent(self, host_agent):
        """Test calling the inventory agent."""
        response = await host_agent._call_inventory_agent("Find smart TVs", "test-context-123")

        assert response == "I found 3 smart TVs in stock."

        # Verify the call was made correctly
        host_agent._client.post.assert_called()
        call_args = host_agent._client.post.call_args
        assert "inventory" in call_args[0][0]  # URL contains inventory

    @pytest.mark.asyncio
    async def test_call_customer_service_agent(self, host_agent):
        """Test calling the customer service agent."""
        response = await host_agent._call_customer_service_agent("What are your hours?", "test-context-456")

        assert response == "Our store hours are 9 AM to 9 PM daily."

        # Verify the call was made correctly
        host_agent._client.post.assert_called()
        call_args = host_agent._client.post.call_args
        assert "customer" in call_args[0][0]  # URL contains customer

    @pytest.mark.asyncio
    async def test_call_agent_with_a2a(self, host_agent):
        """Test the generic A2A call method."""
        response = await host_agent._call_agent_with_a2a(host_agent.INVENTORY_AGENT_URL, "Test query", "test-context")

        assert isinstance(response, str)
        assert len(response) > 0

        # Verify request format
        call_args = host_agent._client.post.call_args
        request_data = call_args[1]["json"]
        assert "messages" in request_data
        assert request_data["messages"][0]["role"] == "user"
        assert request_data["messages"][0]["content"] == "Test query"

    @pytest.mark.asyncio
    async def test_call_agents_parallel(self, host_agent):
        """Test parallel execution of both agents."""
        result = await host_agent.call_agents_parallel(
            "Find laptops", "What's the return policy?", "test-parallel-context"
        )

        assert isinstance(result, dict)
        assert "inventory" in result
        assert "customer_service" in result
        assert "I found 3 smart TVs" in result["inventory"]
        assert "9 AM to 9 PM" in result["customer_service"]

        # Verify both agents were called
        assert host_agent._client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_run_inventory_query(self, host_agent):
        """Test run method with inventory query."""
        response = await host_agent.run("Show me all smart TVs", "test-session-inv")

        assert isinstance(response, dict)
        assert "response" in response
        assert "smart TVs" in response["response"]

    @pytest.mark.asyncio
    async def test_run_customer_service_query(self, host_agent):
        """Test run method with customer service query."""
        response = await host_agent.run("What time do you close?", "test-session-cs")

        assert isinstance(response, dict)
        assert "response" in response
        assert "9 PM" in response["response"]

    @pytest.mark.asyncio
    async def test_run_both_agents_query(self, host_agent):
        """Test run method with query requiring both agents."""
        response = await host_agent.run("What products do you have and what are your hours?", "test-session-both")

        assert isinstance(response, dict)
        assert "response" in response
        # Should contain responses from both agents
        assert "smart TVs" in response["response"]
        assert "9 AM to 9 PM" in response["response"]

    @pytest.mark.asyncio
    async def test_error_handling_agent_unavailable(self, host_agent):
        """Test error handling when an agent is unavailable."""
        # Make the client raise an exception
        host_agent._client.post.side_effect = httpx.HTTPError("Connection refused")

        with pytest.raises(httpx.HTTPError):
            await host_agent._call_inventory_agent("test", "context")

    @pytest.mark.asyncio
    async def test_error_handling_invalid_response(self, host_agent):
        """Test error handling with invalid agent response."""
        # Mock invalid response
        invalid_response = Mock()
        invalid_response.status_code = 200
        invalid_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)

        host_agent._client.post.return_value = invalid_response

        response = await host_agent._call_inventory_agent("test", "context")
        assert response == ""  # Should return empty string on error

    @pytest.mark.asyncio
    async def test_get_agent_status(self, host_agent):
        """Test checking agent status."""
        # Mock successful responses for status check
        host_agent._client.post.return_value.status_code = 200

        status = await host_agent.get_agent_status()

        assert isinstance(status, str)
        assert "Inventory Agent: Online" in status
        assert "Customer Service Agent: Online" in status

    @pytest.mark.asyncio
    async def test_get_agent_status_partial_failure(self, host_agent):
        """Test agent status when one agent is down."""

        # Make inventory calls succeed but customer service fail
        def mock_post_partial(url, *args, **kwargs):
            if "inventory" in url:
                response = Mock()
                response.status_code = 200
                return response
            else:
                raise httpx.HTTPError("Service unavailable")

        host_agent._client.post = AsyncMock(side_effect=mock_post_partial)

        status = await host_agent.get_agent_status()

        assert "Inventory Agent: Online" in status
        assert "Customer Service Agent: Offline" in status

    def test_query_analysis_edge_cases(self, host_agent):
        """Test query analysis with edge cases."""
        # Empty query
        assert host_agent._analyze_query("") == "customer_service"

        # Very long query
        long_query = "product " * 100 + "hours " * 100
        assert host_agent._analyze_query(long_query) == "both"

        # Special characters
        assert host_agent._analyze_query("What's the price of TV?") == "inventory"

        # Mixed case
        assert host_agent._analyze_query("FIND PRODUCTS IN STOCK") == "inventory"

    @pytest.mark.asyncio
    async def test_context_preservation(self, host_agent):
        """Test that context is preserved across agent calls."""
        context_id = "unique-context-123"

        await host_agent.run("Find products", context_id)

        # Verify context was passed in the request
        call_args = host_agent._client.post.call_args
        request_data = call_args[1]["json"]
        assert request_data["context"]["context_id"] == context_id
