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
        with patch("langchain_google_genai.ChatGoogleGenerativeAI", return_value=mock_model):
            agent = CustomerServiceAgent()
            agent.model = mock_model
            return agent

    def test_agent_initialization(self, customer_service_agent):
        """Test that the agent initializes correctly."""
        assert customer_service_agent.model is not None
        assert customer_service_agent.tools is not None
        assert len(customer_service_agent.tools) == 3
        assert hasattr(customer_service_agent, "graph")

    @pytest.mark.asyncio
    async def test_stream_response(self, customer_service_agent):
        """Test the streaming response functionality."""
        query = "What are your store hours?"
        session_id = "test-session-123"

        # Mock the graph's astream method
        mock_astream = AsyncMock()
        mock_astream.return_value.__aiter__.return_value = [
            {"messages": [{"role": "assistant", "content": "Our store hours are..."}]}
        ]
        customer_service_agent.graph.astream = mock_astream

        # Mock get_agent_response
        customer_service_agent.get_agent_response = Mock(
            return_value={
                "is_task_complete": True,
                "require_user_input": False,
                "content": "Our store hours are Monday-Saturday 9 AM - 9 PM, Sunday 10 AM - 6 PM.",
            }
        )

        responses = []
        async for response in customer_service_agent.stream(query, session_id):
            responses.append(response)

        # Should have at least one response
        assert len(responses) > 0

        # Check response structure
        last_response = responses[-1]
        assert "content" in last_response or "is_task_complete" in last_response

    def test_invoke_method(self, customer_service_agent):
        """Test the invoke method."""
        query = "What are your store hours?"
        session_id = "test-session-123"

        # Mock the graph's invoke method
        customer_service_agent.graph.invoke = Mock()

        # Mock get_agent_response
        customer_service_agent.get_agent_response = Mock(
            return_value={
                "is_task_complete": True,
                "require_user_input": False,
                "content": "Our store hours are Monday-Saturday 9 AM - 9 PM.",
            }
        )

        result = customer_service_agent.invoke(query, session_id)

        assert isinstance(result, dict)
        assert "content" in result
        customer_service_agent.graph.invoke.assert_called_once()

    def test_tools_exist(self, customer_service_agent):
        """Test that the required tools are present."""
        tool_names = [tool.name for tool in customer_service_agent.tools]

        assert "check_order_status" in tool_names
        assert "get_store_hours" in tool_names
        assert "process_return_request" in tool_names
