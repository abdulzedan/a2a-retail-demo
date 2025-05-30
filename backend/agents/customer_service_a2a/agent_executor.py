import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
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
            async for item in self.agent.stream(query, task.contextId):
                is_task_complete = item.get("is_task_complete", False)
                require_user_input = item.get("require_user_input", False)
                inventory_query = item.get("inventory_query", False)
                content = item.get("content", "")

                if not is_task_complete and not require_user_input:
                    # Working state - update status
                    updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            content,
                            task.contextId,
                            task.id,
                        ),
                    )

                elif require_user_input:
                    # Need more input from user
                    updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(
                            content,
                            task.contextId,
                            task.id,
                        ),
                        final=True,
                    )
                    break

                elif inventory_query:
                    # This is an inventory query - indicate it should be routed
                    updater.update_status(
                        TaskState.failed,
                        new_agent_text_message(
                            "I need to check our inventory system for product availability. Please ask the host agent to route your query to the inventory agent.",
                            task.contextId,
                            task.id,
                        ),
                        final=True,
                    )
                    break

                else:
                    # Task completed successfully
                    updater.add_artifact(
                        [Part(root=TextPart(text=content))],
                        name="customer_service_response",
                    )
                    updater.complete()
                    break

        except Exception as e:
            logger.error(f"Error executing customer service agent: {e}", exc_info=True)
            updater.failed(
                new_agent_text_message(
                    f"I apologize, but I encountered an error: {str(e)}",
                    task.contextId,
                    task.id,
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> Task | None:
        """Cancel a task - not supported for this agent."""
        raise ServerError(error=UnsupportedOperationError())
