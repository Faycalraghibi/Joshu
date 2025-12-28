"""
A2A HTTP Server for exposing Joshu agent capabilities.

This module provides a FastAPI HTTP server with SSE streaming
for real-time agent communication.

NOTE: This module provides transport and orchestration only.
It must not introduce new agent logic or execution semantics.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from joshu.a2a.event_bus import get_event_bus
from joshu.a2a.events import AgentExecutionEvent
from joshu.a2a.executor import TaskNotFoundError, get_agent_executor
from joshu.a2a.task import AgentSettings

logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateTaskRequest(BaseModel):
    """Request to create a new task."""

    message: str = Field(..., description="Initial user message")
    model: Optional[str] = Field(None, description="Model to use")
    target_directory: Optional[str] = Field(None, description="Working directory")
    tools_enabled: bool = Field(True, description="Enable tool calling")


class TaskResponse(BaseModel):
    """Response with task information."""

    task_id: str
    state: str
    created_at: str
    message: Optional[str] = None


class TaskMetadataResponse(BaseModel):
    """Response with task metadata."""

    task_id: str
    state: str
    created_at: str
    updated_at: str
    is_terminal: bool
    pending_confirmation: Optional[str] = None


class CancelRequest(BaseModel):
    """Request to cancel a task."""

    reason: str = Field("Canceled by user", description="Cancellation reason")


class CancelResponse(BaseModel):
    """Response to cancel request."""

    success: bool
    task_id: str
    message: str


class ConfirmationResponse(BaseModel):
    """Request to respond to confirmation."""

    call_id: str = Field(..., description="Tool call ID")
    response: str = Field(..., description="Response: proceed_once, cancel, cancel_task")


class ExecuteCommandRequest(BaseModel):
    """Request to execute a CLI command."""

    command: str = Field(..., description="Command name to execute")
    args: Dict[str, Any] = Field(default_factory=dict, description="Command arguments")
    workspace_path: Optional[str] = Field(None, description="Working directory")


class CommandArgumentInfo(BaseModel):
    """Information about a command argument."""

    name: str
    description: str
    type: str = "string"
    required: bool = False
    default: Any = None


class SubcommandInfo(BaseModel):
    """Information about a subcommand."""

    name: str
    description: str
    arguments: List[CommandArgumentInfo] = []


class CommandInfo(BaseModel):
    """Information about an available command."""

    name: str
    description: str
    arguments: List[CommandArgumentInfo] = []
    subcommands: List[SubcommandInfo] = []


class AgentCard(BaseModel):
    """Agent metadata and capabilities."""

    name: str
    version: str
    description: str
    capabilities: List[str]
    supported_models: List[str]


# ============================================================================
# Lifespan and App Setup
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler for startup/shutdown."""
    logger.info("A2A Server starting...")

    from joshu.a2a.commands.registry import register_default_commands

    register_default_commands()

    yield
    logger.info("A2A Server shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Joshu A2A Server",
    description="Agent-to-Agent Communication Server for Joshu",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Task Endpoints
# ============================================================================


@app.post("/tasks", response_model=TaskResponse)
async def create_task(request: CreateTaskRequest) -> TaskResponse:
    """
    Create a new agent task.

    Creates a task in SUBMITTED state. Use /tasks/{id}/stream
    to execute and stream events.
    """
    executor = get_agent_executor()

    settings = AgentSettings(
        model=request.model or "default",
        target_directory=request.target_directory or ".",
        tools_enabled=request.tools_enabled,
    )

    task = await executor.create_task(request.message, settings)

    return TaskResponse(
        task_id=task.task_id,
        state=task.state.value,
        created_at=task.created_at.isoformat(),
        message="Task created successfully",
    )


@app.get("/tasks/{task_id}", response_model=TaskMetadataResponse)
async def get_task(task_id: str) -> TaskMetadataResponse:
    """Get task metadata."""
    executor = get_agent_executor()

    try:
        metadata = executor.get_task_metadata(task_id)
        return TaskMetadataResponse(**metadata)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")


@app.get("/tasks/metadata")
async def get_all_tasks_metadata() -> List[Dict[str, Any]]:
    """Get metadata for all active tasks."""
    executor = get_agent_executor()

    tasks_metadata = []
    for task_id in executor._active_tasks:
        try:
            metadata = executor.get_task_metadata(task_id)
            tasks_metadata.append(metadata)
        except TaskNotFoundError:
            pass

    return tasks_metadata


@app.get("/tasks/{task_id}/stream")
async def stream_task(task_id: str, request: Request) -> StreamingResponse:
    """
    Stream task execution events via SSE.

    Starts execution if task is in SUBMITTED state.
    Returns events until task reaches terminal state or client disconnects.
    """
    executor = get_agent_executor()

    # Verify task exists
    try:
        await executor.get_task(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    async def event_generator():
        """Generate SSE events."""
        try:
            async for event in executor.execute_task(task_id):
                # Check for client disconnect
                if await request.is_disconnected():
                    logger.info(f"Client disconnected for task {task_id}")
                    await executor.cancel_task(task_id, "Client disconnected")
                    break

                yield event.to_sse()

        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for task {task_id}")
        except Exception as e:
            logger.error(f"Stream error for task {task_id}: {e}")
            error_event = AgentExecutionEvent.error(task_id, str(e))
            yield error_event.to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@app.post("/tasks/{task_id}/cancel", response_model=CancelResponse)
async def cancel_task(task_id: str, request: CancelRequest) -> CancelResponse:
    """Cancel a running task."""
    executor = get_agent_executor()

    success = await executor.cancel_task(task_id, request.reason)

    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Could not cancel task {task_id} - not found or already terminal",
        )

    return CancelResponse(
        success=True,
        task_id=task_id,
        message=f"Task canceled: {request.reason}",
    )


@app.post("/tasks/{task_id}/confirm")
async def respond_to_confirmation(task_id: str, response: ConfirmationResponse) -> Dict[str, Any]:
    """Respond to a tool confirmation request."""
    executor = get_agent_executor()

    success = await executor.respond_to_confirmation(task_id, response.call_id, response.response)

    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid confirmation response for task {task_id}",
        )

    return {"success": True, "task_id": task_id, "call_id": response.call_id}


# ============================================================================
# Command Execution Endpoints
# ============================================================================


@app.post("/executeCommand")
async def execute_command(
    request: ExecuteCommandRequest, http_request: Request
) -> StreamingResponse:
    """
    Execute a CLI command with SSE streaming.

    Executes the specified command and streams TaskStatusUpdateEvents
    as Server-Sent Events for real-time feedback.
    """
    from uuid import uuid4

    from joshu.a2a.commands.registry import get_command_registry
    from joshu.a2a.commands.types import CommandContext

    registry = get_command_registry()
    command = registry.get(request.command)

    if not command:
        raise HTTPException(status_code=404, detail=f"Command not found: {request.command}")

    # Determine workspace path
    workspace_path = Path(
        request.workspace_path or os.environ.get("CODER_AGENT_WORKSPACE_PATH", ".")
    )

    # Create command context
    task_id = str(uuid4())
    ctx = CommandContext(
        workspace_path=workspace_path,
        config={},  # Could load from config file
        event_bus=get_event_bus(),
        executor=get_agent_executor(),
        task_id=task_id,
    )

    async def event_generator():
        """Generate SSE events from command execution."""
        try:
            # Publish start event
            start_event = AgentExecutionEvent.message(
                task_id,
                f"Executing command: {request.command}",
            )
            yield start_event.to_sse()

            # Execute command
            async for result in command.execute(ctx, request.args):
                # Check for client disconnect
                if await http_request.is_disconnected():
                    logger.info(f"Client disconnected during command: {request.command}")
                    break

                # Convert result to SSE event
                event = AgentExecutionEvent.message(
                    task_id,
                    result.message,
                )
                event.data["status"] = result.status.value
                event.data["command_data"] = result.data
                if result.error:
                    event.data["error"] = result.error
                yield event.to_sse()

            # Complete event
            complete_event = AgentExecutionEvent.complete(
                task_id,
                f"Command {request.command} completed",
            )
            yield complete_event.to_sse()

        except Exception as e:
            logger.error(f"Command execution error: {e}")
            error_event = AgentExecutionEvent.error(task_id, str(e))
            yield error_event.to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/listCommands", response_model=List[CommandInfo])
async def list_commands() -> List[CommandInfo]:
    """
    List all available CLI commands.

    Returns a comprehensive list of all top-level commands,
    their descriptions, arguments, and subcommands.
    """
    from joshu.a2a.commands.registry import get_command_registry

    registry = get_command_registry()
    commands_data = registry.list_commands()

    result = []
    for cmd_data in commands_data:
        # Convert arguments
        arguments = [
            CommandArgumentInfo(
                name=arg["name"],
                description=arg["description"],
                type=arg.get("type", "string"),
                required=arg.get("required", False),
                default=arg.get("default"),
            )
            for arg in cmd_data.get("arguments", [])
        ]

        # Convert subcommands
        subcommands = [
            SubcommandInfo(
                name=sub["name"],
                description=sub["description"],
                arguments=[
                    CommandArgumentInfo(
                        name=arg["name"],
                        description=arg["description"],
                        type=arg.get("type", "string"),
                        required=arg.get("required", False),
                        default=arg.get("default"),
                    )
                    for arg in sub.get("arguments", [])
                ],
            )
            for sub in cmd_data.get("subcommands", [])
        ]

        result.append(
            CommandInfo(
                name=cmd_data["name"],
                description=cmd_data["description"],
                arguments=arguments,
                subcommands=subcommands,
            )
        )

    return result


# ============================================================================
# Agent Metadata Endpoints
# ============================================================================


@app.get("/.well-known/agent-card.json", response_model=AgentCard)
@app.get("/agent-card.json", response_model=AgentCard)
async def agent_card() -> AgentCard:
    """
    Get agent metadata and capabilities.

    Returns information about the Joshu agent for client discovery.
    """
    return AgentCard(
        name="Joshu",
        version="0.1.0",
        description="AI-powered CLI assistant with tool execution capabilities",
        capabilities=[
            "code_generation",
            "code_editing",
            "file_operations",
            "shell_commands",
            "web_search",
            "tool_calling",
        ],
        supported_models=[
            "gemini-2.0-flash-exp",
            "gemini-1.5-pro",
            "gpt-4",
            "claude-3-sonnet",
        ],
    )


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "joshu-a2a"}


# ============================================================================
# Server Runner
# ============================================================================


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """
    Run the A2A server.

    Args:
        host: Host to bind to
        port: Port to listen on
    """
    import uvicorn

    logger.info(f"Starting A2A server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Joshu A2A Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    run_server(args.host, args.port)
