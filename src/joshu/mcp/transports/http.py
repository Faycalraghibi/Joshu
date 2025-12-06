"""
MCP HTTP/SSE Transport.

Transport implementation for MCP servers using HTTP with
streamable responses and Server-Sent Events (SSE).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

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


class HTTPTransport(MCPTransport):
    """
    HTTP transport for MCP servers.

    Communicates with MCP servers over HTTP using streamable responses.
    Supports both standard HTTP and Server-Sent Events (SSE) for streaming.
    """

    def __init__(self, config: MCPServerConfig):
        """
        Initialize the HTTP transport.

        Args:
            config: Server configuration with url.
        """
        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None
        self._session_id: Optional[str] = None

    async def connect(self) -> bool:
        """
        Initialize HTTP client and handshake with server.

        Returns:
            True if connection successful.

        Raises:
            MCPConnectionError: If connection fails.
        """
        if self._connected:
            return True

        if not self.config.url:
            raise MCPConnectionError(self.server_name, "No URL specified for HTTP transport")

        try:
            # Create HTTP client
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )

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

            logger.info(f"Connected to MCP server: {self.server_name} at {self.config.url}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MCP server {self.server_name}: {e}")
            if self._client:
                await self._client.aclose()
                self._client = None
            raise MCPConnectionError(self.server_name, str(e))

    async def disconnect(self) -> None:
        """Close the HTTP client."""
        if self._client:
            try:
                await self._client.aclose()
            except Exception as e:
                logger.warning(f"Error closing HTTP client for {self.server_name}: {e}")
            self._client = None

        self._connected = False
        self._session_id = None
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

    async def _send_request(
        self,
        method: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send a JSON-RPC request over HTTP.

        Args:
            method: RPC method name.
            params: Method parameters.

        Returns:
            Response result.

        Raises:
            MCPTransportError: If request fails.
            MCPTimeoutError: If request times out.
        """
        if not self._client:
            raise MCPTransportError(self.server_name, "Not connected", "http")

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }

        try:
            response = await self._client.post(
                self.config.url,
                json=request,
            )
            response.raise_for_status()

            # Check content type for SSE
            content_type = response.headers.get("content-type", "")

            if "text/event-stream" in content_type:
                # Handle SSE response
                return await self._handle_sse_response(response)
            else:
                # Standard JSON response
                data = response.json()

                if "error" in data:
                    error = data["error"]
                    raise MCPTransportError(
                        self.server_name, error.get("message", "Unknown error"), "http"
                    )

                return data.get("result", {})

        except httpx.TimeoutException:
            raise MCPTimeoutError(method, self.config.timeout, self.server_name)
        except httpx.HTTPError as e:
            raise MCPTransportError(self.server_name, str(e), "http")

    async def _handle_sse_response(self, response: httpx.Response) -> Dict[str, Any]:
        """
        Handle Server-Sent Events response.

        Args:
            response: HTTP response with SSE content.

        Returns:
            Final result from SSE stream.
        """
        result = {}

        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = line[6:]
                try:
                    event = json.loads(data)

                    # Check for final result
                    if "result" in event:
                        result = event["result"]
                    elif "error" in event:
                        error = event["error"]
                        raise MCPTransportError(
                            self.server_name, error.get("message", "Unknown error"), "sse"
                        )

                except json.JSONDecodeError:
                    logger.warning(f"Invalid SSE JSON: {data}")

        return result

    async def _send_notification(
        self,
        method: str,
        params: Dict[str, Any],
    ) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._client:
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }

        try:
            await self._client.post(
                self.config.url,
                json=notification,
            )
        except Exception as e:
            logger.warning(f"Failed to send notification to {self.server_name}: {e}")
