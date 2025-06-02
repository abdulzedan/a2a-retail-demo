"""
Integration tests for A2A agent communication.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from backend.agents.host_agent.agent import HostAgent
from backend.agents.inventory_agent_a2a.agent import InventoryAgent
from backend.agents.customer_service_a2a.agent import CustomerServiceAgent


class TestAgentIntegration:
    """Integration tests for multi-agent communication."""

    @pytest.mark.asyncio
    async def test_host_agent_routing_to_inventory(self):
        """Test host agent routing to inventory agent."""
        # Mock the A2A client and responses
        mock_response = "Found 3 smart TVs in stock: 55-inch 4K, 65-inch OLED, and 75-inch QLED"
        
        host_agent = HostAgent()
        
        # Mock the _call_agent_with_a2a method
        with patch.object(host_agent, "_call_agent_with_a2a", return_value=mock_response) as mock_call:
            response = await host_agent.call_inventory_agent("Find smart TVs", "test-context")
            
            assert response == mock_response
            mock_call.assert_called_once_with(
                host_agent.INVENTORY_AGENT_URL,
                "Find smart TVs",
                "test-context"
            )

    @pytest.mark.asyncio
    async def test_host_agent_routing_to_customer_service(self):
        """Test host agent routing to customer service agent."""
        mock_response = "Our store hours are Monday-Saturday 9 AM - 9 PM, Sunday 10 AM - 6 PM"
        
        host_agent = HostAgent()
        
        with patch.object(host_agent, "_call_agent_with_a2a", return_value=mock_response) as mock_call:
            response = await host_agent.call_customer_service_agent("What are your hours?", "test-context")
            
            assert response == mock_response
            mock_call.assert_called_once_with(
                host_agent.CUSTOMER_SERVICE_AGENT_URL,
                "What are your hours?",
                "test-context"
            )

    @pytest.mark.asyncio
    async def test_parallel_agent_execution(self):
        """Test parallel execution of multiple agents."""
        host_agent = HostAgent()
        
        # Mock both agent calls
        with patch.object(host_agent, "call_inventory_agent", return_value="Inventory: 5 laptops in stock"):
            with patch.object(host_agent, "call_customer_service_agent", return_value="CS: 30-day return policy"):
                
                # Time the parallel execution
                import time
                start_time = time.time()
                
                # Add artificial delay to simulate network calls
                async def delayed_inventory_call(*args):
                    await asyncio.sleep(0.1)
                    return "Inventory: 5 laptops in stock"
                
                async def delayed_cs_call(*args):
                    await asyncio.sleep(0.1)
                    return "CS: 30-day return policy"
                
                host_agent.call_inventory_agent = delayed_inventory_call
                host_agent.call_customer_service_agent = delayed_cs_call
                
                result = await host_agent.call_agents_parallel(
                    "Find laptops and return policy",
                    "test-context",
                    ["inventory", "customer_service"]
                )
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Verify both responses are present
                assert "inventory" in result
                assert "customer_service" in result
                assert "5 laptops" in result["inventory"]
                assert "30-day" in result["customer_service"]
                
                # Verify parallel execution (should take ~0.1s, not 0.2s)
                assert execution_time < 0.15  # Allow some overhead

    @pytest.mark.asyncio
    async def test_agent_error_handling(self):
        """Test error handling when an agent fails."""
        host_agent = HostAgent()
        
        # Mock one agent to fail
        with patch.object(host_agent, "call_inventory_agent", side_effect=Exception("Connection failed")):
            with patch.object(host_agent, "call_customer_service_agent", return_value="CS: Store hours 9-9"):
                
                result = await host_agent.call_agents_parallel(
                    "Test query",
                    "test-context",
                    ["inventory", "customer_service"]
                )
                
                # Should still get customer service response
                assert "customer_service" in result
                assert "Store hours" in result["customer_service"]
                
                # Inventory should have error message
                assert "inventory" in result
                assert "error" in result["inventory"].lower()

    @pytest.mark.asyncio
    async def test_inventory_agent_stream_response(self, mock_vector_store, mock_agent_runner):
        """Test inventory agent streaming response."""
        with patch("backend.agents.inventory_agent_a2a.agent.VertexSearchStore", return_value=mock_vector_store):
            with patch("backend.agents.inventory_agent_a2a.agent.Runner", return_value=mock_agent_runner):
                inventory_agent = InventoryAgent()
                
                # Mock session service
                mock_session = Mock(id="test-session")
                inventory_agent._runner.session_service.get_session = AsyncMock(return_value=mock_session)
                
                # Mock run_async to return events
                async def mock_run_async(*args, **kwargs):
                    # Status event
                    yield Mock(content=None, is_final_response=Mock(return_value=False))
                    # Final response
                    yield Mock(
                        content=Mock(parts=[Mock(text="Found 3 products")]),
                        is_final_response=Mock(return_value=True)
                    )
                
                inventory_agent._runner.run_async = mock_run_async
                
                events = []
                async for event in inventory_agent.stream("Find products", "test-session"):
                    events.append(event)
                
                assert len(events) >= 2  # At least status and result
                assert any(e.get("type") == "status" for e in events)
                assert any(e.get("type") == "result" for e in events)

    @pytest.mark.asyncio
    async def test_customer_service_agent_stream(self):
        """Test customer service agent streaming."""
        with patch("langchain_google_genai.ChatGoogleGenerativeAI"):
            cs_agent = CustomerServiceAgent()
            
            # Mock the graph's astream
            async def mock_astream(*args, **kwargs):
                yield {"messages": [{"role": "assistant", "content": "Our return policy is..."}]}
            
            cs_agent.graph.astream = mock_astream
            cs_agent.get_agent_response = Mock(return_value={
                "is_task_complete": True,
                "content": "30-day return policy with receipt"
            })
            
            events = []
            async for event in cs_agent.stream("What's your return policy?", "test-session"):
                events.append(event)
            
            assert len(events) >= 2
            final_event = events[-1]
            assert final_event["is_task_complete"] is True
            assert "30-day" in final_event["content"]

    @pytest.mark.asyncio
    async def test_agent_status_check(self):
        """Test checking agent status."""
        host_agent = HostAgent()
        
        # Mock successful agent card retrieval for both agents
        mock_inventory_card = Mock(name="Inventory Agent", description="Inventory Description")
        mock_cs_card = Mock(name="Customer Service Agent", description="CS Description")
        
        async def mock_get_card(url):
            if "8001" in url:
                return mock_inventory_card
            elif "8002" in url:
                return mock_cs_card
            return None
        
        with patch.object(host_agent, "_get_agent_card", side_effect=mock_get_card):
            status = await host_agent.get_agent_status()
            
            assert isinstance(status, str)
            assert "Status" in status
            assert "Inventory Agent" in status
            assert "Customer Service Agent" in status

    @pytest.mark.asyncio
    async def test_end_to_end_flow_mock(self):
        """Test simplified end-to-end flow with mocks."""
        host_agent = HostAgent()
        
        # Mock the stream method to return proper events
        async def mock_stream(query, session_id):
            yield {"type": "status", "message": "Processing query..."}
            yield {"type": "tool_call", "tool_name": "route_to_inventory", "message": "Routing to inventory agent..."}
            yield {"type": "result", "content": "Found 5 products matching your search"}
        
        with patch.object(host_agent, "stream", mock_stream):
            events = []
            async for event in host_agent.stream("Find laptops", "test-session"):
                events.append(event)
            
            assert len(events) == 3
            assert events[0]["type"] == "status"
            assert events[1]["type"] == "tool_call"
            assert events[2]["type"] == "result"
            assert "5 products" in events[2]["content"]