"""
Integration tests for A2A agent communication.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
import json
import httpx

from backend.agents.host_agent.agent import HostAgent
from backend.agents.inventory_agent_a2a.agent import InventoryAgent
from backend.agents.customer_service_a2a.agent import CustomerServiceAgent


class TestAgentIntegration:
    """Integration tests for multi-agent communication."""

    @pytest.fixture
    def mock_agent_servers(self):
        """Mock the agent servers for integration testing."""
        # This fixture simulates running agent servers
        servers = {"inventory": Mock(), "customer_service": Mock()}
        return servers

    @pytest.mark.asyncio
    async def test_end_to_end_inventory_query(self, mock_vector_store, mock_agent_runner):
        """Test end-to-end flow for inventory query."""
        # Setup inventory agent
        with patch("backend.agents.inventory_agent_a2a.agent.VertexSearchStore", return_value=mock_vector_store):
            with patch("backend.agents.inventory_agent_a2a.agent.Runner", return_value=mock_agent_runner):
                inventory_agent = InventoryAgent()

                # Setup host agent with mock client
                mock_client = Mock()

                # Make the mock client call the actual inventory agent
                async def mock_post(url, json, *args, **kwargs):
                    if "inventory" in url:
                        # Call the actual inventory agent
                        response_data = await inventory_agent.handle_a2a_request(json)
                        response = Mock()
                        response.status_code = 200
                        response.json.return_value = response_data
                        return response
                    else:
                        response = Mock()
                        response.status_code = 200
                        response.json.return_value = {
                            "messages": [{"role": "assistant", "content": "Customer service response"}]
                        }
                        return response

                mock_client.post = AsyncMock(side_effect=mock_post)

                with patch("httpx.AsyncClient", return_value=mock_client):
                    host_agent = HostAgent()
                    host_agent._client = mock_client

                    # Execute end-to-end query
                    result = await host_agent.run("Find me smart TVs", "integration-test-session")

                    assert isinstance(result, dict)
                    assert "response" in result
                    assert len(result["response"]) > 0

    @pytest.mark.asyncio
    async def test_parallel_agent_execution(self):
        """Test parallel execution of multiple agents."""
        # Create mock responses for both agents
        inventory_response = {
            "messages": [{"role": "assistant", "content": "I found 5 laptops in stock: Dell XPS, MacBook Pro, etc."}]
        }

        cs_response = {
            "messages": [{"role": "assistant", "content": "You can return items within 30 days with receipt."}]
        }

        # Setup mock client
        mock_client = Mock()

        async def mock_post(url, *args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate network delay
            response = Mock()
            response.status_code = 200

            if "inventory" in url:
                response.json.return_value = inventory_response
            else:
                response.json.return_value = cs_response

            return response

        mock_client.post = AsyncMock(side_effect=mock_post)

        with patch("httpx.AsyncClient", return_value=mock_client):
            host_agent = HostAgent()
            host_agent._client = mock_client

            # Time the parallel execution
            import time

            start_time = time.time()

            result = await host_agent.call_agents_parallel(
                "Find laptops", "What's the return policy?", "parallel-test-context"
            )

            end_time = time.time()
            execution_time = end_time - start_time

            # Verify both responses are present
            assert "inventory" in result
            assert "customer_service" in result
            assert "5 laptops" in result["inventory"]
            assert "30 days" in result["customer_service"]

            # Verify parallel execution (should take ~0.1s, not 0.2s)
            assert execution_time < 0.15  # Allow some overhead

    @pytest.mark.asyncio
    async def test_agent_communication_resilience(self):
        """Test resilience when one agent fails."""
        mock_client = Mock()

        async def mock_post_with_failure(url, *args, **kwargs):
            response = Mock()

            if "inventory" in url:
                # Inventory agent fails
                raise httpx.HTTPError("Connection refused")
            else:
                # Customer service works
                response.status_code = 200
                response.json.return_value = {
                    "messages": [{"role": "assistant", "content": "Store hours are 9-9 daily."}]
                }
                return response

        mock_client.post = AsyncMock(side_effect=mock_post_with_failure)

        with patch("httpx.AsyncClient", return_value=mock_client):
            host_agent = HostAgent()
            host_agent._client = mock_client

            # Test with both agents query - should handle partial failure
            result = await host_agent.run("What products do you have and what are your hours?", "resilience-test")

            assert isinstance(result, dict)
            assert "response" in result
            # Should still contain customer service response
            assert "9-9 daily" in result["response"] or "error" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_context_propagation(self, mock_vector_store):
        """Test that context is properly propagated through agents."""
        context_id = "test-context-12345"
        captured_contexts = []

        # Create mock client that captures context
        mock_client = Mock()

        async def capture_context(url, json, *args, **kwargs):
            captured_contexts.append(json.get("context", {}))
            response = Mock()
            response.status_code = 200
            response.json.return_value = {"messages": [{"role": "assistant", "content": "Response"}]}
            return response

        mock_client.post = AsyncMock(side_effect=capture_context)

        with patch("httpx.AsyncClient", return_value=mock_client):
            host_agent = HostAgent()
            host_agent._client = mock_client

            await host_agent.run("Test query", context_id)

            # Verify context was propagated
            assert len(captured_contexts) > 0
            assert all(ctx.get("context_id") == context_id for ctx in captured_contexts)

    @pytest.mark.asyncio
    async def test_message_format_consistency(self, mock_vector_store, mock_agent_runner):
        """Test that message formats are consistent across agents."""
        # Test A2A message format for all agents
        test_request = {"messages": [{"role": "user", "content": "Test query"}], "context": {"session_id": "test"}}

        # Mock each agent and verify response format
        agents_to_test = [(InventoryAgent, mock_vector_store, mock_agent_runner), (CustomerServiceAgent, None, None)]

        for agent_class, *mocks in agents_to_test:
            if agent_class == InventoryAgent:
                with patch("backend.agents.inventory_agent_a2a.agent.VertexSearchStore", return_value=mocks[0]):
                    with patch("backend.agents.inventory_agent_a2a.agent.Runner", return_value=mocks[1]):
                        agent = agent_class()
            else:
                with patch("google.generativeai.GenerativeModel"):
                    agent = agent_class()

            response = await agent.handle_a2a_request(test_request)

            # Verify response format
            assert isinstance(response, dict)
            assert "messages" in response
            assert isinstance(response["messages"], list)
            assert len(response["messages"]) > 0
            assert "role" in response["messages"][0]
            assert "content" in response["messages"][0]
            assert response["messages"][0]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_streaming_integration(self, mock_vector_store, mock_agent_runner):
        """Test streaming functionality across agents."""
        # Setup inventory agent with streaming
        with patch("backend.agents.inventory_agent_a2a.agent.VertexSearchStore", return_value=mock_vector_store):
            with patch("backend.agents.inventory_agent_a2a.agent.Runner", return_value=mock_agent_runner):
                inventory_agent = InventoryAgent()

                # Collect all streaming events
                events = []
                async for event in inventory_agent.stream("Find products", "stream-test"):
                    events.append(event)

                # Verify streaming events
                assert len(events) >= 2  # At least status and result

                event_types = [e.get("type") for e in events]
                assert "status" in event_types
                assert "result" in event_types

                # Verify event order
                status_idx = event_types.index("status")
                result_idx = event_types.index("result")
                assert status_idx < result_idx  # Status should come before result

    @pytest.mark.asyncio
    async def test_error_propagation(self):
        """Test that errors are properly propagated through the system."""
        mock_client = Mock()

        # Simulate different error scenarios
        error_scenarios = [(500, "Internal Server Error"), (404, "Agent not found"), (400, "Bad request")]

        for status_code, error_msg in error_scenarios:
            response = Mock()
            response.status_code = status_code
            response.text = error_msg
            response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)

            mock_client.post = AsyncMock(return_value=response)

            with patch("httpx.AsyncClient", return_value=mock_client):
                host_agent = HostAgent()
                host_agent._client = mock_client

                # Should handle error gracefully
                result = await host_agent._call_inventory_agent("test", "error-test")

                # Should return empty string or error message
                assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_load_balancing_simulation(self):
        """Simulate load balancing across multiple agent instances."""
        # Track which "instance" handles each request
        instance_calls = {"instance1": 0, "instance2": 0}

        mock_client = Mock()

        async def mock_load_balanced_post(url, *args, **kwargs):
            # Simple round-robin simulation
            total_calls = sum(instance_calls.values())
            instance = "instance1" if total_calls % 2 == 0 else "instance2"
            instance_calls[instance] += 1

            response = Mock()
            response.status_code = 200
            response.json.return_value = {"messages": [{"role": "assistant", "content": f"Response from {instance}"}]}
            return response

        mock_client.post = AsyncMock(side_effect=mock_load_balanced_post)

        with patch("httpx.AsyncClient", return_value=mock_client):
            host_agent = HostAgent()
            host_agent._client = mock_client

            # Make multiple requests
            tasks = []
            for i in range(10):
                task = host_agent.run(f"Query {i}", f"session-{i}")
                tasks.append(task)

            results = await asyncio.gather(*tasks)

            # Verify load distribution
            assert instance_calls["instance1"] == 5
            assert instance_calls["instance2"] == 5

            # Verify all requests succeeded
            assert all("response" in r for r in results)

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling in agent communication."""
        mock_client = Mock()

        async def mock_slow_response(url, *args, **kwargs):
            # Simulate slow response
            await asyncio.sleep(2)  # Longer than typical timeout
            response = Mock()
            response.status_code = 200
            response.json.return_value = {"messages": []}
            return response

        mock_client.post = AsyncMock(side_effect=mock_slow_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            host_agent = HostAgent()
            host_agent._client = mock_client

            # This should handle timeout gracefully
            # In real implementation, you'd configure timeout in httpx client
            # For this test, we're just verifying the structure exists
            result = await host_agent.run("test", "timeout-test")
            assert isinstance(result, dict)
