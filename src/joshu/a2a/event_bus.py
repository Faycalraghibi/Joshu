"""
A2A Event Bus for streaming execution events.

This module provides an event bus for publishing and subscribing
to agent execution events, enabling SSE streaming to clients.

NOTE: This module provides transport and orchestration only.
It must not introduce new agent logic or execution semantics.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import AsyncIterator, Dict, List, Optional, Set

from joshu.a2a.events import AgentExecutionEvent

logger = logging.getLogger(__name__)


class ExecutionEventBus:
    """
    Event bus for streaming agent execution events.

    Supports multiple subscribers per task, with async iteration
    for SSE streaming. Handles subscriber cleanup on disconnect.

    Example:
        >>> bus = ExecutionEventBus()
        >>> # Subscribe to task events
        >>> async for event in bus.subscribe("task-123"):
        ...     print(event.to_sse())
        >>> # Publish an event
        >>> await bus.publish(event)
    """

    def __init__(self) -> None:
        # task_id -> list of subscriber queues
        self._subscribers: Dict[
            str, List[asyncio.Queue[Optional[AgentExecutionEvent]]]
        ] = defaultdict(list)
        # Set of active task IDs
        self._active_tasks: Set[str] = set()
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def publish(self, event: AgentExecutionEvent) -> None:
        """
        Publish an event to all subscribers for the task.

        Args:
            event: The event to publish
        """
        async with self._lock:
            queues = self._subscribers.get(event.task_id, [])
            for queue in queues:
                try:
                    await queue.put(event)
                except Exception as e:
                    logger.warning(f"Failed to publish event to subscriber: {e}")

        logger.debug(f"Published {event.event_type.value} for task {event.task_id}")

    async def subscribe(
        self, task_id: str, timeout: Optional[float] = None
    ) -> AsyncIterator[AgentExecutionEvent]:
        """
        Subscribe to events for a specific task.

        Yields events as they are published. The iterator ends when:
        - A COMPLETE or ERROR event is received
        - The task is marked as ended
        - A sentinel (None) is received

        Args:
            task_id: ID of the task to subscribe to
            timeout: Optional timeout in seconds for waiting

        Yields:
            AgentExecutionEvent instances
        """
        queue: asyncio.Queue[Optional[AgentExecutionEvent]] = asyncio.Queue()

        async with self._lock:
            self._subscribers[task_id].append(queue)
            self._active_tasks.add(task_id)

        logger.debug(f"New subscriber for task {task_id}")

        try:
            while True:
                try:
                    if timeout:
                        event = await asyncio.wait_for(queue.get(), timeout=timeout)
                    else:
                        event = await queue.get()

                    # None is sentinel for end of stream
                    if event is None:
                        logger.debug(f"Subscriber received end signal for task {task_id}")
                        break

                    yield event

                    # Check for terminal events
                    if event.event_type.value in ("complete", "error"):
                        logger.debug(f"Subscriber ending due to {event.event_type.value}")
                        break

                except asyncio.TimeoutError:
                    logger.debug(f"Subscriber timeout for task {task_id}")
                    break
                except asyncio.CancelledError:
                    logger.debug(f"Subscriber cancelled for task {task_id}")
                    break

        finally:
            # Cleanup subscriber
            async with self._lock:
                if task_id in self._subscribers:
                    try:
                        self._subscribers[task_id].remove(queue)
                        if not self._subscribers[task_id]:
                            del self._subscribers[task_id]
                    except ValueError:
                        pass  # Already removed
            logger.debug(f"Subscriber cleanup for task {task_id}")

    async def end_task(self, task_id: str) -> None:
        """
        Signal end of task to all subscribers.

        Sends a sentinel value to all subscribers to close their streams.

        Args:
            task_id: ID of the task to end
        """
        async with self._lock:
            self._active_tasks.discard(task_id)
            queues = self._subscribers.get(task_id, [])
            for queue in queues:
                try:
                    await queue.put(None)  # Sentinel
                except Exception as e:
                    logger.warning(f"Failed to send end signal: {e}")

        logger.debug(f"Ended task {task_id}")

    def is_task_active(self, task_id: str) -> bool:
        """Check if a task is still active."""
        return task_id in self._active_tasks

    def get_subscriber_count(self, task_id: str) -> int:
        """Get number of subscribers for a task."""
        return len(self._subscribers.get(task_id, []))

    async def clear_task(self, task_id: str) -> None:
        """Clear all subscribers for a task."""
        await self.end_task(task_id)
        async with self._lock:
            if task_id in self._subscribers:
                del self._subscribers[task_id]


# Module-level event bus instance
_event_bus: Optional[ExecutionEventBus] = None


def get_event_bus() -> ExecutionEventBus:
    """
    Get the global event bus instance.

    Returns:
        ExecutionEventBus singleton instance
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = ExecutionEventBus()
    return _event_bus
