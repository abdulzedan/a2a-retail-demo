"""Customer Service Agent Executor for A2A Protocol."""

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

from .agent import CustomerServiceAgent

logger = logging.getLogger(__name__)


class CustomerServiceAgentExecutor(AgentExecutor):
    """Customer Service Agent Executor for A2A Protocol."""
    
    def __init__(self):
        self.agent = CustomerServiceAgent()
    
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute customer service agent request."""
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
                require_user_input = item.get("require_user_input", False)
                
                if not is_task_complete and not require_user_input:
                    # Update status with progress message
                    updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            item["content"],
                            task.contextId,
                            task.id,
                        ),
                    )
                elif require_user_input:
                    # Need more input from user
                    updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(
                            item["content"],
                            task.contextId,
                            task.id,
                        ),
                        final=True,
                    )
                    break
                else:
                    # Task is complete, add artifact and finish
                    updater.add_artifact(
                        [Part(root=TextPart(text=item["content"]))],
                        name="customer_service_response",
                    )
                    updater.complete()
                    break
                    
        except Exception as e:
            logger.error(f"Error executing customer service agent: {e}")
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