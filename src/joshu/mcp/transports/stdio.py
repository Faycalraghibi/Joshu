"""
MCP Stdio Transport.

Transport implementation for MCP servers running as subprocesses
communicating via stdin/stdout using JSON-RPC.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from joshu.mcp.exceptions import (
    MCPConnectionError,
    MCPTimeoutError,
    MCPToolExecutionError,
    MCPTransportError,
)
from joshu.mcp.schemas import (
    MCPContentBlock,
    MCPPromptDefinition,
    MCPResourceDefinition,
    MCPServerConfig,
    MCPToolDefinition,
    MCPToolResult,
)
from joshu.mcp.transports.base import MCPTransport

logger = logging.getLogger(__name__)


class StdioTransport(MCPTransport):
    """
    Stdio transport for MCP servers.

    Spawns a subprocess and communicates via JSON-RPC over stdin/stdout.
    """

    def __init__(self, config: MCPServerConfig):
        """
        Initialize the Stdio transport.

        Args:
            config: Server configuration with command and args.
        """
        super().__init__(config)
        self._process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._read_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """
        Start the MCP server subprocess and initialize the connection.

        Returns:
            True if connection successful.

        Raises:
            MCPConnectionError: If subprocess fails to start.
        """
        if self._connected:
            return True

        if not self.config.command:
            raise MCPConnectionError(self.server_name, "No command specified for stdio transport")

        try:
            # Build environment
            env = os.environ.copy()
            env.update(self.config.env)

            # Start subprocess
            logger.info(f"Starting MCP server: {self.config.command} {' '.join(self.config.args)}")

            import sys

            # On Windows, commands like npx need shell execution
            if sys.platform == "win32":
                # Use shell execution for Windows to handle .cmd/.bat scripts
                full_command = f"{self.config.command} {' '.join(self.config.args)}"
                self._process = await asyncio.create_subprocess_shell(
                    full_command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
            else:
                self._process = await asyncio.create_subprocess_exec(
                    self.config.command,
                    *self.config.args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )

            # Start reading responses
            self._read_task = asyncio.create_task(self._read_loop())

            # Initialize connection
            result = await self._send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "joshu",
                        "version": "0.1.0",
                    },
                },
            )

            self._server_info = result
            self._connected = True

            # Send initialized notification
            await self._send_notification("notifications/initialized", {})

            logger.info(f"Connected to MCP server: {self.server_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to start MCP server {self.server_name}: {e}")
            raise MCPConnectionError(self.server_name, str(e))

    async def disconnect(self) -> None:
        """Stop the subprocess and clean up."""
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None

        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
            except Exception as e:
                logger.warning(f"Error stopping MCP server {self.server_name}: {e}")
            self._process = None

        self._connected = False
        self._pending_requests.clear()
        logger.info(f"Disconnected from MCP server: {self.server_name}")

    async def list_tools(self) -> List[MCPToolDefinition]:
        """Get list of available tools."""
        result = await self._send_request("tools/list", {})
        tools = []

        for tool_data in result.get("tools", []):
            tool = MCPToolDefinition.from_mcp_response(tool_data, self.server_name)
            tools.append(tool)

        logger.debug(f"Server {self.server_name} has {len(tools)} tools")
        return tools

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
    ) -> MCPToolResult:
        """Execute a tool on the server."""
        try:
            result = await self._send_request(
                "tools/call",
                {
                    "name": name,
                    "arguments": arguments,
                },
            )

            # Parse content blocks
            content_blocks = []
            for block in result.get("content", []):
                content_blocks.append(MCPContentBlock.from_mcp_response(block))

            # Extract text content
            text_content = "\n".join(block.get_text_content() for block in content_blocks)

            is_error = result.get("isError", False)

            return MCPToolResult(
                success=not is_error,
                content=text_content if text_content else result.get("content"),
                error=text_content if is_error else None,
                tool_name=name,
                server_name=self.server_name,
                is_error=is_error,
            )

        except Exception as e:
            logger.error(f"Tool execution failed: {name} on {self.server_name}: {e}")
            raise MCPToolExecutionError(name, str(e), self.server_name)

    async def list_resources(self) -> List[MCPResourceDefinition]:
        """Get list of available resources."""
        result = await self._send_request("resources/list", {})
        resources = []

        for resource_data in result.get("resources", []):
            resource = MCPResourceDefinition.from_mcp_response(resource_data, self.server_name)
            resources.append(resource)

        return resources

    async def read_resource(self, uri: str) -> Any:
        """Read a resource from the server."""
        result = await self._send_request("resources/read", {"uri": uri})

        contents = result.get("contents", [])
        if contents:
            # Return first content block
            first = contents[0]
            if first.get("text"):
                return first["text"]
            elif first.get("blob"):
                return first["blob"]

        return None

    async def list_prompts(self) -> List[MCPPromptDefinition]:
        """Get list of available prompts."""
        result = await self._send_request("prompts/list", {})
        prompts = []

        for prompt_data in result.get("prompts", []):
            prompt = MCPPromptDefinition.from_mcp_response(prompt_data, self.server_name)
            prompts.append(prompt)

        return prompts

    async def _read_loop(self) -> None:
        """Background task to read responses from the subprocess."""
        if not self._process or not self._process.stdout:
            return

        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    break

                try:
                    message = json.loads(line.decode("utf-8"))
                    await self._handle_message(message)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from MCP server: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error reading from MCP server: {e}")

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle an incoming message from the server."""
        if "id" in message:
            # This is a response to a request
            request_id = message["id"]
            if request_id in self._pending_requests:
                future = self._pending_requests.pop(request_id)

                if "error" in message:
                    error = message["error"]
                    future.set_exception(
                        MCPTransportError(
                            self.server_name, error.get("message", "Unknown error"), "stdio"
                        )
                    )
                else:
                    future.set_result(message.get("result", {}))
        else:
            # This is a notification
            method = message.get("method", "")
            logger.debug(f"Received notification from {self.server_name}: {method}")

    async def _send_request(
        self,
        method: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send a JSON-RPC request and wait for response.

        Args:
            method: RPC method name.
            params: Method parameters.

        Returns:
            Response result.

        Raises:
            MCPTransportError: If request fails.
            MCPTimeoutError: If request times out.
        """
        if not self._process or not self._process.stdin:
            raise MCPTransportError(self.server_name, "Not connected", "stdio")

        self._request_id += 1
        request_id = self._request_id

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        # Create future for response
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        try:
            # Send request
            message = json.dumps(request) + "\n"
            self._process.stdin.write(message.encode("utf-8"))
            await self._process.stdin.drain()

            # Wait for response with timeout
            result = await asyncio.wait_for(future, timeout=self.config.timeout)
            return result

        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise MCPTimeoutError(method, self.config.timeout, self.server_name)
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            raise MCPTransportError(self.server_name, str(e), "stdio")

    async def _send_notification(
        self,
        method: str,
        params: Dict[str, Any],
    ) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._process or not self._process.stdin:
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }

        message = json.dumps(notification) + "\n"
        self._process.stdin.write(message.encode("utf-8"))
        await self._process.stdin.drain()
