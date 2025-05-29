#!/usr/bin/env python3
"""CLI client for interacting with A2A agents."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.utils.a2a_utils import A2AManager


class A2ACLIClient:
    """CLI client for A2A agent interaction."""

    def __init__(self):
        self.manager = A2AManager()
        self.current_agent = "host"

    async def initialize(self):
        """Initialize the client."""
        print("🔌 Initializing A2A CLI Client...")
        await self.manager.initialize()

        # Check agent status
        health = await self.manager.check_all_agents()
        print("\n📊 Agent Status:")
        for name, online in health.items():
            status = "✅ Online" if online else "❌ Offline"
            print(f"   {name}: {status}")

        print(f"\n🎯 Current agent: {self.current_agent}")

    def show_help(self):
        """Show help information."""
        print("\n🆘 Available Commands:")
        print("   /help          - Show this help")
        print("   /status        - Check agent status")
        print("   /switch <name> - Switch to agent (host, inventory, customer_service)")
        print("   /quit          - Exit the client")
        print("   /clear         - Clear screen")
        print("\n💬 A2A Queries:")
        print("   Just type your message to send to the current agent")
        print("\n📝 Example queries:")
        print("   • Do you have Smart TVs in stock?")
        print("   • What's the status of order ORD-12345?")
        print("   • Show me wireless earbuds under $200")
        print("   • What are your store hours?")

    async def handle_command(self, command: str) -> bool:
        """Handle CLI commands. Returns True to continue, False to quit."""
        command = command.strip()

        if command == "/help":
            self.show_help()
        elif command == "/quit":
            print("👋 Goodbye!")
            return False
        elif command == "/clear":
            import os

            os.system("clear" if os.name == "posix" else "cls")
        elif command == "/status":
            health = await self.manager.check_all_agents()
            print("\n📊 Agent Status:")
            for name, online in health.items():
                status = "✅ Online" if online else "❌ Offline"
                print(f"   {name}: {status}")
        elif command.startswith("/switch "):
            agent_name = command.split(" ", 1)[1].strip()
            if agent_name in self.manager.agent_urls:
                self.current_agent = agent_name
                print(f"🔄 Switched to {agent_name} agent")
            else:
                print(f"❌ Unknown agent: {agent_name}")
                print(f"   Available: {', '.join(self.manager.agent_urls.keys())}")
        else:
            print(f"❌ Unknown command: {command}")
            print("   Type /help for available commands")

        return True

    async def send_message(self, message: str):
        """Send a message to the current agent."""
        print(f"📤 Sending to {self.current_agent} agent: {message}")
        print("⏳ Processing...")

        try:
            response = await self.manager.send_to_agent(self.current_agent, message)
            if response:
                print(f"📥 Response:\n{response}")
            else:
                print("❌ No response received")
        except Exception as e:
            print(f"❌ Error: {e}")

    async def run(self):
        """Run the CLI client."""
        await self.initialize()
        self.show_help()

        print("\n" + "=" * 60)
        print("🎮 A2A CLI Client - Ready for interaction!")
        print("=" * 60)

        while True:
            try:
                # Show prompt
                prompt = f"\n[{self.current_agent}]> "
                user_input = input(prompt).strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    should_continue = await self.handle_command(user_input)
                    if not should_continue:
                        break
                else:
                    # Send message to agent
                    await self.send_message(user_input)

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except EOFError:
                print("\n\n👋 Goodbye!")
                break


async def main():
    """Main entry point."""
    client = A2ACLIClient()
    await client.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ CLI Client error: {e}")
        sys.exit(1)
