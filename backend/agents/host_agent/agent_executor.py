"""Host Agent Executor for A2A Protocol."""

import logging
from typing import Any, Dict

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InternalError,
    InvalidParamsError,
    Part,
    Task,
    TaskState,
    TextPart,
    Message,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_agent_text_message,
    new_task,
)
from a2a.utils.errors import ServerError

from .agent import HostAgent

logger = logging.getLogger(__name__)


class HostAgentExecutor(AgentExecutor):
    """Host Agent Executor for A2A Protocol."""
    
    def __init__(self):
        self.agent = HostAgent()
    
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute host agent request."""
        # Validate request
        if not context.message or not context.get_user_input():
            raise ServerError(error=InvalidParamsError())
        
        query = context.get_user_input()
        task = context.current_task
        
        # Create new task if none exists
        if not task:
            task = new_task(context.message)
            event_queue.enqueue_event(task)
        
        updater = TaskUpdater(event_queue, task.id, task.contextId)
        
        try:
            # Start working
            updater.start_work()
            
            # Execute agent logic
            async for event in self.agent.stream(query, task.contextId):
                event_type = event.get('type')
                
                if event_type == 'status':
                    # Update status
                    updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            event['message'],
                            task.contextId,
                            task.id,
                        ),
                    )
                
                elif event_type == 'routing':
                    # Routing to another agent
                    updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            f"Routing to {event['agent']} agent: {event['message']}",
                            task.contextId,
                            task.id,
                        ),
                    )
                
                elif event_type == 'agent_response':
                    # Response from sub-agent
                    updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            f"Received response from {event['agent']} agent",
                            task.contextId,
                            task.id,
                        ),
                    )
                
                elif event_type == 'result':
                    # Final result
                    content = event['content']
                    parts = [Part(root=TextPart(text=str(content)))]
                    
                    # Add artifact
                    updater.add_artifact(
                        parts,
                        name='host_response',
                    )
                    
                    # Complete task
                    updater.complete()
                    break
                    
                elif event_type == 'error':
                    # Error occurred
                    updater.failed(
                        new_agent_text_message(
                            f"Error: {event['message']}",
                            task.contextId,
                            task.id,
                        )
                    )
                    break
                    
        except Exception as e:
            logger.error(f"Error executing host agent: {e}", exc_info=True)
            updater.failed(
                new_agent_text_message(
                    f"Internal error: {str(e)}",
                    task.contextId,
                    task.id,
                )
            )
    
    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> Task | None:
        """Cancel a task - not supported for this agent."""
        raise ServerError(error=UnsupportedOperationError())