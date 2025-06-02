#!/usr/bin/env python3
"""Test script to verify A2A setup is working correctly."""

import asyncio
import sys
import httpx
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from a2a.client import A2AClient
except ImportError:
    print("❌ A2A client not available. Please install dependencies with 'make setup'")
    sys.exit(1)


async def test_agent_health():
    """Test agent health checks."""
    print("💪 Testing agent health...")

    agents = {
        "Host Agent": "http://localhost:8000",
        "Inventory Agent": "http://localhost:8001",
        "Customer Service Agent": "http://localhost:8002",
    }

    results = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in agents.items():
            try:
                # Try to get agent card
                a2a_client = await A2AClient.get_client_from_agent_card_url(
                    httpx_client=client, base_url=url
                )
                print(f"   ✅ {name}: Online at {url}")
                results[name] = True
            except Exception as e:
                print(f"   ❌ {name}: Offline at {url} ({str(e)[:50]}...)")
                results[name] = False
    
    return results


async def test_agent_discovery():
    """Test agent card discovery."""
    print("\n🔍 Testing agent discovery...")

    agents = {
        "Host Agent": "http://localhost:8000",
        "Inventory Agent": "http://localhost:8001", 
        "Customer Service Agent": "http://localhost:8002",
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in agents.items():
            try:
                response = await client.get(f"{url}/agent-card")
                if response.status_code == 200:
                    card_data = response.json()
                    agent_name = card_data.get("name", "Unknown")
                    description = card_data.get("description", "No description")
                    print(f"   ✅ {name}: {agent_name}")
                    print(f"      Description: {description}")
                else:
                    print(f"   ❌ {name}: Agent card not available (HTTP {response.status_code})")
            except Exception as e:
                print(f"   ❌ {name}: Cannot fetch agent card ({str(e)[:50]}...)")


async def test_a2a_communication():
    """Test basic A2A communication with host agent."""
    print("\n💬 Testing A2A communication...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test host agent communication
            a2a_client = await A2AClient.get_client_from_agent_card_url(
                httpx_client=client, base_url="http://localhost:8000"
            )
            print("   ✅ Successfully connected to host agent via A2A protocol")
            print("   💡 Full communication test requires all agents to be running")
            
    except Exception as e:
        print(f"   ❌ A2A communication failed: {str(e)}")


async def main():
    """Run all tests."""
    print("🧪 A2A Retail Demo - Setup Test")
    print("=" * 50)

    try:
        # Test agent health first
        health_results = await test_agent_health()
        
        # Only proceed with discovery if at least one agent is online
        if any(health_results.values()):
            await test_agent_discovery()
            await test_a2a_communication()
        else:
            print("\n⚠️  No agents are currently running!")
            
        print("\n🎯 Test Summary:")
        online_count = sum(health_results.values())
        print(f"   Agents online: {online_count}/3")
        
        if online_count == 3:
            print("   🎉 All agents are ready!")
        elif online_count > 0:
            print("   ⚠️  Some agents are offline")
        else:
            print("   ❌ No agents are running")

        print("\n💡 To start all agents:")
        print("   1. Ensure GOOGLE_API_KEY is set in .env")
        print("   2. Run: make start")
        print("   3. Wait for all agents to be ready (may take 30-60 seconds)")
        print("   4. Access the demo at: http://localhost:8080")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
