"""A tiny MCP server over stdio (newline-delimited JSON-RPC) for tests."""

import json
import sys

PROMPTS = [
    {
        "name": "review",
        "description": "Review a file",
        "arguments": [{"name": "path", "required": True}, {"name": "focus"}],
    }
]
RESOURCES = [{"uri": "notes://todo", "name": "TODO list", "mimeType": "text/plain"}]
TOOLS = [
    {
        "name": "echo",
        "description": "Echo text back",
        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}},
    }
]


def reply(message_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": message_id, "result": result}) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    message = json.loads(line)
    method, params, message_id = (
        message.get("method"),
        message.get("params") or {},
        message.get("id"),
    )
    if message_id is None:
        continue  # notifications
    if method == "initialize":
        reply(
            message_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "prompts": {}, "resources": {}},
                "serverInfo": {"name": "fake", "version": "1"},
            },
        )
    elif method == "tools/list":
        reply(message_id, {"tools": TOOLS})
    elif method == "tools/call":
        text = (params.get("arguments") or {}).get("text", "")
        reply(message_id, {"content": [{"type": "text", "text": f"echo: {text}"}]})
    elif method == "prompts/list":
        reply(message_id, {"prompts": PROMPTS})
    elif method == "prompts/get":
        arguments = params.get("arguments") or {}
        focus = arguments.get("focus") or "everything"
        text = f"Review {arguments.get('path')} focusing on {focus}."
        reply(
            message_id, {"messages": [{"role": "user", "content": {"type": "text", "text": text}}]}
        )
    elif method == "resources/list":
        reply(message_id, {"resources": RESOURCES})
    elif method == "resources/read":
        reply(
            message_id,
            {"contents": [{"uri": params.get("uri"), "text": "1. ship v0.3.0\n2. write docs"}]},
        )
    else:
        reply(message_id, {})
