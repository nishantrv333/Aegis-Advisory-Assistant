"""
Expose any Aegis tool server as an MCP server over JSON-RPC/stdio.

    python -m mcp_layer.stdio_server portfolio

This exists to prove the point that the tool layer is genuinely
protocol-shaped rather than protocol-flavoured. The same handler functions
the agents call in-process are served here over the wire, implementing
`initialize`, `tools/list` and `tools/call` with no changes to the tools
themselves. Point Claude Desktop or any MCP client at this command and the
tools show up.

Try it by hand:

    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \\
      | python -m mcp_layer.stdio_server portfolio
"""

from __future__ import annotations

import json
import sys
from typing import Any

from core.trace import Trace
from mcp_layer.registry import ToolServer, ToolRegistry

PROTOCOL_VERSION = "2024-11-05"


def _response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(request: dict[str, Any], registry: ToolRegistry, server_name: str) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")

    if method == "initialize":
        return _response(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": f"aegis-{server_name}", "version": "0.1.0"},
            },
        )

    if method in {"notifications/initialized", "initialized"}:
        return None  # notification, no reply

    if method == "tools/list":
        return _response(request_id, {"tools": [s.to_dict() for s in registry.list_tools()]})

    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not name:
            return _error(request_id, -32602, "params.name is required")
        result = registry.call(name, arguments, Trace())
        return _response(request_id, result.to_dict())

    if method == "ping":
        return _response(request_id, {})

    return _error(request_id, -32601, f"Method not found: {method}")


def build_registry(server_name: str) -> tuple[ToolRegistry, ToolServer]:
    import tools  # noqa: F401  (mounts every server)
    from tools import compliance_server, portfolio_server, research_server

    servers = {
        "portfolio": portfolio_server.server,
        "research": research_server.server,
        "compliance": compliance_server.server,
    }
    if server_name not in servers:
        raise SystemExit(f"Unknown server '{server_name}'. Choose from: {', '.join(servers)}")

    registry = ToolRegistry()
    registry.mount(servers[server_name])
    return registry, servers[server_name]


def main() -> None:
    server_name = sys.argv[1] if len(sys.argv) > 1 else "portfolio"
    registry, _ = build_registry(server_name)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps(_error(None, -32700, "Parse error")), flush=True)
            continue
        reply = handle(request, registry, server_name)
        if reply is not None:
            print(json.dumps(reply), flush=True)


if __name__ == "__main__":
    main()
