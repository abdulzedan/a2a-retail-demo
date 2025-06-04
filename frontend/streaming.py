"""Streaming handler with detailed thought process and real-time updates."""
import asyncio
import uuid
from typing import Dict, List, AsyncIterable, Optional
from datetime import datetime
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

class StreamingEvent:
    """Represents a streaming event with metadata."""
    def __init__(self, event_type: str, content: str, metadata: Optional[Dict] = None):
        self.event_type = event_type
        self.content = content
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()

class StreamingHandler:
    """Streaming handler with detailed thought process."""
    
    def __init__(self):
        self.agent_urls = {
            "host": "http://localhost:8000",
            "inventory": "http://localhost:8001", 
            "customer_service": "http://localhost:8002"
        }
        self.thinking_phrases = {
            "analysis": [
                "🤔 Analyzing your request...",
                "🔍 Understanding your needs...",
                "📋 Processing your query...",
                "🎯 Identifying the right approach..."
            ],
            "routing": [
                "🔄 Determining the best agent for your request...",
                "🧭 Routing to the appropriate specialist...",
                "🔗 Connecting to the right expert...",
                "📡 Establishing connection with specialized agent..."
            ],
            "searching": [
                "🔎 Searching our inventory database...",
                "📊 Analyzing product availability...",
                "🏪 Checking store systems...",
                "💾 Querying product information..."
            ],
            "processing": [
                "⚙️ Processing your order information...",
                "📝 Reviewing account details...",
                "🔧 Working on your request...",
                "💡 Formulating the best response..."
            ]
        }
    
    async def stream_message_with_thoughts(
        self, 
        message: str, 
        context_id: str,
        show_thoughts: bool = True
    ) -> AsyncIterable[StreamingEvent]:
        """Stream a message with detailed thought process."""
        
        # Step 1: Initial analysis
        if show_thoughts:
            yield StreamingEvent(
                "thinking",
                "🤔 Analyzing your request...",
                {"stage": "analysis", "progress": 10}
            )
            await asyncio.sleep(0.5)
            
            yield StreamingEvent(
                "thinking", 
                "🧠 Understanding context and intent...",
                {"stage": "analysis", "progress": 25}
            )
            await asyncio.sleep(0.3)
        
        # Step 2: Determine routing
        if show_thoughts:
            yield StreamingEvent(
                "thinking",
                "🔄 Determining the best agent for your request...",
                {"stage": "routing", "progress": 40}
            )
            await asyncio.sleep(0.4)
        
        # Step 3: Connect to host agent
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if show_thoughts:
                    yield StreamingEvent(
                        "thinking",
                        "📡 Connecting to host agent...",
                        {"stage": "connecting", "progress": 50}
                    )
                    await asyncio.sleep(0.3)
                
                # Get A2A client
                a2a_client = await A2AClient.get_client_from_agent_card_url(
                    httpx_client=client, 
                    base_url=self.agent_urls["host"]
                )
                
                if show_thoughts:
                    yield StreamingEvent(
                        "thinking",
                        "✅ Connected! Sending your request...",
                        {"stage": "connected", "progress": 60}
                    )
                    await asyncio.sleep(0.2)
                
                # Create message
                a2a_message = Message(
                    messageId=str(uuid.uuid4()),
                    contextId=context_id,
                    role=Role.user,
                    parts=[Part(root=TextPart(text=message))],
                )
                
                # Create request
                request = SendMessageRequest(
                    id=str(uuid.uuid4()),
                    params=MessageSendParams(
                        message=a2a_message,
                        configuration=MessageSendConfiguration(
                            acceptedOutputModes=["text/plain", "text"]
                        )
                    ),
                )
                
                if show_thoughts:
                    yield StreamingEvent(
                        "thinking",
                        "🔄 Processing through A2A protocol...",
                        {"stage": "processing", "progress": 75}
                    )
                    await asyncio.sleep(0.5)
                
                # Send message
                response = await a2a_client.send_message(request)
                
                if show_thoughts:
                    yield StreamingEvent(
                        "thinking",
                        "📨 Receiving response from agents...",
                        {"stage": "receiving", "progress": 90}
                    )
                    await asyncio.sleep(0.3)
                
                # Extract response
                response_text = await self._extract_response(response)
                
                # Final response
                yield StreamingEvent(
                    "response",
                    response_text,
                    {"stage": "complete", "progress": 100, "final": True}
                )
                
        except Exception as e:
            yield StreamingEvent(
                "error",
                f"Error communicating with agents: {str(e)}",
                {"stage": "error", "progress": 0}
            )
    
    async def _extract_response(self, response) -> str:
        """Extract text response from A2A response."""
        if hasattr(response, "root"):
            result = response.root.result
        else:
            result = response.result if hasattr(response, "result") else response
        
        if isinstance(result, Task):
            if result.artifacts:
                texts = []
                for artifact in result.artifacts:
                    for part in artifact.parts:
                        if hasattr(part, "root") and hasattr(part.root, "text"):
                            texts.append(part.root.text)
                return "\n".join(texts) if texts else "Task completed with no text response"
            elif result.status and result.status.message:
                return get_message_text(result.status.message)
            else:
                return f"Task {result.id} status: {result.status.state if result.status else 'unknown'}"
        elif isinstance(result, Message):
            return get_message_text(result)
        else:
            return "Received response but unable to extract text"
    
    async def stream_with_agent_details(
        self, 
        message: str, 
        context_id: str,
        show_thoughts: bool = True
    ) -> AsyncIterable[StreamingEvent]:
        """Stream with detailed agent interaction information."""
        
        # Analyze message to predict routing
        predicted_agent = self._predict_agent_routing(message)
        
        if show_thoughts:
            yield StreamingEvent(
                "thinking",
                f"🎯 This looks like a {predicted_agent} query",
                {"stage": "prediction", "agent": predicted_agent}
            )
            await asyncio.sleep(0.4)
            
            yield StreamingEvent(
                "thinking",
                f"📋 Preparing to route to {predicted_agent} specialist...",
                {"stage": "preparation", "agent": predicted_agent}
            )
            await asyncio.sleep(0.3)
        
        # Stream the actual message
        async for event in self.stream_message_with_thoughts(message, context_id, show_thoughts):
            # Add agent prediction metadata
            if event.metadata:
                event.metadata["predicted_agent"] = predicted_agent
            yield event
    
    def _predict_agent_routing(self, message: str) -> str:
        """Predict which agent will handle the message."""
        message_lower = message.lower()
        
        # Inventory keywords
        inventory_keywords = [
            "stock", "inventory", "product", "available", "price", "cost",
            "buy", "purchase", "search", "find", "show", "category", "brand"
        ]
        
        # Customer service keywords  
        service_keywords = [
            "order", "return", "refund", "complaint", "help", "support",
            "hours", "store", "location", "policy", "shipping", "delivery"
        ]
        
        inventory_score = sum(1 for keyword in inventory_keywords if keyword in message_lower)
        service_score = sum(1 for keyword in service_keywords if keyword in message_lower)
        
        if inventory_score > service_score:
            return "inventory"
        elif service_score > inventory_score:
            return "customer service"
        else:
            return "general"
    
    async def check_agent_health_with_details(self) -> Dict[str, Dict]:
        """Check agent health with detailed status information."""
        health_status = {}
        
        for agent_name, url in self.agent_urls.items():
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Check agent card
                    start_time = datetime.now()
                    response = await client.get(f"{url}/.well-known/agent.json")
                    response_time = (datetime.now() - start_time).total_seconds()
                    
                    if response.status_code == 200:
                        agent_card = response.json()
                        health_status[agent_name] = {
                            "online": True,
                            "response_time": response_time,
                            "name": agent_card.get("name", "Unknown"),
                            "version": agent_card.get("version", "Unknown"),
                            "capabilities": agent_card.get("capabilities", {}),
                            "url": url
                        }
                    else:
                        health_status[agent_name] = {
                            "online": False,
                            "error": f"HTTP {response.status_code}",
                            "url": url
                        }
            except Exception as e:
                health_status[agent_name] = {
                    "online": False,
                    "error": str(e),
                    "url": url
                }
        
        return health_status
    
    async def simulate_complex_interaction(
        self, 
        message: str, 
        context_id: str
    ) -> AsyncIterable[StreamingEvent]:
        """Simulate a complex multi-agent interaction with detailed steps."""
        
        steps = [
            ("🔍 Analyzing query complexity", 1),
            ("🧠 Breaking down into sub-tasks", 1.5),
            ("📊 Checking system capabilities", 1),
            ("🔄 Initializing agent coordination", 2),
            ("📡 Establishing A2A connections", 1.5),
            ("⚙️ Processing through specialized agents", 3),
            ("🔄 Consolidating responses", 1),
            ("✅ Finalizing comprehensive answer", 1)
        ]
        
        total_steps = len(steps)
        for i, (step_description, duration) in enumerate(steps):
            progress = int((i + 1) / total_steps * 100)
            
            yield StreamingEvent(
                "processing",
                step_description,
                {
                    "step": i + 1,
                    "total_steps": total_steps,
                    "progress": progress,
                    "stage": "complex_processing"
                }
            )
            
            await asyncio.sleep(duration)
        
        # Now do the actual processing
        async for event in self.stream_message_with_thoughts(message, context_id, True):
            yield event

# Usage example for integration with Mesop frontend
class StreamingIntegration:
    """Integration layer for Mesop frontend."""
    
    def __init__(self):
        self.handler = StreamingHandler()
    
    async def process_user_message(
        self, 
        message: str, 
        context_id: str,
        show_thoughts: bool = True,
        complex_mode: bool = False
    ) -> List[Dict]:
        """Process user message and return events for Mesop state updates."""
        events = []
        
        stream_method = (
            self.handler.simulate_complex_interaction if complex_mode 
            else self.handler.stream_with_agent_details
        )
        
        async for event in stream_method(message, context_id):
            events.append({
                "type": event.event_type,
                "content": event.content,
                "metadata": event.metadata,
                "timestamp": event.timestamp,
                "is_final": event.metadata.get("final", False)
            })
        
        return events
    
    async def get_detailed_agent_status(self) -> Dict:
        """Get detailed agent status for UI display."""
        return await self.handler.check_agent_health_with_details()

# Example of how to integrate with the Mesop frontend
async def send_message_handler(message_text: str, context_id: str, show_thoughts: bool = True):
    """Message handler for Mesop integration."""
    integration = StreamingIntegration()
    
    events = await integration.process_user_message(
        message_text, 
        context_id, 
        show_thoughts=show_thoughts,
        complex_mode=len(message_text.split()) > 10  # Complex mode for longer queries
    )
    
    return events