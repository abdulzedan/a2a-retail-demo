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
    DataPart,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_agent_text_message,
    new_task,
)
from a2a.utils.errors import ServerError

from .agent import InventoryAgent

logger = logging.getLogger(__name__)


class InventoryAgentExecutor(AgentExecutor):
    """Inventory Agent Executor for A2A Protocol."""

    def __init__(self):
        self.agent = InventoryAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute inventory agent request."""
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
                event_type = event.get("type")

                if event_type == "status":
                    # Update status
                    updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            event["message"],
                            task.contextId,
                            task.id,
                        ),
                    )

                elif event_type == "tool_call":
                    # Tool is being called
                    updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            f"Calling {event['tool_name']}: {event.get('message', 'Processing...')}",
                            task.contextId,
                            task.id,
                        ),
                    )

                elif event_type == "result":
                    # Final result
                    content = event["content"]

                    # Check if it's JSON data or plain text
                    if isinstance(content, dict):
                        parts = [Part(root=DataPart(data=content))]
                    else:
                        parts = [Part(root=TextPart(text=str(content)))]

                    # Add artifact
                    updater.add_artifact(
                        parts,
                        name="inventory_result",
                    )

                    # Complete task
                    updater.complete()
                    break

                elif event_type == "error":
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
            logger.error(f"Error executing inventory agent: {e}", exc_info=True)
            updater.failed(
                new_agent_text_message(
                    f"Internal error: {str(e)}",
                    task.contextId,
                    task.id,
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> Task | None:
        """Cancel a task - not supported for this agent."""
        raise ServerError(error=UnsupportedOperationError())
