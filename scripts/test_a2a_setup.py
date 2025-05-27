#!/usr/bin/env python3
"""Test script to verify A2A setup is working correctly."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.utils.a2a_utils import A2AManager, check_agent_health


async def test_agent_discovery():
    """Test agent discovery."""
    print("🔍 Testing agent discovery...")
    
    manager = A2AManager()
    await manager.initialize()
    
    for name, url in manager.agent_urls.items():
        card = manager.get_agent_info(name)
        if card:
            print(f"✅ {name}: {card.name} - {card.description}")
        else:
            print(f"❌ {name}: Not available at {url}")


async def test_agent_health():
    """Test agent health checks."""
    print("\n💪 Testing agent health...")
    
    agents = {
        "Host Agent": "http://localhost:8000",
        "Inventory Agent": "http://localhost:8001", 
        "Customer Service Agent": "http://localhost:8002",
    }
    
    for name, url in agents.items():
        healthy = await check_agent_health(url)
        status = "✅ Online" if healthy else "❌ Offline"
        print(f"   {name}: {status}")


async def test_a2a_communication():
    """Test A2A communication."""
    print("\n💬 Testing A2A communication...")
    
    manager = A2AManager()
    
    # Test host agent communication
    try:
        response = await manager.send_to_agent("host", "Check agent status")
        if response:
            print("✅ Host agent communication successful")
            print(f"   Response: {response[:100]}...")
        else:
            print("❌ No response from host agent")
    except Exception as e:
        print(f"❌ Host agent communication failed: {e}")


async def main():
    """Run all tests."""
    print("🧪 A2A Retail Demo - Setup Test")
    print("=" * 50)
    
    try:
        await test_agent_health()
        await test_agent_discovery()
        await test_a2a_communication()
        
        print("\n🎉 All tests completed!")
        print("\n💡 If any agents are offline:")
        print("   1. Make sure you've set GOOGLE_API_KEY in .env")
        print("   2. Run: make start")
        print("   3. Wait for all agents to be ready")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())