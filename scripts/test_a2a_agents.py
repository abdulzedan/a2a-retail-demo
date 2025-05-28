#!/usr/bin/env python3
"""Test script to verify all A2A agents are working correctly with proper protocol."""

import asyncio
import json
import sys
import uuid
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx
from a2a.client import A2AClient
from a2a.types import (
    Message,
    Part,
    Role,
    TextPart,
    SendMessageRequest,
    MessageSendParams,
    MessageSendConfiguration,
    Task,
    TaskState,
)
from a2a.utils import get_message_text


async def test_agent_card(name: str, url: str):
    """Test agent card endpoint."""
    print(f"\n🔍 Testing {name} Agent Card at {url}")
    
    try:
        async with httpx.AsyncClient() as hc:
            # Get agent card
            response = await hc.get(f"{url}/.well-known/agent.json")
            response.raise_for_status()
            
            agent_card = response.json()
            print(f"✅ Agent Card Retrieved:")
            print(f"   Name: {agent_card.get('name')}")
            print(f"   Version: {agent_card.get('version')}")
            print(f"   Description: {agent_card.get('description')}")
            
            # Check capabilities
            capabilities = agent_card.get('capabilities', {})
            print(f"   Capabilities:")
            print(f"     - Streaming: {capabilities.get('streaming', False)}")
            print(f"     - Push Notifications: {capabilities.get('pushNotifications', False)}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {str(e)}")
        return False


async def test_agent_message(name: str, url: str, test_query: str):
    """Test sending a message to an agent using A2A protocol."""
    print(f"\n📤 Testing {name} Message Handling")
    print(f"   Query: {test_query}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as hc:
            # Initialize A2A client
            client = await A2AClient.get_client_from_agent_card_url(
                httpx_client=hc,
                base_url=url
            )
            
            # Create message
            context_id = str(uuid.uuid4())
            message = Message(
                messageId=str(uuid.uuid4()),
                contextId=context_id,
                role=Role.user,
                parts=[Part(root=TextPart(text=test_query))]
            )
            
            # Create request
            request = SendMessageRequest(
                params=MessageSendParams(
                    message=message,
                    configuration=MessageSendConfiguration(
                        acceptedOutputModes=["text/plain", "text"]
                    )
                )
            )
            
            print("   📨 Sending message...")
            
            # Send message
            response = await client.send_message(request)
            
            # Extract response
            if hasattr(response, 'root'):
                result = response.root.result
            else:
                result = response.result if hasattr(response, 'result') else response
            
            print(f"   📥 Response type: {type(result).__name__}")
            
            # Handle different response types
            if isinstance(result, Task):
                print(f"   Task ID: {result.id}")
                print(f"   Status: {result.status.state if result.status else 'unknown'}")
                
                if result.artifacts:
                    print("   Artifacts:")
                    for i, artifact in enumerate(result.artifacts):
                        print(f"     Artifact {i+1}: {artifact.name or 'unnamed'}")
                        for part in artifact.parts:
                            if hasattr(part, 'root') and hasattr(part.root, 'text'):
                                text = part.root.text[:200] + "..." if len(part.root.text) > 200 else part.root.text
                                print(f"       Content: {text}")
                
                return True
                
            elif isinstance(result, Message):
                text = get_message_text(result)
                print(f"   Message: {text[:200]}..." if len(text) > 200 else f"   Message: {text}")
                return True
                
            else:
                print(f"   ⚠️ Unexpected response type: {type(result)}")
                return False
                
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_streaming(name: str, url: str, test_query: str):
    """Test streaming capability of an agent."""
    print(f"\n🌊 Testing {name} Streaming")
    print(f"   Query: {test_query}")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as hc:
            # Initialize A2A client
            client = await A2AClient.get_client_from_agent_card_url(
                httpx_client=hc,
                base_url=url
            )
            
            # Check if streaming is supported
            if hasattr(client, 'agent_card') and client.agent_card:
                if not client.agent_card.capabilities.streaming:
                    print("   ℹ️ Agent does not support streaming")
                    return True
            
            # Create message
            context_id = str(uuid.uuid4())
            message = Message(
                messageId=str(uuid.uuid4()),
                contextId=context_id,
                role=Role.user,
                parts=[Part(root=TextPart(text=test_query))]
            )
            
            # Create streaming request
            from a2a.types import SendStreamingMessageRequest
            request = SendStreamingMessageRequest(
                params=MessageSendParams(
                    message=message,
                    configuration=MessageSendConfiguration(
                        acceptedOutputModes=["text/plain", "text"]
                    )
                )
            )
            
            print("   🌊 Starting stream...")
            
            # Stream messages
            event_count = 0
            async for response in client.send_message_streaming(request):
                event_count += 1
                
                if hasattr(response, 'root'):
                    result = response.root.result
                else:
                    result = response.result if hasattr(response, 'result') else response
                
                print(f"   Event {event_count}: {type(result).__name__}", end="")
                
                # Check for task state updates
                if hasattr(result, 'status') and result.status:
                    print(f" - {result.status.state}")
                elif hasattr(result, 'artifact'):
                    print(f" - Artifact")
                else:
                    print()
            
            print(f"   ✅ Received {event_count} streaming events")
            return True
            
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {str(e)}")
        return False


async def test_host_agent_routing():
    """Test host agent routing to sub-agents."""
    print("\n🔀 Testing Host Agent Routing")
    
    host_url = "http://localhost:8000"
    
    # Test inventory routing
    print("\n  📦 Testing Inventory Routing:")
    success = await test_agent_message(
        "Host (→ Inventory)",
        host_url,
        "Do you have Smart TVs in stock?"
    )
    
    # Test customer service routing
    print("\n  🎧 Testing Customer Service Routing:")
    success2 = await test_agent_message(
        "Host (→ Customer Service)",
        host_url,
        "What's the status of order ORD-12345?"
    )
    
    return success and success2


async def main():
    """Run all tests."""
    print("🧪 A2A Retail Demo - Protocol Compliance Test Suite")
    print("=" * 60)
    
    agents = [
        ("Inventory", "http://localhost:8001", "Show me all products under $50"),
        ("Customer Service", "http://localhost:8002", "What are your store hours?"),
        ("Host", "http://localhost:8000", "Do you have Yoga Mats in stock?"),
    ]
    
    # Test 1: Agent Cards
    print("\n📋 Test 1: Agent Card Endpoints")
    print("-" * 40)
    card_results = []
    for name, url, _ in agents:
        result = await test_agent_card(name, url)
        card_results.append((name, result))
    
    # Test 2: Message Handling
    print("\n\n💬 Test 2: Message Handling")
    print("-" * 40)
    message_results = []
    for name, url, query in agents:
        result = await test_agent_message(name, url, query)
        message_results.append((name, result))
    
    # Test 3: Streaming (if supported)
    print("\n\n🌊 Test 3: Streaming Support")
    print("-" * 40)
    stream_results = []
    for name, url, query in agents:
        result = await test_streaming(name, url, query)
        stream_results.append((name, result))
    
    # Test 4: Host Agent Routing
    print("\n\n🔀 Test 4: Host Agent Routing")
    print("-" * 40)
    routing_result = await test_host_agent_routing()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print("-" * 40)
    
    print("\nAgent Cards:")
    for name, result in card_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")
    
    print("\nMessage Handling:")
    for name, result in message_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")
    
    print("\nStreaming Support:")
    for name, result in stream_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")
    
    print(f"\nHost Routing: {'✅ PASS' if routing_result else '❌ FAIL'}")
    
    # Overall result
    all_passed = (
        all(r[1] for r in card_results) and
        all(r[1] for r in message_results) and
        all(r[1] for r in stream_results) and
        routing_result
    )
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed! Your A2A implementation is compliant.")
    else:
        print("❌ Some tests failed. Please review the implementation.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        # First check if any agent is running
        async def check_agents():
            urls = ["http://localhost:8000", "http://localhost:8001", "http://localhost:8002"]
            any_online = False
            
            async with httpx.AsyncClient(timeout=2.0) as client:
                for url in urls:
                    try:
                        response = await client.get(f"{url}/.well-known/agent.json")
                        if response.status_code == 200:
                            any_online = True
                            break
                    except:
                        pass
            
            return any_online
        
        if not asyncio.run(check_agents()):
            print("❌ No agents are running. Please start the demo first:")
            print("   ./scripts/start_a2a_demo.sh")
            sys.exit(1)
        
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Test interrupted")
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        sys.exit(1)