"""
Unit tests for the Customer Service Agent.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from backend.agents.customer_service_a2a.agent import CustomerServiceAgent


class TestCustomerServiceAgent:
    """Test suite for CustomerServiceAgent."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock Gemini model."""
        model = Mock()

        # Create mock response
        mock_response = Mock()
        mock_response.text = "I can help you with that. Our return policy allows returns within 30 days."

        model.generate_content_async = AsyncMock(return_value=mock_response)
        return model

    @pytest.fixture
    def customer_service_agent(self, mock_model):
        """Create a CustomerServiceAgent instance with mocked dependencies."""
        with patch("google.generativeai.GenerativeModel", return_value=mock_model):
            agent = CustomerServiceAgent()
            agent._model = mock_model
            return agent

    def test_agent_initialization(self, customer_service_agent):
        """Test that the agent initializes correctly."""
        assert customer_service_agent._name == "Customer Service Assistant"
        assert customer_service_agent._description is not None
        assert customer_service_agent._model is not None
        assert hasattr(customer_service_agent, "_graph")

    def test_store_info_node(self, customer_service_agent):
        """Test the store information node."""
        state = {"messages": []}

        result = customer_service_agent._store_info(state)

        assert "messages" in result
        assert len(result["messages"]) > 0

        message = result["messages"][0]
        assert message.role == "assistant"
        assert "Monday-Saturday: 9 AM - 9 PM" in message.content
        assert "Sunday: 10 AM - 6 PM" in message.content

    def test_shipping_info_node(self, customer_service_agent):
        """Test the shipping information node."""
        state = {"messages": []}

        result = customer_service_agent._shipping_info(state)

        assert "messages" in result
        assert len(result["messages"]) > 0

        message = result["messages"][0]
        assert message.role == "assistant"
        assert "Standard Shipping" in message.content
        assert "$4.99" in message.content

    def test_return_policy_node(self, customer_service_agent):
        """Test the return policy node."""
        state = {"messages": []}

        result = customer_service_agent._return_policy(state)

        assert "messages" in result
        message = result["messages"][0]
        assert "30-day return policy" in message.content
        assert "Original packaging" in message.content

    @pytest.mark.asyncio
    async def test_general_help_node(self, customer_service_agent):
        """Test the general help node."""
        from langgraph.graph.message import HumanMessage

        state = {"messages": [HumanMessage(content="How do I track my order?")]}

        result = await customer_service_agent._general_help(state)

        assert "messages" in result
        assert len(result["messages"]) > 0

        # Verify model was called
        customer_service_agent._model.generate_content_async.assert_called_once()

    def test_should_go_to_store_info(self, customer_service_agent):
        """Test routing to store info."""
        from langgraph.graph.message import HumanMessage

        state = {"messages": [HumanMessage(content="What are your store hours?")]}

        result = customer_service_agent._should_go_to_store_info(state)
        assert result is True

        # Test negative case
        state["messages"] = [HumanMessage(content="How do I return an item?")]
        result = customer_service_agent._should_go_to_store_info(state)
        assert result is False

    def test_should_go_to_shipping_info(self, customer_service_agent):
        """Test routing to shipping info."""
        from langgraph.graph.message import HumanMessage

        shipping_queries = [
            "What are your shipping rates?",
            "How long does delivery take?",
            "Do you offer express shipping?",
        ]

        for query in shipping_queries:
            state = {"messages": [HumanMessage(content=query)]}
            result = customer_service_agent._should_go_to_shipping_info(state)
            assert result is True, f"Query '{query}' should route to shipping info"

    def test_should_go_to_return_policy(self, customer_service_agent):
        """Test routing to return policy."""
        from langgraph.graph.message import HumanMessage

        return_queries = ["How do I return an item?", "What's your refund policy?", "Can I exchange a product?"]

        for query in return_queries:
            state = {"messages": [HumanMessage(content=query)]}
            result = customer_service_agent._should_go_to_return_policy(state)
            assert result is True, f"Query '{query}' should route to return policy"

    def test_build_graph(self, customer_service_agent):
        """Test that the graph is built correctly."""
        # The graph should be built during initialization
        assert customer_service_agent._graph is not None

        # Test graph structure (this is implementation specific)
        # Could verify nodes and edges if the graph exposes them

    @pytest.mark.asyncio
    async def test_run_method(self, customer_service_agent):
        """Test the run method."""
        response = await customer_service_agent.run("What are your store hours?", "test-session-123")

        assert isinstance(response, dict)
        assert "response" in response
        assert "Monday-Saturday" in response["response"]

    @pytest.mark.asyncio
    async def test_handle_a2a_request(self, customer_service_agent):
        """Test handling A2A protocol requests."""
        request_data = {
            "messages": [{"role": "user", "content": "What's your return policy?"}],
            "context": {"session_id": "test-a2a-session"},
        }

        response = await customer_service_agent.handle_a2a_request(request_data)

        assert isinstance(response, dict)
        assert "messages" in response
        assert len(response["messages"]) > 0
        assert response["messages"][0]["role"] == "assistant"
        assert "30-day return policy" in response["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_order_lookup_simulation(self, customer_service_agent):
        """Test order lookup functionality."""
        from langgraph.graph.message import HumanMessage

        state = {"messages": [HumanMessage(content="Where is my order ORD-12345?")]}

        # The general help should handle order lookups
        result = await customer_service_agent._general_help(state)

        assert "messages" in result
        # Should call the model for order-related queries
        customer_service_agent._model.generate_content_async.assert_called()

    def test_edge_cases(self, customer_service_agent):
        """Test edge cases in routing."""
        from langgraph.graph.message import HumanMessage

        # Empty message
        state = {"messages": [HumanMessage(content="")]}
        assert customer_service_agent._should_go_to_store_info(state) is False
        assert customer_service_agent._should_go_to_shipping_info(state) is False
        assert customer_service_agent._should_go_to_return_policy(state) is False

        # Multiple keywords
        state = {"messages": [HumanMessage(content="What are your hours and shipping rates?")]}
        # Should match the first applicable condition
        result_store = customer_service_agent._should_go_to_store_info(state)
        result_ship = customer_service_agent._should_go_to_shipping_info(state)
        assert result_store or result_ship  # At least one should match

    @pytest.mark.asyncio
    async def test_conversation_history(self, customer_service_agent):
        """Test that conversation history is maintained."""
        from langgraph.graph.message import HumanMessage, AIMessage

        state = {
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(content="Hi! How can I help you?"),
                HumanMessage(content="What are your hours?"),
            ]
        }

        result = customer_service_agent._store_info(state)

        # Should append to messages, not replace
        assert len(result["messages"]) == 1  # Only the new message
        assert result["messages"][0].role == "assistant"

    @pytest.mark.asyncio
    async def test_error_handling_model_failure(self, customer_service_agent):
        """Test error handling when model fails."""
        # Make the model raise an exception
        customer_service_agent._model.generate_content_async.side_effect = Exception("API Error")

        from langgraph.graph.message import HumanMessage

        state = {"messages": [HumanMessage(content="Help me with something")]}

        # Should handle the error gracefully
        with pytest.raises(Exception):
            await customer_service_agent._general_help(state)

    def test_special_hours_info(self, customer_service_agent):
        """Test that special hours information is included."""
        state = {"messages": []}

        result = customer_service_agent._store_info(state)
        message_content = result["messages"][0].content

        # Should include holiday hours
        assert "Holiday hours may vary" in message_content
        assert "123 Main Street" in message_content
        assert "(555) 123-4567" in message_content

    def test_shipping_zones(self, customer_service_agent):
        """Test shipping zone information."""
        state = {"messages": []}

        result = customer_service_agent._shipping_info(state)
        message_content = result["messages"][0].content

        # Should include different shipping options
        assert "Express Shipping" in message_content
        assert "1-2 business days" in message_content
        assert "Continental US" in message_content

    @pytest.mark.asyncio
    async def test_complex_query_routing(self, customer_service_agent):
        """Test routing of complex queries."""
        response = await customer_service_agent.run(
            "I bought a TV last week but it's damaged. What are your return policies and how long will it take to get a replacement?",
            "complex-query-session",
        )

        assert isinstance(response, dict)
        assert "response" in response
        # Should route to return policy based on keywords
        assert "return" in response["response"].lower() or "policy" in response["response"].lower()
