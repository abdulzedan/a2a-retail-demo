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
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())
        
        query = context.get_user_input()
        task = context.current_task
        
        # Create new task if none exists
        if not task:
            task = new_task(context.message)
            event_queue.enqueue_event(task)
        
        updater = TaskUpdater(event_queue, task.id, task.contextId)
        
        try:
            async for item in self.agent.stream(query, task.contextId):
                is_task_complete = item["is_task_complete"]
                
                if not is_task_complete:
                    # Update status with progress message
                    updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            item["updates"],
                            task.contextId,
                            task.id,
                        ),
                    )
                else:
                    # Task is complete, add artifact and finish
                    updater.add_artifact(
                        [Part(root=TextPart(text=item["content"]))],
                        name="host_response",
                    )
                    updater.complete()
                    break
                    
        except Exception as e:
            logger.error(f"Error executing host agent: {e}")
            raise ServerError(error=InternalError()) from e
    
    def _validate_request(self, context: RequestContext) -> bool:
        """Validate the incoming request."""
        # Basic validation - ensure we have user input
        try:
            user_input = context.get_user_input()
            return not user_input or not user_input.strip()
        except Exception:
            return True
    
    async def cancel(
        self,
        request: RequestContext,
        event_queue: EventQueue
    ) -> Task | None:
        """Cancel a task - not supported for this agent."""
        raise ServerError(error=UnsupportedOperationError())