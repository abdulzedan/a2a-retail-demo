"""
Unit tests for the Host Agent.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import httpx

from backend.agents.host_agent.agent import HostAgent


class TestHostAgent:
    """Test suite for HostAgent."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx client."""
        client = Mock(spec=httpx.AsyncClient)
        return client

    @pytest.fixture
    def mock_a2a_client(self):
        """Create a mock A2A client."""
        client = Mock()
        
        # Just return a simple mock response
        client.send_message = AsyncMock(return_value=Mock(root=Mock(result="Mock response")))
        
        return client

    @pytest.fixture
    def mock_agent_card(self):
        """Create a mock agent card."""
        card = Mock()
        card.id = "test-agent"
        card.name = "Test Agent"
        card.description = "A test agent"
        card.supported_input_content_types = ["text/plain"]
        card.supported_output_content_types = ["text/plain"]
        return card

    @pytest.fixture
    def host_agent(self, mock_httpx_client):
        """Create a HostAgent instance with mocked dependencies."""
        with patch("backend.agents.host_agent.agent.httpx.AsyncClient", return_value=mock_httpx_client):
            agent = HostAgent()
            agent._client = mock_httpx_client
            return agent

    def test_agent_initialization(self, host_agent):
        """Test that the host agent initializes correctly."""
        assert host_agent.INVENTORY_AGENT_URL is not None
        assert host_agent.CUSTOMER_SERVICE_AGENT_URL is not None
        assert host_agent.INVENTORY_AGENT_URL == "http://localhost:8001"
        assert host_agent.CUSTOMER_SERVICE_AGENT_URL == "http://localhost:8002"
        assert hasattr(host_agent, "_agent")
        assert hasattr(host_agent, "_runner")

    @pytest.mark.asyncio
    async def test_get_agent_card(self, host_agent, mock_agent_card):
        """Test getting agent card."""
        # Mock the httpx response
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "test-agent",
            "name": "Test Agent",
            "description": "A test agent",
            "supported_input_content_types": ["text/plain"],
            "supported_output_content_types": ["text/plain"],
            "capabilities": {},
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
            "skills": [],
            "url": "http://localhost:8001",
            "version": "1.0.0"
        }
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            card = await host_agent._get_agent_card("http://localhost:8001")
            
            assert card is not None
            assert card.name == "Test Agent"

    @pytest.mark.asyncio
    async def test_call_inventory_agent(self, host_agent, mock_a2a_client):
        """Test calling the inventory agent."""
        with patch.object(host_agent, "_call_agent_with_a2a", return_value="Product found: Widget"):
            response = await host_agent.call_inventory_agent("Do you have widgets?", "test-context")
            
            assert response == "Product found: Widget"

    @pytest.mark.asyncio
    async def test_call_customer_service_agent(self, host_agent, mock_a2a_client):
        """Test calling the customer service agent."""
        with patch.object(host_agent, "_call_agent_with_a2a", return_value="Our store hours are 9-5"):
            response = await host_agent.call_customer_service_agent("What are your hours?", "test-context")
            
            assert response == "Our store hours are 9-5"

    @pytest.mark.asyncio
    async def test_call_agents_parallel(self, host_agent):
        """Test calling agents in parallel."""
        # Mock the individual agent calls
        with patch.object(host_agent, "call_inventory_agent", return_value="Inventory response"):
            with patch.object(host_agent, "call_customer_service_agent", return_value="Customer service response"):
                responses = await host_agent.call_agents_parallel(
                    "Test query",
                    "test-context",
                    ["inventory", "customer_service"]
                )
                
                assert "inventory" in responses
                assert "customer_service" in responses
                assert responses["inventory"] == "Inventory response"
                assert responses["customer_service"] == "Customer service response"

    @pytest.mark.asyncio
    async def test_get_agent_status(self, host_agent):
        """Test getting agent status."""
        with patch.object(host_agent, "_get_agent_card") as mock_get_card:
            # Mock successful card retrieval
            mock_get_card.return_value = Mock(name="Test Agent")
            
            status = await host_agent.get_agent_status()
            
            assert isinstance(status, str)
            assert "Status" in status

    @pytest.mark.asyncio
    async def test_stream_response(self, host_agent):
        """Test the streaming response functionality."""
        query = "Do you have any TVs in stock?"
        session_id = "test-session-123"
        
        # Mock the runner's async stream
        mock_event = Mock()
        mock_event.content = Mock(parts=[Mock(text="We have TVs in stock")])
        mock_event.is_final_response = Mock(return_value=True)
        
        host_agent._runner.run_async = AsyncMock()
        host_agent._runner.run_async.return_value.__aiter__.return_value = [mock_event]
        
        # Mock session service
        host_agent._runner.session_service.get_session = AsyncMock(return_value=None)
        host_agent._runner.session_service.create_session = AsyncMock(return_value=Mock(id=session_id))
        
        responses = []
        async for response in host_agent.stream(query, session_id):
            responses.append(response)
        
        # Should have at least one response
        assert len(responses) > 0
        
        # Check final response
        final_response = responses[-1]
        assert "type" in final_response
        assert final_response["type"] == "result"

    def test_supported_content_types(self, host_agent):
        """Test that supported content types are defined."""
        assert "text" in host_agent.SUPPORTED_CONTENT_TYPES
        assert "text/plain" in host_agent.SUPPORTED_CONTENT_TYPES