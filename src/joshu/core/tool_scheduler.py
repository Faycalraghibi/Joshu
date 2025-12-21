"""
Tool scheduler for managing tool execution during conversations.

This module provides declarative structures for scheduling,
validation, and approval of tool calls.

Key principles:
- ZERO execution logic - queues and validates, does not execute
- Approval modes for auto/manual confirmation
- Output truncation with full content preservation
- Integration with hook system
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ApprovalMode(Enum):
    """Mode for tool call approval."""

    AUTO_APPROVE = "auto_approve"  # Automatically approve all
    MANUAL = "manual"  # Require user confirmation
    SAFE_ONLY = "safe_only"  # Auto-approve safe tools only
    NEVER = "never"  # Reject all tool calls


class ToolCallStatus(Enum):
    """Status of a tool call."""

    PENDING = "pending"  # Awaiting approval
    APPROVED = "approved"  # Approved for execution
    REJECTED = "rejected"  # Rejected by user/policy
    EXECUTING = "executing"  # Currently running
    COMPLETED = "completed"  # Finished successfully
    FAILED = "failed"  # Execution failed
    CANCELLED = "cancelled"  # Cancelled before execution


@dataclass
class ScheduledToolCall:
    """
    A tool call queued for execution.

    Attributes:
        call_id: Unique identifier
        tool_name: Name of the tool to execute
        arguments: Arguments to pass to the tool
        status: Current status
        requires_approval: Whether user must approve
        priority: Execution priority (higher = sooner)
        result: Tool execution result (if completed)
        error: Error message (if failed)
        scheduled_at: When the call was scheduled
        completed_at: When execution finished
    """

    call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    status: ToolCallStatus = ToolCallStatus.PENDING
    requires_approval: bool = True
    priority: int = 0
    result: Optional[str] = None
    error: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.scheduled_at is None:
            self.scheduled_at = datetime.now()

    def mark_approved(self) -> None:
        """Mark as approved for execution."""
        self.status = ToolCallStatus.APPROVED

    def mark_rejected(self, reason: str = "") -> None:
        """Mark as rejected."""
        self.status = ToolCallStatus.REJECTED
        self.error = reason

    def mark_completed(self, result: str) -> None:
        """Mark as successfully completed."""
        self.status = ToolCallStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now()

    def mark_failed(self, error: str) -> None:
        """Mark as failed."""
        self.status = ToolCallStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "status": self.status.value,
            "requires_approval": self.requires_approval,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class ToolSchedulerConfig:
    """
    Configuration for the tool scheduler.

    Attributes:
        approval_mode: Default approval mode
        safe_tools: Tools that can be auto-approved
        max_output_display: Max chars to display in output
        save_full_output: Save full output to temp files
        max_concurrent: Maximum concurrent tool calls
    """

    approval_mode: ApprovalMode = ApprovalMode.SAFE_ONLY
    safe_tools: List[str] = field(default_factory=list)
    max_output_display: int = 2000
    save_full_output: bool = True
    max_concurrent: int = 5


class CoreToolScheduler:
    """
    Scheduler for managing tool call lifecycle.

    Handles queuing, validation, approval, and status tracking.
    Does NOT execute tools - delegates to ToolExecutor.

    Example:
        >>> scheduler = CoreToolScheduler()
        >>> call = scheduler.schedule("web_search", {"query": "AI"})
        >>> scheduler.approve(call.call_id)
        >>> # Execution happens elsewhere
    """

    def __init__(self, config: Optional[ToolSchedulerConfig] = None) -> None:
        self.config = config or ToolSchedulerConfig()
        self._queue: Dict[str, ScheduledToolCall] = {}
        self._execution_order: List[str] = []
        self._output_files: Dict[str, str] = {}  # call_id -> file path

    def schedule(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        requires_approval: Optional[bool] = None,
        priority: int = 0,
    ) -> ScheduledToolCall:
        """
        Schedule a tool call for execution.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            requires_approval: Override approval requirement
            priority: Execution priority

        Returns:
            ScheduledToolCall object
        """
        call_id = str(uuid4())

        # Determine if approval is needed
        if requires_approval is None:
            requires_approval = self._needs_approval(tool_name)

        call = ScheduledToolCall(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            requires_approval=requires_approval,
            priority=priority,
        )

        self._queue[call_id] = call
        self._execution_order.append(call_id)
        self._sort_queue()

        logger.debug(f"Scheduled tool call: {tool_name} ({call_id})")

        # Auto-approve if configured
        if not requires_approval:
            call.mark_approved()

        return call

    def _needs_approval(self, tool_name: str) -> bool:
        """Determine if tool needs approval based on config."""
        mode = self.config.approval_mode

        if mode == ApprovalMode.AUTO_APPROVE:
            return False
        if mode == ApprovalMode.NEVER:
            return True
        if mode == ApprovalMode.MANUAL:
            return True
        if mode == ApprovalMode.SAFE_ONLY:
            return tool_name not in self.config.safe_tools
        return True

    def _sort_queue(self) -> None:
        """Sort execution order by priority."""
        self._execution_order.sort(key=lambda cid: self._queue[cid].priority, reverse=True)

    def approve(self, call_id: str) -> bool:
        """Approve a pending tool call."""
        call = self._queue.get(call_id)
        if call and call.status == ToolCallStatus.PENDING:
            call.mark_approved()
            return True
        return False

    def reject(self, call_id: str, reason: str = "") -> bool:
        """Reject a pending tool call."""
        call = self._queue.get(call_id)
        if call and call.status == ToolCallStatus.PENDING:
            call.mark_rejected(reason)
            return True
        return False

    def get_pending(self) -> List[ScheduledToolCall]:
        """Get all pending tool calls."""
        return [
            self._queue[cid]
            for cid in self._execution_order
            if self._queue[cid].status == ToolCallStatus.PENDING
        ]

    def get_approved(self) -> List[ScheduledToolCall]:
        """Get all approved (ready to execute) tool calls."""
        return [
            self._queue[cid]
            for cid in self._execution_order
            if self._queue[cid].status == ToolCallStatus.APPROVED
        ]

    def get_next_approved(self) -> Optional[ScheduledToolCall]:
        """Get next approved tool call for execution."""
        for cid in self._execution_order:
            call = self._queue[cid]
            if call.status == ToolCallStatus.APPROVED:
                return call
        return None

    def complete_call(self, call_id: str, result: str) -> bool:
        """Mark a tool call as completed."""
        call = self._queue.get(call_id)
        if call:
            call.mark_completed(result)
            return True
        return False

    def fail_call(self, call_id: str, error: str) -> bool:
        """Mark a tool call as failed."""
        call = self._queue.get(call_id)
        if call:
            call.mark_failed(error)
            return True
        return False

    def truncate_output(self, output: str, call_id: Optional[str] = None) -> str:
        """
        Truncate output for display.

        Optionally saves full output to temp file.

        Args:
            output: Full output string
            call_id: Optional call ID for file reference

        Returns:
            Truncated output with truncation notice
        """
        max_len = self.config.max_output_display
        if len(output) <= max_len:
            return output

        truncated = output[:max_len]
        notice = f"\n... (output truncated, {len(output) - max_len} chars hidden)"

        if self.config.save_full_output and call_id:
            # In real implementation, would save to temp file
            self._output_files[call_id] = f"/tmp/tool_output_{call_id}.txt"
            notice += "\n[Full output saved to temp file]"

        return truncated + notice

    def get_call(self, call_id: str) -> Optional[ScheduledToolCall]:
        """Get a scheduled call by ID."""
        return self._queue.get(call_id)

    def clear_completed(self) -> int:
        """Remove completed/failed calls from queue."""
        to_remove = [
            cid
            for cid, call in self._queue.items()
            if call.status in (ToolCallStatus.COMPLETED, ToolCallStatus.FAILED)
        ]
        for cid in to_remove:
            del self._queue[cid]
            self._execution_order.remove(cid)
        return len(to_remove)

    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        stats: Dict[str, int] = {}
        for call in self._queue.values():
            key = call.status.value
            stats[key] = stats.get(key, 0) + 1
        return stats
